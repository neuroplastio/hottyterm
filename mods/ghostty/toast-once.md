---
title: "The same toast is not queued again while it is up (GTK)"
patch: 0032-gtk-the-same-toast-is-not-queued-again-while-it-is-u.patch
upstream-fit: yes
---

**What it changes:** each clipboard write toasted "Copied to clipboard",
and libadwaita's toast overlay shows toasts one at a time, so a program
that wrote the clipboard many times in a row queued a toast per write.
They kept coming, three seconds each, long after the writes stopped.
`Window.addToast` now skips a toast whose title is the one it queued
less than its timeout ago. A different toast still queues, and the same
one shows again once the last has timed out. 20 lines, in the GTK apprt
only.

**Why we carry it:** programs that copy on every selection change, over
OSC 52, filled the window with toasts.

**For upstream:** yes. It is written in upstream's style, any GTK user of
a program that copies often sees the same flood, and nothing in it is
ours.
