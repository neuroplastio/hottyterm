---
title: "A reply goes to the program once"
patch: 0056-hottyterm-a-reply-goes-to-the-program-once.patch
upstream-fit: no
---

**What it changes:** what the surfaces collect for the program (a click,
a key, a `fit`) sits in one buffer in `hotty.zig`, and two threads sent
it. The app thread's `deliver`, after a click or a key, read and emptied
the buffer without the renderer lock. The IO thread sent and emptied it
under the lock: in `osc`, when the program wrote a HOTTY command, and in
`tick`. When the two met, both sent the same bytes, and a click reached
the program twice, in the same millisecond, with the same `count`. The
IO thread also emptied the buffer after a send that lets go of the lock
when the mailbox is full, so what the app thread collected in that gap
was dropped.

Now every sender takes the buffer's bytes and empties it in one step,
under the lock (`takeReplies`), and sends after.

**Why we carry it:** a toggle clicked once flipped back. It showed under
plx, which writes HOTTY commands to hottyterm all the time (placements,
fits, the program's frames), so the IO thread was often sending right as
a release was delivered: tophot under plx got 5 doubled clicks in 43, and
none in 42 alone on hottyterm. plx's relay was read end to end and
writes each host message once.

**For upstream:** no. The buffer and both senders are `hotty.zig`'s.
