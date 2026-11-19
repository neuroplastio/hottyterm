---
title: "Stage stamps for the latency rig (HOTTY_TRACE)"
patch: 0041-hottyterm-stage-stamps-for-the-latency-rig-HOTTY_TRA.patch
upstream-fit: maybe
---

**What it changes:** with `HOTTY_TRACE=<dir>` set, the terminal writes
`hottyterm-<pid>.jsonl` in the trace format hotty/1 (hottyterm's
`docs/trace.md`): one JSON line per stage, on the monotonic clock every
process of neuroplastio's rig shares. It stamps:
- the app's key and pointer events;
- the pty's reads and writes;
- each batch parsed on `io-reader`, and each hotty command in it;
- hotty-blitz rendering the surfaces;
- every wait for the terminal's lock;
- the renderer's draw and upload, and its redraw reaching GTK;
- GTK's frame clock and presentation, and macOS's display link and layer.

A stamp makes no write and takes no lock: it puts its line into a
lock-free ring of about 8 MB. The `hotty-trace` thread writes the ring out
every 50 ms, at exit and on SIGTERM, so a disk that stalls holds up that
thread alone, never one that holds the terminal's lock. Exit and SIGTERM
wait for it 1 s at most, and a second SIGTERM not at all. A full ring
drops lines and says how many (`trace.dropped`). Without the variable, a stamp is one atomic load and a
branch, with no thread. The code is in `hotty.zig`. Upstream files get
hooks: the input callbacks' lock sites in `Surface.zig` go through one
function (19 lines), and a few lines each in `termio/Exec.zig`,
`renderer/generic.zig`, `renderer/metal/IOSurfaceLayer.zig`,
`apprt/gtk/class/surface.zig` and `apprt/gtk/class/render_surface.zig`.

**Why we carry it:** gov R-22 times a key, a click or a hover to the
screen, process by process. The terminal's own stages are what a screen
copy can't separate: the pty, the parse, the paint, the lock, the
renderer or GTK's frame clock. The release build is the stamped build.

**For upstream:** maybe. Ghostty has no per-event latency trace. Its input
latency work could use the pty, parse, lock and frame-clock stamps, but in
its own format and logging, not in hotty's file.
