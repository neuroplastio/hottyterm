---
title: "The program's menu, kept per screen, and its palette"
patch: 0034-hottyterm-the-program-s-menu-kept-per-screen-and-its.patch
upstream-fit: no
---

**What it changes:** the terminal tells hotty-blitz which screen it is on,
so a program's menu (HOTTY §10.7) is kept per screen: leaving the
alternate screen drops that screen's, hides the level shown and closes the
palette. A new binding action, `toggle_hotty_palette` (Control+Shift+Space,
Cmd+Shift+Space on macOS), opens a palette of the menu's items at the top
of the screen, with a filter line. While it is open it takes every key but
its own binding. A pick goes to the program as the Edit menu sends a
command: `copy` copies the selection, `paste` reads the clipboard first,
and the rest go as commands with no key. Upstream lines: 20 (`Binding.zig`
10, `Config.zig` 7, `Surface.zig` 2, `command.zig` 1).

**Why we carry it:** a program's actions can be found and run without
knowing its keys, and the same tree serves AI agents that drive a TUI.

**For upstream:** no. It is part of HOTTY.
