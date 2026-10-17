---
title: "Zooming a surface is a browser's zoom"
patch: 0018-hottyterm-a-zoom-is-a-browser-s-zoom-SPEC-5.3.patch
upstream-fit: no
---

**What it changes:** Ctrl+= changed the font's size in points and kept the
scale, so hotty-blitz laid a document out larger in CSS px with only the
font grown, and each placement kept its old source rectangle, showing the
top left of the new frame stretched. Now CSS px come from the configured
`font-size`, and a zoom multiplies the scale instead: the layout stays,
and everything grows (hotty SPEC §5.3). A resize resets each placement's
source rectangle to its window at the new cell size, and wakes the IO
mailbox after its replies. A config reload that changes `font-size`
changes CSS px, and the program hears `resize`.

**Why we carry it:** zooming hottyterm zooms its documents as a browser
does.

**For upstream:** no. It changes how hotty measures, not the cells.
