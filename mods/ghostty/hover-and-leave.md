---
title: "Hover reaches the program, and leaving the window ends it"
patch: 0008-hottyterm-hover-reaches-the-program-and-leaving-the-.patch
upstream-fit: no
---

**What it changes:** a placement with `v=1` hears `hover`, with the nearest
id under the pointer, each time it changes, and `out` when the pointer
leaves the window (HOTTY SPEC §9.4). The apprts report leaving the window
as a move to -1, -1, which `hotty.zig` ignored, so a surface stayed
hovered. Now the surface under the pointer is left then, unless a press
holds the pointer for it.

**Why we carry it:** menus and tooltips in HOTTY programs.

**For upstream:** no. The fix is in `hotty.zig`'s own handling; Ghostty's
cells already handle leaving.
