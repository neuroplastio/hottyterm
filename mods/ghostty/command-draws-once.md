---
title: "A HOTTY command draws once, with the output it came in"
patch: 0044-hottyterm-a-HOTTY-command-draws-once-with-the-output.patch
upstream-fit: no
---

**What it changes:** `hotty.zig`'s OSC handler queued a render after
every HOTTY command. Termio had already queued one when the output
arrived, under the lock the parse holds, so the renderer draws once the
parse is done, with everything the commands changed and what `flush`
rendered at the end of the batch. Now a command queues a render only
after it sends a reply: that send can let go of the lock when the
mailbox is full, and a draw may run before the rest of the parse.

**Why we carry it:** the second wakeup drew the same frame again, and
GTK gave the copy a refresh of its own. A hotty dashboard at 10 frames a
second painted 20, and a key typed meanwhile waited behind the copy. On
gov R-22's rig it now paints 10, and a key in a hotty field went from 20
to 16 ms at p50 (31 to 26 at p95).

**For upstream:** no. The handler is `hotty.zig`'s.
