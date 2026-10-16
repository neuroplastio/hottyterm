---
title: "The pointer reaches the cells through a surface's empty parts"
patch: 0004-hottyterm-the-pointer-passes-through-what-a-surface-.patch
upstream-fit: no
---

**What it changes:** a surface takes the pointer only where CSS hit testing
finds an element there that takes it (`pointer-events: none` is skipped),
looking from the top window down. Anywhere else, presses, motion and
releases are reported to the program as on any cell, and the pointer has
the shape the program set with OSC 22. The capabilities announce it.

**Why we carry it:** HOTTY SPEC §9.3, so that a program can float a surface
over its own text and still be clicked through it.

**For upstream:** no. It only changes how HOTTY surfaces are hit.
