---
title: "A secondary press that opens the menu does not hold the pointer"
patch: 0060-hottyterm-a-secondary-press-that-opens-the-menu-does.patch
upstream-fit: no
---

**What it changes:** a secondary press that Ghostty leaves unconsumed, so
that the apprt opens its context menu, ends the press there: Ghostty's state
of the button is released, and the program no longer holds the pointer for
it. The logic and its test are in `hotty.zig` (`menuPress`); the hook is two
lines in `Surface.mouseButtonCallback`, one at each place it returns false
for the menu.

**Why we carry it:** a press nothing takes on a surface is the cells', and
the program holds the pointer for it until the last button is released
(SPEC §9.1). The menu takes that release (GTK's popover grabs the pointer,
AppKit's menu tracks it), so the hold never ended. Every later click, hover
and wheel over a surface was taken for the program's; a program that does not
report the mouse heard none of it, and the surface was dead until the next
secondary release. It looked like a deadlock, but no thread waited on a lock.
A right-click on cells with no surface behaves as before, and a left
gesture still down keeps its hold.

**For upstream:** no. The hold only exists for hotty surfaces.
