---
title: "hotty surfaces paint off the terminal's lock"
patch: 0045-hottyterm-hotty-surfaces-paint-off-the-terminal-s-lo.patch
upstream-fit: no
---

**What it changes:** hotty-blitz paints a surface with the terminal's lock
let go. A repaint runs on a thread of its own, `hotty-paint`, and the
stream parses on meanwhile. A first frame stays on `io-reader`, in order.
While a paint runs, anything else that calls hotty-blitz waits on a
condition, which lets the lock go, and it has the host before the next
paint; the stream then queues a draw for what it parses after, as 0044
does after a send. The painter's frames and effects are applied once it
has the lock back, which it takes ahead of the stream, as the renderer
does. The IO thread no longer waits for a paint: it writes the keys. The
renderer waits for each paint, as it waited for the lock, so one frame
shows the cells and the surfaces drawn for them. After a synchronized
update it waits until that update's repaint is in, so cells after it
never show beside a surface's pixels from before it (SPEC §6.3). After
100 ms the hold gives up. The hooks are in
- `renderer/State.zig` (the hold) and `renderer/generic.zig` (honours it);
- `termio/stream_handler.zig` (an update's end);
- `termio/Termio.zig` (the thread stops; the inspector is looked up per
  byte, since the lock can go mid-parse).

**Why we carry it:** gov R-22 S1. `io-reader` held the lock for the whole
of each paint, 35–50 ms when plx opens a palette. A key in another window,
and an echo beside a repainting surface, waited that long for the lock.
Nothing here is apprt code, so macOS gets it too. There, every window's
keys and IME point take the same lock on the one main thread.

**For upstream:** no. Ghostty has no hotty surfaces, and the hold only
exists for them.
