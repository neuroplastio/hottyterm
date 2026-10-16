---
title: "A click on a surface carries the platform's click count"
patch: 0026-hottyterm-a-HOTTY-click-carries-the-platform-s-count.patch
upstream-fit: no
---

**What it changes:** GTK's click gesture counts presses by the user's
double-click time and distance (`n_press`), which Ghostty ignored. The
count now goes to hotty-blitz with the next press on a surface, which
keeps a run of clicks to one element. Where the platform gives no count,
as on macOS today, `hotty.zig` counts presses as Ghostty's own selection
does, with `click-repeat-interval` and a cell's width. The capabilities
report `count`. One upstream line, in the GTK surface.

**Why we carry it:** double and triple clicks in HOTTY documents select
words and lines (HOTTY SPEC §9).

**For upstream:** no. Only HOTTY surfaces use the count.
