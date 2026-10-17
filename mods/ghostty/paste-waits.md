---
title: "Keys wait behind a paste, and a screen switch drops its commands"
patch: 0031-hottyterm-keys-wait-behind-a-paste-command-and-a-scr.patch
upstream-fit: no
---

**What it changes:** keys pressed while a paste command waits for the
clipboard wait too, and reach the program after it, in order. A paste
whose clipboard hasn't come in 2 s goes without text. The stream handler
syncs the screen at each switch, so leaving the alternate screen and coming
back within one frame still drops the commands taken there (hotty SPEC
§10.6).

**Why we carry it:** plx found both, as its panes paste and switch screens.

**For upstream:** no. It serves hotty edit commands.
