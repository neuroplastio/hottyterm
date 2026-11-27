---
title: "A hold's end draws only a frame the hold kept back"
patch: 0069-hottyterm-a-hold-s-end-draws-only-a-frame-the-hold-k.patch
upstream-fit: no
---

**What it changes:** while hotty surfaces paint, the renderer holds its
frames, and the end of the hold queued a render every time. The renderer
now notes a frame it skipped for the hold, and the end of the hold queues
a render only then.

**Why we carry it:** every paint of a surface ended in a terminal frame,
even when nothing had waited for one. An animation drew the whole terminal
at the display's rate. With layers (`layers.md`) a surface's paint needs
no terminal frame at all, so this was most of what was left.

**For upstream:** no. The hold is hottyterm's (`hotty_hold`).
