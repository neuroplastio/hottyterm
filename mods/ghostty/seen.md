---
title: "What plays out of view asks for no frames"
patch: 0066-hottyterm-what-plays-out-of-view-asks-for-no-frames.patch
upstream-fit: no
---

**What it changes:** a hotty surface scrolled out of the view, or in a
hidden window (minimised, covered), kept asking for a frame of each CSS
animation on it. hotty-blitz painted every one, and the terminal uploaded
and drew it at the display's rate, for pixels nobody saw. Now the terminal
tells hotty-blitz which surfaces can be seen (`hotty_host_set_seen`):
placed on the screen that shows, on rows of the view, in a visible window.
It looks again when it schedules a frame, when the renderer finds the view
moved (a scroll, or output pushing lines up), and when the window is
hidden or shown. A surface seen again asks for a frame at once, at the
time it then is.

**Why we carry it:** an animated surface left in the scrollback cost more
CPU than one on screen: 42% against 0.4% after this, in the Linux test of
plx's strips scrolled away.

**For upstream:** no. It is about hotty surfaces; Ghostty's own kitty
images don't animate.
