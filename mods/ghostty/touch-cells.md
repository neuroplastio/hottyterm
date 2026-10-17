---
title: "A finger drags in the program's cells"
patch: 0037-hottyterm-a-finger-drags-in-the-cells-SPEC-9.6.patch
upstream-fit: no
---

**What it changes:** a program that names areas of its cells with
`a=touch` (hotty §9.6) gets a finger's drag there as the mouse's. A touch
that begins on the cells goes to hotty-blitz (`hotty_host_cells_touch`),
told whether the program reports the mouse and whether the viewport shows
the screen. In an area, its moves wait until it goes past the slop: a pan
scrolls as before, and a drag the area's way, or a tap, becomes the
primary button, reported by Ghostty's own `mouseReport` in the program's
mode and encoding: pressed where the touch began, moved with the finger,
released where it lifts, or on the last cell at a second finger. Nothing
is selected, and Shift is left out unless `mouse-shift-capture` gives
Shift presses to the program. A touch elsewhere is the terminal's, as
before. Two upstream functions, `mouseReport` and `mouseShiftCapture`,
become public; the logic is in `hotty.zig`.

**Why we carry it:** a full-screen program's slider, divider or scrollbar
drawn in the cells moves under a finger on a touchscreen, where a drag
would otherwise only scroll.

**For upstream:** no. It serves hotty's `a=touch`; a terminal without it
keeps touch drags as scrolls.
