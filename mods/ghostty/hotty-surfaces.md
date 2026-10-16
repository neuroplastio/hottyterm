---
title: "Programs draw HTML surfaces over the cells (HOTTY)"
patch: 0001-hottyterm-HOTTY-surfaces-over-hotty-blitz.patch
upstream-fit: no
---

**What it changes:** a program can send HOTTY, HTML over the TTY, on OSC
7279: documents that the terminal lays out and draws through hotty-blitz,
Blitz behind a C ABI, and shows as kitty images placed in the cells,
updated by kitty frame edits of the rectangles that changed. The logic is a
new file, `src/termio/hotty.zig`. Upstream files get hooks only: Termio's
settings, a flush per read and the resize; the stream handler's unknown OSC
(#14452) and full reset; the Surface's keys, clicks, hover and font size;
and linking `libhotty_blitz`.

**Why we carry it:** it is hottyterm, a terminal that speaks HOTTY
natively, with no script, no network and no kitty graphics across the pty.

**For upstream:** no. It serves HOTTY, our protocol, and links a Rust
library that Ghostty doesn't build.
