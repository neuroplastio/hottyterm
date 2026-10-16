---
title: "A scrolling surface takes the wheel before the terminal"
patch: 0009-hottyterm-a-document-that-scrolls-takes-the-wheel-fi.patch
upstream-fit: no
---

**What it changes:** a document that asks to scroll (`a=doc` with
`scroll=1`, `2` or `3`) scrolls as a page does. A wheel, a touchpad scroll
or a touch drag over it is the document's while something in it can move
that way. Past that, it goes on to the terminal as before (the scrollback,
mouse reports, alternate scroll) unless `overscroll-behavior` stops it.
`Surface.scrollCallback` hands the wheel to `hotty.zig` first (two
upstream lines), which turns Ghostty's offsets into pixels, with
`mouse-scroll-multiplier`. Scrollbars fade, so key and pointer events now
set the frame timer after they render.

**Why we carry it:** HOTTY SPEC §5.3. Long documents, such as docs pages,
scroll inside their surface.

**For upstream:** no. It routes the wheel to HOTTY surfaces.
