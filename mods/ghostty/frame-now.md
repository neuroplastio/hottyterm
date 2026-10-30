---
title: "A new frame paints now, not a refresh after the last input"
patch: 0042-gtk-paint-a-new-frame-now-not-a-refresh-after-the-la.patch
upstream-fit: maybe
---

**What it changes:** when the renderer hands GTK a frame, the surface
queues its draw, as before. If GTK's frame clock is holding its next
cycle back, and nothing has painted within the last refresh, the surface
also makes the clock's pending source (`[gtk] gdk_frame_clock_frame`)
ready now. It is 30 lines in `render_surface.zig` and one in
`surface.zig`.

**Why we carry it:** GTK handles each input event in a frame clock cycle
of its own, and that cycle paints nothing. GDK's idle frame clock then
holds the next cycle back until a refresh after it began
(`min_next_frame_time`), so that a clock not synced to vblank doesn't
busy-loop. A frame for input is ready a few ms after it, and waited
11–16 ms more at p50 for GTK to paint it, in stock Ghostty too. Now it
waits 0.1 ms: on gov R-22's rig, a key in a hotty field went from 26 to
16 ms p50 and a hover from 26 to 10 ms, with the same paints a second,
CPU and scrollbar fade as before. GTK's pacing stays as it was:
a painted frame still waits for the compositor's frame callback (the
clock is stopped then, with no source to make ready), its own animations
keep their pace, and the surface never asks for more than one paint a
refresh. GTK's `no-vsync` debug flag removes the same hold, but it also
unpaced everything else: 6,237 paints a second while the overlay
scrollbar faded. So it was dropped.

**For upstream:** maybe. The hold is GTK's, and so is the real fix: a
cycle that only flushed events shouldn't defer the next one. Until GTK
has it, Ghostty has the same frame of latency, and this is a small
workaround. It relies on GTK's name for its source, and does nothing if
that changes.
