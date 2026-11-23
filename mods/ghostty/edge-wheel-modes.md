---
title: "Tell Blitz which terminal modes receive edge wheels"
patch: 0063-hottyterm-tell-Blitz-which-terminal-modes-receive-ed.patch
upstream-fit: no
---

The stream handler sends Blitz the active screen and whether DECSET 9,
1000, 1002 or 1003 has selected a mouse-reporting mode. It updates Blitz
at host creation, on alternate-screen switches, when mouse tracking
changes and after RIS. The hooks add eight lines in
`src/termio/stream_handler.zig`.

Blitz uses both values to decide whether a gesture stays with the
document at its edge (hotty SPEC §5.3). Main-screen scrollback still
handles edge wheels when mouse tracking is off. This is specific to
the hotty host.
