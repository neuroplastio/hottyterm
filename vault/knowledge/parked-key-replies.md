# Parked: a key's replies before its echo

Parked by gov R-22 on 2026-11-01. It's a patch for `mods/ghostty`, written
and measured. It is correct, and its own number moves, but what reaches
the screen doesn't. It would be 0047 on main's set, and 0050 on
hotty-0.6's.

## What it does

A key for the surface holding the keyboard goes to hotty-blitz, which
paints the echo there and then, under the terminal's lock (`keyPressed`
and `keyBytes` in `termio/hotty.zig`). The key's replies went to the pty
only after that paint, in `deliver`. They are the keys the surface didn't
use and the events it heard, such as the `input` plx's palette filters
on. The patch sends them to the IO thread's mailbox before the paint, so
the program starts on its answer while the echo paints. It has no test of
its own.

## The A/B

The setup, on gov R-22's rig:
- plx's palette, E7K: s, p, l and three BackSpaces, at 1.6, through plx;
- 8 rounds, pinned to the fast cores, 144 keys of each kind a side;
- both sides built here from main's set, without and with the patch, on
  the same hotty-blitz (0.5.11).

Times are in ms, p50 / p95, and z is Mann-Whitney's:

| | without | with | z |
| --- | --- | --- | --- |
| letter: key to the pty | 1.44 / 4.13 | 0.93 / 3.53 | −7.9 |
| BackSpace: key to the pty | 1.49 / 4.92 | 0.88 / 3.91 | −7.6 |
| letter: plx's answer read | 3.19 | 2.67 | |
| BackSpace: plx's answer read | 3.55 | 2.79 | |
| letter: answer painted | 8.90 | 8.94 | |
| BackSpace: answer painted | 8.71 | 7.80 | |
| letter: echo on screen | 9.82 / 18.88 | 10.01 / 19.73 | +0.2 |
| BackSpace: echo on screen | 10.02 / 16.59 | 10.16 / 16.41 | −0.6 |
| letter: last change on screen | 30.61 / 46.37 | 30.76 / 46.78 | +0.1 |
| BackSpace: last change on screen | 30.47 / 47.73 | 30.33 / 47.34 | −0.4 |

E1, E1P, E2, E3, E6 and E7m are level.

## Why the screen doesn't move

plx's answer reaches the screen a refresh after the echo, with the patch
or without it. In a sampled 'p':
- the echo's frame makes the refresh at 9.0 ms;
- the answer is painted at 8.8 ms, but its frame is ready only at 11.5 ms;
- so the answer shows at the next refresh, at 25 ms.

A head start of 0.5 ms changes which refresh the answer makes for about 3%
of keys (0.5 of 16.7 ms). That's about 0.5 ms on the mean, under what 144
keys a side can show (about 1.2 ms).

When the list's height changes (each 'l' and most first and third
BackSpaces), plx places the palette again after its answer. That costs a
round trip and a full repaint, and the last change comes at 40 ms at p50,
against 26 without.

## When to look again

- When the answer's own chain is short enough to make the echo's refresh
  (gov R-22's F3; it is about 2.6 ms short at p50 on this rig). Then a
  head start decides whether more keys make that refresh.
- On a host where the echo's paint takes longer than it does here, since
  the head start is the length of that paint. On macOS, measure it with
  the probe first.

## Where the patch is

Next to this note, in `parked-key-replies/`:
- the patch, as exported on main's set (its 0047);
- its `.md` for `mods/ghostty`, with these numbers.

Its fork commit is f083e44f7, on 548790c65 (the top of main's set), in
hotty-perf's fork clone, not pushed. It cherry-picks cleanly onto the top
of hotty-0.6's set, fa06b9ca0. To take it up:
1. `git am` the patch on the fork.
2. Export the set again.
3. Put the `.md` in `mods/ghostty` with its `patch:` renumbered.
