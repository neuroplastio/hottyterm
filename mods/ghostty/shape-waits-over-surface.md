---
title: "A program's pointer shape waits while a surface is hovered"
patch: 0046-hottyterm-a-program-s-pointer-shape-waits-while-a-su.patch
upstream-fit: no
---

**What it changes:** while the pointer is over a hotty surface, a shape
the program sets (OSC 22) is kept in `terminal.mouse_shape` but not
shown, so the pointer keeps the shape the surface's document asks for
(CSS `cursor`, hotty SPEC §9). When the pointer leaves the surface,
`hotty.zig`'s `shapeChange` shows the program's latest. The hook is the
`.set_mouse_shape` message in `src/Surface.zig`, which asks `hotty.zig`
whether a surface is hovered, under the terminal's lock.

**Why we carry it:** a motion over a surface is the surface's and never
reaches the program, so the program's last pointer position is the cell
before the surface. plx sets its shape per cell, one of its frames after
the motion. When the pointer crossed into a surface within that frame,
the change for the cell it had left arrived while the surface was
hovered and was shown over it: an arrow over a row that asks for a hand.
It stayed until the row's shape changed or the pointer left. A program
that writes a shape for any other reason while a surface is hovered, as
plx did on a hover event, did the same at any speed.

In a headless sway, a program wrote each cell's shape a frame after the
motion, above a row that asks for a hand. Without this patch the row
ended on the program's shape in 5 of 10 crossings 8 ms from the last
cell, 10 of 10 at 25 ms (written 40 ms late) and 10 of 10 with a write
on a hover event. With it, in none, and leaving the row showed the
program's latest shape in all 30. In plx's agents tool, a crossing from
a tab's pill onto an agent's row showed the arrow 16 of 16 times before
and the hand 32 of 32 after, over the pill and the dock line.
The hook is in core code, not an apprt's, so macOS has it too.

**For upstream:** no. Ghostty has no hotty surfaces.
