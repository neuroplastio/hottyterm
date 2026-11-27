---
title: "macOS composites hotty layers as Core Animation layers"
patch: 0072-macos-hotty-layers-are-Core-Animation-layers-over-th.patch
upstream-fit: no
---

**What it changes:** each hotty layer is a `CALayer` clipped to its
placement, whose contents is an sRGB IOSurface the window server
composites with the terminal's (`src/renderer/metal/HottyLayers.zig`). A
change writes only the rectangles that changed into an IOSurface the
window server isn't reading (`IOSurfaceIsInUse`), brought up to date from
the newest first, and draws no terminal frame. Where the layers show goes
with the terminal frame's IOSurface: the main thread lays them out as it
shows that IOSurface, in the same transaction.

**Why we carry it:** on the probe runner's virtual M1, the idle probe's
plx page went from 13.1% CPU to 6.8%, and a single pulsing dot from 8.6%
to 4.0%. Screenshots match the old path pixel for pixel.

**For upstream:** no, it composites hotty's layers (`layers.md`).
