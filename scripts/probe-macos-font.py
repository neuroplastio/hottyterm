#!/usr/bin/env python3
"""Draws an emoji with CoreText from each sbix variant of Noto Color Emoji,
on a probe-macos-font CI runner, to find the one CoreText draws.

    probe-macos-font.py <NotoColorEmoji.ttf> <OpenMoji-color-sbix.ttf> <out dir>

Variants (scripts/noto-sbix.py's convert, then):
  plain      as hottyterm's build makes it
  novert     without vhea and vmtx
  post3      post table format 3 (no glyph names)
  both       novert and post3
  boxes      glyf outlines a box over each bitmap
  openmoji   OpenMoji's own sbix build, the control that drew in hottyterm

For each: the colour-glyphs trait, the glyph, its bounding rect, and the
coloured pixels of 😀 drawn at 64 pt, with a PNG of it in <out dir>.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import CoreText
import Quartz
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTFont

import importlib.util

spec = importlib.util.spec_from_file_location(
    "noto_sbix", os.path.join(os.path.dirname(os.path.abspath(__file__)), "noto-sbix.py"))
noto_sbix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(noto_sbix)


def variant(src: str, name: str, out: str) -> str:
    base = os.path.join(out, "plain.ttf")
    if not os.path.exists(base):
        noto_sbix.convert(src, base)
    if name == "plain":
        return base
    f = TTFont(base)
    if name in ("novert", "both"):
        for t in ("vhea", "vmtx"):
            if t in f:
                del f[t]
    if name in ("post3", "both"):
        f["post"].formatType = 3.0
    if name == "boxes":
        upem = f["head"].unitsPerEm
        strike = list(f["sbix"].strikes.values())[0]
        scale = upem / strike.ppem
        glyf = f["glyf"]
        for gname, g in strike.glyphs.items():
            if g.graphicType != "png " or not g.imageData:
                continue
            w, h = png_size(g.imageData)
            x0, y0 = g.originOffsetX * scale, g.originOffsetY * scale
            pen = TTGlyphPen(None)
            pen.moveTo((x0, y0))
            pen.lineTo((x0, y0 + h * scale))
            pen.lineTo((x0 + w * scale, y0 + h * scale))
            pen.lineTo((x0 + w * scale, y0))
            pen.closePath()
            glyf[gname] = pen.glyph()
        f["maxp"].maxPoints = max(f["maxp"].maxPoints, 4)
        f["maxp"].maxContours = max(f["maxp"].maxContours, 1)
    path = os.path.join(out, name + ".ttf")
    f.save(path)
    return path


def png_size(data: bytes):
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def draw(path: str, png: str) -> str:
    data = open(path, "rb").read()
    desc = CoreText.CTFontManagerCreateFontDescriptorFromData(data)
    if desc is None:
        return "no descriptor"
    font = CoreText.CTFontCreateWithFontDescriptor(desc, 64.0, None)
    traits = CoreText.CTFontGetSymbolicTraits(font)
    colour = bool(traits & CoreText.kCTFontTraitColorGlyphs)
    ok, glyphs = CoreText.CTFontGetGlyphsForCharacters(font, "😀", None, 2)
    glyph = glyphs[0] if ok else 0
    rect = CoreText.CTFontGetBoundingRectsForGlyphs(font, 0, [glyph], None, 1)
    w = h = 128
    cs = Quartz.CGColorSpaceCreateDeviceRGB()
    ctx = Quartz.CGBitmapContextCreate(None, w, h, 8, w * 4, cs, Quartz.kCGImageAlphaPremultipliedLast)
    Quartz.CGContextSetRGBFillColor(ctx, 0.5, 0.5, 0.5, 1)
    CoreText.CTFontDrawGlyphs(font, [glyph], [Quartz.CGPointMake(20, 30)], 1, ctx)
    img = Quartz.CGBitmapContextCreateImage(ctx)
    buf = Quartz.CGDataProviderCopyData(Quartz.CGImageGetDataProvider(img))
    px = bytes(buf)
    coloured = sum(
        1 for i in range(0, len(px), 4)
        if px[i + 3] and max(px[i:i + 3]) - min(px[i:i + 3]) > 48)
    drawn = sum(1 for i in range(3, len(px), 4) if px[i])
    url = Quartz.CFURLCreateWithFileSystemPath(None, png, Quartz.kCFURLPOSIXPathStyle, False)
    dest = Quartz.CGImageDestinationCreateWithURL(url, "public.png", 1, None)
    Quartz.CGImageDestinationAddImage(dest, img, None)
    Quartz.CGImageDestinationFinalize(dest)
    name = CoreText.CTFontCopyFullName(font)
    return (f"name={name} colourTrait={colour} glyph={glyph} rect={rect} "
            f"drawn={drawn} coloured={coloured}")


def main() -> None:
    noto, openmoji, out = sys.argv[1:4]
    os.makedirs(out, exist_ok=True)
    for name in ("plain", "novert", "post3", "both", "boxes", "openmoji"):
        try:
            path = openmoji if name == "openmoji" else variant(noto, name, out)
            print(f"{name:9} {draw(path, os.path.join(out, name + '.png'))}", flush=True)
        except Exception as e:  # report every variant
            print(f"{name:9} error: {e!r}", flush=True)


if __name__ == "__main__":
    main()
