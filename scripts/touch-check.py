#!/usr/bin/env python3
"""touch-check.py: a manual check of touch on a touchscreen (SPEC §9.1).

    HOTTY_DIR=~/code/neuroplastio/hotty/main \
        scripts/run.sh -e python3 "$PWD/scripts/touch-check.py"

The headless display used by `make smoke` cannot touch, so this is checked
by hand. It prints numbered lines into the scrollback, then places a surface
under them, whose document scrolls vertically (scroll=1), with:
  - a slider (`touch-action: pan-y`) of 20 steps, each with an id and
    `data-on="drag click"`: a drag across them, or a click on one, moves the
    thumb there;
  - a pad (`touch-action: none`, `data-on=drag`), which drags either way;
  - a list that scrolls, of buttons that opt in to drags with the initial
    `touch-action: auto`, so a touch pans them and never drags them;
  - the last events the surface sent, newest at the bottom.
The placement asks for `press`, so every press shows. q quits.

What each touch should show in the log (SPEC §9.1). A tap is a touch that
lifts within 8 CSS px: it presses where it lifts and never drags, so it
sends no `dragstart` or `dragend`.
  1. Slider, a sideways swipe: `press sA`, `dragstart sA c=… r=…` where it
     began, a `drag s…` for each step crossed (one at once if the finger is
     already past sA), `dragend s…`. Add `click sA` if it lifts on sA. The
     blue step follows the finger.
  2. Slider, a vertical swipe: nothing in the log. The scrollback moves.
  3. Slider, a tap: `press sN`, `click sN`. The blue step jumps there.
  4. Pad, a drag either way: `press pad`, `dragstart pad`, then
     `drag (none)` per cell once outside it, `dragend`.
     Pad, a tap: `press pad` only. The pad reports no click.
  5. List, a vertical swipe starting on a button: nothing in the log. The
     list scrolls, and past its end the scrollback does.
  6. List, a tap on a button: `press itemN`, `focus (none)` (only the first
     time the surface takes the keyboard; focus names no element),
     `click itemN`.
  7. A slider drag, then a second finger: `dragend (none)`. The blue step
     stops following. Nothing more until every finger lifts.
  8. Alt held on a keyboard: a sideways swipe on the slider logs nothing,
     and a tap logs `press sN`, `click sN` as in 3.
  9. The finger, not the mouse:
     - With the mouse pointer resting on the list, a swipe on the
       scrollback text moves the scrollback and not the list.
     - With it resting on the text, a swipe on the list scrolls the list.
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOTTY = os.environ.get("HOTTY_DIR") or os.path.join(HERE, "..", "..", "..", "hotty", "main")
sys.path.insert(0, os.path.join(HOTTY, "clients", "python"))
from hotty import Event, Hotty  # noqa: E402

STEPS = 20

HTML = """
<style>
  body { margin: 0; }
  .row { display: flex; align-items: center; gap: 1ch; height: 2rlh; padding: 0 1ch; }
  .label { width: 8ch; opacity: .7; }
  #slider { flex: 1; display: flex; height: 1rlh; touch-action: pan-y; }
  #slider span { flex: 1; margin: 0 1px; border-radius: 3px;
                 background: color-mix(in srgb, var(--hotty-bg) 75%, white); }
  #slider span.on { background: var(--hotty-ansi-4); }
  #pad { flex: 1; height: 1.6rlh; touch-action: none; border-radius: 6px; text-align: center;
         line-height: 1.6rlh; background: color-mix(in srgb, var(--hotty-ansi-5) 50%, var(--hotty-bg)); }
  #list { height: 6rlh; overflow-y: auto; margin: 0 1ch; border: 1px solid var(--hotty-ansi-8); }
  #list button { display: block; width: 100%; height: 1rlh; border: 0; text-align: left;
                 font: inherit; color: var(--hotty-fg); background: transparent; }
  #list button:nth-child(odd) { background: color-mix(in srgb, var(--hotty-bg) 90%, white); }
  #log { margin: 4px 1ch 0; height: 6rlh; white-space: pre; overflow: hidden; opacity: .85; }
</style>
<div class=row><span class=label>slider</span><div id=slider>""" + "".join(
    f'<span id=s{i} data-on="drag click"{" class=on" if i == 0 else ""}></span>' for i in range(STEPS)
) + """</div></div>
<div class=row><span class=label>pad</span><div id=pad data-on=drag>drag me any way</div></div>
<div id=list>""" + "".join(
    f'<button id=item{i} data-on=drag>item {i}: swipe to scroll, tap to click</button>' for i in range(1, 41)
) + """</div>
<div id=log>(events show here)</div>
"""


def step(target):
    """The slider step an event's target names, or None."""
    if target.startswith("s") and target[1:].isdigit() and int(target[1:]) < STEPS:
        return int(target[1:])
    return None


def main():
    lam = Hotty()
    size = shutil.get_terminal_size()
    cols = min(size.columns, 64)
    with Hotty.raw():
        if lam.query() is None:
            print("touch-check.py needs a HOTTY host: run it in hottyterm.")
            return
        lam.write("".join(f"scrollback line {i}\r\n" for i in range(1, 201)))
        lam.doc("touch", HTML, scroll=1)
        lam.place("touch", cols, press=True)
        lam.write("\r\n q quits")
        log = []
        thumb = 0
        sliding = False

        def show(line):
            log.append(line)
            del log[:-6]
            lam.text("touch", "log", "\n".join(log))

        def move_thumb(to):
            nonlocal thumb
            if to is None or to == thumb:
                return
            lam.attr("touch", f"s{thumb}", "class", "")
            lam.attr("touch", f"s{to}", "class", "on")
            thumb = to

        try:
            while True:
                lam.read(1.0)
                msgs, keys = lam.take()
                for m in msgs:
                    if m["a"] != "ev":
                        continue
                    e = Event(m)
                    d = e.drag()
                    show(f"{e.kind} {e.target or '(none)'}" + (f" c={d.c} r={d.r} {d.keys}" if d else ""))
                    if e.kind == "dragstart":
                        sliding = step(e.target) is not None
                    if (sliding and e.kind in ("dragstart", "drag")) or e.kind == "click":
                        move_thumb(step(e.target))
                    if e.kind == "dragend":
                        sliding = False
                if b"q" in keys:
                    break
        except (KeyboardInterrupt, EOFError):
            pass
        lam.delete("touch")


if __name__ == "__main__":
    main()
