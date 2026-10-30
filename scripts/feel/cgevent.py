#!/usr/bin/env python3
"""cgevent.py: keys and pointer moves for the latency rig on macOS (gov R-22).

    scripts/feel/cgevent.py <trace dir> <e1|e2|e3> --pid PID --layout FILE
                            [--n 60] [--warmup 3] [--gap-ms 150:300]
                            [--seed S] [--dry]

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
- --dry posts nothing and stamps anyway, on CLOCK_MONOTONIC off macOS: it
  checks the plan anywhere.
"""
import argparse
import glob
import json
import os
import random
import sys
import time

DARWIN = sys.platform == "darwin"
CLOCK = time.CLOCK_UPTIME_RAW if DARWIN else time.CLOCK_MONOTONIC
# US-layout virtual key codes (Carbon's kVK_ANSI_*): a s d f j k l.
KEYS = [0, 1, 2, 3, 38, 40, 37]
HOLD_NS = 30_000_000
# The host's stamp of an input reaching it (docs/trace.md).
DELIVERED = {"key": "term.key", "move": "term.pointer"}


def now():
    return time.clock_gettime_ns(CLOCK)


class Poster:
    """CGEventPost, or nothing with --dry."""

    def __init__(self, dry):
        self.dry = dry
        if dry:
            return
        import Quartz  # pyobjc-framework-Quartz, in the probe's venv
        self.q = Quartz
        preflight = getattr(Quartz, "CGPreflightPostEventAccess", None)
        if preflight:
            print(f"cgevent: CGPreflightPostEventAccess: {bool(preflight())}", flush=True)

    def key(self, code, down):
        if self.dry:
            return
        q = self.q
        ev = q.CGEventCreateKeyboardEvent(None, code, down)
        q.CGEventSetFlags(ev, 0)
        q.CGEventPost(q.kCGHIDEventTap, ev)

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


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("trace_dir")
    ap.add_argument("scenario", choices=["e1", "e2", "e3"])
    ap.add_argument("--pid", type=int, required=True, help="hottyterm's pid: its window, for e3")
    ap.add_argument("--layout", required=True, help="feelprog's --layout file")
    ap.add_argument("--n", type=int, default=60, help="stamped inputs")
    ap.add_argument("--warmup", type=int, default=3, help="unstamped inputs first")
    ap.add_argument("--gap-ms", default="150:300", help="the wait after an input, uniform in lo:hi")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--dry", action="store_true", help="post nothing")
    a = ap.parse_args()
    lo, hi = (float(v) for v in a.gap_ms.split(":"))
    rng = random.Random(a.seed)
    post = Poster(a.dry)
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
                time.sleep(HOLD_NS / 1e9)
                post.key(code, False)
            else:
                post.move(*targets[k % 2])
            if i >= 0:
                out.write(json.dumps({"t": t, "n": "rig.input", "tr": "input",
                                      "a": {"i": i, "sc": sc, "kind": kind}}) + "\n")
                out.flush()
            if k == 0 and not a.dry and not host_stamped(a.trace_dir, DELIVERED[kind], t):
                print(f"cgevent: the terminal never stamped the first {kind} ({DELIVERED[kind]}): "
                      "the runner does not let this process post events", flush=True)
                sys.exit(3)
            time.sleep(rng.uniform(lo, hi) / 1e3)
    print(f"cgevent: {a.n} {kind}s stamped into {path}", flush=True)


if __name__ == "__main__":
    main()
