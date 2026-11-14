---
title: "Emoji sequences draw from a font that keys them on VS16"
patch: 0058-font-emoji-sequences-draw-from-a-font-that-keys-them.patch
upstream-fit: maybe
---

**What it changes:** the run iterator dropped every presentation
selector before shaping. That suits Noto Color Emoji, whose ligatures
for emoji sequences also match without VS16. OpenMoji's include VS16, so
the rainbow flag (🏳️‍🌈) drew as a white flag with a rainbow beside it,
and heart on fire (❤️‍🔥) as its two parts. The iterator now passes VS16
on to the shaper when the run's font maps it. A font that does not map
it, as Noto Color Emoji, gets the same buffer as before, and VS15 is
still dropped. A keycap's base (0-9, # and *) asked for with emoji
presentation also matches a colour font whose own digit is plain, as
OpenMoji's are, because the keycap's colour comes from its ligature.
Before, 1️⃣ fell to discovery and drew from the system's emoji font.
Upstream lines added: 6 in `src/font/shaper/run.zig`, 10 in
`src/font/Collection.zig`, and a test in `src/font/shaper/harfbuzz.zig`
that shapes three sequences with OpenMoji.

**Why we carry it:** hottyterm draws emoji from OpenMoji
(`emoji-openmoji.md`), and without this its sequences break in the
cells while hotty-blitz's surfaces draw them whole.

**For upstream:** maybe. It helps any emoji font built like OpenMoji
that a user picks with `font-family`, and passing VS16 to a font that
maps it is what browsers do. Upstream would want the test on a font in
its own test set, as the test uses the OpenMoji face the previous patch
embeds.
