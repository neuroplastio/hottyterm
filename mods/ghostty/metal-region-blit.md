---
title: "Metal writes a kitty frame edit's rectangles with a blit"
patch: 0024-renderer-Metal-writes-a-kitty-frame-edit-s-rectangle.patch
upstream-fit: yes
---

**What it changes:** region updates of kitty images were OpenGL only,
because Metal's `replaceRegion` writes from the CPU at once while frames in
flight may still be drawing with the texture. Each backend now has
`replaceTextureRegions`. OpenGL writes the rectangles as before. Metal
encodes a blit from a staging buffer per rectangle into a command buffer of
its own, committed before the frame's, so the queue and its hazard tracking
order the write after the earlier frames' reads. 50 lines in `Metal.zig`,
14 in `OpenGL.zig`, 2 in `renderer/image.zig`.

**Why we carry it:** the same surface frames, on macOS.

**For upstream:** yes, together with "A kitty frame edit uploads only the
rectangle it changed".
