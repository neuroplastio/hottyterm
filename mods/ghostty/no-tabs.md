---
title: "No tabs: windows and full screen are the window manager's"
patch: 0021-hottyterm-no-tabs-and-windows-and-full-screen-are-th.patch
upstream-fit: no
---

**What it changes:** the default keys for tabs (new, close, previous and
next, by number, move, the overview), for quitting, for closing windows and
for full screen are gone. A new tab, from a binding, a menu or
`+new-tab`, opens a new window. On GTK the menus lose their tab items, the
header bar's button is New Window and the tab overview button is hidden. On
macOS windows never group as tabs, whatever the system's tab setting, and
the File menu loses New Tab and Close Tab.

**Why we carry it:** in hottyterm, tabs are plx's, and windows and full
screen are the window manager's (the maintainer, 2026-10-10).

**For upstream:** no. It is a product choice of ours, the opposite of
Ghostty's.
