---
title: "Key sequences, edit commands and which-key menus"
patch: 0030-hottyterm-key-sequences-edit-commands-and-menus-SPEC.patch
upstream-fit: no
---

**What it changes:** Mod is Command on macOS and Control elsewhere, and two
new settings, `hotty-leader` and `hotty-key-timeout`, set the leader and
the timeout of key sequences. A key of an edit command the program took
(`a=edit`, per screen, dropped on leaving the alternate screen and on RIS)
reaches it as a `command` event: a copy with a selection on the cells
copies that instead, and a paste reads the clipboard first. The which-key
menu, of a sequence that waits or the program's own, shows at the bottom
right of the screen (HOTTY SPEC §10.4 to §10.6). Upstream lines: 13 in
`Config.zig`, 1 in `Surface.zig`.

**Why we carry it:** HOTTY programs bind keys without knowing the
platform's.

**For upstream:** no. It is part of HOTTY.
