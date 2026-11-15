---
title: "Surfaces follow the system's reduced-motion setting"
patch: 0059-hottyterm-surfaces-follow-the-system-s-reduced-motio.patch
upstream-fit: no
---

**What it changes:** `prefers-reduced-motion` follows GtkSettings'
`gtk-enable-animations` (false means reduce) and macOS's
`accessibilityDisplayShouldReduceMotion`. Both settings are watched; a
change reaches `hotty_host_set_reduced_motion` and repaints idle surfaces.
The value is kept before hotty-blitz's lazy host exists, so new documents
inherit it too. The GTK signal and AppKit notification observer are removed
before their terminal surface is freed. Seventeen lines added to upstream
files: two GTK lifecycle calls, a namespaced embedded C bridge and its
header declaration, and AppKit preference hooks. The host logic stays in
`src/termio/hotty.zig`.

**Why we carry it:** SPEC §8 and HOST §4 require the surfaces to follow the
user's preference on the system where the terminal runs, including after
it changes. A headless GTK check exercises both initial settings, live
changes, and later documents. The macOS probe runs only in CI.

**For upstream:** no. It carries hotty's preference into hotty-blitz.
