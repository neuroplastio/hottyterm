---
title: "A plain click opens a link"
patch: 0011-hottyterm-a-plain-click-opens-a-link-hotty-link-clic.patch
upstream-fit: maybe
---

**What it changes:** a new setting, `hotty-link-click`. With `plain`, the
default, a click with no modifier opens a URL or an OSC 8 hyperlink in the
cells, or a surface's link, as a browser does, and the pointer over one
underlines it. A drag still selects, and Ctrl+click (Cmd+click on macOS)
still opens. While the program reports the mouse, the click stays the
program's here; a later patch opens links there too. `modifier` is
Ghostty's behaviour. Upstream lines: 4 in
`Surface.zig`, 14 in `Config.zig`.

**Why we carry it:** links open as in a browser, in the cells and in hotty
documents alike.

**For upstream:** maybe. The cells' half is small and generic, but the
setting is named for hotty and the decision is made in `hotty.zig`. It
would need a name of Ghostty's and its logic moved into `Surface.zig`.
