---
title: "A plain click opens only an OSC 8 hyperlink"
patch: 0036-hottyterm-a-plain-click-opens-only-an-OSC-8-hyperlin.patch
upstream-fit: no
---

**What it changes:** with `hotty-link-click = plain`, a click with no
modifier opens an OSC 8 hyperlink in the cells, and the pointer over one
underlines it, but no longer a URL or a path that Ghostty's `link`
regex finds in the text: those open with Ctrl (Cmd on macOS) and click,
as in Ghostty. Leaving a link for text that is none also redraws, so the
link's underline goes. Upstream lines: 4 in `Surface.zig`, 4 in
`Config.zig`.

**Why we carry it:** the regex is a guess. With the plain gesture it
underlined a prompt's directory together with the text after it
(`~/code/neuroplastio 6s`) and opened it on a plain click, and in a
multiplexer, which draws a pane row by row, it opened the first row of a
wrapped URL cut short. An OSC 8 hyperlink is the program's word that its
text is a link, and the terminal's to open (patches 0011 and 0032).

**For upstream:** no. It narrows hottyterm's own plain click; Ghostty
has no plain gesture to narrow. The redraw on leaving a link could go
upstream alone, where a Ctrl-held pointer leaving an OSC 8 link for
plain text leaves its underline until the row next changes.
