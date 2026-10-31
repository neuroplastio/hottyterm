# Feel

This page turns "hottyterm feels slower than the browser" into numbers. It
covers how long a key, a pointer move or a document takes to reach the
screen in hottyterm, in stock Ghostty and in Chromium with
xterm-addon-hotty, where that time goes, and what was changed because of
it. It is neuroplastio's research note R-22, measured.
[performance.md](performance.md) covers the other cost, CPU.

## How it is measured

`scripts/feel/` times an input to the pixels on a private headless sway,
never on a desktop the user works in:

- `blackbox.py` is a Wayland client. It types through the virtual keyboard
  and moves the virtual pointer, and copies the output at every refresh
  (60 Hz, as a display shows it) until the region it watches changes. The
  time is from the input to the presentation of the first frame that shows
  it. Each input waits a random part of a refresh first, so the inputs
  don't keep the same phase as the output's frames.
- Every process of the stack writes stage stamps on one clock
  ([trace.md](trace.md)): the terminal, hotty-blitz, the scenario's program,
  and plx when it runs inside one. The rig waits until the stack is quiet
  before the next input, so `merge.py` assigns every stamp to its input
  without IDs. `report.py` gives each scenario's end-to-end time at
  p50/p95/p99, and splits it into a waterfall: the time each process spent
  on the way, the terminal's lock waits on their own row.
- `scripts/feel/prog` is the scenarios' program (on hotty-go):

| | what is timed |
| --- | --- |
| E1 | a key echoed by the program into the cells, as a shell does |
| E1P | the same while a dash below it repaints at 10 Hz |
| E2 | a key typed into a hotty surface's text field, which the terminal handles itself |
| E3 | the pointer moved across a list's rows, each `:hover` |
| E6 | a whole document (~60 KB) replaced by another |
| E8 | a plx-script Lua tool answering a key with a delta, through plx (plx's own scenario) |

Each runs at scale 1, 1.6 and 2 on a full-window surface. `--plx` runs the
program in a throwaway plx, which is how hotty is used day to day.

The machine is a Ryzen AI laptop (Radeon 890M) with two kinds of core: 4
Zen 5 (CPUs 0–3, with their siblings 12–15) and 8 Zen 5c, about 1.4 times
slower. Other work on it, builds and checks, runs on the Zen 5c cores at
idle priority. Before each run, the rig waits up to 5 minutes for the
Zen 5 cores to be under 10% busy over 5 s (`--gate-cpus 0-3,12-15`), and
records that figure, the 1-min load, and how busy other work kept those
cores during the run (`quiet.py`). The runs that compare two builds pin
the whole stack to the Zen 5 cores, since a run that lands on the others
is 1.4 times slower in every stage, alternate the builds, and drop a run
during which other work kept those cores more than 8% busy. The matrix
below runs unpinned, as a terminal does day to day. macOS numbers come
from GitHub's macOS runner (a 3-vCPU VM), through `probe-macos.yml`.

## Results

Measured on 2026-10-31, on the builds that shipped that day:

- hottyterm 26.10.31-dev.3bbee9e, with hotty-blitz 0.5.8;
- stock Ghostty at hottyterm's Ghostty base (`ghostty-ref`);
- xterm-addon-hotty 0.5.4 in Chromium 156;
- plx 26.10.31-dev.b668065, where it runs.

Each host, scenario and scale ran in three rounds of 40 inputs, of which
the first 2 warm up, with the hosts alternating within each round. A run
during which other work kept the Zen 5 cores 8% busy or more is left out:
the cores' busy time less all of the rig's CPU time, a lower bound, since
the stack was unpinned. That took out 16 of 99 runs. So a cell has 76 to
114 inputs, except E6 at 1.6, which has 38. Stock Ghostty draws no hotty
surfaces, so it runs E1 alone. All times are end to end, p50 / p95, in ms.
At 60 Hz a frame is 16.7 ms, so a frame that is ready waits 8 ms for the
display on average.

| | scale | hottyterm | Ghostty | Chromium |
| --- | ---: | ---: | ---: | ---: |
| E1 shell echo | 1 | 9.6 / 16.0 | 24.9 / 36.9 | 10.5 / 19.3 |
| | 1.6 | 9.5 / 15.6 | 25.6 / 37.4 | 11.3 / 20.2 |
| | 2 | 9.1 / 15.5 | 25.5 / 38.0 | 10.6 / 20.2 |
| E1P echo, dash beside | 1 | 10.6 / 24.9 | | 13.1 / 22.8 |
| | 1.6 | 9.6 / 26.7 | | 13.4 / 25.6 |
| | 2 | 10.2 / 25.3 | | 13.6 / 25.5 |
| E2 field key | 1 | 13.6 / 23.7 | | 9.6 / 19.0 |
| | 1.6 | 13.5 / 24.3 | | 10.2 / 19.3 |
| | 2 | 13.6 / 22.8 | | 10.0 / 19.5 |
| E3 hover | 1 | 9.7 / 19.3 | | 9.4 / 18.7 |
| | 1.6 | 10.4 / 20.4 | | 9.6 / 18.7 |
| | 2 | 10.4 / 19.3 | | 10.3 / 19.6 |
| E6 document swap | 1 | 58.5 / 75.0 | | 40.5 / 51.5 |
| | 1.6 | 59.5 / 78.4 | | 41.9 / 53.2 |
| | 2 | 59.2 / 71.2 | | 42.2 / 59.9 |

Through plx, at scale 1.6 only, plx's usual scale in hottyterm. There
were two rounds, and one run was left out (Ghostty's E8, which keeps one):

| | hottyterm | Ghostty | Chromium |
| --- | ---: | ---: | ---: |
| E1 shell echo | 9.3 / 15.2 | 25.4 / 38.4 | 13.7 / 24.1 |
| E2 field key | 13.8 / 23.2 | | 10.3 / 19.8 |
| E3 hover | 10.6 / 19.7 | | 10.3 / 19.7 |
| E6 document swap | 61.3 / 80.2 | | 42.7 / 56.5 |
| E8 Lua tool's delta | 11.4 / 19.2 | 24.7 / 35.1 | 13.1 / 20.3 |

Where hottyterm's time goes at scale 1.6, as each input's mean, in ms.
"input" is the compositor delivering the event, and "present" is from
GTK's main thread taking the frame to the compositor showing it, which
includes the wait for the display's next refresh:

| | input | hottyterm | lock wait | hotty-blitz | plx | present | mean |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| E1 | 0.3 | 1.7 | | | | 8.1 | 10.2 |
| E2 | 0.3 | 3.5 | | 3.9 | | 7.2 | 14.9 |
| E3 | 0.3 | 2.0 | | 1.1 | | 7.8 | 11.2 |
| E6 | 0.2 | 3.4 | 4.5 | 44.4 | | 9.7 | 62.3 |
| E8, through plx | 0.3 | 1.5 | 0.1 | 0.7 | 0.7 | 8.4 | 11.7 |

What the numbers say:

- **A shell's echo (E1)** takes hottyterm 9–10 ms at p50, 1.7 ms of its
  own and the rest the wait for the display. Stock Ghostty takes 25 ms,
  about a frame more, because GTK holds the frame (below). Chromium takes
  10.5–11.3 ms. hottyterm's p95 is 21–23 ms under stock Ghostty's: the
  mods below take a frame off, not add one.
- **With a dash repainting at 10 Hz beside it (E1P),** hottyterm's p50
  stays at 10 ms, and its p95 rises to 25–27 ms, as Chromium's rises to
  23–26.
- **A key in a hotty field (E2)** is 3.3–4.0 ms behind Chromium at p50
  and 3–5 at p95. Of hottyterm's time, 3.9 ms is hotty-blitz repainting
  the field's surface and 3.5 is hottyterm's own: the key through GTK,
  the host's input path and the frame.
- **A hover (E3)** is level with Chromium, at p50 and at p95.
- **A whole-document swap (E6)** is the largest gap left: 59 ms against
  Chromium's 41 at p50. 44 ms of it is hotty-blitz styling, laying out and
  painting the new 60 KB document, and 4.5 is GTK waiting on the
  terminal's lock meanwhile.
- **plx adds under 1 ms of its own** to each scenario, and hottyterm's
  numbers through plx are within the noise of its direct ones. A Lua
  tool's answer to a key (E8) reaches the screen in 11.4 ms in hottyterm
  and 13.1 in Chromium. In stock Ghostty, where plx draws the tool's
  picker in cells, it takes 24.7.
- **In Chromium, plx's frames cost xterm.js about 2.5 ms** more than a
  bare echo: E1 through plx is 13.7 / 24.1 against 11.3 / 20.2 direct.
  plx writes each frame inside a synchronized update (mode 2026), and
  when one ends, xterm.js 6.1.0-beta.304 redraws every row, not only the
  rows it buffered during the update. The same plx without the bracket
  gives 11.5 / 20.4 (alternating rounds, 4 a side). hottyterm and Ghostty
  show no such gap. plx keeps the bracket, which stops a terminal drawing
  half a frame, so the fix belongs to the xterm.js that xterm-addon-hotty
  runs on, not to plx.

## A frame late: GTK's frame clock

In stock Ghostty, and in hottyterm before the fixes below, a key's frame
reaches the screen about one refresh later than Chromium's. The stamps
show the frame is ready 2–9 ms after the key, and then waits.

Each input event GTK handles asks its frame clock for a cycle
(`gdk_surface_handle_event` requests the flush-events phase), and that
cycle runs at once and paints nothing. When a cycle ends without a paint,
GDK's idle frame clock (`gdkframeclockidle.c`) holds the next one back
until a refresh after it began (`min_next_frame_time`), so that a clock not
synced to vblank doesn't busy-loop. A painted cycle is different: the
clock then stops until the compositor's frame callback and starts again
without the hold. After a key, the cycle that would paint the key's frame
is held until a refresh after the key, and the compositor shows it at the
vblank after that. The `term.fc` stamps show the cycle that handled the
key, the renderer's redraw arriving during the hold, and the paint at its
end. The compositor's frame callback had come long before.

GTK's hold of a ready frame, from `term.redraw` to `term.snapshot`, at
scale 1.6, three alternating rounds of 20 inputs:

| | base p50 | base p95 | no hold p50 | no hold p95 |
| --- | ---: | ---: | ---: | ---: |
| E1 | 13.2 | 19.2 | 0.1 | 0.5 |
| E1P | 13.8 | 20.2 | 0.1 | 0.5 |
| E2 | 12.0 | 19.8 | 0.2 | 0.7 |
| E3 | 11.9 | 21.6 | 0.2 | 0.8 |
| E6 | 14.8 | 21.6 | 0.1 | 2.1 |

The first way tried to remove the hold was GTK's `no-vsync` debug flag,
which Ghostty would have to set in code, because it overwrites
`GDK_DEBUG` at start. It removes the hold, and with it every pace GTK
keeps: the wait for the frame callback, and the pace of its own
animations. With it, a flood of output painted 275–291 frames a second
on a 60 Hz output (base: 61–62), with more CPU in the terminal and in the
compositor, and the overlay scrollbar's fade after a scroll painted 34,031
frames a second (base: 18). It was dropped.

The fix kept, `gtk: paint a new frame now, not a refresh after the last
input`, leaves GTK's pacing alone. When the renderer hands GTK a frame,
the surface finds the frame clock's pending source (GTK names it `[gtk]
gdk_frame_clock_frame`) and makes it ready now. After a paint, GDK
freezes the surface's updates until the compositor's frame callback
(`gdksurface-wayland.c`), and the clock, stopped, has no source, so a
frame drawn meanwhile still waits for the callback. A first version also
skipped frames that came within a refresh of the last paint, to keep to
one paint a refresh. The freeze already does that, and the check made a
frame that came soon after a paint (typing fast, a dashboard beside)
wait a refresh, so it went.

### A frame with nothing new

With the hold gone, a key in a hotty field (E2) and a hover (E3) reached
the screen a refresh sooner, but a shell's echo (E1) didn't: GTK now
painted the first frame it got at once, and then waited for the
compositor's frame callback before the next. A key drew two frames before
its echo arrived. The surface queued a render to show the selection it
clears and the viewport it scrolls to the bottom, and the IO thread redrew
after it drained the key's write from its mailbox. Neither has anything to
show while the selection is empty, the viewport is at the bottom and the
program hasn't answered. GTK painted that frame, and the echo's frame,
ready a millisecond later, waited behind it for the next refresh.
`core: a keystroke draws only what it changed` leaves both out.

A hotty dashboard had the same shape. Each HOTTY command queued a render
of its own, on top of the one Termio queues when output arrives, so each
tick drew its frame twice and GTK painted both, a refresh each: a dash at
10 Hz painted 20 frames a second, and a key typed meanwhile could wait
behind the copy (E1P's tail). `hottyterm: a HOTTY command draws once, with
the output it came in` leaves the second out.

### The three, measured

End to end at scale 1.6, p50 / p95 in ms. The builds alternated in three
rounds of 20 inputs (n = 54 each), with the load at 1.0–2.8. "+0042"
is the frame clock and the keystroke fix together; "+0044" adds a
HOTTY command's single render; "all" has 0042 without the recent-paint
check.

| | base | +0042, 0043 | +0044 | all |
| --- | ---: | ---: | ---: | ---: |
| E1 echo | 26.0 / 40.1 | 9.5 / 15.7 | 10.4 / 18.3 | 9.8 / 16.6 |
| E1P echo, dash beside | 26.1 / 35.8 | 12.7 / 26.4 | 12.1 / 26.8 | 10.3 / 22.9 |
| E2 field key | 29.5 / 40.6 | 20.0 / 30.9 | 16.3 / 25.7 | 16.4 / 27.5 |
| E3 hover | 29.4 / 42.6 | 10.6 / 21.3 | 10.3 / 20.3 | 9.8 / 19.9 |
| E6 document swap | 99.1 / 111.2 | 74.9 / 90.6 | 73.3 / 89.8 | 73.6 / 90.2 |

What else could get worse didn't: a flood of output paints 62 frames a
second in every build, the scrollbar's fade 18, an idle terminal 1.7.
A dash at 10 Hz painted 20 frames a second before 0044 and 10 after, a
dash at 60 Hz 62 and 60. The terminal's CPU was the same within the
noise (idle 0.2–0.4%, a 10 Hz dash 6–8%, a flood 103–105% of a core).

A dash at 60 Hz looked a little dearer with 0044 over two rounds; over six,
untraced, alternating, at load 0.9–1.8, the terminal's CPU was the same:
32.5 ± 2.0% of a core in base, 31.6 ± 1.4 with 0042 and 0043, 32.0 ± 2.1
with all three. A dash at 10 Hz went from 7.4% to 6.8–6.9%, half its
paints gone.

The three shipped as mods/ghostty 0042–0044 in hottyterm
26.10.30-dev.f1eff01.

## The terminal's lock

`io-reader` parses the program's output, and renders hotty's surfaces,
while it holds the terminal's lock (`renderer_state.mutex`). Everything
else that needs the terminal waits for that lock: GTK's main thread
handling a key, the pointer or the IME's position, and the renderer at the
start of each frame. At light load the wait is at most about 3 ms. Under
load, a dash's paint took 50–75 ms, and GTK's main thread stalled for all
of it: the window stops answering while a surface paints.

hotty-blitz's host is shared by `io-reader` and GTK's input path, and the
lock is what keeps them apart. To paint without the lock, the host needs a
lock of its own, taken before the terminal's in both places, and the
terminal's lock held only to write the frame into the image.

On an opening of plx's palette, the lock's holder is Ghostty's parse
stage, for each batch of up to 64 KB of output. hotty-blitz renders inside
it and is over 95% of the hold. Of GTK's main thread's waits on a first
opening, the resolve is 46%, the scene 18%, the raster 13% and making the
documents 6%; parsing cells is under 1%. Freeing the lock moves no
opening's end to end: plx writes its frame inside a synchronized update
(mode 2026), and the terminal draws nothing until the update ends, so
every wait is over before the pixels. What the lock costs is everything
else in the process: for 40–65 ms per opening, keys wait and no other
hottyterm window draws.

`hottyterm: hotty surfaces paint off the terminal's lock` (mods/ghostty
0045) gives the host that lock of its own. Repaints go to a paint thread,
and the renderer waits for each one, so the end of a synchronized batch
isn't shown before its paints are in (SPEC §6.3). At scale 1.6, in
alternating rounds, GTK's longest wait on the lock per opening went from
43.5 ms on a first opening and 19.4 on a later one to 0. Against frame-now
alone (4 rounds, then 6 to confirm), a key typed into a second window of
the same process during an opening reached the screen in 15.7 ms instead
of 31.2 at p50. E1, E1P, E2, E3, E6's first openings and plx's palette
were level or better.

E6's later openings were about 2 ms slower, 70.7 → 72.8 ms at p50. The
patch adds no work. With the other threads no longer asleep on the lock,
an opening's resolve landed on a Zen 5c core more often: 51 of 110
openings, against 35 of 110. It shipped with that cost, with frame-now,
in hottyterm 26.10.30-dev.f1eff01.

## hotty-blitz's own costs

Where hotty-blitz's time went when R-22 started, on 0.5.3:

- A key in a text field repaints the whole surface: at scale 2, a full
  window's 1.7–3.5 M px for a caret and one glyph.
- Replacing a document (E6) costs about 75 ms in hotty-blitz at p50.
- A host's first document is slow: 80–99 ms. In a profile of it (perf at
  4 kHz, user stacks), 56% of the CPU goes to decoding the bundled WOFF2
  fonts (wuff's glyf transform and brotli), on several threads, and 9% to
  fontconfig matching fonts.
- After it, a new surface with a 601-byte box document, plx's pattern,
  takes 2.4 ms at p50 (1.8 to parse, style and lay it out, 0.65 to
  paint), about 2.6 ms of CPU. A fifth of that CPU is CSS parsing: each
  surface parses Blitz's 24.6 KB user-agent stylesheet twice, for its
  document and for the scratch document deltas are parsed in. Then come
  fontconfig matching fonts again (16%), glyphs hinted again (13%), and
  Stylo's cascade (12%), which builds the user agent's part again because
  Stylo caches it by the stylesheet's identity. Paint is 9%. The parse,
  the font matching and the hinting are the same for every surface of a
  host: a cache per host would save up to half of a new surface's CPU.

hotty-blitz 0.5.4 makes the second half a cache:
the scratch document takes no stylesheet; the clones of the font context
share one source cache, so a system font is the same blob in every
surface and the renderers' glyph caches serve it; Blitz parses a user
agent stylesheet once for the documents of a URL (a read-only sheet,
which Stylo's cache of the user agent's cascade data then serves); and
fontique asks the system for a fallback font once for every clone. In
`hotty replay` of a new surface a frame, each step took off its share,
and the frame went from 2.46 ms at p50 to 0.63.

On the rig (load 0.9–2.6, before and after interleaved, 8 rounds), it
holds in hotty-blitz's own time and not in what the eye sees at 60 Hz.
In plx main, where the palette is two new documents at every opening,
the last frame hotty-blitz delivers came 51 ms after the key at p50 and
now 45, and creating the two documents went from 5.3 ms to 4.1; the
pixels land on the same frame, 77 ms after the key, before and after.
E2, E3, E6 and plx's chrome are unchanged. A first opening is cold for
other reasons: plx takes 16–19 ms before it sends anything (4–5 ms on
a later one), and GTK's main thread waits 35–40 ms on the terminal's
lock while the surfaces render (above).

The font decode was never on that path. hottyterm makes a host at a
program's first HOTTY command, and plx's first is its caps query, so
the faces decode on a thread of their own seconds before the palette
opens. Shipping them decoded takes `hotty replay`'s first frame from
76–92 ms to 20–25, saves 175 ms of CPU and 16 MB of heap a process, and
makes the library 10.9 MB larger; neither E6 nor an opening of plx's
palette moves, so it was left out.

### What shipped after the caches

Each was measured in alternating rounds against the build before it,
first in `hotty replay` of plx's palette and box and then in the rig
through plx. The numbers are p50.

- **0.5.4, a font query keeps its last match** (mods/parley 0004). plx's
  dialog box is one inline-block per cell, about 1,340 text layouts, and
  each made a fresh font query. The box's resolve per opening went from
  11–17 ms to 7.5–8.5, and a later opening of plx's palette from 77.1 to
  74.8 ms end to end (p95 93.5 to 77.8).
- **0.5.5, blank glyphs and a shadow's inside cost no paint.** Glyph runs
  that draw nothing are left out of the scene (the box's scene 3.14 →
  1.83 ms), and the inside of a blurred rectangle is filled instead of
  worked out pixel by pixel (the palette's raster 1.90 → 1.62).
  blitz-paint's limit of 1,024 layers a paint now counts the layers open
  at once, not every layer pushed, so a document with more than about
  1,000 clipped elements keeps its clips.
- **0.5.6, more render contexts, and small ones draw without workers.**
  A host keeps 10 contexts, at most 4 of them large (the palette's scene
  2.30 → 1.74 ms), and a context under 256K px draws on the thread that
  asks, without worker threads (the box's paint 2.69 → 2.31).
- **0.5.7, a clip layer nothing is drawn in is not pushed**
  (mods/vello_cpu 0005). plx's box is a grid of `overflow: hidden` cells,
  most of them blank: its paint through plx went from 3.28 to 2.59 ms.
- **0.5.8, a border keeps the device pixels Stylo snapped it to**
  (mods/blitz 0048). At 1.6 a 1px border draws on every side, and with
  every side the same width it is one stroke instead of four edges: E6's
  raster went from 5.12 to 1.70 ms, its paint from 9.78 to 7.23.

## macOS

`probe-macos.yml` runs E1, E2 and E3 on GitHub's macOS runner (a 3-vCPU
VM) with the stamps alone. It has no screen copy, so an input ends at the
terminal's `term.contents` for its frame (`report.py --end`), and three
rounds alternate the release against a baseline. On
26.10.31-dev.3bbee9e (hotty-blitz 0.5.8), p50 / p95 per round, in ms:

| | round 1 | round 2 | round 3 |
| --- | ---: | ---: | ---: |
| E1 shell echo | 4.4 / 7.8 | 4.4 / 21.2 | 4.6 / 7.1 |
| E2 key in a hotty field | 7.7 / 27.8 | 7.5 / 25.7 | 7.6 / 11.9 |
| E3 pointer over `:hover` rows | 5.0 / 14.5 | 5.0 / 11.7 | 6.9 / 17.8 |

- The terminal's lock and GTK's hold aren't on macOS's path: the lock
  wait is 0 on nearly every input, and hottyterm's own share is 2–5 ms
  even at p95.
- The tail is hotty-blitz's raster waiting on its worker threads. About
  half the rasters over 5 ms end within 1 ms of a multiple of 10 ms, the
  scheduler's time slice on three busy vCPUs. Since 0.5.6, a small render
  context draws without workers: E3's rasters over 5 ms went from 19% to
  0%, and its end-to-end p95 from 43–83 ms to 8–17.
- E2's share of rasters over 5 ms went from about 18% on 0.5.4 to about
  28% on 0.5.5, higher in each of 3 rounds, with end-to-end p95 level.
  None of 0.5.5's changes reaches E2's raster, and on 3 Zen 5 cores Linux
  is level. 0.5.8, whose changes don't reach it either, then measured
  12.0% against 0.5.7's 22.7%. One build's rounds spread from 4% to 38%,
  as wide as either change, and rasters within a round aren't
  independent, so E2's tail is an open entry: the next comparison goes
  round by round, over 8 rounds (the workflow's `rounds` input).
- The runner has one performance level ("Apple M1 (Virtual), 1
  performance level(s): Standard 3 CPUs"). A QoS class can't move a
  thread to a faster core there, so whether the raster workers and an
  opening's resolve should run at the user-interactive class, as
  Ghostty's renderer thread does, is unmeasured.
