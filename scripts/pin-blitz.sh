#!/bin/sh
# Pins hotty-blitz: writes the commit that CI builds, and so every release, to
# hotty-blitz-ref. Without an argument, hotty-blitz's main as pushed.
#
#   scripts/pin-blitz.sh [<commit>]
#
# CI checks the commit out from GitHub, so it must be on hotty-blitz's
# origin/main. Commit hotty-blitz-ref (with the patches that need it, if any):
# the push builds both platforms and releases.
set -eu
HERE="$(cd "$(dirname "$0")/.." && pwd)"

blitz_dir() {
  for d in "${HOTTY_BLITZ_DIR:-}" "$(dirname "$HERE")/../hotty-blitz/main" "$(dirname "$HERE")/hotty-blitz"; do
    [ -n "$d" ] && [ -f "$d/crates/hotty-blitz/include/hotty_blitz.h" ] && { (cd "$d" && pwd); return; }
  done
  echo "no hotty-blitz checkout: set HOTTY_BLITZ_DIR" >&2; exit 1
}
BLITZ="$(blitz_dir)"

git -C "$BLITZ" fetch -q origin
want="$(git -C "$BLITZ" rev-parse --verify -q "${1:-origin/main}^{commit}")" ||
  { echo "pin-blitz: $BLITZ has no commit ${1:-origin/main}" >&2; exit 1; }
git -C "$BLITZ" merge-base --is-ancestor "$want" origin/main ||
  { echo "pin-blitz: $want is not on hotty-blitz's origin/main: push it first" >&2; exit 1; }
old="$(grep -v '^#' "$HERE/hotty-blitz-ref" | head -1)"
short() { git -C "$BLITZ" rev-parse --short "$1"; }
if [ "$want" = "$old" ]; then
  echo "hotty-blitz-ref pins $(short "$want") already"
  exit 0
fi
echo "$want" > "$HERE/hotty-blitz-ref"
if git -C "$BLITZ" merge-base --is-ancestor "$old" "$want" 2>/dev/null; then
  git -C "$BLITZ" --no-pager log --oneline "$old..$want"
fi
echo "hotty-blitz-ref: $(short "$old") -> $(short "$want")"
