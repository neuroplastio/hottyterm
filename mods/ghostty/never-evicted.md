---
title: "A placed hotty surface's image is never evicted"
patch: 0051-hottyterm-a-placed-surface-s-image-is-never-evicted.patch
upstream-fit: no
---

**What it changes:** each hotty surface is a kitty image. Past
`image-storage-limit` (320 MB a screen by default), the storage evicted
the oldest images first, and those are the static surfaces: a focus
ring, a dock, a tool at rest. `hotty.zig` then forgot the surface and
told hotty-blitz it was unplaced (SPEC 5.4, patch `unplaced`), but the
program had not asked for that and nothing made it place the surface
again, so it stayed blank until a restart. A placed surface's image is
now kept (`Image.evictable`, patch `image-keep`): a program's other kitty
images are evicted first, and a surface's never. A hidden surface's image
may go: it only saves sending pixels, and showing the surface again draws
it anew. The images still count toward the limit, because nothing else
bounds them: hotty-blitz takes a surface up to 1000 by 1000 cells, and any
number of surfaces, and enforces no `limits.surfaces` (SPEC 13). So past
the limit, with only surfaces left, a new image or surface fails as one
over the limit does. The other ways a surface's image goes without the
program asking (an erase, another program's delete, clearing the screen,
a full reset) still follow SPEC 5.4.

**Why we carry it:** a workspace manager with many surfaces lost them, one
by one, after a while.

**For upstream:** no. Only `hotty.zig`, which upstream doesn't have,
changes.
