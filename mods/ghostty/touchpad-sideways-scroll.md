---
title: "A touchpad's sideways scroll reaches the terminal"
patch: 0060-hottyterm-a-touchpad-s-sideways-scroll-reaches-the-t.patch
upstream-fit: no
---

**What it changes:** on GTK, a touchpad's sideways swipe no longer switches
tabs. It goes to `Surface.scrollCallback` as a precise scroll, scaled as
the vertical one is, so a hotty surface that scrolls sideways (SPEC §5.3),
a wide table say, scrolls under two fingers. A notched wheel's sideways
click is unchanged. `gtk-horizontal-tab-scroll` does nothing any more.

**Why we carry it:** hottyterm has no tabs (no-tabs), so Ghostty's
horizontal tab scroll, on by default, swallowed the swipe and did nothing
with it. The maintainer hit it on hotty-pot's Tasks table (2026-11-16).

**For upstream:** no. It drops a feature Ghostty has because hottyterm
drops tabs. Upstream's sideways swipe without tabs to switch would want the
same forwarding, and its precision flag, but that is a small change of its
own.
