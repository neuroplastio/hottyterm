---
title: "Emoji draw from OpenMoji on every platform"
patch: 0057-hottyterm-emoji-draw-from-OpenMoji-on-every-platform.patch
upstream-fit: no
---

**What it changes:** the emoji fallback is OpenMoji 17.0 (CC BY-SA 4.0,
by HfG Schwäbisch Gmünd) on every platform. The colour font comes in the
format the platform's rasterizer draws: sbix for CoreText, CBDT for
FreeType, whose path in Ghostty turns COLR glyphs grey. OpenMoji Black
covers text presentation. The release's `openmoji-font.zip` is a lazy
dependency in `build.zig.zon`, as Adwaita Mono's is. The fonts replace
Noto Color Emoji and Noto Emoji, which stay embedded for the tests, so
they no longer reach the binary. That is about 8 MB less on Linux. On
macOS, Apple Color Emoji is no longer added ahead of them. The fallback
faces come before discovery, so the system's emoji font is used only for
an emoji OpenMoji lacks. A `font-family` or `font-codepoint-map` that
names another emoji font still wins. Upstream lines: the dependency in
`build.zig.zon` and `deps/packages.txt`, two imports in
`src/build/SharedDeps.zig`, the faces in `src/font/embedded.zig`, and the
fallback in `src/font/SharedGridSet.zig`, where it removes upstream's
Apple Color Emoji lookup. Its test is "hottyterm: emoji draw from
OpenMoji".

**Why we carry it:** hotty-blitz draws a surface's emoji in OpenMoji's
COLR build (its `fonts.rs`), so an emoji in the cells and one in a
surface beside them are the same drawing, and they look the same on
Linux and macOS whatever emoji font the system has.

**For upstream:** no. Upstream prefers the platform's own emoji on macOS
and Noto elsewhere, and the choice of OpenMoji is ours.
