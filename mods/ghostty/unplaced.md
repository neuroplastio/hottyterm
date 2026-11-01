---
title: "The host hears of a placement the terminal removed"
patch: 0049-hottyterm-the-host-hears-of-a-placement-the-terminal.patch
upstream-fit: no
---

**What it changes:** a hotty placement can go without the program
removing it (SPEC 5.4): the line it was placed on leaves the scrollback,
or an erase or an eviction takes its image. `hotty.zig` now tells
hotty-blitz (`hotty_host_unplaced`), which does what `a=hide` does but
remove the placement, already gone. The keyboard goes back to the
terminal, and the program hears `blur`; a drag ends; and the surface is
no backdrop (patch 0047) until a placement makes it one. A line leaving
the scrollback takes the kitty placement and keeps the image, which
`hotty.zig` didn't notice until the image went too. It now checks the
placement and hides the surface as `a=hide` would, keeping the image,
so placing it again sends no pixels. Leaving the alternate screen
deletes the surfaces placed there with `a=del`, as before. It needs a
hotty-blitz with `hotty_host_unplaced` (0.6.0).

**Why we carry it:** hotty 0.6 makes `b=1` the placement's, not the
surface's. Before, a backdrop whose line had left the scrollback stayed
a backdrop to the host, and a surface that had the keyboard kept it
while it was no longer on the screen, so keys went to a surface nobody
saw.

**For upstream:** no. Only `hotty.zig`, which upstream doesn't have,
changes.
