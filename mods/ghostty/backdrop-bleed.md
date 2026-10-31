---
title: "A backdrop bleeds to the window's edges"
patch: 0048-hottyterm-a-backdrop-bleeds-to-the-window-s-edges-V6.patch
upstream-fit: no
---

**What it changes:** a hotty backdrop (patch 0047, hotty 0.6's V6-06)
that reaches an edge of the grid goes on to the window's edge, as V6-06
asks of a host. It covers the padding round the cells and the pixels left over
when the window isn't a whole number of cells. Past each edge it
reaches, the renderer draws a strip of the backdrop's outermost pixels,
sampled at their middle so the strip is their colour exactly, and in a
corner its corner pixel. Only hotty backdrops bleed: a surface's image
at a kitty z below INT32_MIN/2. A program's own kitty image there is
drawn as before. The cells' backgrounds are drawn after, so a cell that
paints its background still extends it over the padding with
`window-padding-color = extend`.

**Why we carry it:** without it, a backdrop the size of the screen
still leaves a strip of the terminal's own background along the bottom
and the right. At 1.6 in a 2874x1845 window, 55 rows of 33 pixels and
191 columns of 15 leave 30 pixels below the grid and 9 to its right, and
`window-padding` adds a strip on every side. That breaks the cards'
look. It goes with patch 0047.

**For upstream:** no. It serves hotty's backdrops alone. A general
version would be a kitty graphics extension: a flag that lets an image
under the backgrounds bleed into the padding. Kitty's protocol has no
such flag, and upstream follows kitty's protocol.
