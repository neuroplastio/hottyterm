#!/bin/sh
# Writes the fork's commits since ghostty-ref back to patches/, replacing
# what is there. Run after every change to the fork.
#
#   scripts/export.sh
set -eu
HERE="$(cd "$(dirname "$0")/.." && pwd)"
FORK="${HOTTYTERM_GHOSTTY:-$(dirname "$HERE")/ghostty}"
REV="$(grep -v '^#' "$HERE/ghostty-ref" | head -1)"
rm -f "$HERE"/patches/*.patch
git -C "$FORK" format-patch -q --no-signature --zero-commit -o "$HERE/patches" "$REV..hottyterm"
ls "$HERE"/patches
