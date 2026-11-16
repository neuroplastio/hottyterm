---
title: "Scrolls and a finger's moves paint on the paint thread"
patch: 0062-hottyterm-scrolls-and-a-finger-s-moves-paint-on-the-.patch
upstream-fit: no
---

**What it changes:** a scroll (wheel, touchpad, touch drag) and a touch's
move that pans a surface no longer repaint the surface on GTK's main
thread. They mark the host dirty and wake hotty-paint (paint-off-the-lock),
which repaints from the latest position. While a paint is under way, the
latest move and the sum of the scrolls since wait for it rather than the
main thread waiting it out, and whoever has the host next hands them over
first, so a lift never goes ahead of its moves. These paints hold no
renderer: no cells change with them.

**Why we carry it:** GDK compresses pointer motion and smooth scrolls to
one per frame, but not a touch's updates. On a 120 Hz touchscreen each
update cost a 6 ms repaint on the main thread, the event queue never
emptied, and GTK's frame clock, which runs only once it has, showed nothing
for up to a second while a finger dragged hotty-pot's Tasks table
(2026-11-16). On a synthetic 120 Hz drag on a private sway, frames shown
went from 23 to 119 a second, and a scroll reached the screen in 4 ms at
the median instead of 650 ms.

**For upstream:** no. It is about hotty's surfaces. Ghostty's own touch
scroll moves the viewport, which costs no paint on the main thread.
