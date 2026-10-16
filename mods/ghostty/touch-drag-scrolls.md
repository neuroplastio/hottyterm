---
title: "A touch drag scrolls (GTK)"
patch: 0014-gtk-a-touch-drag-scrolls.patch
upstream-fit: yes
---

**What it changes:** on a touchscreen, a drag with one finger selected text
instead of scrolling, since GTK emulates a pointer from it. A touch-only
`GestureDrag` in the capture phase now turns each drag update into a
precision scroll of its delta, through `Surface.scrollCallback`, so a touch
drag goes wherever a touchpad's scroll goes: mouse reports, the alternate
screen, the scrollback. A mouse drag still selects. The scrolled window's
kinetic scrolling is off, so the same drag isn't scrolled twice. 68 lines,
in the GTK apprt only.

**Why we carry it:** hottyterm on touchscreen laptops and tablets.

**For upstream:** yes. It is written in upstream's style, it fixes touch
scrolling on Linux for every Ghostty user, and nothing in it is ours.
