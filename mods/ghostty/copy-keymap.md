---
title: "Copying from a surface follows its keymap"
patch: 0029-hottyterm-copying-follows-the-keymap-SPEC-10.2-11.patch
upstream-fit: no
---

**What it changes:** a selection in a surface's document is offered every
key first (`hotty_host_copy_key`), before the surface holding the keyboard
and the shortcuts. Its keymap copies with Ctrl+c and Cmd+c by default, and
a program that binds one of them hears it while text is selected. A text
field copies its selection by its own keymap. Ctrl+c and Super+c, which
hottyterm binds to copying the cells, then copy nothing from a surface;
Ctrl+Shift+c and the menu copy a surface's selection whatever the keymaps
say (HOTTY SPEC §10.2, §11).

**Why we carry it:** the program decides what its copy keys do.

**For upstream:** no. It serves HOTTY keymaps.
