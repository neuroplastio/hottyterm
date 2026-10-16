---
title: "The click that focuses a terminal clicks too"
patch: 0012-hottyterm-the-click-that-focuses-a-terminal-clicks-t.patch
upstream-fit: maybe
---

**What it changes:** Ghostty drops the click that gives a terminal focus.
On macOS the view declines first mouse and eats the click that moves split
focus (#2595), and GTK suppresses the press and release on a terminal
without focus. A new setting, `hotty-focus-click`: `pass`, the default,
lets that click through, to a surface, a link, or the program as a mouse
event, as a browser does. `focus` is Ghostty's behaviour. Upstream lines:
11 in `Config.zig`, 2 in `Surface.zig`, 1 in the GTK surface and 21 in the
macOS app.

**Why we carry it:** a click on a button in a HOTTY document in another
split, or another window, presses it.

**For upstream:** maybe. It is generic, but Ghostty drops the click on
purpose (a click that only meant to focus vim would move its cursor), so
it would only be wanted as an option, named as Ghostty names things.
