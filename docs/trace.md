# Trace format hotty/1

The stage stamps of neuroplastio's latency rig (gov R-22). Every process an
input passes through writes them: hottyterm, hotty-blitz, plx's viewer,
plxd, plx-script, the rig's programs and the rig itself. They all use one
clock, so the files merge into one timeline without IDs passed between
processes. `scripts/feel/merge.py` merges them and writes a Chrome
trace-event file that opens in Perfetto. The rig is described in
[feel.md](feel.md).

## Turning it on

- **`HOTTY_TRACE=<dir>`** turns stamps on in every process that inherits it.
  Unset or empty means off. The rig creates the directory.
- **When off, a stamp costs one branch** on a value read once: no clock
  read, no allocation, no file.
- The name is not a `PLX_*` one, because the rig unsets every `PLX_*` it
  inherits.

## Files

- Each process writes `<dir>/<proc>-<pid>.jsonl`. `<proc>` is in
  `[a-z0-9-]`: `hottyterm`, `blitz`, `plx` (the viewer), `plxd`,
  `plx-script`, `prog`, `rig`.
- A library inside another process can write a file of its own under the
  same pid: hotty-blitz inside hottyterm writes `blitz-<pid>.jsonl`. The
  merge groups files by pid.
- The first line is a header:

  ```json
  {"trace":"hotty/1","proc":"blitz","pid":4242,"clock":"monotonic"}
  ```

  `clock` is `monotonic` (Linux `CLOCK_MONOTONIC`) or `uptime-raw` (macOS
  `CLOCK_UPTIME_RAW`, which is `mach_absolute_time` in ns). The merge
  refuses a mix.

## Lines

Each line after the header is one event, a JSON object:

| field | | |
| --- | --- | --- |
| `t` | int, required | ns on the clock: a span's start, or the instant |
| `n` | str, required | `<component>.<stage>`, in `[a-z0-9_.-]` |
| `dur` | int | ns: the line is a span. Without it, an instant |
| `tr` | int or str | the track: an OS thread id, or a role such as `input` or `pty.p-3`. Spans on one track nest |
| `a` | object | flat arguments: numbers, strings, bools |
| `c` | object | flat numbers: the line is a counter sample (a heap size, a histogram's delta) |

- **A span is one line,** written at its end, with its start and its
  duration. There are no begin and end pairs.
- **Lines needn't be sorted;** the merge sorts.
- **Writing:** buffer whole lines and write them out at the end of each
  unit of work (a command handled, a frame drawn), or at least every
  100 ms. Also flush at exit and on SIGTERM. The rig stops a run with
  SIGTERM after it has been quiet for 300 ms or more, and sends SIGKILL
  2 s later.

## Names

| component | process |
| --- | --- |
| `rig.*` | the rig: `rig.input` when it injects input N (`a`: `i`, `sc`, `kind`), `rig.pixels` at the presented time of the first frame that shows the change, `rig.mark` when it sends a step a scenario marked (`a`: `mark`, `sc`, `kind`), timed or not, such as the `:` E7W and E7T don't wait on |
| `term.*` | hottyterm |
| `blitz.*` | hotty-blitz |
| `prog.*` | the rig's programs: `prog.read` when input arrives, `prog.write` when the answer is written |
| `viewer.*`, `plxd.*`, `lua.*`, `go.*` | plx's viewer, plxd, plx-script's Lua, and the Go runtime in each |

### hottyterm

| name | | when |
| --- | --- | --- |
| `term.key`, `term.key.up` | instant | the app hands the terminal a key press or release (GTK's main thread) |
| `term.pointer`, `term.button`, `term.wheel` | instant | the same for a pointer move, a button and a scroll |
| `term.pty.write` | instant | a write to the pty completed (`a.n` bytes), on the IO thread |
| `term.pty.read` | instant | a read from the pty (`a.n` bytes), on `io-gather` |
| `term.parse` | span | a batch of output parsed on `io-reader` (`a.n`), with every hotty command in it |
| `term.osc` | span | one hotty command handed to hotty-blitz and applied (`a.n`) |
| `term.lock` | span | a thread waits 20 µs or more for the terminal's lock (`a.fn`: where): GTK's main thread on the input path (a key, the pointer, the IME's point), or the renderer at the start of a frame (`updateFrame`). `io-reader` holds the lock while it parses and paints output |
| `term.render` | span | hotty-blitz renders the dirty surfaces into their images: on `io-reader` after output, on GTK's main thread after input the host handles (hover, a field, the wheel) |
| `term.draw` | span | the renderer thread draws a frame and exports it |
| `term.upload` | span | inside `term.draw`: the images' textures updated |
| `term.redraw` | instant | the renderer's redraw reaches GTK's main thread, which queues a draw |
| `term.fc` | instant | a phase of GTK's frame clock (`a.p`: `flush_events`, `before_paint`, `update`, `layout`, `paint`, `resume_events`; `a.frame`: its counter). A cycle with no `paint` only handled events |
| `term.snapshot`, `term.snapshot.cpu` | instant | GTK's main thread takes the frame (a DMABUF, or a CPU copy when DMABUFs fail) |
| `term.frame` | instant | after a painted cycle (`a.frame`; `a.frame_t`, the frame clock's time for it; `a.predicted`, its predicted presentation), on GTK's clock converted to the trace's |
| `term.presented` | instant | stamped at the time the compositor reports a frame presented (`a.frame`), once its timings complete |
| `term.vsync` | instant | macOS: the display link's tick, on CoreVideo's thread. While the link runs, the renderer draws only on a tick |
| `term.present` | instant | macOS: the GPU finished a frame, and its IOSurface goes to the main thread |
| `term.contents` | instant | macOS: the main thread sets the layer's `contents` to it (`a.sync`: a draw on the main thread itself, during a resize; `a.discard`: the frame was the wrong size and is dropped) |

The frame's presentation is the rig's `rig.pixels` on Linux. On macOS, where
the rig has no screen copies (scripts/probe-macos.sh, `latency`), the last
the terminal sees of a frame is `term.contents`: Core Animation commits it
with the main thread's run loop and the window server shows it at a later
refresh.

### hotty-blitz

| name | | when |
| --- | --- | --- |
| `blitz.osc` | span | a hotty command through the C ABI (`a.n` bytes) |
| `blitz.handle` | span | the command applied: a delta, a document (`a.a`, `a.s`) |
| `blitz.pointer`, `blitz.key`, `blitz.keybytes`, `blitz.wheel` | span | input the host handles: hover, a field's typing, a scroll |
| `blitz.render` | span | every dirty surface rendered, through the C ABI |
| `blitz.resolve` | span | a surface's style and layout |
| `blitz.damage` | span | its damage turned into rectangles |
| `blitz.paint` | span | its rectangles painted (`a.rects`, `a.px`, `a.w`, `a.h`) |
| `blitz.scene` | span | one rectangle's scene built |
| `blitz.raster` | span | one rectangle rasterised by vello_cpu's workers (`a.px`) |
| `blitz.deliver` | span | the frame handed to the terminal, which writes its rectangles into the image (`a.full`, `a.px`) |

## Correlation

The rig spaces its inputs: after the pixels for input N arrive, it waits
until the stack has been quiet for 200 ms before it sends N + 1. So
everything between `rig.input` N and `rig.input` N + 1 belongs to N.
