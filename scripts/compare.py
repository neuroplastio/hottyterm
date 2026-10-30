#!/usr/bin/env python3
"""pairs: blind before/after pairs, side by side (gov R-22, R-23).

    pairs                                list the pairs and their briefs
    pairs prepare [pair...] [--missing]  build the sides into ~/.cache/compare
    pairs <pair> [--dry-run]             open a pair: an empty workspace,
                                         windows A and B, left and right
    pairs close [pair...] [--dry-run]    kill what a pair started (all open)
    pairs verdict <pair> A|B|same "<note>"
                                         record the verdict, then the key

Pairs are TOML files in compare/pairs/; docs/compare.md says how to add
one. Stdlib only (Python 3.11+ for tomllib).

Blind: the sides are shuffled into A and B per opening ("a round"). The
key is written to ~/.cache/compare/<pair>/key and shown only by
`pairs verdict`. What the window manager shows (titles, the window
process's argv and env) names the slot, A or B, never the side.

Isolation: each side gets its own throwaway PLX_DIR under /run/user/<uid>,
a fresh env with every inherited PLX_*, GHOSTTY_* and TERM_PROGRAM* gone,
and its own hottyterm process (--gtk-single-instance=false). Everything a
pair starts carries COMPARE_RUN=<token> or PLX_DIR=<its dir>, and `close`
kills only processes whose environ holds one of those.

--wm sway is for tests only: it drives a private headless sway (SWAYSOCK)
instead of Hyprland, with the same launch and checks.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import secrets
import shlex
import shutil
import signal
import subprocess
import sys
import time
import tomllib
from pathlib import Path

# --- Settings -------------------------------------------------------------
REPO = Path(__file__).resolve().parent.parent
# The pair files: this repository's compare/pairs/, then every other
# neuroplastio checkout's main/compare/pairs/, so each track keeps its pairs
# beside the code they build. COMPARE_PAIRS (directories, `:` between them)
# points tests elsewhere.
def pair_dirs() -> list[Path]:
    if os.environ.get("COMPARE_PAIRS"):
        return [Path(d).expanduser() for d in os.environ["COMPARE_PAIRS"].split(":") if d]
    own = REPO / "compare" / "pairs"
    others = sorted(d for d in REPO.parent.parent.glob("*/main/compare/pairs")
                    if d.is_dir() and d.resolve() != own.resolve())
    return [own, *others]


PAIRS = pair_dirs()
# Built sides, keys, sessions, logs.
CACHE = Path(os.environ.get("COMPARE_CACHE") or "~/.cache/compare").expanduser()
# The verdicts that count: one Markdown file per pair, blind (no key).
# gov commits and unblinds them.
VERDICTS = Path(os.environ.get("COMPARE_VERDICTS")
                or "~/code/neuroplastio/gov/main/research/0022/verdicts").expanduser()
# Every verdict with its key, for the builders.
VERDICTS_JSONL = CACHE / "verdicts.jsonl"
# The maintainer's binds launch apps with this (binds.lua, launchPrefix).
LAUNCH_PREFIX = "uwsm app -- "
# Throwaway PLX_DIRs live here: a unix socket path must fit in 107 bytes.
RUNTIME = Path(f"/run/user/{os.getuid()}")
HOTTYTERM = "/usr/lib/hottyterm/bin/hottyterm"
# Seconds to wait for a window to map.
MAP_TIMEOUT = 20.0
# Inherited variables a side never sees.
SCRUB_PREFIXES = ("PLX_", "GHOSTTY_", "TERM_PROGRAM", "COMPARE_", "SIDE_")
SIDES = ("before", "after")
SLOTS = ("A", "B")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,23}$")
# A plx socket under the deepest dir plx uses, for the length check.
PLX_SOCKET_TAIL = "/daemons/default/plxd-01ARZ3NDEKTSV4RRFFQ69G5FAV.sock"
SCRIPT = Path(__file__).resolve()


class Fail(Exception):
    pass


def warn(msg: str) -> None:
    print(f"pairs: {msg}", file=sys.stderr)


def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S %z")


# --- Pairs ----------------------------------------------------------------
class Side:
    def __init__(self, pair: "Pair", name: str, t: dict):
        self.pair, self.name = pair, name
        unknown = set(t) - {"build", "run", "hottyterm", "hottyterm_args", "label"}
        if unknown:
            raise Fail(f"{pair.file.name} [{name}]: unknown keys {sorted(unknown)}")
        self.build = t.get("build")
        self.run = t.get("run")
        if not isinstance(self.run, str) or not self.run.strip():
            raise Fail(f"{pair.file.name} [{name}]: `run` is required: the one command the side runs")
        self.hottyterm = t.get("hottyterm", pair.hottyterm)
        self.hottyterm_args = list(t.get("hottyterm_args", pair.hottyterm_args))
        self.label = t.get("label", "")

    @property
    def dir(self) -> Path:          # SIDE_DIR while building
        return CACHE / self.pair.name / self.name

    @property
    def work(self) -> Path:         # SIDE_WORK: sources and caches, kept
        return CACHE / self.pair.name / "work" / self.name

    @property
    def stamp(self) -> Path:
        return CACHE / self.pair.name / f"{self.name}.built"

    @property
    def log(self) -> Path:
        return CACHE / self.pair.name / f"{self.name}.build.log"

    def hottyterm_in(self, side_dir: Path) -> str:
        p = self.hottyterm.replace("${SIDE_DIR}", str(side_dir)).replace("$SIDE_DIR", str(side_dir))
        return str(Path(p).expanduser())

    def built(self) -> tuple[bool, str]:
        if not self.build:
            return True, "nothing to build"
        try:
            st = json.loads(self.stamp.read_text())
        except (OSError, ValueError):
            return False, "not built"
        if not st.get("ok"):
            return False, f"build failed {st.get('time', '')}"
        if st.get("build") != self.build:
            return False, "build command changed since"
        return True, f"built {st.get('time', '')}"


class Pair:
    def __init__(self, file: Path):
        self.file = file
        self.name = file.stem
        if not NAME_RE.match(self.name):
            raise Fail(f"{file.name}: a pair's name is [a-z0-9-], at most 24 characters")
        try:
            t = tomllib.loads(file.read_text())
        except tomllib.TOMLDecodeError as e:
            raise Fail(f"{file.name}: {e}") from None
        known = {"brief", "track", "example", "results", "home", "seed",
                 "hottyterm", "hottyterm_args", "before", "after"}
        unknown = set(t) - known
        if unknown:
            raise Fail(f"{file.name}: unknown keys {sorted(unknown)}")
        self.brief = t.get("brief", "")
        if not self.brief:
            raise Fail(f"{file.name}: `brief` is required: one neutral line on the one difference")
        self.track = t.get("track", "")
        self.example = bool(t.get("example", False))
        r = t.get("results", [])
        self.results = [r] if isinstance(r, str) else list(r)
        self.home = t.get("home", "throwaway")
        if self.home not in ("throwaway", "real"):
            raise Fail(f"{file.name}: home is \"throwaway\" or \"real\"")
        self.seed = list(t.get("seed", ["config/plx", "config/fish"]))
        for s in self.seed:
            if not re.match(r"^(config|state|data|cache)/[^/]+$", s) or ".." in s:
                raise Fail(f"{file.name}: seed entries look like \"config/plx\"")
        self.hottyterm = t.get("hottyterm", HOTTYTERM)
        self.hottyterm_args = list(t.get("hottyterm_args", []))
        for s in SIDES:
            if s not in t:
                raise Fail(f"{file.name}: needs a [{s}] table")
        self.sides = {s: Side(self, s, t[s]) for s in SIDES}

    @property
    def dir(self) -> Path:
        return CACHE / self.name

    @property
    def session_file(self) -> Path:
        return self.dir / "session.json"

    @property
    def key_file(self) -> Path:
        return self.dir / "key"

    def lint(self) -> list[str]:
        """What would let argv tell the sides apart."""
        out = []
        b, a = self.sides["before"], self.sides["after"]
        hb, ha = b.hottyterm_in(Path("$S")), a.hottyterm_in(Path("$S"))
        if hb != ha:
            out.append("the sides run different hottyterm paths, so the window's argv "
                       "tells them apart; build both into $SIDE_DIR/bin/hottyterm")
        if b.hottyterm_args != a.hottyterm_args:
            out.append("the sides pass different hottyterm_args, which argv shows; "
                       "use $SIDE_DIR/<file> with --config-file= on both sides")
        return out


def load_pairs() -> dict[str, Pair]:
    pairs = {}
    for d in PAIRS:
        for f in sorted(d.glob("*.toml")):
            p = Pair(f)
            if p.name in pairs:
                raise Fail(f"two pairs named {p.name!r}: {pairs[p.name].file} and {f}")
            pairs[p.name] = p
    return pairs


def get_pair(name: str) -> Pair:
    p = load_pairs().get(name)
    if p is None:
        raise Fail(f"no pair {name!r}; `pairs` lists them")
    return p


# --- Processes, by environ ------------------------------------------------
def environ_of(pid: int) -> list[bytes] | None:
    try:
        with open(f"/proc/{pid}/environ", "rb") as f:
            return f.read().split(b"\0")
    except OSError:
        return None


def comm_of(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/comm").read_text().strip()
    except OSError:
        return "?"


def ppid_of(pid: int) -> int:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        return int(stat.rsplit(")", 1)[1].split()[1])
    except (OSError, ValueError, IndexError):
        return 0


def ancestors(pid: int) -> set[int]:
    out = set()
    while pid > 1 and pid not in out:
        out.add(pid)
        pid = ppid_of(pid)
    return out


def marks(slots: dict) -> dict[bytes, str]:
    """environ entries that mark a slot's processes -> slot name."""
    m = {}
    for slot, s in slots.items():
        m[f"COMPARE_RUN={s['token']}".encode()] = slot
        m[f"PLX_DIR={s['plx_dir']}".encode()] = slot
    return m


def find_procs(slots: dict) -> list[tuple[int, str, str]]:
    """(pid, slot, comm) of every process whose environ holds a slot's
    token or PLX_DIR, except this process and its ancestors."""
    m = marks(slots)
    skip = ancestors(os.getpid())
    out = []
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        pid = int(d)
        if pid in skip:
            continue
        env = environ_of(pid)
        if not env:
            continue
        for e in env:
            slot = m.get(e)
            if slot:
                out.append((pid, slot, comm_of(pid)))
                break
    return out


def still_ours(pid: int, slots: dict) -> bool:
    env = environ_of(pid)
    return bool(env) and any(e in marks(slots) for e in env)


def kill_procs(procs: list[tuple[int, str, str]], slots: dict, wait: float = 3.0) -> list[int]:
    """TERM, then KILL what is left. Returns the pids that would not die."""
    for pid, _, _ in procs:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + wait
    alive = [p for p, _, _ in procs]
    while alive and time.monotonic() < deadline:
        time.sleep(0.1)
        alive = [p for p in alive if Path(f"/proc/{p}").exists() and still_ours(p, slots)]
    for pid in alive:
        if still_ours(pid, slots):          # the pid may have been reused
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    time.sleep(0.2)
    return [p for p in alive if Path(f"/proc/{p}").exists() and still_ours(p, slots)]


def scrubbed(env: dict) -> dict:
    return {k: v for k, v in env.items() if not k.startswith(SCRUB_PREFIXES)}


# --- Window managers ------------------------------------------------------
class Window:
    def __init__(self, pid, title, workspace, x, y, w, h, ident):
        self.pid, self.title, self.workspace = pid, title, workspace
        self.x, self.y, self.w, self.h, self.ident = x, y, w, h, ident


class WM:
    """The window manager that pairs drives. Every command goes through run()."""
    name = "?"
    READ_ONLY: set = set()

    def __init__(self, dry_run: bool):
        self.dry_run = dry_run
        self.planned: list[str] = []

    def cmdline(self, argv: list[str]) -> str:
        return shlex.join(argv)

    def run(self, argv: list[str], *, mutate: bool) -> str:
        """Run argv. A mutating command is only printed in a dry run."""
        if mutate:
            if self.dry_run:
                self.planned.append(self.cmdline(argv))
                return ""
            if os.environ.get("COMPARE_NO_DISPATCH") and self.name == "hyprland":
                raise Fail(f"COMPARE_NO_DISPATCH is set; refusing: {self.cmdline(argv)}")
        elif tuple(argv[1:]) not in self.READ_ONLY:
            raise Fail(f"not a read-only query: {self.cmdline(argv)}")
        r = subprocess.run(argv, capture_output=True, text=True)
        if r.returncode != 0:
            raise Fail(f"{self.cmdline(argv)}: {(r.stderr or r.stdout).strip()}")
        return r.stdout


class Hyprland(WM):
    name = "hyprland"
    READ_ONLY = {("version",), ("-j", "workspaces"), ("-j", "clients"), ("-j", "monitors"),
                 ("-j", "activewindow")}

    def __init__(self, dry_run: bool):
        super().__init__(dry_run)
        self.target = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
        if not self.target:
            raise Fail("HYPRLAND_INSTANCE_SIGNATURE is not set: run pairs in the Hyprland session")
        if not shutil.which("hyprctl"):
            raise Fail("hyprctl is not on PATH")

    def q(self, *args) -> object:
        return json.loads(self.run(["hyprctl", *args], mutate=False))

    def dispatch(self, lua: str) -> None:
        out = self.run(["hyprctl", "dispatch", lua], mutate=True)
        if not self.dry_run and out.strip() != "ok":
            raise Fail(f"hyprctl dispatch {lua!r}: {out.strip()}")

    def version(self) -> str:
        first = self.run(["hyprctl", "version"], mutate=False).splitlines()[0]
        return " ".join(first.split()[:2])

    def pick_workspace(self) -> tuple[str, str]:
        mons = self.q("-j", "monitors")
        wss = self.q("-j", "workspaces")
        focused = next((m for m in mons if m.get("focused")), mons[0] if mons else None)
        if not focused:
            raise Fail("hyprctl -j monitors lists no monitor")
        mname = focused["name"]
        visible_elsewhere = {m["activeWorkspace"]["id"] for m in mons if m is not focused}
        empty = sorted(w["id"] for w in wss
                       if w["id"] > 0 and w["windows"] == 0 and w["monitor"] == mname
                       and w["id"] not in visible_elsewhere)
        if empty:
            ws = empty[0]
            why = f"workspace {ws}: the lowest empty one on {mname}, the focused monitor"
        else:
            used = {w["id"] for w in wss}
            ws = next(i for i in range(1, 1000) if i not in used)
            why = f"workspace {ws}: no empty one on {mname}; a new one"
        w, h = focused["width"], focused["height"]
        if focused.get("transform", 0) % 2 == 1:
            w, h = h, w
        if h > w:
            why += f" (portrait {w}x{h}: the windows may stack; pairs toggles the split)"
        return str(ws), why

    def focus(self, ws: str) -> None:
        self.dispatch(f"hl.dsp.focus({{ workspace = {ws} }})")

    def launch(self, ws: str, cmd: str) -> None:
        self.dispatch(f"hl.dsp.exec_cmd({lua_str(LAUNCH_PREFIX + cmd)}, "
                      f"{{ workspace = \"{ws} silent\" }})")

    def windows(self) -> list[Window]:
        out = []
        for c in self.q("-j", "clients"):
            ws = c.get("workspace", {})
            (x, y), (w, h) = c.get("at", (0, 0)), c.get("size", (0, 0))
            out.append(Window(c.get("pid", -1), c.get("title", ""),
                              str(ws.get("name", ws.get("id", "?"))), x, y, w, h,
                              c.get("address", "")))
        return out

    def active_pid(self) -> int:
        a = self.q("-j", "activewindow")
        return a.get("pid", -1) if isinstance(a, dict) else -1

    def fix_stacked(self, a: Window, b: Window) -> bool:
        if self.active_pid() not in (a.pid, b.pid):
            return False
        self.dispatch('hl.dsp.layout("togglesplit")')
        return True

    def fix_order(self, a: Window, b: Window) -> bool:
        act = self.active_pid()
        if act == b.pid:
            self.dispatch('hl.dsp.window.swap({ direction = "r" })')
        elif act == a.pid:
            self.dispatch('hl.dsp.window.swap({ direction = "l" })')
        else:
            return False
        return True


class Sway(WM):
    """For tests only: a private headless sway, never the user's session."""
    name = "sway"
    READ_ONLY = {("-t", "get_version"), ("-t", "get_workspaces"), ("-t", "get_tree"),
                 ("-t", "get_outputs"), ("-t", "get_seats")}

    def __init__(self, dry_run: bool):
        super().__init__(dry_run)
        self.target = os.environ.get("SWAYSOCK", "")
        if not self.target:
            raise Fail("--wm sway needs SWAYSOCK: the private headless sway's IPC socket")
        self.swaymsg = os.environ.get("COMPARE_SWAYMSG") or shutil.which("swaymsg") or "swaymsg"

    def run(self, argv, *, mutate):
        return super().run([self.swaymsg, *argv[1:]], mutate=mutate)

    def q(self, *args):
        return json.loads(self.run(["swaymsg", *args], mutate=False))

    def version(self) -> str:
        return "sway " + self.q("-t", "get_version").get("human_readable", "?")

    def pick_workspace(self):
        used = {str(w.get("num", w["name"])) for w in self.q("-t", "get_workspaces")}
        ws = next(str(i) for i in range(1, 1000) if str(i) not in used)
        return ws, f"workspace {ws}: the lowest number not in use"

    def focus(self, ws):
        self.run(["swaymsg", "workspace", "number", ws], mutate=True)

    def launch(self, ws, cmd):
        self.run(["swaymsg", "exec", "--", LAUNCH_PREFIX + cmd], mutate=True)

    def windows(self):
        out = []

        def walk(n, ws):
            if n.get("type") == "workspace":
                ws = n.get("name")
            if n.get("pid") and n.get("type") in ("con", "floating_con"):
                r = n["rect"]
                out.append(Window(n["pid"], n.get("name") or "", str(ws), r["x"], r["y"],
                                  r["width"], r["height"], n["id"]))
            for c in n.get("nodes", []) + n.get("floating_nodes", []):
                walk(c, ws)
        walk(self.q("-t", "get_tree"), None)
        return out

    def fix_stacked(self, a, b):
        self.run(["swaymsg", f"[con_id={a.ident}]", "layout", "splith"], mutate=True)
        return True

    def fix_order(self, a, b):
        self.run(["swaymsg", f"[con_id={b.ident}]", "swap", "container", "with", "con_id",
                  str(a.ident)], mutate=True)
        return True


def lua_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def make_wm(name: str, dry_run: bool) -> WM:
    return {"hyprland": Hyprland, "sway": Sway}[name](dry_run)


# --- The clients check ----------------------------------------------------
def ours(wm: WM, slots: dict) -> dict[str, Window]:
    m = marks({k: v for k, v in slots.items()})
    found = {}
    for w in wm.windows():
        env = environ_of(w.pid) or []
        for e in env:
            if e.startswith(b"COMPARE_RUN=") and e in m:
                found[m[e]] = w
    return found


def clients_check(wm: WM, ws: str, slots: dict, title: str) -> tuple[bool, str]:
    """A table of the pair's windows and what else is on the workspace."""
    all_w = wm.windows()
    mine = ours(wm, slots)
    lines = [f"clients check ({title}): workspace {ws}"]
    lines.append(f"  {'slot':4}  {'pid':>7}  {'title':5}  {'workspace':9}  {'at':>11}  {'size':>11}")
    for slot in SLOTS:
        w = mine.get(slot)
        if not w:
            lines.append(f"  {slot:4}  {'-':>7}  no window")
            continue
        lines.append(f"  {slot:4}  {w.pid:>7}  {w.title[:5]:5}  {w.workspace:9}  "
                     f"{f'{w.x},{w.y}':>11}  {f'{w.w}x{w.h}':>11}")
    others = [w for w in all_w if w.workspace == ws and w.pid not in {x.pid for x in mine.values()}]
    for w in others:
        lines.append(f"  {'?':4}  {w.pid:>7}  {w.title[:5]:5}  {w.workspace:9}  "
                     f"{f'{w.x},{w.y}':>11}  {f'{w.w}x{w.h}':>11}  not from pairs")
    problems = []
    a, b = mine.get("A"), mine.get("B")
    for slot, w in (("A", a), ("B", b)):
        if not w:
            problems.append(f"no window {slot}")
        elif w.workspace != ws:
            problems.append(f"{slot} is on workspace {w.workspace}")
        elif w.title != slot:
            problems.append(f"{slot}'s title is {w.title!r}")
    if a and b and a.workspace == b.workspace == ws:
        if abs(a.y - b.y) > abs(a.x - b.x):
            problems.append("A and B are stacked, not side by side")
        elif a.x >= b.x:
            problems.append("B is left of A")
    if others:
        problems.append(f"{len(others)} other window(s) on workspace {ws}")
    ok = not problems
    lines.append("  ok: A left, B right, both on workspace " + ws if ok
                 else "  NOT OK: " + "; ".join(problems))
    return ok, "\n".join(lines)


# --- list -----------------------------------------------------------------
def last_verdicts() -> dict[str, dict]:
    out = {}
    try:
        for line in VERDICTS_JSONL.read_text().splitlines():
            try:
                v = json.loads(line)
                out[v["pair"]] = v
            except (ValueError, KeyError):
                pass
    except OSError:
        pass
    return out


def cmd_list() -> int:
    try:
        pairs = load_pairs()
    except Fail as e:
        warn(str(e))
        return 1
    if not pairs:
        print("no pairs in " + ", ".join(map(str, PAIRS)))
        return 0
    verdicts = last_verdicts()
    width = max(len(n) for n in pairs)
    real = [p for p in pairs.values() if not p.example]
    examples = [p for p in pairs.values() if p.example]
    for group, title in ((real, "pairs"), (examples, "examples (to try the tool; nothing to judge)")):
        if not group:
            continue
        print(f"{title}:")
        for p in group:
            built = all(s.built()[0] for s in p.sides.values())
            state = []
            if p.session_file.exists():
                state.append("open")
            elif not built:
                state.append("needs prepare")
            if p.name in verdicts:
                state.append(f"judged {verdicts[p.name]['time'][:10]}")
            track = f"[{p.track}] " if p.track else ""
            tail = f"  ({', '.join(state)})" if state else ""
            print(f"  {p.name:<{width}}  {track}{p.brief}{tail}")
            for l in p.lint():
                print(f"  {'':<{width}}  warning: {l}")
    print("\npairs <pair> opens one; pairs prepare builds them; docs/compare.md adds one.")
    return 0


# --- prepare --------------------------------------------------------------
def cmd_prepare(names: list[str], missing: bool) -> int:
    pairs = [get_pair(n) for n in names] if names else list(load_pairs().values())
    failed = 0
    for p in pairs:
        if p.session_file.exists():
            warn(f"{p.name} is open; `pairs close {p.name}` first")
            failed += 1
            continue
        for l in p.lint():
            warn(f"{p.name}: warning: {l}")
        for s in p.sides.values():
            ok, why = s.built()
            if not s.build:
                s.dir.mkdir(parents=True, exist_ok=True)
                print(f"{p.name} {s.name}: nothing to build")
                continue
            if missing and ok:
                print(f"{p.name} {s.name}: {why}, kept")
                continue
            failed += not build_side(p, s)
    return 1 if failed else 0


def build_side(p: Pair, s: Side) -> bool:
    if s.dir.exists():
        shutil.rmtree(s.dir)
    s.dir.mkdir(parents=True)
    s.work.mkdir(parents=True, exist_ok=True)
    env = scrubbed(os.environ)
    env.update(SIDE_DIR=str(s.dir), SIDE_WORK=str(s.work), SIDE=s.name, PAIR=p.name,
               PAIR_FILE=str(p.file), COMPARE_REPO=str(REPO),
               NEUROPLASTIO=str(REPO.parent.parent))
    print(f"{p.name} {s.name}: building (log {s.log})", flush=True)
    t0 = time.monotonic()
    with open(s.log, "w") as log:
        log.write(f"# {now()}\n# SIDE_DIR={s.dir}\n# SIDE_WORK={s.work}\n# {s.build}\n")
        log.flush()
        r = subprocess.run(["/bin/sh", "-ec", s.build], cwd=s.work, env=env,
                           stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    ok = r.returncode == 0
    hot = Path(s.hottyterm_in(s.dir))
    if ok and not os.access(hot, os.X_OK):
        ok = False
        with open(s.log, "a") as log:
            log.write(f"\npairs: the build left no hottyterm at {hot}\n")
    s.stamp.write_text(json.dumps({"ok": ok, "build": s.build, "time": now(),
                                   "seconds": round(time.monotonic() - t0, 1)}))
    if ok:
        print(f"{p.name} {s.name}: built in {time.monotonic() - t0:.0f} s")
    else:
        print(f"{p.name} {s.name}: FAILED (exit {r.returncode}); the log's end:")
        print("".join(s.log.read_text().splitlines(keepends=True)[-30:]))
    return ok


# --- open -----------------------------------------------------------------
def mirror(src: Path, dst: Path) -> None:
    """dst mirrors src by hardlinks, so paths under dst name the slot."""
    dst.mkdir(parents=True)
    if not src.is_dir():
        return
    for root, dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        d = dst / rel
        for name in list(dirs):
            sp = Path(root) / name
            if sp.is_symlink():
                os.symlink(os.readlink(sp), d / name)
                dirs.remove(name)
            else:
                (d / name).mkdir()
                shutil.copystat(sp, d / name)
        for name in files:
            sp = Path(root) / name
            if sp.is_symlink():
                os.symlink(os.readlink(sp), d / name)
                continue
            try:
                os.link(sp, d / name)
            except OSError:
                shutil.copy2(sp, d / name)


def open_session_or_none(p: Pair) -> dict | None:
    try:
        return json.loads(p.session_file.read_text())
    except (OSError, ValueError):
        return None


def cmd_open(name: str, wm_name: str, dry_run: bool) -> int:
    p = get_pair(name)
    for l in p.lint():
        warn(f"warning: {l}")
    for s in p.sides.values():
        ok, why = s.built()
        if not ok:
            raise Fail(f"{p.name} {s.name}: {why}; run `pairs prepare {p.name}` first")
        hot = s.hottyterm_in(s.dir)
        if not os.access(hot, os.X_OK):
            raise Fail(f"{p.name} {s.name}: no hottyterm at {hot}")
    if open_session_or_none(p) and not dry_run:
        raise Fail(f"{p.name} is already open; `pairs close {p.name}` first")
    longest = len(str(RUNTIME / f"pxd-cmp-{p.name}-A-xxxx")) + len(PLX_SOCKET_TAIL)
    if longest > 107:
        raise Fail(f"PLX_DIR paths would be {longest} bytes deep: shorten the pair's name")

    wm = make_wm(wm_name, dry_run)
    ver = wm.version()
    ws, why = wm.pick_workspace()
    pre = [w for w in wm.windows() if w.workspace == ws]
    open_dir = p.dir / "open"
    slots = {}
    for slot in SLOTS:
        slots[slot] = {
            "token": f"{p.name}-{slot}-{secrets.token_hex(8)}",
            "plx_dir": str(RUNTIME / f"pxd-cmp-{p.name}-{slot}-"
                           f"{''.join(random.choices('abcdefghijkmnpqrstuvwxyz23456789', k=4))}"),
            "dir": str(open_dir / slot),
            "script": str(open_dir / f"{slot}.sh"),
            "log": str(open_dir / f"{slot}.log"),
            "xdg": str(open_dir / f"{slot}.xdg"),
            "home": p.home,
        }

    def launch_cmd(slot: str) -> str:
        return shlex.join([sys.executable, "-I", str(SCRIPT), "_launch",
                           str(p.session_file), slot])

    if dry_run:
        return print_dry_run(p, wm, ver, ws, why, pre, launch_cmd)
    if pre:
        raise Fail(f"workspace {ws} is not empty")

    # The round: shuffle, then write the key before anything shows.
    order = list(SIDES)
    secrets.SystemRandom().shuffle(order)
    key = {"pair": p.name, "round": time.strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(2),
           "A": order[0], "B": order[1], "opened": now()}
    p.dir.mkdir(parents=True, exist_ok=True)
    write_private(p.key_file, json.dumps(key) + "\n")
    fd = os.open(p.dir / "keys.jsonl", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a") as f:
        f.write(json.dumps(key) + "\n")

    if open_dir.exists():
        shutil.rmtree(open_dir)
    open_dir.mkdir(parents=True)
    for slot in SLOTS:
        side = p.sides[key[slot]]
        sl = slots[slot]
        mirror(side.dir, Path(sl["dir"]))
        Path(sl["script"]).write_text(side.run if side.run.endswith("\n") else side.run + "\n")
        os.mkdir(sl["plx_dir"], 0o700)
        if p.home == "throwaway":
            seed_xdg(Path(sl["xdg"]), p.seed)
        sl["argv"] = [side.hottyterm_in(Path(sl["dir"])), "--gtk-single-instance=false",
                      f"--title={slot}", *side.hottyterm_args, "-e",
                      sys.executable, "-I", str(SCRIPT), "_side", str(p.session_file), slot]
    session = {"pair": p.name, "round": key["round"], "wm": wm.name, "target": wm.target,
               "workspace": ws, "opened": now(), "slots": slots}
    write_private(p.session_file, json.dumps(session, indent=1) + "\n")

    print(f"{p.name}: opening on {why}  [{ver}]")
    wm.focus(ws)
    for slot in SLOTS:
        wm.launch(ws, launch_cmd(slot))
        w = wait_window(wm, slots, slot)
        if not w:
            log = Path(slots[slot]["log"])
            tail = log.read_text()[-2000:] if log.exists() else "(no log: _launch never ran)"
            warn(f"window {slot} did not map within {MAP_TIMEOUT:.0f} s. {log}:\n{tail}")
            warn(f"`pairs close {p.name}` cleans up")
            return 1
    time.sleep(0.3)
    ok, table = clients_check(wm, ws, slots, f"{wm.name}")
    if not ok:
        print(table)
        found = ours(wm, slots)
        a, b = found.get("A"), found.get("B")
        fixed = False
        if a and b and abs(a.y - b.y) > abs(a.x - b.x):
            fixed = wm.fix_stacked(a, b)
            time.sleep(0.3)
            found = ours(wm, slots)
            a, b = found.get("A"), found.get("B")
        if a and b and a.x >= b.x and abs(a.y - b.y) <= abs(a.x - b.x):
            fixed = wm.fix_order(a, b) or fixed
        if fixed:
            time.sleep(0.3)
            ok, table = clients_check(wm, ws, slots, f"{wm.name}, after fixing the layout")
    print(table)
    print(f"\nBrief: {p.brief}\n")
    print(f"Use both, then: pairs verdict {p.name} A|B|same \"<note>\"")
    print(f"Close the windows with: pairs close {p.name}")
    return 0 if ok else 1


def print_dry_run(p, wm, ver, ws, why, pre, launch_cmd) -> int:
    q = wm.cmdline
    print(f"pairs {p.name} --dry-run  [{ver}, instance {wm.target[:16]}...]")
    print("\nRead-only queries, run now:")
    if wm.name == "hyprland":
        for args in (("version",), ("-j", "monitors"), ("-j", "workspaces"), ("-j", "clients")):
            print(f"  {q(['hyprctl', *args])}")
    print(f"\nWorkspace: {why}")
    if pre:
        print(f"  NOT EMPTY: {len(pre)} window(s) there; a real run would refuse")
    print(f"\nKey: sides shuffled into A and B, written to {p.key_file} (not in a dry run)")
    print(f"Slots: {p.dir / 'open'}/A and /B mirror {p.dir}/before and /after by hardlinks")
    print(f"PLX_DIRs: {RUNTIME}/pxd-cmp-{p.name}-A-xxxx and -B-xxxx")
    print("\nWould run, in order:")
    wm.focus(ws)
    for slot in SLOTS:
        wm.launch(ws, launch_cmd(slot))
    n = 0
    for line in wm.planned[:1]:
        n += 1
        print(f"  {n}. {line}")
    for slot, line in zip(SLOTS, wm.planned[1:]):
        n += 1
        print(f"  {n}. {line}")
        print(f"     then poll `{q(['hyprctl', '-j', 'clients']) if wm.name == 'hyprland' else 'swaymsg -t get_tree'}` "
              f"until window {slot} maps (a pid whose environ has COMPARE_RUN={p.name}-{slot}-...), "
              f"{MAP_TIMEOUT:.0f} s at most")
    print(f"     which execs: {p.sides['before'].hottyterm_in(Path(f'{p.dir}/open/A'))} "
          f"--gtk-single-instance=false --title=A -e {sys.executable} -I {SCRIPT} _side "
          f"{p.session_file} A  (B likewise)")
    n += 1
    print(f"  {n}. the clients check: {q(['hyprctl', '-j', 'clients']) if wm.name == 'hyprland' else 'swaymsg -t get_tree'}, "
          f"expecting A left of B, both titled by slot, on workspace {ws}, nothing else there")
    if wm.name == "hyprland":
        print("     only if it fails: hyprctl -j activewindow, then")
        print(f"       stacked:      {q(['hyprctl', 'dispatch', 'hl.dsp.layout(\"togglesplit\")'])}")
        print(f"       B left of A:  {q(['hyprctl', 'dispatch', 'hl.dsp.window.swap({ direction = \"r\" })'])}"
              "  (B active; direction \"l\" if A is)")
        print("     and the clients check again")
    print("\nThe clients check's output looks like:")
    print(f"  clients check ({wm.name}): workspace {ws}")
    print(f"    slot      pid  title  workspace           at         size")
    print(f"    A       12345  A      {ws:9}          0,0    1716x1440")
    print(f"    B       12399  B      {ws:9}       1724,0    1716x1440")
    print(f"    ok: A left, B right, both on workspace {ws}")
    return 0


def wait_window(wm: WM, slots: dict, slot: str) -> Window | None:
    deadline = time.monotonic() + MAP_TIMEOUT
    while time.monotonic() < deadline:
        w = ours(wm, slots).get(slot)
        if w:
            return w
        time.sleep(0.15)
    return None


def write_private(path: Path, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)


def xdg_real(kind: str) -> Path:
    var, default = {"config": ("XDG_CONFIG_HOME", ".config"), "state": ("XDG_STATE_HOME", ".local/state"),
                    "data": ("XDG_DATA_HOME", ".local/share"), "cache": ("XDG_CACHE_HOME", ".cache")}[kind]
    return Path(os.environ.get(var) or Path.home() / default)


def seed_xdg(root: Path, seed: list[str]) -> None:
    for kind in ("config", "state", "data", "cache"):
        (root / kind).mkdir(parents=True, exist_ok=True)
    for s in seed:
        kind, name = s.split("/", 1)
        src = xdg_real(kind) / name
        if src.is_dir():
            shutil.copytree(src, root / kind / name, symlinks=True, dirs_exist_ok=True)
        elif src.is_file():
            shutil.copy2(src, root / kind / name)


# --- inside the compositor's exec: _launch -> hottyterm -> _side ----------
def cmd_launch(session_path: str, slot: str) -> int:
    s = json.loads(Path(session_path).read_text())
    sl = s["slots"][slot]
    fd = os.open(sl["log"], os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    os.dup2(fd, 1)
    os.dup2(fd, 2)
    print(f"[{now()}] _launch {slot}, pid {os.getpid()}", flush=True)
    want = s["target"]
    have = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE" if s["wm"] == "hyprland" else "SWAYSOCK", "")
    if have != want:
        print(f"refusing: this exec runs under {have!r}, not the {s['wm']} that pairs targeted "
              f"({want!r})", flush=True)
        return 1
    env = scrubbed(os.environ)
    left = sorted(k for k in env if k.startswith("PLX_"))
    if left:
        print(f"refusing: PLX_* left in the env: {left}", flush=True)
        return 1
    env.update(COMPARE_RUN=sl["token"], SIDE_DIR=sl["dir"], PLX_DIR=sl["plx_dir"])
    os.chdir(Path.home())
    argv = sl["argv"]
    print(f"exec {shlex.join(argv)}", flush=True)
    os.execve(argv[0], argv, env)
    return 1


def cmd_side(session_path: str, slot: str) -> int:
    s = json.loads(Path(session_path).read_text())
    sl = s["slots"][slot]
    plx = {k: v for k, v in os.environ.items() if k.startswith("PLX_")}
    problems = []
    if os.environ.get("COMPARE_RUN") != sl["token"]:
        problems.append("COMPARE_RUN is not this slot's")
    if plx != {"PLX_DIR": sl["plx_dir"]}:
        problems.append(f"PLX_* is {sorted(plx)}, not this slot's PLX_DIR alone")
    if problems:
        print(f"pairs: refusing to start side {slot}: " + "; ".join(problems))
        input("Press Enter to close.")
        return 1
    env = dict(os.environ)
    if sl.get("home") == "throwaway":
        x = Path(sl["xdg"])
        env.update(XDG_CONFIG_HOME=str(x / "config"), XDG_STATE_HOME=str(x / "state"),
                   XDG_DATA_HOME=str(x / "data"), XDG_CACHE_HOME=str(x / "cache"))
    slots = {slot: sl}
    child = subprocess.Popen(["/bin/sh", sl["script"]], env=env)

    def stop(signum, frame):
        try:
            child.send_signal(signum)
            child.wait(timeout=2)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            pass
        kill_procs(find_procs(slots), slots, wait=2)
        os._exit(128 + signum)
    for sig in (signal.SIGHUP, signal.SIGTERM):
        signal.signal(sig, stop)
    for sig in (signal.SIGINT, signal.SIGQUIT, signal.SIGTSTP):
        signal.signal(sig, signal.SIG_IGN)
    rc = child.wait()
    # The side cleans up after itself: a plxd it left behind goes too.
    kill_procs(find_procs(slots), slots, wait=2)
    if rc != 0:
        print(f"\npairs: side {slot} exited with status {rc}.")
        try:
            input("Press Enter to close.")
        except EOFError:
            pass
    return rc


# --- close ----------------------------------------------------------------
def cmd_close(names: list[str], dry_run: bool) -> int:
    if names:
        pairs = [get_pair(n) for n in names]
    else:
        pairs = [p for p in load_pairs().values() if p.session_file.exists()]
        if not pairs:
            print("no pair is open")
            return 0
    bad = 0
    for p in pairs:
        s = open_session_or_none(p)
        if not s:
            print(f"{p.name}: not open")
            continue
        slots = s["slots"]
        procs = find_procs(slots)
        print(f"{p.name}: {len(procs)} process(es) carry its marks"
              f"{' (dry run: nothing killed)' if dry_run else ''}")
        for pid, slot, comm in sorted(procs, key=lambda t: (t[1], t[0])):
            print(f"  {slot}  {pid:>7}  {comm}")
        if dry_run:
            continue
        stuck = kill_procs(procs, slots)
        if stuck:
            warn(f"{p.name}: still alive: {stuck}")
            bad += 1
            continue
        for sl in slots.values():
            d = Path(sl["plx_dir"])
            if d.parent == RUNTIME and d.name.startswith("pxd-cmp-") and d.exists():
                shutil.rmtree(d, ignore_errors=True)
        shutil.rmtree(p.dir / "open", ignore_errors=True)
        p.session_file.unlink(missing_ok=True)
        print(f"{p.name}: closed")
    return 1 if bad else 0


# --- verdict --------------------------------------------------------------
def cmd_verdict(name: str, pick: str, note: str) -> int:
    p = get_pair(name)
    pick = {"a": "A", "b": "B", "same": "same"}.get(pick.lower())
    if not pick:
        raise Fail("the verdict is A, B or same")
    try:
        key = json.loads(p.key_file.read_text())
    except (OSError, ValueError):
        raise Fail(f"{p.name} has not been opened: no round to judge") from None
    judged = {v.get("round") for v in read_jsonl(VERDICTS_JSONL) if v.get("pair") == p.name}
    if key["round"] in judged:
        raise Fail(f"round {key['round']} of {p.name} is judged and its key shown; "
                   f"`pairs {p.name}` opens a new round")
    t = now()
    # 1. The blind record, for gov: no key in it.
    VERDICTS.mkdir(parents=True, exist_ok=True)
    gov = VERDICTS / f"{p.name}.md"
    new = not gov.exists()
    with open(gov, "a") as f:
        if new:
            f.write(f"# {p.name}\n\n{p.brief}\n\n"
                    "Blind verdicts from `pairs verdict`. The key for each round is in\n"
                    f"`{tilde(p.dir / 'keys.jsonl')}`.\n\n")
        f.write(f"- {t} · round `{key['round']}` · verdict **{pick}**\n")
        for line in (note.strip() or "(no note)").splitlines():
            f.write(f"  > {line}\n")
    # 2. With the key, for the builders.
    picked = pick if pick == "same" else key[pick]
    VERDICTS_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with open(VERDICTS_JSONL, "a") as f:
        f.write(json.dumps({"pair": p.name, "track": p.track, "round": key["round"], "time": t,
                            "verdict": pick, "picked": picked, "note": note,
                            "A": key["A"], "B": key["B"]}) + "\n")
    print(f"Recorded: {p.name}, round {key['round']}: {pick}.  ({gov})\n")
    # 3. The key.
    for slot in SLOTS:
        side = p.sides[key[slot]]
        label = f" — {side.label}" if side.label else ""
        print(f"  {slot} was {key[slot]}{label}")
    print("\n  You found no difference." if pick == "same" else f"\n  You chose {pick}: the {picked} side.")
    # 4. The rig's numbers, after the verdict only.
    if p.results:
        for r in p.results:
            path = Path(r).expanduser()
            path = path if path.is_absolute() else REPO / path
            print(f"\n--- {path} ---")
            try:
                print(path.read_text().rstrip())
            except OSError as e:
                print(f"(cannot read: {e.strerror})")
    elif p.track == "R-22":
        print("\n(no results file named for this pair)")
    return 0


def tilde(path: Path) -> str:
    home = str(Path.home())
    return "~" + str(path)[len(home):] if str(path).startswith(home + "/") else str(path)


def read_jsonl(path: Path) -> list[dict]:
    out = []
    try:
        for line in path.read_text().splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    except OSError:
        pass
    return out


# --- main -----------------------------------------------------------------
def main(argv: list[str]) -> int:
    if len(argv) >= 1 and argv[0] in ("_launch", "_side"):
        if len(argv) != 3:
            return 2
        return (cmd_launch if argv[0] == "_launch" else cmd_side)(argv[1], argv[2])
    ap = argparse.ArgumentParser(prog="pairs", description=__doc__.split("\n\nPairs are TOML")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 epilog="Pairs: " + ", ".join(map(str, PAIRS)))
    ap.add_argument("--wm", choices=("hyprland", "sway"), default="hyprland",
                    help="sway is for tests, in a private headless sway")
    ap.add_argument("--dry-run", action="store_true",
                    help="run only read-only queries and print every command it would run")
    ap.add_argument("--missing", action="store_true",
                    help="prepare: build only sides not built yet")
    ap.add_argument("words", nargs="*")
    a = ap.parse_intermixed_args(argv)
    w = a.words
    try:
        if not w:
            return cmd_list()
        if w[0] == "prepare":
            return cmd_prepare(w[1:], a.missing)
        if w[0] == "close":
            return cmd_close(w[1:], a.dry_run)
        if w[0] == "verdict":
            if len(w) not in (3, 4):
                raise Fail('usage: pairs verdict <pair> A|B|same "<note>"')
            return cmd_verdict(w[1], w[2], w[3] if len(w) == 4 else "")
        if len(w) != 1:
            raise Fail("usage: pairs <pair>; `pairs -h` for the rest")
        return cmd_open(w[0], a.wm, a.dry_run)
    except Fail as e:
        warn(str(e))
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
