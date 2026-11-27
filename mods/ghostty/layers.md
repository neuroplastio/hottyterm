---
title: "hotty surfaces are layers the apprt composites"
patch: 0070-hottyterm-hotty-surfaces-are-layers-the-apprt-compos.patch
upstream-fit: no
---

**What it changes:** a surface placed above the text on the active screen
is a layer. Its paints go to a store of premultiplied pixels
(`src/renderer/hotty_layers.zig`), with the rectangles that changed, and
the renderer draws no quad for it. Each exported frame carries where its
layers show (`Geometry`), so a scroll moves them with the cells. A paint
that changed only layers asks the apprt to composite again, through the
store's notifier or a redraw, and draws no terminal frame. A surface that
stops being a layer (hidden, under the text, on the other screen) is
drawn into its kitty image again whole.

**Why we carry it:** it's stage 1 of `docs/compositor.md`, the browser's
model. A surface animating on its own drew the whole terminal, cells and
every image quad, at the display's rate. Now only its changed pixels move.
The apprt patches (`layers-gtk.md`, `layers-macos.md`) composite them.

**For upstream:** no. It's built on hotty's surfaces. Animated kitty
images could use the same idea, but not this code.
