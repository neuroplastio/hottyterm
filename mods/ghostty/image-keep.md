---
title: "An image can be kept through eviction"
patch: 0050-terminal-kitty-an-image-can-be-kept-through-eviction.patch
upstream-fit: maybe
---

**What it changes:** the kitty image storage evicts the oldest images,
unused and transient ones first, when a new image would take it past
`image-storage-limit`. An image now has `evictable` (default true): an
image with it false is passed over, by a new image, an animation frame
or a lowered limit alike, and the others go first. It still counts
toward the limit, so the limit still bounds memory: when only kept
images are left and a new image does not fit, the new image fails as
one over the limit does. A retransmission of the id resets it. 7 lines
outside tests (`graphics_image.zig` 6, `graphics_storage.zig` 1), and a
test of the eviction order and of the failure.

**Why we carry it:** hottyterm draws each hotty surface as a kitty image.
Surfaces that change little are the oldest images, so a program's images
evicted them first, and the surface went blank with nothing to bring it
back (patch `never-evicted`).

**For upstream:** maybe. Nothing in Ghostty sets the flag, so as it is it
only serves an embedder (libghostty) that draws its own interface as
kitty images and cannot afford to lose it. Ghostty would take it once it
had such a use, or as part of libghostty's API, named its way.
