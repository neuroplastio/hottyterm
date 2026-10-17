---
title: "hotty surfaces keep their images through many resizes"
patch: 0003-hottyterm-surface-image-ids-never-collide.patch
upstream-fit: no
---

**What it changes:** each placement of a surface at a new size takes a new
kitty image id. The ids cycled through 256 values, so a program that
resizes its surfaces often came round to the id of another surface's live
image and replaced it, and surfaces vanished after a few dozen resizes. Ids
now cycle through 65,536 values and skip any that a surface holds or an
image on either screen uses.

**Why we carry it:** hotty programs resize surfaces all the time, as plx's
dialogs do.

**For upstream:** no. Only `hotty.zig`, which upstream doesn't have,
assigns these ids.
