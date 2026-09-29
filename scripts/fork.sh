#!/bin/sh
# Sets up the Ghostty fork at ../ghostty: upstream at ghostty-ref, branch
# `hottyterm`, with patches/*.patch applied and the branding generated on top
# (scripts/brand.py). It stays local; a GitHub fork of a public repository
# would be public.
#
#   scripts/fork.sh
set -eu
HERE="$(cd "$(dirname "$0")/.." && pwd)"
FORK="${HOTTYTERM_GHOSTTY:-$(dirname "$HERE")/ghostty}"
REV="$(grep -v '^#' "$HERE/ghostty-ref" | head -1)"

if [ -d "$FORK/.git" ]; then
  # Already there: say where it stands against the patches, change nothing.
  have=$(git -C "$FORK" rev-list --count "$REV..hottyterm" 2>/dev/null || echo "?")
  want=$(ls "$HERE"/patches/*.patch 2>/dev/null | wc -l)
  echo "ghostty fork at $FORK: $have commit(s) on ${REV%${REV#????????}}, $want patch(es) in patches/"
  exit 0
fi

git init -q "$FORK"
git -C "$FORK" remote add origin https://github.com/ghostty-org/ghostty
git -C "$FORK" fetch -q --depth 200 origin "$REV"
git -C "$FORK" checkout -q -b hottyterm "$REV"
git -C "$FORK" am -q "$HERE"/patches/*.patch
"$HERE/scripts/brand.py" "$FORK"
echo "ghostty fork ready at $FORK"
