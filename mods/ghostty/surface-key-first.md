---
title: "A surface is offered a key before the shortcuts"
patch: 0021-hottyterm-a-surface-is-offered-a-key-as-pressed-firs.patch
upstream-fit: no
---

**What it changes:** Ghostty's shortcuts ran before a surface had a key:
Shift+Home and Shift+End scrolled the terminal, Ctrl+Shift+arrows switched
tabs, and on macOS Cmd+Left became the 0x01 its binding writes. Now the
surface holding the keyboard is offered a key that types no text first,
named from the key event as `super` and the like (`hotty_host_key_pressed`). A
key it doesn't use goes on to the shortcuts, and is then offered as bytes.
hottyterm keeps the keys of a key sequence or a key table, and keys bound
to opening, closing or picking windows and splits, quitting and the
config. On macOS such a key's binding isn't `consumed`, so the menu
doesn't take it first (HOTTY SPEC §10.4).

**Why we carry it:** text fields and key bindings inside HOTTY documents.

**For upstream:** no. It routes keys to HOTTY surfaces.
