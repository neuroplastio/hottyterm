---
title: "A kitty frame edit uploads only the rectangle it changed (OpenGL)"
patch: 0020-renderer-a-kitty-frame-edit-uploads-only-the-rectang.patch
upstream-fit: yes
---

**What it changes:** a frame edit of the displayed frame (`a=f` with `r`)
composes a rectangle into the image in place, but the renderer copied the
whole image under the terminal lock and uploaded it into a new texture, so
a one-cell change to a large image cost the whole image. Now the image logs
each edit's rectangle with the generation it stamped. Anything else that
stamps a generation breaks the chain, and a full chain (64 edits) keeps its
latest half. A renderer with an earlier generation copies only those
rectangles and writes them into the texture it has
(`Texture.replaceRegion`). This patch does OpenGL; Metal follows in its
own. About 250 lines outside tests, with tests of the chain and the
renderer's region.

**Why we carry it:** hotty surfaces arrive as kitty frame edits of the
rectangles that changed. It is part of what took a 10 Hz dashboard from
about 15% of a core to 8%.

**For upstream:** yes. Every program that animates kitty images with frame
edits gets cheaper frames, and nothing else behaves differently.
