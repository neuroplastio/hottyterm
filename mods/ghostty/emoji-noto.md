---
title: "Emoji draw from Noto Color Emoji on every platform"
patch: 0057-hottyterm-emoji-draw-from-Noto-Color-Emoji-on-every-.patch
upstream-fit: no
---

**What it changes:** the emoji fallback is Noto Color Emoji on every
platform, ahead of any emoji font the system has. On Linux this is
upstream's own embedded file (CBDT) and Noto Emoji for text presentation,
as upstream has it. On macOS upstream adds Apple Color Emoji instead;
here it embeds the same Noto PNGs as an sbix font, because CoreText draws
no CBDT. `scripts/build-macos.sh` makes that copy with
`scripts/noto-sbix.py` (fontTools, pinned) and names it in
`HOTTYTERM_EMOJI_SBIX`. A `font-family` or `font-codepoint-map` that
names another emoji font still wins. Upstream lines: the sbix import in
`src/build/SharedDeps.zig`, `emoji_color` in `src/font/embedded.zig`,
and the fallback in `src/font/SharedGridSet.zig`, where it removes
upstream's Apple Color Emoji lookup. Its test is "hottyterm: emoji draw
from Noto Color Emoji".

**Why we carry it:** hotty-blitz draws a surface's emoji from the same
file (its `fonts.rs`), so an emoji in the cells and one in a surface
beside them are the same drawing, on Linux and macOS alike. It replaces
OpenMoji, whose outlined art looked poor on dark backgrounds; Apple's
emoji can't be shipped. The patch that passed VS16 to the shaper for
OpenMoji's sequences went with it: Noto's match without VS16.

**For upstream:** no. Upstream prefers the platform's own emoji on macOS,
and the choice of one emoji font everywhere is ours.
