---
title: "The command palette has no default key"
patch: 0039-hottyterm-the-command-palette-has-no-default-key.patch
upstream-fit: no
---

**What it changes:** Ctrl+Shift+P, and Cmd+Shift+P on the Mac, no longer
open the command palette: the key reaches the program like any other. The
palette stays in the GTK context menu and the macOS View menu, and a
`keybind` for `toggle_command_palette` gives it a key again. Upstream
lines: one in `hottytermDefaults` in `src/config/Config.zig`, which drops
the tab keys too, and its comment.

**Why we carry it:** in hottyterm the key is the program's, as the
maintainer put it: "ctrl+shift+p should be just passed through into plx".
plx's vscode keymap opens plx's palette with it. With the terminal keeping
the key, someone used to VS Code got the terminal's palette over plx, and
its Split Right split the window outside plx (gov's plx UX audit,
2026-10-26).

**For upstream:** no. Upstream's palette key matches VS Code on purpose;
hottyterm yields it because plx runs inside.
