---
title: "Acknowledge keys delivered as edit commands"
patch: 0064-hottyterm-acknowledge-keys-delivered-as-edit-command.patch
upstream-fit: no
---

A key the focused surface gives to the program already reaches the
terminal's edit-command lookup. When the terminal sends an edit command
for the key, it tells Blitz that the command replaced its bytes so that
a pending prefix starts. A terminal selection still wins on Copy.
For Paste, the acknowledgement follows the command when the clipboard
read completes or times out.

This implements hotty SPEC §10.6 entirely in `src/termio/hotty.zig`.
