#!/bin/sh
# compare-build.sh: one side of a compare pair (docs/compare.md), hottyterm
# as it builds at a commit of this repository, from local checkouts only.
#
#   build = '"$COMPARE_REPO/scripts/compare-build.sh" <ref> [<hotty-blitz ref>]'
#
# In $SIDE_WORK: this repository at <ref>; the Ghostty fork at that tree's
# ghostty-ref, with its mods/ghostty/ and the branding (scripts/brand.py);
# hotty-blitz at its hotty-blitz-ref, or at <hotty-blitz ref> when one is
# given (a pair whose difference is hotty-blitz's), with the Blitz, parley
# and vello_cpu forks from its own mods/, and the Stylo fork where its mods/
# has that set. Each comes from the local repository beside
# this one (git clone --shared), never from the network, and nothing in
# those repositories changes. Then scripts/build.sh, and the result goes
# into $SIDE_DIR (bin/hottyterm). Both sides of a pair build the same way,
# so the difference is only in what <ref> holds.
set -eu
REF="${1:?usage: compare-build.sh <ref> [<hotty-blitz ref>]}"
: "${SIDE_DIR:?run from pairs prepare}" "${SIDE_WORK:?run from pairs prepare}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
CODE="$(dirname "$(dirname "$HERE")")"
W="$SIDE_WORK"

. "$HERE/scripts/lib-blitz.sh"

# hottyterm at <ref>
rm -rf "$W/hottyterm"; mkdir -p "$W/hottyterm"
git -C "$HERE" archive "$REF" | tar -x -C "$W/hottyterm"
H="$W/hottyterm"

# Ghostty: base, the set, the branding
at "$(dirname "$HERE")/ghostty" "$W/ghostty" "$(grep -v '^#' "$H/ghostty-ref" | head -1)" hottyterm
apply "$W/ghostty" "$H/mods/ghostty"
"$H/scripts/brand.py" "$W/ghostty"

# hotty-blitz at the pin, and its forks beside it
HB="$CODE/hotty-blitz"   # main, blitz, parley, vello_cpu, stylo
HBREF="$(git -C "$HB/main" rev-parse --verify "${2:-$(grep -v '^#' "$H/hotty-blitz-ref" | head -1)}^{commit}")"
blitz_tree "$HB" "$HBREF" "$W"

# The two checkouts are new paths to mise: their mise.toml are this
# repository's and hotty-blitz's own.
MISE_TRUSTED_CONFIG_PATHS="$H:$W/hotty-blitz${MISE_TRUSTED_CONFIG_PATHS:+:$MISE_TRUSTED_CONFIG_PATHS}" \
HOTTYTERM_GHOSTTY="$W/ghostty" HOTTY_BLITZ_DIR="$W/hotty-blitz" "$H/scripts/build.sh" ReleaseFast
cp -a "$W/ghostty/zig-out/." "$SIDE_DIR/"
echo "compare-build: hottyterm at $(git -C "$HERE" rev-parse --short "$REF"), hotty-blitz at $(git -C "$HB/main" rev-parse --short "$HBREF"), into $SIDE_DIR"
