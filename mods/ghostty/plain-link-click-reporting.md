---
title: "A plain click opens a link though the program reports the mouse"
patch: 0031-hottyterm-a-plain-click-opens-a-link-though-the-prog.patch
upstream-fit: maybe
---

**What it changes:** with `hotty-link-click = plain`, a click with no
modifier now opens a URL or an OSC 8 hyperlink in the cells while the
program reports the mouse too, and the pointer over one underlines it.
The press on a link is kept from the program, and its release opens the
link. If the pointer leaves the press's cell first, the held press goes
to the program after all, before the motion, so a drag that starts on a
link still selects in the program. Ctrl+click and other modified clicks
stay the program's. Upstream lines: 22 in `Surface.zig`, 5 in
`Config.zig`.

**Why we carry it:** a hyperlink is the terminal's to open. Under
reporting Ghostty gives every click to the program, so in a multiplexer,
an editor or Claude Code's full screen a link needed the program to open
it, or a modifier. Claude Code, for one, asks for Ctrl on Linux.

**For upstream:** maybe. Opening links with a plain click while a
program reports the mouse would help any Ghostty user, and the held
press keeps drags whole. But it changes who owns a click, which upstream
would want as a setting of its own, and the logic sits in `hotty.zig`
under a setting named for hotty.
