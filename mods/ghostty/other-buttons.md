---
title: "Route mouse buttons and context gestures through Blitz"
patch: 0065-hottyterm-route-mouse-buttons-and-context-gestures-t.patch
upstream-fit: no
---

The terminal offers Blitz primary and auxiliary presses, their
releases and captured moves. Buttons taken for a surface stay out of
Ghostty's mouse-reporting state. GTK's capture-phase controller
preserves chords alongside GestureClick and processes releases even
when the GTK gesture has stopped. A middle click on a field can read
either configured clipboard, and a focused element can take the menu key
or Shift+F10 through its context-menu listener.

AppKit offers Control-click before building its menu. Shift keeps
the terminal menu and Option over a surface passes the press to the
terminal program. The button map reverses AppKit's conversion to
Ghostty's button enum for hotty events. Ghostty still encodes AppKit
`buttonNumber` 7 as `.four`, which becomes SGR 64 (wheel) if it reaches
terminal mouse reporting.

This implements hotty SPEC §9. The platform hooks adapt input to
`src/termio/hotty.zig`.
