---
title: "Motion paces to the display's refresh rate"
patch: 0062-hottyterm-motion-paces-to-the-display-s-refresh-rate.patch
upstream-fit: no
---

**What it changes:** hottyterm passes hotty-blitz the refresh rate of the
display its window is on, through `hotty_host_set_refresh_rate`, so that
CSS animations and transitions mid-flight, and scrollbars fading, ask for
frames at that rate rather than at 60 Hz. On GTK it watches the widget's
GdkSurface from realize to unrealize (a tab moved to another window gets a
new one), the monitors that surface enters and leaves (the last entered is
the one it is on), and that monitor's `refresh-rate` for a mode change. On
macOS it sends the screen's rate, 1 over its `minimumRefreshInterval` (or
its `maximumFramesPerSecond`), as the window changes screens, as its
backing properties change, and as the screen parameters change. The rate
is kept before hotty-blitz's lazy host exists, so the host starts with it;
0, a rate the platform cannot tell, is hotty-blitz's 60 Hz. Twenty-one
lines added to upstream files: two GTK lifecycle calls, a namespaced
embedded C bridge and its header declaration, and AppKit hooks.
The logic stays in `src/termio/hotty.zig`.

**Why we carry it:** a browser renders motion at the display's rate. At a
fixed 60 Hz, motion on a 120 or 144 Hz display ran at half its rate or
less, and a slower display was asked for frames it could not show.
`scripts/refresh-rate-check.sh` checks it on a headless sway, with a
program animating a surface: the rate the host is handed and the renders a
second it draws, on the first output, moved to a second with another rate,
that output's mode changed, and moved back, then a close with no GLib
criticals. The macOS hooks are built only in CI.

**For upstream:** no. It carries the display's rate into hotty-blitz;
Ghostty's own renderer already follows the display through its own vsync.
