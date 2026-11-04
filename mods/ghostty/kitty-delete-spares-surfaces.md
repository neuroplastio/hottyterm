---
title: "A program's kitty commands leave hotty surfaces alone"
patch: 0052-hottyterm-a-program-s-kitty-delete-leaves-surfaces-a.patch
upstream-fit: no
---

**What it changes:** every hotty surface is a kitty image in the screen's
image storage, with an id in hotty's range. A kitty delete a program sent
took those too: `a=d` (every visible placement), and a delete by id, range,
cell, column, row or z that matched one. The kitty graphics command from
the stream now goes through `hotty.zig` (a one-line hook in
`stream_handler.zig`). A delete runs with the active screen's surface
images and placements set aside and puts them back unchanged, so a
program's own images go exactly as before. A transmit or placement that
names a surface's image id, or places relative to one, is refused with
`EINVAL`. The terminal's own erases, Cmd+K, scrollback pruning and RIS
are unchanged.

**Why we carry it:** plx relays its panes' kitty images and sends `a=d`
before placing them again. Each time, every surface lost its placement,
was unplaced (patch 0049) and placed again by plx, so the whole hotty UI
flashed away and back whenever a pane showed a picture. SPEC 5.4 lists
what removes a placement, and a program's kitty command is not among
them: that surfaces are kitty images is hottyterm's own detail.

**For upstream:** no. It guards `hotty.zig`'s images, which upstream
doesn't have.
