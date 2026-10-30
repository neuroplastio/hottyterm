---
title: "A keystroke draws only what it changed"
patch: 0043-core-a-keystroke-draws-only-what-it-changed.patch
upstream-fit: yes
---

**What it changes:** a key that writes to the pty queues a render only
when it cleared a selection or scrolled the viewport to the bottom, and
the IO thread no longer redraws after it drains a write from its mailbox.
Before, every such key drew twice, although the selection is usually
empty, the viewport usually at the bottom, and a write shows nothing
until the program answers. The answer, its echo, queues its own render
when its output is parsed, as before. It is 12 lines in `keyCallback` in
`Surface.zig` and 5 in `termio/Thread.zig`.

**Why we carry it:** the frame a key drew showed nothing new, but it
still went to GTK, which then waited for the compositor's frame callback
before painting again. The echo's frame, ready a millisecond or two
later, waited with it for the refresh after. With GTK's hold removed
(`frame-now.md`), this was what kept a key's echo a refresh late. With
both, on gov R-22's rig, a key's echo in a shell went from 26 to 10 ms
at p50 (36 to 16 at p95), with the same paints a second and CPU. It also
saves a draw per keystroke.

**For upstream:** yes. A render of nothing new is wasted work on every
platform, and it is a small change in upstream's own terms.
