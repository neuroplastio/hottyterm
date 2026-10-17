---
title: "Animated GIFs, APNGs and WebPs in a surface play"
patch: 0005-hottyterm-animated-images-play.patch
upstream-fit: no
---

**What it changes:** hotty-blitz says when an animation's next frame is
due. A timer on the IO thread's loop fires then, renders the frame under
the terminal lock as a frame edit, wakes the renderer and sets itself for
the next one. With nothing playing there is no timer. While the program
holds its output (mode 2026) the timer waits, so a batch still shows whole.
One upstream line, in Termio, hands the loop to `hotty.zig`.

**Why we carry it:** hotty documents show images as a browser would.

**For upstream:** no. It animates hotty surfaces only.
