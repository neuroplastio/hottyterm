---
title: "Edit commands and programs' menus"
patch: 0030-hottyterm-edit-commands-and-programs-menus-SPEC-10.5.patch
upstream-fit: no
---

**What it changes:** Mod is Command on macOS and Control elsewhere. A key
of an edit command the program took (`a=edit`, per screen, dropped on
leaving the alternate screen and on RIS) reaches it as a `command` event:
a copy with a selection on the cells copies that instead, and a paste
reads the clipboard first. A program's which-key menu (`a=menu`), from the
cells or a surface, shows at the bottom right of the screen, and a key it
doesn't list hides it. Key sequences are the program's (HOTTY 0.3): a key
its keymap binds to `prefix` hands it the keys after it, so hottyterm has
no leader or timeout of its own. Upstream lines: 1 in `Surface.zig`.

**Why we carry it:** HOTTY programs bind keys without knowing the
platform's, and show what their keys do.

**For upstream:** no. It is part of HOTTY.
