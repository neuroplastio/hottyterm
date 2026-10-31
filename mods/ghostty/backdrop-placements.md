---
title: "A hotty surface can be a backdrop under the cells"
patch: 0047-hottyterm-a-backdrop-placement-is-drawn-under-the-ce.patch
upstream-fit: no
---

**What it changes:** a hotty placement with `b=1` is a backdrop (hotty
0.6's V6-06). It is drawn under the cells instead of over them. A cell
with the default background is transparent over it, while the text, the
cursor and any other background cover it. Surfaces are already kitty
images, so a backdrop is one whose kitty z is below INT32_MIN/2, which
Ghostty draws before the cells' backgrounds (its `kitty_below_bg`
layer). Backdrops stack by their own z and creation, under every other
placement. They take no pointer: the hit test leaves them out, so a
press reaches the cells. hotty-blitz reads the key, refuses `a=focus` on
a backdrop, and passes each placement's backdrop to `place`. `hotty.zig`
tells it the terminal draws them (`hotty_host_set_backdrops`), so the
capabilities list the feature `backdrop`. It needs a hotty-blitz with
V6-06, whose `place` callback carries the backdrop.

**Why we carry it:** a program that shows several terminals at once, as
a multiplexer does with its panes, can then draw each pane as a rounded
card on a darker canvas, with its focus as a ring around the card, in
place of box-drawing borders. The text stays in the cells, so typing is
drawn as before.

**For upstream:** no. Only `hotty.zig`, which upstream doesn't have,
changes. The layer it draws in is upstream's kitty graphics, unchanged.
