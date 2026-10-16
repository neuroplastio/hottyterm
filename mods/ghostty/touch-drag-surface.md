---
title: "A touch drags what a surface keeps from panning"
patch: 0017-hottyterm-a-touch-drags-what-opts-out-of-panning-SPE.patch
upstream-fit: no
---

**What it changes:** a touch that begins over a surface, where the surface
takes the pointer, is hotty-blitz's to decide (`hotty_host_touch`): every
phase of it goes there, taps included, and none to the pointer. While it
may still become a drag, its moves wait. Once it pans, the terminal scrolls
from where it began; once it drags, its moves are the surface's. A second
finger, or the platform, cancels it. A touch over the cells, or one that
only focuses a split, is the terminal's as before (HOTTY SPEC §9.1). The
GTK surface gets the touch's offsets; the logic is in `hotty.zig`.

**Why we carry it:** sliders and drag and drop in HOTTY documents, on a
touchscreen.

**For upstream:** no. It serves HOTTY surfaces.
