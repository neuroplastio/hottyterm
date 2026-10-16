---
title: "A resize no longer races a full-screen app's redraw"
patch: 0019-termio-set-the-pty-size-after-the-grid-s-under-the-r.patch
upstream-fit: yes
---

**What it changes:** `Termio.resize` set the pty's size (`TIOCSWINSZ`, so
the child gets `SIGWINCH`) before it took the renderer lock and resized the
terminal. The read thread parses the child's output under that lock, so
under load the frame a full-screen app drew for the new size could be
parsed onto the old grid. The resize then moved it: a shorter screen trims
rows from the top, and a wider frame wraps and scrolls. Images anchored to
those rows moved with them. Now the terminal is resized first, and the pty
size set while the lock is still held. The in-band size report (mode 2048)
still follows. 11 lines in `Termio.zig`.

**Why we carry it:** plx's decorations showed from two sizes at once after
a window resize under load.

**For upstream:** yes. It is a small fix to a race that any full-screen
program can hit.
