---
title: "A keystroke draws only what it changed"
patch: 0043-core-a-keystroke-draws-only-what-it-changed.patch
upstream-fit: yes
---

**What it changes:** a key that writes to the pty queues a render only
when it cleared a selection or scrolled the viewport to the bottom. Before,
every such key did, although the selection is usually empty and the
viewport usually at the bottom. The program's answer, its echo, queues its
own render when its output is parsed, as before. It is 12 lines in
`keyCallback` in `Surface.zig`.

**Why we carry it:** the frame a key drew showed nothing new, but it still
went to GTK. With GTK's hold removed (`frame-now.md`), GTK painted it at
once and then waited for the compositor's frame callback, so the echo's
frame, ready a millisecond later, waited for the next refresh. The two
together take a key's echo to the screen a refresh sooner; neither alone
does it. It also saves a draw per keystroke.

**For upstream:** yes. A render of nothing new is wasted work on every
platform, and it is a small change in upstream's own terms.
