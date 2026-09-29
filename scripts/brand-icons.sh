#!/bin/sh
# Renders brand/icon.svg to the PNGs that replace upstream's icons
# (brand/icons; brand/brand.toml says where they go). Run after changing the icon; commit the PNGs.
set -eu
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$HERE/brand/icons"
mkdir -p "$OUT"
for n in 16 32 64 128 256 512 1024 2048; do
  magick -background none -density 400 "RSVG:$HERE/brand/icon.svg" -resize "${n}x${n}" "PNG32:$OUT/$n.png"
done
ls "$OUT"
