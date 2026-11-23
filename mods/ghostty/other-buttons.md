---
title: "Route mouse buttons and context gestures through Blitz"
patch: 0065-hottyterm-route-mouse-buttons-and-context-gestures-t.patch
upstream-fit: no
---

The terminal offers Blitz primary and auxiliary presses, their
releases and captured moves. Buttons taken for a surface stay out of
Ghostty's mouse-reporting state. GTK's capture-phase controller
preserves chords alongside GestureClick and processes releases even
when the GTK gesture has stopped. A second physical button with the
same DOM number stays local, so the initiating button ends its drag.
An Alt press over the cells returns the keyboard to the terminal. A middle click on a field can read
either configured clipboard, and a focused element can take the menu key
or Shift+F10 through its context-menu listener.

AppKit offers Control-click before building its menu. An existing
chord keeps its owner. Shift opens the terminal menu for a new gesture.
Option over a surface tracks the physical left button in Ghostty.
The terminal reports right-button press, motion, and release for that
gesture with Control removed. The button map reverses AppKit's
conversion to Ghostty's button enum for hotty events. Ghostty still encodes AppKit
`buttonNumber` 7 as `.four`, which becomes SGR 64 (wheel) if it reaches
terminal mouse reporting.

This implements hotty SPEC §9. The platform hooks adapt input to
`src/termio/hotty.zig`.
