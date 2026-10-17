---
title: "The macOS menu sees keys as key-remap makes them"
patch: 0023-hottyterm-the-macOS-menu-sees-keys-as-key-remap-make.patch
upstream-fit: maybe
---

**What it changes:** with `key-remap` swapping Command and Control
(`super=ctrl`, `ctrl=super`), AppKit's menu still matched keys as they came
in: the key that reaches macOS as Command hit Copy, Select All, Hide and
Minimize with C, A, H and M, instead of reaching the terminal as Control.
The menu now sees each key as remapped. A key that becomes no Command key
is the terminal's; one that becomes a Command key goes to the menu as that.
`ghostty_surface_key_remap_mods` gives Swift the remapped modifiers. The
same patch drops the Mac's default keys for quit, close and full screen.

**Why we carry it:** hottyterm swaps Command and Control on the Mac, as it
swaps Option and Alt (the maintainer, 2026-10-10).

**For upstream:** maybe. The menu fix is a real bug for anyone who swaps
Command and Control with `key-remap`, but it shares the patch with our
removal of the Mac's default keys, so it would need splitting first.
