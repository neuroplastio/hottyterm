#!/usr/bin/env python3
"""run.py: gov R-22's latency rig, one matrix of runs (docs/feel.md).

    scripts/feel/run.py [--hosts hottyterm,ghostty,chromium] [--scenarios E1,E2,E3,E6]
                        [--scales 1,1.6,2] [--sizes full] [--rounds 2] [--n 40]
                        [--out out/feel/<stamp>] [--plx]

Each run is one host × scenario × scale × size × round, in a directory of
its own under --out, with:
- every process's trace (HOTTY_TRACE, docs/trace.md);
- meta.json: the labels, the builds, and the load before and after.

The hosts alternate within each round, so a change in the machine's load
reaches all of them. After every run, merge.py and report.py write the
tables.

Everything runs on the perf sway (scripts/feel/sway.sh), under its lock.
Each host gets a clean environment:
- every PLX_*, GHOSTTY_RESOURCES_DIR and TERM_PROGRAM* is unset, and the rig
  refuses to start while one remains;
- an empty XDG_CONFIG_HOME, so no one's own terminal config takes part.

Hosts (override a binary with HOTTYTERM_BIN, GHOSTTY_BIN, CHROMIUM_BIN):
- hottyterm: the fork's build (../ghostty/zig-out), stamped;
- ghostty: stock Ghostty at ghostty-ref (../ghostty-stock/zig-out);
- chromium: xterm-addon-hotty's demo page and serve.py.
With --plx, the program runs inside a throwaway plx (plx's
scripts/perf/plx-run.sh, PLX_RUN).
"""
import argparse
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
CODE = os.path.dirname(os.path.dirname(REPO))  # …/neuroplastio
CACHE = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "hotty")
SWAY = os.path.join(CACHE, "sway-feel")
PROG = os.path.join(HERE, "prog", "feelprog")
ADDON = os.environ.get("ADDON_DIR", os.path.join(CODE, "xterm-addon-hotty", "main"))
OUT_W, OUT_H = 2400, 1500  # the perf sway's output, device pixels

BUILDS = os.path.expanduser("~/.cache/hotty-perf/builds")
HOSTS = {
    "hottyterm": os.environ.get("HOTTYTERM_BIN", os.path.join(BUILDS, "hottyterm-stamps", "bin", "hottyterm")),
    "ghostty": os.environ.get("GHOSTTY_BIN", os.path.join(BUILDS, "ghostty-stock", "bin", "ghostty")),
    "chromium": os.environ.get("CHROMIUM_BIN", "/usr/bin/chromium"),
}
# hottyterm's hotty-blitz: the build's own lib/, ahead of its RUNPATH.
HOTTYTERM_LIB = os.environ.get("HOTTYTERM_LIB", os.path.join(os.path.dirname(os.path.dirname(HOSTS["hottyterm"])), "lib"))
# Stock Ghostty draws no hotty: it runs the text-only scenarios.
TEXT_ONLY = {"ghostty"}
TEXT_SCENARIOS = {"E1"}


def load():
    with open("/proc/loadavg") as f:
        return f.read().split()[0]


def clean_env(trace_dir, extra=None):
    env = {k: v for k, v in os.environ.items()
           if not (k.startswith("PLX_") or k.startswith("TERM_PROGRAM")
                   or k in ("GHOSTTY_RESOURCES_DIR", "DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE",
                            "WAYLAND_DISPLAY", "HOTTY_TRACE", "GHOSTTY_BIN_DIR"))}
    left = [k for k in env if k.startswith("PLX_")]
    if left:
        sys.exit(f"run.py: refusing to start while {left} remain")
    with open(os.path.join(SWAY, "display")) as f:
        env["WAYLAND_DISPLAY"] = f.read().strip()
    env["HOTTY_TRACE"] = trace_dir
    cfg = os.path.join(trace_dir, "config")
    os.makedirs(cfg, exist_ok=True)
    env["XDG_CONFIG_HOME"] = cfg
    env.update(extra or {})
    return env


def program_argv(sc, size, layout):
    """The scenario's program (scripts/feel/prog)."""
    name = {"E1": "e1", "E1P": "e1", "E2": "e2", "E2P": "e2", "E3": "e3", "E3P": "e3", "E6": "e6"}[sc]
    argv = [PROG, name]
    if sc.endswith("P"):
        argv += ["--paint"]
        if sc != "E1P" and size == "full":
            size = "half"  # the dash takes the rest
    if name != "e1" or sc == "E1P":
        argv += ["--size", size]
    if layout:
        argv += ["--layout", layout]
    return argv


def plx_wrap(argv, setup=None):
    """The program as the only pane of a throwaway plx (plx's
    scripts/perf/plx-run.sh, PLX_RUN): its own session dir, every PLX_*
    unset, HOTTY_TRACE passed through, everything stopped on SIGTERM."""
    run = os.environ.get("PLX_RUN", os.path.join(CODE, "plx", "main", "scripts", "perf", "plx-run.sh"))
    if not os.access(run, os.X_OK):
        sys.exit(f"run.py: --plx needs plx's launcher at {run} (PLX_RUN)")
    return [run, *(["--setup", setup] if setup else []), "--", *argv]


def launch(host, argv, env, run_dir, port):
    """Starts a host running argv; returns the processes to stop after."""
    log = open(os.path.join(run_dir, f"{host}.log"), "w")
    if host == "hottyterm":
        env = dict(env, LD_LIBRARY_PATH=HOTTYTERM_LIB)
    if host in ("hottyterm", "ghostty"):
        cmd = [HOSTS[host], "--gtk-single-instance=false", "--window-decoration=false",
               "--cursor-style-blink=false", "--confirm-close-surface=false", "-e", *argv]
        return [subprocess.Popen(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)]
    # chromium: the addon's demo page over serve.py's pty.
    serve = subprocess.Popen([sys.executable, os.path.join(ADDON, "serve.py"), "--port", str(port), "--", *argv],
                             env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    time.sleep(0.5)
    profile = os.path.join(run_dir, "chromium-profile")
    chrome = subprocess.Popen([HOSTS["chromium"], "--ozone-platform=wayland", f"--user-data-dir={profile}",
                               "--no-first-run", "--no-default-browser-check", "--disable-extensions",
                               "--disable-sync", "--password-store=basic",
                               f"--app=http://127.0.0.1:{port}/"],
                              env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    return [chrome, serve]


def stop(procs):
    for p in procs:
        try:
            os.killpg(p.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.time() + 2
    for p in procs:
        try:
            p.wait(max(0.05, deadline - time.time()))
        except subprocess.TimeoutExpired:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            p.wait()


def file_steps(spec, n):
    """A scenario file's steps: its untimed lead, then its timed steps
    repeated until n timed inputs have run."""
    lead, cycle = [], []
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


def steps(sc, scale, n, layout, host, spec=None):
    """The timed inputs for a scenario, as blackbox.py's JSON lines."""
    if spec:
        return file_steps(spec, spec.get("n", n))
    lw, lh = OUT_W / scale, OUT_H / scale
    out = []
    if sc in ("E1", "E1P", "E2", "E2P"):
        letters = "abcdefghijklmnopqrstuvwxyz"
        for i in range(n):
            out.append({"key": letters[i % 26]})
            if sc in ("E1", "E1P") and i % 40 == 39:
                out.append({"untimed": True, "key": "Return"})
    elif sc in ("E3", "E3P"):
        geo = json.load(open(layout)) if layout and os.path.exists(layout) else None
        pts = e3_points(geo, scale, host, os.path.dirname(layout)) if geo else None
        if not pts:
            sys.exit(f"run.py: {sc} needs the program's layout ({layout}) and, in plx, the pane's")
        out.append({"untimed": True, "move": list(pts[0])})
        for i in range(n):
            x, y = pts[(i + 1) % len(pts)]
            out.append({"move": [round(x), round(y)]})
    elif sc == "E6":
        for i in range(n):
            out.append({"key": "n"})
    return out


def e3_points(geo, scale, host, run_dir):
    """Two rows' centres, in logical output px, from the program's layout
    file: each row's centre in device px from the program's grid's top
    left (dx, dy), plus where that grid starts (origin), over the output's
    scale."""
    x0, y0, _ = origin(geo, scale, host, run_dir)
    if x0 is None:
        return None
    return [((x0 + r["dx"]) / scale, (y0 + r["dy"]) / scale) for r in geo["rows"][:2]]


def grid_top(geo, scale, host):
    """Where the terminal's grid starts, in device px. The window is the
    whole output. In Ghostty the grid starts after its default window
    padding, floor(2 pt at the font's DPI) device px; on the addon's demo
    page, 8 CSS px in (#term's inset)."""
    if host == "chromium":
        return 8 * scale
    return int(2 * 96 * ((geo or {}).get("scale") or scale) / 72)


def pane(run_dir):
    """plx's pane rect, when the program runs in one: plx's
    scripts/perf/plx-run.sh writes $HOTTY_TRACE/plx-pane.json, the pane's
    text rect in the terminal's cells (col, row, cols, rows) and, when it
    knows them, a cell's device px (cell_dev)."""
    f = os.path.join(run_dir, "plx-pane.json")
    try:
        with open(f) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def origin(geo, scale, host, run_dir):
    """Where the program's grid starts, in device px, and a cell's device
    px (None when nobody said): the terminal's grid, moved by plx's pane
    when there is one."""
    top = grid_top(geo, scale, host)
    cell = (geo or {}).get("cell_dev")
    cell = cell if cell and cell[0] else None
    p = pane(run_dir)
    if not p:
        return top, top, cell
    cell = p.get("cell_dev") or cell
    if not cell:
        return None, None, None
    return top + p["col"] * cell[0], top + p["row"] * cell[1], cell


def roi(sc, scale, layout, host, plx=False):
    """Where the rig looks for the change, in logical px: E1's echo row
    only, so E1P's dash below it doesn't count; with E2P and E3P, the
    field's or the list's surface, above their dash. In plx's pane, the
    same things moved by the pane; plain E1 inside plx without a cell's
    size watches the whole output (plx's chrome doesn't change on a key)."""
    lw, lh = OUT_W / scale, OUT_H / scale
    run_dir = os.path.dirname(layout)
    geo = json.load(open(layout)) if os.path.exists(layout) else None
    if sc in ("E1", "E1P"):
        if not pane(run_dir):
            return None if plx else f"0,0,{int(lw)},{int(40)}"
        _, y0, cell = origin(geo, scale, host, run_dir)
        if y0 is None:
            return None
        return f"0,{int(y0 / scale)},{int(lw)},{int((cell[1] + 4) / scale) + 1}"
    if sc in ("E2P", "E3P"):
        if not geo or not geo.get("dash"):
            sys.exit(f"run.py: {sc} needs the program's layout with its dash ({layout})")
        _, y0, _ = origin(geo, scale, host, run_dir)
        if y0 is None:
            sys.exit(f"run.py: {sc} in plx needs a cell's size (plx-pane.json's cell_dev or the layout's)")
        bottom = y0 + geo["surface_cells"][1] * geo["cell_dev"][1]
        return f"0,{int(y0 / scale)},{int(lw)},{int((bottom - y0) / scale)}"
    return None


def run_one(args, host, sc, scale, size, rnd, port, spec=None):
    name = (f"{host}-{sc}-s{scale}-{size}-r{rnd}" + ("-plx" if args.plx or (spec or {}).get("plx") else "")
            + ("-on-demand" if args.on_demand else ""))
    run_dir = os.path.join(args.out, name)
    os.makedirs(run_dir, exist_ok=True)
    layout = os.path.join(run_dir, "layout.json")
    argv = spec["argv"] if spec else program_argv(sc, size, layout)
    if args.plx or (spec or {}).get("plx"):
        argv = plx_wrap(argv, (spec or {}).get("setup"))
    env = clean_env(run_dir, dict(e.split("=", 1) for e in args.env))
    meta = {"host": host, "sc": sc, "scale": scale, "size": size, "round": rnd, "plx": args.plx,
            "on_demand": args.on_demand, "env": args.env,
            "bin": HOSTS[host], "load_before": load(), "argv": argv}
    subprocess.run([os.path.join(HERE, "sway.sh"), "scale", str(scale)], check=True,
                   stdout=subprocess.DEVNULL)
    procs = launch(host, argv, env, run_dir, port)
    try:
        time.sleep(args.startup)
        in_plx = args.plx or (spec or {}).get("plx")
        if in_plx:
            deadline = time.time() + 10
            while not pane(run_dir) and time.time() < deadline:
                time.sleep(0.2)
            if not pane(run_dir):
                print(f"{name}: no plx-pane.json from plx-run.sh: the program's coordinates are the window's",
                      file=sys.stderr, flush=True)
        st = os.path.join(run_dir, "steps.jsonl")
        with open(st, "w") as f:
            for s in steps(sc, scale, args.n, layout, host, spec):
                f.write(json.dumps(s) + "\n")
        bb = [sys.executable, os.path.join(HERE, "blackbox.py"), "--scenario", sc,
              "--settle-ms", str(args.settle), "--timeout-ms", str(args.timeout), "--json",
              "--warmup", str(args.warmup), *(["--on-demand"] if args.on_demand else [])]
        r = roi(sc, scale, layout, host, in_plx)
        if spec and spec.get("roi_frac"):
            fx, fy, fw, fh = spec["roi_frac"]
            lw, lh = OUT_W / scale, OUT_H / scale
            r = f"{int(fx * lw)},{int(fy * lh)},{int(fw * lw)},{int(fh * lh)}"
        if r:
            bb += ["--roi", r]
        bb.append(st)
        with open(os.path.join(run_dir, "blackbox.jsonl"), "w") as out:
            subprocess.run(bb, env=env, stdout=out, stderr=subprocess.STDOUT, timeout=600)
        time.sleep(0.4)  # the trace's 300 ms of quiet before the stop
    finally:
        stop(procs)
    meta["load_after"] = load()
    with open(os.path.join(run_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    subprocess.run([sys.executable, os.path.join(HERE, "merge.py"), run_dir],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"{name}: load {meta['load_before']}→{meta['load_after']}", flush=True)
    return run_dir


def main():
    # A run killed from outside (a timeout, a closed terminal) still stops
    # what it started: the hosts run in sessions of their own, out of reach
    # of a signal to this group, and only `finally` stops them.
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda n, _: sys.exit(128 + n))
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--hosts", default="hottyterm,ghostty,chromium")
    p.add_argument("--scenarios", default="E1,E2,E3,E6",
                   help="E1, E1P, E2, E2P, E3, E3P, E6 (P: a dash painting at 10 Hz beside what is timed)")
    p.add_argument("--scales", default="1,1.6,2")
    p.add_argument("--sizes", default="full")
    p.add_argument("--rounds", type=int, default=2)
    p.add_argument("--n", type=int, default=40)
    p.add_argument("--settle", type=int, default=200)
    p.add_argument("--timeout", type=int, default=3000)
    p.add_argument("--startup", type=float, default=4.0)
    p.add_argument("--env", action="append", default=[], metavar="K=V",
                   help="set in the host's environment (GDK_DEBUG=frames, …)")
    p.add_argument("--warmup", type=int, default=2,
                   help="timed inputs first that don't count: the page's focus, the first frames")
    p.add_argument("--plx", action="store_true")
    p.add_argument("--on-demand", action="store_true",
                   help="blackbox --on-demand: the output draws when a client commits, not at its refresh")
    p.add_argument("--scenario-file", action="append", default=[],
                   help="a scenario as JSON: name, argv, steps, roi_frac, plx, setup, n")
    p.add_argument("--out", default=os.path.join(REPO, "out", "feel", time.strftime("%Y%m%d-%H%M%S")))
    args = p.parse_args()
    hosts = args.hosts.split(",")
    for h in hosts:
        if not os.access(HOSTS[h], os.X_OK):
            sys.exit(f"run.py: no {h} at {HOSTS[h]}")
    if not os.access(PROG, os.X_OK):
        sys.exit(f"run.py: no scenario programs at {PROG}: build scripts/feel/prog")
    os.makedirs(args.out, exist_ok=True)
    runs = []
    port = 18765
    specs = [json.load(open(f)) for f in args.scenario_file]
    if specs:
        args.scenarios = ""
    for rnd in range(args.rounds):
        for scale in [float(s) for s in args.scales.split(",")]:
            for spec in specs:
                order = hosts[:] if rnd % 2 == 0 else hosts[::-1]
                for host in order:
                    port += 1
                    runs.append(run_one(args, host, spec["name"], scale, "-", rnd, port, spec))
            for sc in [x for x in args.scenarios.split(",") if x]:
                for size in args.sizes.split(","):
                    order = hosts[:] if rnd % 2 == 0 else hosts[::-1]
                    for host in order:
                        if host in TEXT_ONLY and sc not in TEXT_SCENARIOS:
                            continue
                        if sc in ("E1",) and size != args.sizes.split(",")[0]:
                            continue
                        port += 1
                        runs.append(run_one(args, host, sc, scale, size, rnd, port))
    subprocess.run([sys.executable, os.path.join(HERE, "report.py"), *runs,
                    "--md", os.path.join(args.out, "report.md")])


if __name__ == "__main__":
    main()
