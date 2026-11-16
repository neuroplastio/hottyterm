#!/usr/bin/env python3
"""Noto Color Emoji's CBDT build as an sbix font, for CoreText.

CoreText draws no CBDT bitmaps, so hottyterm's macOS build embeds this copy
of the file Ghostty embeds (src/font/res/NotoColorEmoji.ttf): the same PNGs,
moved from CBDT/CBLC into an sbix strike, with empty outlines in glyf, as
sbix fonts carry them. GSUB, cmap and the metrics are untouched, so a
sequence shapes as in the CBDT build. scripts/build-macos.sh runs it.

    noto-sbix.py <NotoColorEmoji.ttf> <out.ttf>

Needs fontTools.
"""
import sys

from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._g_l_y_f import Glyph
from fontTools.ttLib.tables.sbixGlyph import Glyph as SbixGlyph
from fontTools.ttLib.tables.sbixStrike import Strike


def convert(src: str, out: str) -> None:
    font = TTFont(src)
    cblc, cbdt = font["CBLC"], font["CBDT"]
    if len(cblc.strikes) != 1:
        sys.exit(f"{src}: {len(cblc.strikes)} strikes, expected 1")
    ppem = cblc.strikes[0].bitmapSizeTable.ppemY

    strike = Strike(ppem=ppem, resolution=72)
    order = font.getGlyphOrder()
    bitmaps = cbdt.strikeData[0]
    for name in order:
        g = bitmaps.get(name)
        if g is None:
            continue
        m = g.metrics
        # sbix places the PNG's bottom left at the origin plus the offset,
        # in the strike's pixels; CBDT's BearingY is its top above the
        # baseline.
        strike.glyphs[name] = SbixGlyph(
            glyphName=name,
            graphicType="png ",
            imageData=g.imageData,
            originOffsetX=m.BearingX,
            originOffsetY=m.BearingY - m.height,
        )

    sbix = newTable("sbix")
    sbix.version, sbix.flags = 1, 1
    sbix.strikes = {ppem: strike}
    font["sbix"] = sbix
    del font["CBLC"], font["CBDT"]

    glyf = newTable("glyf")
    glyf.glyphOrder = order
    glyf.glyphs = {name: Glyph() for name in order}
    font["glyf"] = glyf
    font["loca"] = newTable("loca")
    maxp = font["maxp"]
    if maxp.tableVersion != 0x00010000:
        maxp.tableVersion = 0x00010000
        for field in (
            "maxPoints maxContours maxCompositePoints maxCompositeContours "
            "maxTwilightPoints maxStorage maxFunctionDefs maxInstructionDefs "
            "maxStackElements maxSizeOfInstructions maxComponentElements "
            "maxComponentDepth"
        ).split():
            setattr(maxp, field, 0)
        maxp.maxZones = 1
    font["head"].indexToLocFormat = 0
    font.save(out)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    convert(sys.argv[1], sys.argv[2])
