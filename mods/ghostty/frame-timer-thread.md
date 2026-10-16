---
title: "Only the IO loop's thread arms the surfaces' frame timer"
patch: 0013-hottyterm-only-the-loop-s-thread-sets-the-frame-time.patch
upstream-fit: no
---

**What it changes:** `hotty.zig` armed the IO loop's timer from whichever
thread called it: the stream's reader, or the app's thread for keys and the
pointer. xev's loops aren't thread-safe: kqueue's timer reset edits the
loop's timer heap on the caller's thread, and every backend takes a new
timer only on the loop's next turn, against its cached clock. Off the
loop's thread it now wakes the loop instead, through the async that
fetches already use, and the loop's tick sets the timer.

**Why we carry it:** the timer drives animations, fading scrollbars and
coalesced resizes, and arming it from another thread was a data race.

**For upstream:** no. The timer is `hotty.zig`'s.
