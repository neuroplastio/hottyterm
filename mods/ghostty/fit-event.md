---
title: "A program hears how many rows its surface's document needs"
patch: 0006-hottyterm-fit-reaches-the-program.patch
upstream-fit: no
---

**What it changes:** a placement with `f=1` is sent `fit`, the rows its
document needs, whenever that changes (hotty SPEC §5.2). hotty-blitz finds
it while rendering. Every path that renders on the IO thread (a flush, a
resize, the animation timer) now sends the replies a render found, as the
OSC handler does.

**Why we carry it:** a program sizes its surface to what it shows, as plx's
dialogs and margin's prose do.

**For upstream:** no. It is part of hotty.
