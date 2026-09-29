#!/bin/sh
# Renders the icons brand/brand.toml copies into the fork: brand/icon.svg (the
# mark on its ground) at every size upstream uses, and brand/mark.svg (the mark
# alone) for the macOS icon's layer. Run after changing either; commit the PNGs.
set -eu
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$HERE/brand/icons"
mkdir -p "$OUT"
for n in 16 32 64 128 256 512 1024 2048; do
  magick -background none -density 400 "RSVG:$HERE/brand/icon.svg" -resize "${n}x${n}" "PNG32:$OUT/$n.png"
done
magick -background none -density 800 "RSVG:$HERE/brand/mark.svg" -resize 824x824 "PNG32:$OUT/mark-824.png"
ls "$OUT"
