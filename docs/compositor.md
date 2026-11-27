# Toward the browser's compositor (proposal, 2026-11-27)

A browser animates `transform` and `opacity` without restyling, painting or
even waking the page: the element is a layer, painted once, and the
compositor (on macOS, Core Animation in the window server) moves or fades it
each frame. hottyterm today does the opposite for every animation frame:

1. hotty-blitz plays the frame from memory (0.9.1+), about 0.15 ms.
2. hottyterm uploads the changed rectangles to the surface's texture
   (`term.upload`, 0.17–0.3 ms on a 144 Hz Mac at 3440×1440).
3. Ghostty encodes and presents the whole terminal frame (`term.draw`,
   0.5–1 ms), with every cell buffer synced again.

At 144 Hz that's 10–19% of a core for a pulsing dot. Every animation plx
draws is opacity or transform (dot, miniature, typing dots: opacity;
spinner: rotate), which is exactly what a compositor runs for free.

This plan avoids capping frame rates on purpose. It cuts the cost of a
frame instead.

## Stage 0: waste in the current path (days)

Landed: patches 0067 and 0068, and glifo's decode on a miss (hotty-blitz).
Region uploads are left for stage 1, which replaces them. On Linux's
headless display, the plx-like page went from 3.11G to 2.46G instructions
per 10 s (-21%, three alternating rounds). CPU time there is the software
OpenGL's.

Found in a sample of that Mac:

- **A new Metal buffer for every image quad, every frame** (`image.zig`
  `drawQuad`, `newBufferWithBytes`). plx places about 25 surfaces, so that's
  3,600 allocations a second at 144 Hz. Fix: one instance buffer per frame
  for all quads, or `setVertexBytes`.
- **A command buffer and a staging buffer for every region uploaded**
  (`Metal.zig` `replaceTextureRegions`). Fix: a staging ring, encoded into
  the frame's own command buffer.
- **The cell buffers are synced again on frames where no cell changed.**
- **glifo decodes a colour emoji's PNG on every draw, cache hit or not**
  (`glyph.rs`, `Pixmap::from_png` before the atlas lookup). Its size can come
  from the PNG's header, with the decode only on a miss. It's 7% of that
  sample, in a window that repaints text.
- **Something in the maintainer's own workspace repaints all the time**
  (style, layout and text paint, about half a core). Find it with a bundle
  from `diag-macos.sh --trace-dir`.

## Stage 1: a surface is a layer (weeks)

On macOS, each placed hotty surface gets a `CALayer` whose contents is an
`IOSurface`. hotty-blitz paints damage straight into the IOSurface's memory
(shared with the GPU on Apple Silicon: no upload, no copy), and the
terminal's Metal frame no longer draws surfaces.

- A change to a surface alone writes pixels and marks the layer's contents
  changed. The window server composites, and no terminal frame is encoded.
- Stacking follows kitty's z. The terminal splits into a background layer
  and a transparent text layer, with below-text surfaces between them and
  above-text ones on top.
- Placement, scroll and clip move layers in a `CATransaction` with actions
  off, once per terminal frame.
- Two or three IOSurfaces per surface, since the window server reads one
  while hotty-blitz writes the next. Damage is copied forward.
- On Linux, GTK 4.14's `GtkGraphicsOffload` puts a dmabuf texture on a
  Wayland subsurface where the compositor supports it. Elsewhere it keeps
  the GPU composite, with stage 0's costs gone.

The C ABI changes (hotty-blitz paints into a buffer the host owns, per
surface). The spec does not.

## Stage 2a: the loops run in the compositor (weeks)

hotty-blitz's loop cache already holds, checked pixel for pixel against a
full paint, what a compositor needs:

- a `Fade` region is two images and an opacity curve: the high one over
  the low one at the loop's opacity, which is the blend it draws today;
- a `Frames` region is a flipbook: the images at each phase.

Handed to the host as sublayers of the surface's layer, a fade becomes a
`CAKeyframeAnimation` on `opacity`, and a flipbook becomes one on `contents`
(discrete). They repeat with the loop's period, from its start time. The
window server then runs them at the display's rate, with no work in
hottyterm or hotty-blitz per frame. Any change the loop cache already drops
on (a delta, input, damage outside the regions) takes the animations off
and goes back to painting.

On Linux the GL compositor plays them per vsync from a texture array, with
an index or weight uniform: no hotty-blitz work and no upload, only the
composite.

## Stage 2b: true layers (months, only if needed)

hotty-blitz promotes elements whose animations move only transform and
opacity into layers of their own, as Chrome and Safari do. That covers
transitions and non-repeating animations, which 2a doesn't. It has the hard
parts browsers have:
- overlap and squashing;
- ancestors' clips and rounded corners;
- text on transparent layers;
- hit testing mid-animation;
- keeping CA's clock and the document's in step.

Worth it only if a measured case needs it: transitions are short, and
loops are what runs all day.

## Expected

For a plx window at 144 Hz, with one surface's dot pulsing:

| | per animation frame | CPU at 144 Hz |
| --- | --- | --- |
| now | ~0.9–1.5 ms (blitz from memory + upload + terminal frame) | 10–19% |
| stage 0 | the terminal frame without per-quad buffers or cell syncs | ~5–10% (to measure) |
| stage 1 | blitz from memory + a write into an IOSurface | ~2–3% |
| stage 2a | nothing in the process | ~0% |
