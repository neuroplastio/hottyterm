---
title: "A frame's image quads come from one buffer"
patch: 0067-renderer-draw-a-frame-s-image-quads-from-one-buffer.patch
upstream-fit: yes
---

**What it changes:** each image placement created a GPU buffer for its one
quad on every frame, and released it after the draw. The quads of every
placement are now built once per frame (`State.prepare`) into one buffer
that each frame in flight holds, as it holds its cells. Each placement is
one instanced draw starting at its first quad, using a base instance
(`glDrawArraysInstancedBaseInstance` on OpenGL 4.2+, and Metal's
`drawPrimitives:…:baseInstance:`).

**Why we carry it:** hotty programs such as plx place a few dozen surfaces,
and an animation on one of them redraws the terminal at the display's rate.
On a 144 Hz Mac that was thousands of buffer allocations a second, which
showed in `sample` as `newBufferWithBytes` in the driver.

**For upstream:** yes. The `future(mitchellh)` comment in `drawQuad`
already asks for this. It's generic and in upstream's style, and Ghostty
already requires OpenGL 4.3.
