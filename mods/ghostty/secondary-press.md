---
title: "A secondary press on an element that takes it is the surface's"
patch: 0053-hottyterm-a-secondary-press-on-an-element-that-takes.patch
upstream-fit: no
---

**What it changes:** a press of the secondary button over a hotty surface
is asked of hotty-blitz (`hotty_host_secondary`), with the point in device
pixels from the surface's top left and the modifiers as the pointer hook
passes them. If an element there has `secondary` in its `data-on` the
surface takes the press: the program gets no mouse report, Ghostty does no
`right-click-action` (no word selection, menu or paste), its own state of
the button stays released, and the release that follows is consumed too.
Otherwise nothing changes: Shift gives Ghostty's menu, Alt with mouse
reporting on gives the program's report (button 2 plus Alt's 8), and the
press is `right-click-action`'s. Plain moves still hover. The logic is in
`hotty.zig`, in the hook the left button already has; it adds no line to an
upstream file.

**Why we carry it:** a hotty program can open its own context menu on a
secondary press (hotty SPEC §9, HOST.md §3). macOS's Control-click is not
covered: AppKit makes it a menu before the core sees a press.

**For upstream:** no. It serves hotty surfaces.
