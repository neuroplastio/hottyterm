#!/usr/bin/env python3
"""touch-cells-check.py: a manual check of a finger in the cells (SPEC §9.6).

    HOTTY_DIR=~/code/neuroplastio/hotty/main \\
        scripts/run.sh -e python3 "$PWD/scripts/touch-cells-check.py"

The headless display used by `make smoke` cannot touch, so this is checked
by hand on a touchscreen. On the alternate screen, with the mouse reported
(1002, SGR), it draws in its cells:
  - a slider, one row of 40 cells, named with `a=touch` as an area that
    drags across (`x`): a press or a drag on it moves the thumb there;
  - a pad of 20×4 cells, an area that drags either way (`xy`);
  - the last mouse reports the program read, newest at the bottom.
q quits.

What each touch should show in the log:
  1. Slider, a sideways swipe: `press` on the cell where it began, `drag`
     following the finger, past the slider's ends and over the other rows
     too, `release` where it lifts. The thumb follows.
  2. Slider, a vertical swipe: no press, only `wheel` reports, as any touch
     drag on the alternate screen gives.
  3. Slider, a tap: `press` and `release` on the cell tapped, both at the
     lift. The thumb jumps there.
  4. Pad, a drag either way: `press`, `drag`, `release`. A drag exactly
     along a diagonal may pan instead (a tie is a pan).
  5. Outside both, on the log: a swipe is `wheel`, and a tap a click
     (`press`, `release`), as before.
  6. A slider drag, then a second finger: `release` on the cell the first
     finger was last on. The thumb stops following.
  7. Alt held on a keyboard: a sideways swipe on the slider is `wheel`, not
     a press.
  8. Ctrl held: the slider's reports say `ctrl`. Shift held: they do not
     say `shift` (Ghostty keeps a Shift press for selecting, unless
     `mouse-shift-capture` gives it to the program), and nothing is
     selected.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOTTY = os.environ.get("HOTTY_DIR") or os.path.join(HERE, "..", "..", "..", "hotty", "main")
sys.path.insert(0, os.path.join(HOTTY, "clients", "python"))
import hotty  # noqa: E402
from hotty import Hotty, TouchArea  # noqa: E402

SLIDER = (2, 2, 40)  # column, row (0-based) and width
PAD = (2, 5, 20, 4)  # column, row, width and height
LOG_ROW, LOG_ROWS = 11, 8
REPORT = re.compile(rb"\x1b\[<(\d+);(\d+);(\d+)([Mm])")


def at(c, r):
    """The cursor to the screen's cell (c, r), 0-based."""
    return f"\x1b[{r + 1};{c + 1}H"


def name(b, final):
    """What an SGR report's button byte says."""
    if b & 64:
        return "wheel " + ("up" if b & 3 == 0 else "down" if b & 3 == 1 else "side")
    if b & 32:
        return "drag" if b & 3 != 3 else "move"
    kind = "press" if final == b"M" else "release"
    return kind + ("" if b & 3 == 0 else f" button {b & 3}")


def main():
    lam = Hotty()
    with Hotty.raw():
        if lam.query() is None:
            print("touch-cells-check.py needs a hotty host: run it in hottyterm.")
            return
        lam.write("\x1b[?1049h\x1b[?25l\x1b[2J\x1b[?1002h\x1b[?1006h")
        c0, r0, w = SLIDER
        pc, pr, pw, ph = PAD
        lam.write(hotty.touch([TouchArea(c0, r0, w, 1, "x"), TouchArea(pc, pr, pw, ph, "xy")], q=2))
        lam.write(at(c0, r0 - 1) + "slider (drags across)")
        lam.write(at(pc, pr - 1) + "pad (drags either way)")
        for i in range(ph):
            lam.write(at(pc, pr + i) + "\x1b[45m" + " " * pw + "\x1b[0m")
        lam.write(at(0, LOG_ROW - 1) + "mouse reports (q quits):")
        thumb = 0
        log = []

        def slider():
            lam.write(at(c0, r0) + "".join("\x1b[44m \x1b[0m" if i == thumb else "\x1b[100m \x1b[0m" for i in range(w)))

        def show(line):
            log.append(line)
            del log[:-LOG_ROWS]
            for i in range(LOG_ROWS):
                lam.write(at(0, LOG_ROW + i) + "\x1b[2K" + (log[i] if i < len(log) else ""))

        slider()
        held = False
        try:
            while True:
                lam.read(1.0)
                _, keys = lam.take()
                for m in REPORT.finditer(keys):
                    b, c, r = int(m[1]), int(m[2]) - 1, int(m[3]) - 1
                    what = name(b, m[4])
                    mods = "".join(k for bit, k in ((4, " shift"), (8, " alt"), (16, " ctrl")) if b & bit)
                    show(f"{what} c={c} r={r}{mods}")
                    if what == "press":
                        held = r == r0 and c0 <= c < c0 + w
                    if held and what in ("press", "drag"):
                        thumb = min(max(c - c0, 0), w - 1)
                        slider()
                    if what == "release":
                        held = False
                if b"q" in REPORT.sub(b"", keys):
                    break
        except (KeyboardInterrupt, EOFError):
            pass
        lam.write(hotty.touch(q=2))
        lam.write("\x1b[?1002l\x1b[?1006l\x1b[?25h\x1b[?1049l")


if __name__ == "__main__":
    main()
