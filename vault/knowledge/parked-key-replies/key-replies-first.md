---
title: "A key's replies reach the program before its echo is painted"
patch: 0047-hottyterm-a-key-s-replies-reach-the-program-before-i.patch
upstream-fit: no
---

**What it changes:** a key for the surface holding the keyboard goes to
hotty-blitz, which paints its echo there and then, under the terminal's
lock. The key's replies, the keys the surface didn't use and the events
it heard, went to the pty only after that paint, in `deliver`.
`keyPressed` and `keyBytes` now hand them to the IO thread's mailbox, and
wake it, before they paint. Their order is kept, and what the paint finds
for the program (`fit`, `caret`) follows in `deliver`, as before. It is
18 lines in `termio/hotty.zig`.

**Why we carry it:** gov R-22. A program that answers a key, as plx's
palette filters its list as you type, began only once the echo was
painted. On the rig, at 1.6, a key in the palette reaches plx in 0.9 ms
at p50 instead of 1.4, and plx's answer comes back 0.5 to 0.8 ms sooner.
What reaches the screen, the echo and plx's answer, is level: the answer
still shows a refresh after the echo.

**For upstream:** no. Ghostty has no hotty surfaces.
