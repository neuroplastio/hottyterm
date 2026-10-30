#!/usr/bin/env python3
"""cgevent.py: keys and pointer moves for the latency rig on macOS (gov R-22).

    scripts/feel/cgevent.py <trace dir> <e1|e2|e3> --pid PID --layout FILE
                            [--n 60] [--warmup 3] [--gap-ms 150:300]
                            [--seed S] [--via cgevent|osascript] [--dry]
    scripts/feel/cgevent.py <trace dir> <scenario.json> --pid PID
                            [--n N] [--warmup 3] [--settle-ms 200]
                            [--timeout-ms 3000] [--jitter-ms 16.7]
                            [--seed S] [--via cgevent|osascript] [--dry]

scripts/probe-macos.sh (latency) runs it beside hottyterm, which runs
feelprog's scenario (scripts/feel/prog) with HOTTY_TRACE=<trace dir>. It
posts each input with CoreGraphics, at the HID tap where a keyboard's or a
mouse's events enter, and stamps it in <trace dir>/rig-<pid>.jsonl, trace
format hotty/1 (docs/trace.md), on the clock of the rest of the trace
(CLOCK_UPTIME_RAW): rig.input, with t read right before the post and a.i,
a.sc, a.kind (key or move), as blackbox.py does on Linux. The first
--warmup inputs go unstamped. There are no screen copies on the runner, so
no rig.pixels: report.py --end term.contents ends each input at the last
stamp the terminal makes of its frame.

- e1, e2: a letter key, pressed, and released 30 ms later.
- e3: the pointer to the centre of one of two rows of e3's list, in turn,
  so that each move changes :hover. The rows come from the layout file
  (feelprog --layout), in device px from the grid's top-left; the probe
  sets window-padding 0 and macos-titlebar-style hidden, so the grid starts
  at the window's top-left, and a device px is 1/scale points, scale being
  the backing scale (hottyterm's on macOS, docs/trace.md). The window's
  origin is its bounds from CGWindowListCopyWindowInfo, which need no
  screen-recording permission.
- Posting needs the permission to post events, which the runner's image
  decides. It asks CGPreflightPostEventAccess first, and checks after the
  first input that the terminal stamped it (term.key or term.pointer in its
  trace): if not, it says so and exits 3.
- --via osascript posts keys through System Events instead (key code),
  which the probe's text-input mode has shown the runner allows, for when
  CoreGraphics is refused. Each osascript starts a process, so its
  rig.input (a.via) is well before the key: the host's stages, from
  term.key on, are the numbers then. It has no pointer.
- --dry posts nothing and stamps anyway, on CLOCK_MONOTONIC off macOS: it
  checks the plan anywhere.

A scenario file (blackbox.py's steps, as run.py reads them: `steps`, or
`lead` and `cycle`, repeated until --n timed steps, the file's `n` by
default) plays its key and sleep steps the way blackbox.py does on Linux:
a step's mods go down in order before its key and up in reverse after it,
an untimed step waits for the screen to settle after it unless "settle":
false, and a timed step waits for the screen to be quiet, then a random
jitter under one refresh, unless "quiet": false. There being no screen
copies, the screen is the terminal's trace: it has settled when no
term.contents has come for --settle-ms, and a timed step whose input no
term.contents follows within --timeout-ms is a miss (rig.miss). Key names
are blackbox.py's keysym names, and a character that needs Shift on the
US layout gets it (colon is Shift+semicolon). Pointer steps are not
played here.
"""
import argparse
import glob
import json
import os
import random
import subprocess
import sys
import time

DARWIN = sys.platform == "darwin"
CLOCK = time.CLOCK_UPTIME_RAW if DARWIN else time.CLOCK_MONOTONIC
# US-layout virtual key codes (Carbon's kVK_ANSI_*): a s d f j k l.
KEYS = [0, 1, 2, 3, 38, 40, 37]
HOLD_NS = 30_000_000
# Carbon's kVK_* codes on the US layout, by blackbox.py's keysym names.
VK = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9,
    "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17, "1": 18, "2": 19,
    "3": 20, "4": 21, "6": 22, "5": 23, "equal": 24, "9": 25, "7": 26, "minus": 27,
    "8": 28, "0": 29, "bracketright": 30, "o": 31, "u": 32, "bracketleft": 33, "i": 34,
    "p": 35, "Return": 36, "l": 37, "j": 38, "apostrophe": 39, "k": 40, "semicolon": 41,
    "backslash": 42, "comma": 43, "slash": 44, "n": 45, "m": 46, "period": 47,
    "Tab": 48, "space": 49, "grave": 50, "BackSpace": 51, "Escape": 53, "Home": 115,
    "Prior": 116, "Delete": 117, "End": 119, "Next": 121, "Left": 123, "Right": 124,
    "Down": 125, "Up": 126,
}
# Keysyms that are another key with Shift.
SHIFTED = {
    "colon": "semicolon", "underscore": "minus", "plus": "equal", "braceleft": "bracketleft",
    "braceright": "bracketright", "bar": "backslash", "quotedbl": "apostrophe",
    "less": "comma", "greater": "period", "question": "slash", "asciitilde": "grave",
    "exclam": "1", "at": "2", "numbersign": "3", "dollar": "4", "percent": "5",
    "asciicircum": "6", "ampersand": "7", "asterisk": "8", "parenleft": "9", "parenright": "0",
}
CHARS = {
    " ": "space", "-": "minus", "=": "equal", "[": "bracketleft", "]": "bracketright",
    ";": "semicolon", ":": "colon", "'": "apostrophe", '"': "quotedbl", "`": "grave",
    "~": "asciitilde", "\\": "backslash", "|": "bar", ",": "comma", ".": "period",
    "/": "slash", "<": "less", ">": "greater", "?": "question", "_": "underscore",
    "+": "plus", "{": "braceleft", "}": "braceright", "\n": "Return", "\t": "Tab",
}
ALIASES = {"Enter": "Return", "Esc": "Escape", "Backspace": "BackSpace", "Del": "Delete",
           "Page_Up": "Prior", "Page_Down": "Next"}
# A modifier's key (kVK_*), its flag (kCGEventFlagMask*) and System Events' name.
MODS = {"ctrl": (59, 0x40000, "control down"), "shift": (56, 0x20000, "shift down"),
        "alt": (58, 0x80000, "option down"), "super": (55, 0x100000, "command down")}
# The host's stamp of an input reaching it (docs/trace.md).
DELIVERED = {"key": "term.key", "move": "term.pointer"}


def now():
    return time.clock_gettime_ns(CLOCK)


class Poster:
    """CGEventPost, System Events with --via osascript, or nothing with --dry."""

    def __init__(self, dry, via):
        self.dry = dry
        self.via = via
        if dry or via == "osascript":
            return
        import Quartz  # pyobjc-framework-Quartz, in the probe's venv
        self.q = Quartz
        preflight = getattr(Quartz, "CGPreflightPostEventAccess", None)
        if preflight:
            print(f"cgevent: CGPreflightPostEventAccess: {bool(preflight())}", flush=True)

    def key(self, code, down):
        if self.dry:
            return
        if self.via == "osascript":  # a press and its release, on the press
            if down:
                subprocess.run(["osascript", "-e", f'tell application "System Events" to key code {code}'],
                               check=False)
            return
        q = self.q
        ev = q.CGEventCreateKeyboardEvent(None, code, down)
        q.CGEventSetFlags(ev, 0)
        q.CGEventPost(q.kCGHIDEventTap, ev)

    def press(self, code, mods, hold_s):
        """A key with its mods, as blackbox.py sends one: each mod's key down
        in order, the key, its release hold_s later, the mods up in reverse.
        System Events sends the press and its release at once."""
        if self.dry:
            return
        if self.via == "osascript":
            using = ", ".join(MODS[m][2] for m in mods)
            script = f'tell application "System Events" to key code {code}' + (f" using {{{using}}}" if using else "")
            subprocess.run(["osascript", "-e", script], check=False)
            return
        q = self.q

        def post(c, down, flags):
            ev = q.CGEventCreateKeyboardEvent(None, c, down)
            q.CGEventSetFlags(ev, flags)
            q.CGEventPost(q.kCGHIDEventTap, ev)
        flags = 0
        for m in mods:
            flags |= MODS[m][1]
            post(MODS[m][0], True, flags)
        post(code, True, flags)
        time.sleep(hold_s)
        post(code, False, flags)
        for m in reversed(mods):
            flags &= ~MODS[m][1]
            post(MODS[m][0], False, flags)

    def move(self, x, y):
        if self.dry:
            return
        q = self.q
        ev = q.CGEventCreateMouseEvent(None, q.kCGEventMouseMoved, (x, y), q.kCGMouseButtonLeft)
        q.CGEventPost(q.kCGHIDEventTap, ev)

    def window_origin(self, pid):
        """The top-left, in points, of pid's largest on-screen window."""
        if self.dry:
            return 0.0, 0.0
        if self.via == "osascript":
            sys.exit("cgevent: --via osascript has no pointer")
        q = self.q
        wins = q.CGWindowListCopyWindowInfo(q.kCGWindowListOptionOnScreenOnly, q.kCGNullWindowID) or []
        best = None
        for w in wins:
            if int(w.get("kCGWindowOwnerPID", -1)) != pid or int(w.get("kCGWindowLayer", 1)) != 0:
                continue
            b = w["kCGWindowBounds"]
            area = float(b["Width"]) * float(b["Height"])
            if best is None or area > best[0]:
                best = (area, float(b["X"]), float(b["Y"]), float(b["Width"]), float(b["Height"]))
        if best is None:
            sys.exit(f"cgevent: no on-screen window of pid {pid}")
        print(f"cgevent: window at {best[1]:.0f},{best[2]:.0f}, {best[3]:.0f}x{best[4]:.0f} pt", flush=True)
        return best[1], best[2]


def read_layout(path, scaled, timeout=30):
    """The layout once feelprog has written one, with the host's scale when
    `scaled` (e1 asks the host nothing, and its layout has none)."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            with open(path) as f:
                lay = json.load(f)
            if not scaled or lay.get("scale", 0) > 0:
                return lay
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    sys.exit(f"cgevent: no layout{' with a scale' if scaled else ''} in {path} after {timeout} s")


def host_stamped(trace_dir, name, since, timeout=2.0):
    """Whether the terminal's trace has `name` at or after `since`."""
    end = time.time() + timeout
    while time.time() < end:
        for p in glob.glob(os.path.join(trace_dir, "hottyterm-*.jsonl")):
            try:
                with open(p) as f:
                    for line in f:
                        if f'"n":"{name}"' in line:
                            try:
                                if json.loads(line)["t"] >= since:
                                    return True
                            except (ValueError, KeyError):
                                pass
            except OSError:
                pass
        time.sleep(0.05)
    return False


class HostTrace:
    """The terminal's trace as it is written: when it last handed a frame
    to the window server (term.contents), the screen of a scenario file."""

    def __init__(self, trace_dir):
        self.dir = trace_dir
        self.files = {}  # path -> [file, the line read so far]
        self.last_frame = 0

    def poll(self):
        for p in glob.glob(os.path.join(self.dir, "hottyterm-*.jsonl")):
            if p not in self.files:
                try:
                    self.files[p] = [open(p), ""]
                except OSError:
                    continue
            f = self.files[p]
            chunk = f[0].read()
            if not chunk:
                continue
            *lines, f[1] = (f[1] + chunk).split("\n")
            for line in lines:
                if '"n":"term.contents"' in line:
                    try:
                        self.last_frame = max(self.last_frame, json.loads(line)["t"])
                    except (ValueError, KeyError):
                        pass

    def wait_quiet(self, settle, cap, since=0):
        """Until no frame has come for settle ns, counted from since at the
        earliest; False at cap."""
        while True:
            self.poll()
            t = now()
            if t - max(self.last_frame, since) >= settle:
                return True
            if t >= cap:
                return False
            time.sleep(0.005)

    def wait_frame(self, after, cap):
        """Until a frame comes after `after`; False at cap."""
        while True:
            self.poll()
            if self.last_frame > after:
                return True
            if now() >= cap:
                return False
            time.sleep(0.002)


def file_steps(spec, n):
    """A scenario file's steps, as run.py's file_steps has them: its untimed
    lead, then its timed steps repeated until n timed inputs have run. With
    lead and cycle, those."""
    lead, cycle = [], []
    if "cycle" in spec:
        lead, cycle = list(spec.get("lead", [])), spec["cycle"]
    else:
        for st in spec["steps"]:
            (cycle if cycle or not st.get("untimed") else lead).append(st)
    out, timed = list(lead), 0
    while cycle and timed < n:
        for st in cycle:
            out.append(st)
            timed += 0 if st.get("untimed") or "sleep_ms" in st else 1
            if timed >= n:
                break
    return out


def key_code(name):
    """A keysym name's (or a character's) key code and the Shift it needs."""
    name = ALIASES.get(name, CHARS.get(name, name))
    shift = []
    if len(name) == 1 and name.isalpha() and name.isupper():
        name, shift = name.lower(), ["shift"]
    if name in SHIFTED:
        name, shift = SHIFTED[name], ["shift"]
    if name not in VK:
        raise ValueError(f"no macOS key code for {name!r}")
    return VK[name], shift


def compile_steps(raw):
    """blackbox.py's steps, its key, keys and sleep_ms ones, with their codes."""
    out = []
    for st in raw:
        acts = [k for k in ("key", "keys", "move", "click", "wheel", "focus", "sleep_ms") if k in st]
        if len(acts) != 1:
            raise ValueError(f"a step has one action: {st}")
        base = {"untimed": st.get("untimed", False), "settle": st.get("settle", True),
                "quiet": st.get("quiet", True), "mark": st.get("mark"), "hold_ms": st.get("hold_ms")}
        if acts[0] == "sleep_ms":
            out.append({**base, "kind": "sleep", "untimed": True, "ms": float(st["sleep_ms"])})
            continue
        if acts[0] not in ("key", "keys"):
            raise ValueError(f"{acts[0]} steps are not played on macOS, only keys and sleeps")
        for k in [st["key"]] if acts[0] == "key" else list(st["keys"]):
            code, shift = key_code(k)
            mods = list(st.get("mods", []))
            mods += [m for m in shift if m not in mods]
            for m in mods:
                if m not in MODS:
                    raise ValueError(f"no modifier {m!r}: ctrl, shift, alt, super")
            out.append({**base, "kind": "key", "key": k, "code": code, "mods": mods})
    return out


def play_file(a, post):
    """A scenario file's steps (the module's docstring), stamped."""
    with open(a.scenario) as f:
        spec = json.load(f)
    sc = spec.get("name") or os.path.splitext(os.path.basename(a.scenario))[0]
    try:
        steps = compile_steps(file_steps(spec, a.n if a.n is not None else int(spec.get("n", 60))))
    except ValueError as e:
        sys.exit(f"cgevent: {a.scenario}: {e}")
    rng = random.Random(a.seed)
    host = HostTrace(a.trace_dir)
    settle, timeout = int(a.settle_ms * 1e6), int(a.timeout_ms * 1e6)
    via = {"via": a.via} if a.via != "cgevent" else {}
    path = os.path.join(a.trace_dir, f"rig-{os.getpid()}.jsonl")
    with open(path, "a") as out:
        def stamp(t, name, attrs):
            out.write(json.dumps({"t": t, "n": name, "tr": "pixels" if name == "rig.miss" else "input",
                                  "a": attrs}) + "\n")
            out.flush()

        def mark(st, t):
            if st["mark"]:
                stamp(t, "rig.mark", {"mark": st["mark"], "sc": sc, "kind": st["kind"]})

        def delivered(t):
            if not a.dry and not host_stamped(a.trace_dir, DELIVERED["key"], t):
                print("cgevent: the terminal never stamped the first key (term.key): "
                      "the runner does not let this process post events", flush=True)
                sys.exit(3)

        out.write(json.dumps({"trace": "hotty/1", "proc": "rig", "pid": os.getpid(),
                              "clock": "uptime-raw" if DARWIN else "monotonic"}) + "\n")
        out.flush()
        if not a.dry and not host.wait_quiet(settle, now() + timeout):
            print(f"cgevent: {sc}: the screen didn't settle before the first step", flush=True)
        timed = measured = misses = 0
        first = True
        for st in steps:
            if st["kind"] == "sleep":
                mark(st, now())
                time.sleep(st["ms"] / 1e3)
                continue
            hold = (st["hold_ms"] if st["hold_ms"] is not None else HOLD_NS / 1e6) / 1e3
            if st["untimed"]:
                t = now()
                post.press(st["code"], st["mods"], hold)
                mark(st, t)
                if first:
                    delivered(t)
                    first = False
                if st["settle"] and not a.dry and not host.wait_quiet(settle, now() + timeout, since=now()):
                    print(f"cgevent: {sc}: the screen didn't settle after an untimed {st['key']}", flush=True)
                continue
            i = None if timed < a.warmup else measured
            timed += 1
            measured += 0 if i is None else 1
            if st["quiet"]:
                if not a.dry and not host.wait_quiet(settle, now() + timeout):
                    print(f"cgevent: {sc}: a timed {st['key']} sent on a screen that didn't settle", flush=True)
                time.sleep(rng.uniform(0, a.jitter_ms) / 1e3)
            t = now()
            post.press(st["code"], st["mods"], hold)
            mark(st, t)
            attrs = {"i": i, "sc": sc, "kind": "key", **via}
            if i is not None:
                stamp(t, "rig.input", attrs)
            if first:
                delivered(t)
                first = False
            if a.dry:
                continue
            if not host.wait_frame(t, t + timeout):
                misses += 1
                if i is not None:
                    stamp(t + timeout, "rig.miss", attrs)
            host.wait_quiet(settle, now() + timeout, since=t)
    print(f"cgevent: {sc}: {measured} keys stamped into {path}, {misses} without a frame", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("trace_dir")
    ap.add_argument("scenario", help="e1, e2, e3, or a scenario file (.json)")
    ap.add_argument("--pid", type=int, required=True, help="hottyterm's pid: its window, for e3")
    ap.add_argument("--layout", help="feelprog's --layout file (e1, e2, e3)")
    ap.add_argument("--n", type=int, default=None, help="stamped inputs (60), or a file's timed steps (its n)")
    ap.add_argument("--warmup", type=int, default=3, help="unstamped inputs first")
    ap.add_argument("--gap-ms", default="150:300", help="the wait after an input, uniform in lo:hi")
    ap.add_argument("--settle-ms", type=float, default=200, help="a file's settle: no frame for this long")
    ap.add_argument("--timeout-ms", type=float, default=3000, help="a file's wait for a frame or a settle")
    ap.add_argument("--jitter-ms", type=float, default=1000 / 60, help="a file's jitter before a timed step")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--via", choices=["cgevent", "osascript"], default="cgevent")
    ap.add_argument("--dry", action="store_true", help="post nothing")
    a = ap.parse_args()
    post = Poster(a.dry, a.via)
    if a.scenario.endswith(".json"):
        play_file(a, post)
        return
    if a.scenario not in ("e1", "e2", "e3"):
        ap.error("scenario: e1, e2, e3, or a .json file")
    if not a.layout:
        ap.error(f"{a.scenario} needs --layout")
    a.n = 60 if a.n is None else a.n
    lo, hi = (float(v) for v in a.gap_ms.split(":"))
    rng = random.Random(a.seed)
    sc = a.scenario.upper()
    kind = "move" if a.scenario == "e3" else "key"
    lay = read_layout(a.layout, kind == "move")
    targets = []
    if kind == "move":
        rows = lay.get("rows") or []
        if len(rows) < 4:
            sys.exit(f"cgevent: e3's layout has {len(rows)} rows, not 4 or more")
        ox, oy = post.window_origin(a.pid)
        s = lay["scale"]
        # Two rows apart, never neighbours: an aim off by half a row still
        # lands in the right one.
        targets = [(ox + r["dx"] / s, oy + r["dy"] / s) for r in (rows[1], rows[3])]
        print("cgevent: aiming at " + ", ".join(f"{x:.1f},{y:.1f}" for x, y in targets) + " pt", flush=True)
        post.move(*targets[1])
        time.sleep(0.3)

    path = os.path.join(a.trace_dir, f"rig-{os.getpid()}.jsonl")
    with open(path, "a") as out:
        out.write(json.dumps({"trace": "hotty/1", "proc": "rig", "pid": os.getpid(),
                              "clock": "uptime-raw" if DARWIN else "monotonic"}) + "\n")
        out.flush()
        for k in range(a.warmup + a.n):
            i = k - a.warmup
            t = now()
            if kind == "key":
                code = KEYS[k % len(KEYS)]
                post.key(code, True)
                if a.via == "cgevent":
                    time.sleep(HOLD_NS / 1e9)
                post.key(code, False)
            else:
                post.move(*targets[k % 2])
            if i >= 0:
                stamp = {"i": i, "sc": sc, "kind": kind, **({"via": a.via} if a.via != "cgevent" else {})}
                out.write(json.dumps({"t": t, "n": "rig.input", "tr": "input", "a": stamp}) + "\n")
                out.flush()
            if k == 0 and not a.dry and not host_stamped(a.trace_dir, DELIVERED[kind], t):
                print(f"cgevent: the terminal never stamped the first {kind} ({DELIVERED[kind]}): "
                      "the runner does not let this process post events", flush=True)
                sys.exit(3)
            time.sleep(rng.uniform(lo, hi) / 1e3)
    print(f"cgevent: {a.n} {kind}s stamped into {path}", flush=True)


if __name__ == "__main__":
    main()
