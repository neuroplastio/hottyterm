---
title: "A long press over a surface is hotty's secondary press"
patch: 0054-hottyterm-a-long-press-over-a-surface-is-hotty-s-sec.patch
upstream-fit: no
---

**What it changes:** `TouchPhase` gains hotty-blitz's phase 4. Ghostty has
no long-press gesture, so the GTK surface gets a `GtkGestureLongPress`,
touch only and in the capture phase like the touch drag. When GTK takes a
touch that began over a surface for a long press, `hotty.zig` passes phase
4 at the finger's position to `hotty_host_touch`. Over an element with
`secondary` in its `data-on` that is a secondary press: the touch stays the
surface's to its end, and the terminal opens no menu of its own. A touch
over the cells, or one that is the terminal's, is unchanged. The
modifiers are the keyboard's last, as GTK's timeout carries no event.
The apprt adds a gesture in the surface template and one callback calling
into `hotty.zig` (15 lines); macOS has no equivalent yet.

**Why we carry it:** a hotty program's context menu needs a gesture on a
touchscreen (hotty SPEC §9.1, HOST.md §3).

**For upstream:** no. It serves hotty surfaces.
