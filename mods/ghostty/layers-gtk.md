---
title: "GTK composites hotty layers as GL textures"
patch: 0071-gtk-hotty-layers-are-GL-textures-over-the-terminal-s.patch
upstream-fit: no
---

**What it changes:** `RenderSurface` snapshots each hotty layer as its own
texture over the terminal's, where the frame says it shows, clipped to its
placement. A layer's texture is one of up to three GL textures in a
context shared with GTK's. The next one is brought up to date from the
newest on the GPU (`glCopyImageSubData`), only the rectangles that changed
are uploaded (`glTexSubImage2D`), and GTK waits on a fence. Without GL, a
layer is a memory texture.

**Why we carry it:** GTK 4.24's GL renderer uploads a memory texture
whole, even with an update region (measured: no difference), so the
layers upload their own changes. On a 3440×1440 144 Hz output, a plx-like
page went from about 14% CPU to 9%, and terminal frames from about 330 a
second to 2.

Layers blend in sRGB, as browsers do, where Ghostty's Linux renderer
blends in linear light, so translucent surfaces over the text look a
little darker than before.

**For upstream:** no, it composites hotty's layers (`layers.md`).
