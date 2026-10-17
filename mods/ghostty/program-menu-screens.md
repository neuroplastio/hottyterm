---
title: "The program's menu, kept per screen"
patch: 0033-hottyterm-the-program-s-menu-kept-per-screen-SPEC-10.patch
upstream-fit: no
---

**What it changes:** the terminal tells hotty-blitz which screen it is on,
when the host starts and at each switch, so a program's menu (hotty §10.7)
is kept per screen: leaving the alternate screen drops that screen's menu
and hides the level shown. No upstream file changes; the change is in
`src/termio/hotty.zig`.

**Why we carry it:** a full-screen program's actions go with it when it
leaves the alternate screen, and the shell's come back, as its edit
commands do (hotty §10.6).

**For upstream:** no. It is part of hotty.
