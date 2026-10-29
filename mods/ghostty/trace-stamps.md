---
title: "Stage stamps for the latency rig (HOTTY_TRACE)"
patch: 0041-hottyterm-stage-stamps-for-the-latency-rig-HOTTY_TRA.patch
upstream-fit: maybe
---

**What it changes:** with `HOTTY_TRACE=<dir>` set, the terminal writes
`hottyterm-<pid>.jsonl` in the trace format hotty/1 (hottyterm's
`docs/trace.md`). It writes one JSON line per stage, on the monotonic clock
that every process of neuroplastio's rig shares. The stages are:
- the key or pointer event from the app;
- the pty's reads and completed writes;
- each batch parsed on `io-reader`, and each hotty command in it;
- hotty-blitz rendering the surfaces;
- every wait for the terminal's lock on the input path and in the
  renderer's frame, which `io-reader` holds while it parses and paints;
- the renderer's draw and texture upload, and its redraw reaching GTK;
- each phase of GTK's frame clock, the frame taken, and its presentation.

Without the variable, a stamp is one atomic load and a branch. The writer
lives in `hotty.zig`. Upstream files get hooks: the input callbacks' lock
sites in `Surface.zig` go through one function (19 lines), a few lines in
`termio/Exec.zig`, `renderer/generic.zig` and `apprt/gtk/class/surface.zig`,
and the frame clock's in `apprt/gtk/class/render_surface.zig`.

**Why we carry it:** gov R-22 times what a key, a click or a hover takes to
reach the screen, process by process. The terminal's own stages are the
part a screen copy can't separate: was it the pty, the parse, the paint,
the lock, the renderer or GTK's frame clock? Running stamped with the
variable unset is the release build itself, so the stamps never need a
build of their own.

**For upstream:** maybe. Ghostty has no per-event latency trace. The pty,
parse, lock and frame-clock stamps would serve its own work on input
latency, but it would want them in its own format and logging, not in
hotty's file.
