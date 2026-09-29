# hottyterm

**A fork of Ghostty with native HOTTY.** Programs that speak
[HOTTY](https://github.com/neuroplastio/hotty) (HTML Over The TTY) show
HTML/CSS surfaces in the terminal, and hottyterm renders them itself through
[hotty-blitz](https://github.com/neuroplastio/hotty-blitz). Everything else is
Ghostty.

hottyterm is not affiliated with Ghostty. "Ghostty" and its icon are
trademarks of Ghostty's non-profit; hottyterm uses neither.

## What the fork is

A soft fork: upstream Ghostty at the commit in [`ghostty-ref`](ghostty-ref),
plus the patches in [`patches/`](patches/). There is no copy of Ghostty's
tree here, and no GitHub fork (a fork of a public repository would be public).

| | |
| --- | --- |
| upstream | `ghostty-org/ghostty` at `0538f753` (2026-09-29, "1.3.2-dev") |
| patches | one: `0001-hottyterm-HOTTY-surfaces-over-hotty-blitz.patch` |
| new code | `src/termio/hotty.zig`, 702 lines: all of the logic |
| upstream files touched | 4 files, 41 lines, hooks only |

The hooks:

| file | hook |
| --- | --- |
| `src/termio/Termio.zig` | settings from the config; `osc_unknown_max_bytes`; flush once per read; re-render on resize |
| `src/termio/stream_handler.zig` | the `osc_unknown` action (upstream #14452) goes to hotty.zig; full reset |
| `src/Surface.zig` | keys, clicks and hover go to the surfaces first |
| `src/build/GhosttyExe.zig` | links `libhotty_blitz` (`HOTTY_BLITZ_LIB`) |

How it works:

- **Parsing is upstream's.** Ghostty passes every OSC it does not implement to
  the stream handler once `osc_unknown_max_bytes` is set; hotty.zig takes
  OSC 7279 and hands the body to hotty-blitz.
- **Surfaces are kitty images** in the active screen's image storage, placed
  at the cursor with a command built in memory. They scroll, clear and die
  with their screen like any kitty image.
- **Updates are kitty frame edits** (`a=f`, `r=1`) of the damaged rectangles,
  the same edits the polyfill sends to a terminal. After a font size change,
  surfaces re-render at the new cell size and replace their pixels in place.
- **Input:** a surface that holds the keyboard gets keys first; clicks and
  hover on a surface go to it and are not reported to the program.

## Build and run

Needs a checkout of [hotty-blitz](https://github.com/neuroplastio/hotty-blitz)
next to this repository (or `HOTTY_BLITZ_DIR`), and
[hotty](https://github.com/neuroplastio/hotty) for the examples.

```
mise install
make build                    # sets up ../ghostty, builds hotty-blitz and the fork
scripts/run.sh -e python3 ../../hotty/main/examples/dash.py
make check                    # patches apply, build, smoke test
```

`scripts/run.sh` gives hottyterm its own application id
(`io.github.neuroplastio.hottyterm`), so it runs next to an installed Ghostty.
`scripts/build.sh` carries two workarounds for this machine: Zig
0.16 needs LLVM and LLD to link CachyOS's `crt1.o`, and a cached
blueprint-compiler 0.16 whose warnings on upstream's UI files are hidden unless
it fails.

## Changing the fork

1. `scripts/fork.sh` sets up `../ghostty` (branch `hottyterm`) if missing.
2. Change it there, commit, and run `scripts/export.sh`.
3. Commit `patches/` here.

`scripts/canary.sh` applies the patches to upstream's latest `main` in a
throwaway worktree and reports conflicts. Moving `ghostty-ref` is a deliberate
step: canary, rebase, build, smoke test, then commit `ghostty-ref` and
`patches/` together.

## Verified (2026-09-29)

On a private headless display (hotty-blitz's `scripts/headless.sh`):

- `dash.py`: 56 frames in 6 s, 55 of them partial; no kitty graphics failures.
- `form.py`: typing, Tab, a change event back to the program, the checkbox and
  the radio by click.
- Bub-n-Bros (`bubbros.py`): 383 sprites, about 7 changes a frame, 20 fps,
  keys through the kitty keyboard protocol.
- Cost: the terminal process uses 8–9% CPU on the 10 Hz dashboard. An earlier
  fork, which uploaded only the changed rectangles to the GPU, used
  6–7%. Partial texture uploads for kitty frame edits would help any kitty
  graphics user, so they are a candidate for upstream rather than for this
  patch queue.

Headless clicks need a keyboard: Ghostty takes a left click on an unfocused
surface as a focus click and does not report it, and the headless display
has no keyboard unless `wtype` is running.

## Licence

MIT ([LICENSE](LICENSE)), like Ghostty. hotty-blitz, which it links, is
Apache-2.0.
