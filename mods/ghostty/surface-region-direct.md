---
title: "A surface's changed rectangles go straight into its image"
patch: 0023-hottyterm-a-frame-s-rectangles-go-straight-into-the-.patch
upstream-fit: no
---

**What it changes:** `hotty.zig` sent each rectangle of a surface that
changed through a kitty `a=f` command: converted to straight alpha in a new
buffer, copied into a loading image, then composed into the image, with two
more copies and allocations a rectangle. It is now converted from the frame
into the image's pixels in place, and the region is logged for the
renderer as a frame edit logs it. An image that can't take that (animated,
not RGBA) is replaced whole. The conversion copies a row at once and fixes
only translucent pixels, eight at a time. On a 10 Hz dashboard, delivering
a frame fell from about 4.8M instructions to 1.9M. Only `hotty.zig`
changes.

**Why we carry it:** delivering surface frames is hottyterm's busiest path.

**For upstream:** no. It is `hotty.zig`'s own path.
