---
title: "Copy takes a surface's selection too"
patch: 0027-hottyterm-Control-c-and-Command-c-copy-a-surface-s-s.patch
upstream-fit: no
---

**What it changes:** `copy_to_clipboard` takes the text selected in a
surface when the terminal has no selection, and a release on a surface
copies it as `copy-on-select` says, into PRIMARY by default. There is one
selection: a press on a surface drops the terminal's, and a press on the
cells drops the surfaces'. Ctrl+c and Super+c, bound as `performable`,
copy only while something is selected, so Ctrl+c still interrupts
otherwise (hotty SPEC §11).

**Why we carry it:** text selected in a hotty document copies as in a
browser.

**For upstream:** no. It adds hotty surfaces to copying.
