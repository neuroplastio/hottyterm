---
title: "A packaged Linux build finds its library next to bin/"
patch: 0002-hottyterm-a-relocatable-rpath-for-packaged-Linux-bui.patch
upstream-fit: no
---

**What it changes:** the Linux executable gets an rpath of
`$ORIGIN/../lib`, so a build unpacked anywhere finds `libhotty_blitz.so` in
the `lib/` beside its `bin/`. The macOS app links hotty-blitz statically
and needs nothing. Two lines in `GhosttyExe`.

**Why we carry it:** hottyterm's Linux release archive, and the AUR and
Homebrew packages made from it, ship the library that way.

**For upstream:** no. Ghostty links no shared library of its own, so it
has nothing to find.
