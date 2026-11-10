---
title: "Surfaces take the colours a program sets with OSC 4, 10 and 11"
patch: 0055-hottyterm-surfaces-take-the-colours-a-program-sets-w.patch
upstream-fit: no
---

**What it changes:** the host's stylesheet (`--hotty-fg`, `--hotty-bg`,
`--hotty-ansi-N`, `color-scheme`) was built from the terminal's colours
when a surface was first drawn and when the font changed, and never when a
program set the foreground, the background or a palette colour with OSC 4,
10 or 11 (or reset them). The cells moved to the new colours, the surfaces
did not, and a document that fills with `var(--hotty-bg)` drew a second
background beside them (HT-03). At the end of each batch of output the
host's configuration is now taken again if those colours differ from the
ones the surfaces were drawn with. hotty-blitz restyles every surface, and
a program that asked for `caps` hears the new theme (SPEC §8). A program
that sets the colours it already had costs nothing. No lines in upstream's
files: it is all in `src/termio/hotty.zig`.

**Why we carry it:** SPEC §8 hands every surface the terminal's look, and
once a program sets OSC 11 the terminal's background is that colour.

**For upstream:** no. It is about hotty's surfaces.
