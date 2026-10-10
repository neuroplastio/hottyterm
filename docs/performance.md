# Performance

This page covers what a HOTTY surface costs hottyterm in CPU, the changes of
2026-10-10 that lowered that cost, what was tried and dropped, and how to
measure it again. The work spans this fork and
[hotty-blitz](https://github.com/neuroplastio/hotty-blitz), whose changes
reach a release through [`hotty-blitz-ref`](../hotty-blitz-ref). The research
behind it, which also weighed GPU rendering, is neuroplastio's research note
R-5.

## The case measured

The test case is `dash.py`, one of hotty's examples: a single surface redrawn
at 10 Hz. On hotty-blitz's headless display (2400×1500 at scale 2) the
surface is 3.5 Mpx. Each frame changes about 0.45 Mpx in 7–8 rectangles, and
once a second a table update changes 8 more. That is the case the work aimed
at: a large surface that stays up and changes in small parts.

The terminal ran on a laptop (Ryzen AI, 24 threads, Radeon 890M, Mesa) that
other builds kept busy. CPU time there moves with the load and the clock
speed, so the counts to trust are each thread's user-space instructions and
cycles. hotty-blitz's frame times without a terminal come from a quieter
desktop (Ryzen 5 5600X), measured with `hotty replay`.

## Before and now

`scripts/perf.sh` measured each release in turn: 3 alternating rounds of 10 s,
each after 4 s of warm-up, at load 2–4:

| release | adds | instructions | cycles | CPU |
| --- | --- | --- | --- | --- |
| 26.10.10-dev.c2ec526 | (before) | 4327–4384M | 3777–4163M | 1.41–1.49 s |
| 26.10.10-dev.95f16b3 | `0020`; damage priced at a tenth | 4614–4659M | 3412–4161M | 1.36–1.43 s |
| 26.10.10-dev.289954d | vello_cpu's flush; damage priced at a sixteenth; `0023` | 3400–3615M | 3247–3420M | 1.22–1.29 s |
| 26.10.10-dev.4f5a103 | 4 workers; one-pass merge; plain walk; `0020` trimmed | 2879–2978M | 2297–2511M | 0.82–0.87 s |
| 26.10.10-dev.e7fc79d | `0025` (Metal only) | 2891–3032M | 2454–2612M | 0.75–0.82 s |

From before to now:
- CPU fell from 1.46 to 0.80 s per 10 s, from about 15% of a core to 8%.
- Instructions fell by a third and cycles by 36%.

The last two releases behave the same on Linux, so the gap between them is
the measurement's noise.

Per thread, in millions of instructions / cycles (means):

| thread | before (c2ec526) | now (e7fc79d) |
| --- | --- | --- |
| painting (`io-reader`) | 2127 / 1381 | 1428 / 1175 |
| vello_cpu's workers (`io-reader` too) | 1805 / 1486 | 1358 / 838 |
| GTK's main thread (`hottyterm`) | 62 / 302 | 62 / 287 |
| renderer | 368 / 794 | 94 / 237 |
| busy workers / all threads | 31–37 / 115–119 | 12–16 / 78–87 |

Now, the painting thread takes 46% of the cycles, the workers 33%, GTK 11% and
the renderer 9%:

- **Painting:** `io-reader` reads the pty and parses what it reads, so
  hotty.zig hands each HOTTY command to hotty-blitz on that thread. The work
  there:
  - Blitz's styling and layout;
  - the scene;
  - vello_cpu's strips and the dispatch to its workers;
  - the frame's rectangles into the surface's image (`0023`).
- **vello_cpu's workers** rasterise. They take the name of the thread that
  started them.
  - hotty-blitz keeps a render context for each rectangle size (the 8 most
    recent), each with its own pool of 4 workers.
  - `dash.py`'s rectangles use about 3 contexts, so about 12 workers are busy.
  - About a quarter of their cycles go to waiting or spinning for the next
    task.
- **GTK's main thread** is GTK, GObject, GIO and Mesa drawing the window.
  - Ghostty's own code is under 0.1% of the process there.
  - Call graphs don't resolve symbols inside the system libraries, so what
    asks for that work isn't known.
- **The renderer** is Mesa and the texture copies, which now copy only the
  rectangles that changed.

## What changed

### In this fork

- **`0020`, region uploads on OpenGL** (26.10.10-dev.4ba1666).
  - Each kitty frame edit (`a=f`) logs its rectangle on the image. The
    renderer copies only those rectangles under the lock and writes them into
    the texture it keeps (`texture_region_updates`).
  - Anything else that changes the image breaks the chain, and the image
    uploads whole.
  - The patch is generic and in upstream's style, so it can be offered to
    Ghostty.
  - Between c2ec526 and 95f16b3 above, the renderer's cycles fell from 794M
    to 337M.
- **`0020` trimmed** (9bb10e6, 26.10.10-dev.4f5a103).
  - The log held 64 edits and then started again empty. With `dash.py`'s 7–8
    rectangles a frame, one frame in nine uploaded the whole 14 MB image.
  - A full log now forgets only its older half.
  - The renderer's cycles fell from 273–309M to 223–232M per 10 s.
- **`0023`, rectangles straight into the image** (2aedafb,
  26.10.10-dev.289954d).
  - hotty.zig converts a frame's damaged rectangles into the image's pixels in
    place. Before, it built kitty `a=f` edits, with two copies and
    allocations a rectangle.
  - The straight-alpha conversion skips opaque and clear pixels 8 at a time;
    it used to call `memcpy` per pixel.
  - Delivery fell from ~4.8M to ~1.9M instructions a frame.
- **`0025`, region uploads on Metal** (a9101de, 26.10.10-dev.e7fc79d).
  - Metal writes the rectangles with a blit from a staging buffer, in a
    command buffer of its own committed ahead of the frame's. Frames still in
    flight keep their texture, which `replaceRegion` would not wait for.
  - The patch is generic: 66 lines.
  - The probe-macos workflow's `regions` mode checks it: every cell appears
    at its step and stays. The window matches whole uploads pixel for pixel,
    except the blinking cursor.
  - CPU didn't separate on the runner's 1024×768 screen: 0.29 against
    0.29 s, and 0.35 against 0.52 s, over 12 s. The saving is a whole image's
    copy every frame, so it grows with the surface.

### In hotty-blitz

- **Damage priced by area** (8d3d117 at a tenth of the surface, cd7f235 at a
  sixteenth).
  - hotty-blitz paints the whole surface instead of the rectangles once they
    would cost more. It priced each rectangle at 64k px, but a rectangle's
    fixed cost is 2–10% of a full paint, so many small ones cost more than
    one full paint.
  - `hotty bench`'s 32 scattered cells went from 21.5–23.2 to 7.6 ms.
  - At a tenth, `dash.py`'s once-a-second table update repainted whole,
    which shows as the painting thread's 19% more instructions in 95f16b3
    above.
  - At a sixteenth, full paints went from 14 in 136 frames to 1.
- **vello_cpu's flush blocks** (0eb3f7f; vello/0001 in hotty-blitz's
  vello_cpu fork).
  - `flush` looped on `try_recv` until the workers finished, so the painting
    thread spun for as long as they worked.
  - The painting thread's instructions fell by 39%.
  - Upstream vello_cpu 0.3 still spins. The patch stays local.
- **At most 4 workers** (94c70b3, vello/0002; the maintainer's call). Before,
  vello_cpu took up to 8.
  - Fewer workers paint `dash.py` faster, and a full 3.45 Mpx paint barely
    gains past 2 workers. The painting thread's share (scene, strips,
    dispatch) dominates.
  - A full paint stays within ~5% of 8 workers.
- **One-pass `paint::merge`** (f4cc4f1), and **a plain walk** for a
  document's network meta and `<base>` instead of Stylo's `query_selector`
  (d11476a).
  - `hotty bench --only flat` went from 20.6G to 7.6G instructions, nearly
    all of it document setup.

hotty-blitz on its own, measured by the 300-frame `dash.py` replay on the
5600X from 8d3d117 to d11476a:

| | 8d3d117 | d11476a |
| --- | --- | --- |
| paint, mean | 2.51 ms | 1.79 ms |
| paint, p95 | 6.5 ms | 3.7 ms |
| CPU | 3.03 s | 1.86 s |

## Tried and not kept

- **Rasterising on the GPU** (vello and vello_hybrid over wgpu, read back
  into the same C ABI).
  - Their wall time was longer for every document measured, except the
    heaviest full repaint (a 1200-cell grid).
  - On small updates they cost more CPU too. A GPU frame never takes less
    than 0.5 ms wall and 0.2 ms CPU (submission, the wait, the readback), and
    the scene stays on the CPU, as do vello_hybrid's strips.
  - A wgpu device takes 28–69 ms to start and adds 50 MB RSS.
  - Revisit with a shared texture instead of a readback once animation,
    smooth scrolling or video make large full repaints frequent.
- **One thread** (vello_cpu without `multithreading`).
  - Small updates take 40–60% less time and about two thirds less CPU than
    with 8 workers.
  - A full repaint of a heavy document is slower: 7.3 → 10.9 ms at
    2394×1440.
  - The maintainer kept the workers, and the cap of 4 took most of the
    saving.
- **One worker pool for every render context**, a vello_cpu patch of about
  40 lines.
  - It cut the busy workers from 16–24 to 4, and the process's threads from
    76–87 to 56–59.
  - It saved nothing. Over 5 alternating pairs of 10 s on e7fc79d, at load
    5–12 (hence more CPU than the same build above):

    | | instructions | cycles | CPU |
    | --- | --- | --- | --- |
    | separate pools | mean 2950M | mean 2385M | mean 1.27 s |
    | one pool | mean 3087M | mean 2597M | mean 1.27 s |

  - The workers' waiting comes with each task handed out, and the idle pools
    were asleep.
  - The patch isn't in the vello_cpu fork. It would still be the way to cut a host's
    threads from up to 32 to 4, should that ever matter.
- **Left as found** (each under 2% of `dash.py`):
  - rayon's idle workers spin before they sleep;
  - `kurbo` computes `sincos` for every rounded corner's arc.

## Measuring

`scripts/perf.sh` runs an example in hottyterm on a private headless display
(hotty-blitz's `scripts/headless.sh`, as the smoke test does). It counts each
thread's user-space instructions and cycles with `perf stat`, and the
process's CPU time. Each variant is either a whole build or release (a
directory with `bin/hottyterm`), or a directory holding a
`libhotty_blitz.so` to run a binary with. The variants alternate within
each round, and `scripts/perf-sum.py` prints each run and each variant's range
and mean:

```sh
# releases: unpack each Linux archive, then
scripts/perf.sh 3 before=<unpacked>/hottyterm now=/usr/lib/hottyterm

# a hotty-blitz change, without building hottyterm
HOTTYTERM_BIN=/usr/lib/hottyterm/bin/hottyterm \
  scripts/perf.sh 5 now= change=../hotty-blitz/<worktree>/target/release
```

- **Count instructions, and keep the load low anyway.**
  - The same library run as two variants at load 45 matched within 0.5% in
    instructions, but differed by 5% in cycles and 9% in CPU time.
  - Code that spins breaks the rule: before vello/0001 the painting thread
    spun while it waited for the workers. At load 31 the two oldest releases
    above counted up to twice their instructions at load 3.
  - So alternate the variants, run several rounds, report ranges, and look
    at the load column.
- **Swap the library, not the build.**
  - The installed hottyterm (the AUR package) finds `libhotty_blitz.so`
    through RUNPATH `$ORIGIN/../lib`, so `LD_LIBRARY_PATH` replaces it.
  - That works for any hotty-blitz commit with the same C ABI as the
    release's `hotty-blitz-ref`.
- **Threads:** the painting thread and vello_cpu's workers are all called
  `io-reader`; `perf-sum.py` takes the busiest one as the painting thread.
- **Profiles:**
  - Record with `perf record -e instructions:u -c 100000 -p <pid> -- sleep 10`.
  - Read with `perf report --sort comm,dso,sym`, or `--sort pid` for each
    thread.
  - Call graphs stop at GTK's and Mesa's libraries.
- **Frames:**
  - `HOTTY_FRAME_LOG=<file>` makes hotty-blitz write a line per rendered
    surface: each stage's time (handle, resolve, diff, paint, deliver) and
    the damaged pixels. The smoke test reads it.
  - For hotty-blitz alone, without a terminal: `python3 examples/dash.py
    --record dash.stream --frames 300` in hotty, then `hotty replay
    dash.stream --runs 1` from hotty-blitz on a quiet machine, and `hotty
    bench`.
- **macOS:** `gh workflow run probe-macos.yml -f run=<ci run> -f regions=true
  -f baseline=<release>` runs a CI build on a GitHub macOS runner. It colours
  one cell of a grid each step, then changes 4 cells at 10 Hz, and reports
  the CPU against the baseline.

## Not checked

- A real display: every number here comes from the headless one.
- Metal's region uploads on a large surface: the probe runner's screen is too
  small to show their CPU.
- Discrete GPUs, and machines with fewer than 6 cores.
- The worker count at 10 Hz in the terminal: the count was chosen from
  replays, which run frames back to back.
- What in GTK drives its main thread.
- CSS `filter`: vello_cpu draws none while `multithreading` is on.
  - Turning filters on needs a guard for the filters vello_cpu implements; it
    panics on colour matrices.
  - It also needs damage that covers a blur's reach, which runs past the 8 px
    margin.
