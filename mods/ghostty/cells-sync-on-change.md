---
title: "A frame whose cells did not change does not copy them again"
patch: 0068-renderer-a-frame-whose-cells-did-not-change-does-not.patch
upstream-fit: yes
---

**What it changes:** every draw copied all the background and text cells
into the frame's GPU buffers, though the cells change only when
`rebuildCells` runs. The renderer now counts its rebuilds. Each frame state
remembers the count its buffers hold, along with its text cell count, and
copies the cells only when the counts differ.

**Why we carry it:** a frame drawn for something else, such as a changed
image or an animation, copied every cell all the same, at the display's
full rate. On a large window that's hundreds of kilobytes per frame.

**For upstream:** yes. Kitty animations and custom shaders draw frames
whose cells did not change too. It's generic, a few lines, and in
upstream's style.
