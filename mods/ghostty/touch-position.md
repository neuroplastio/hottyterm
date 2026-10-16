---
title: "A touch taps and scrolls where the finger is (GTK)"
patch: 0016-gtk-a-touch-taps-and-scrolls-where-the-finger-touche.patch
upstream-fit: yes
---

**What it changes:** GTK moves no pointer for a touch, so the cursor stayed
where the mouse last was: a touch drag scrolled whatever was under the
mouse, and a tap clicked there. The touch's start point is now the cursor's
position when it begins and while it scrolls, so `mouseButtonCallback` and
`scrollCallback` see where the finger is. It builds on "A touch drag
scrolls".

**Why we carry it:** the same touchscreens.

**For upstream:** yes, together with "A touch drag scrolls". It is generic
and in upstream's style.
