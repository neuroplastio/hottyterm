---
title: "Adwaita Mono is the default font"
patch: 0038-hottyterm-Adwaita-Mono-is-the-default-font.patch
upstream-fit: no
---

**What it changes:** the built-in font, which the terminal uses when
`font-family` names no font or none is found, is Adwaita Mono instead of
JetBrains Mono. It comes from GNOME's adwaita-fonts 50.0 (SIL OFL 1.1),
a lazy dependency in `build.zig.zon`. All four static faces are embedded,
so bold and italic are the font's own rather than weights of a variable
font, and the Inspector draws in it too. JetBrains Mono stays embedded for
the tests, which reference it, so it no longer reaches the binary, which
grows by about 5 MB. Upstream lines: the dependency in `build.zig.zon` and
`build.zig.zon.txt`, four imports in `src/build/SharedDeps.zig`, the
default faces in `src/font/embedded.zig`, the fallback faces in
`src/font/SharedGridSet.zig`, one name in `src/inspector/Inspector.zig`.

**Why we carry it:** hotty-blitz draws surfaces in Adwaita Mono (hotty's
HOST.md §2), in Nerd Fonts' build of the same release, so the letters are
the same. A terminal left at its defaults then shows its cells and the
surfaces under them in one font. A user's `font-family` still wins, and
surfaces follow it (`--hotty-font`).

**For upstream:** no. Upstream chose JetBrains Mono as its default, and
this only swaps the font for the one hotty's renderer uses.
