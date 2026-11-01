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

# A fresh clone of a local repository, at a commit, on a branch of that name.
at() { # <repo> <dir> <commit> <branch>
  rm -rf "$2"
  git clone -q --shared --no-checkout "$1" "$2"
  git -C "$2" checkout -q -B "$4" "$3"
}
apply() { # <dir> <patches dir>
  set -- "$1" "$2"/*.patch
  dir="$1"; shift
  [ -e "$1" ] && git -C "$dir" am -q "$@"
  return 0
}
base_of() { sed -n 's/^base:[[:space:]]*\([^[:space:]#]*\).*/\1/p' "$1"; }
# vello_cpu's base is a crates.io version, the commit hotty-blitz's
# scripts/vello-fork.sh makes of that package: the fork's tag `published`,
# or `published-<version>` for another version.
published() { # <fork> <version>
  for t in $(git -C "$1" for-each-ref --format='%(refname)' refs/tags/published 'refs/tags/published-*'); do
    [ "$(git -C "$1" log -1 --format=%s "$t")" = "vello_cpu $2 as published on crates.io" ] && { echo "$t"; return 0; }
  done
  echo "compare-build: $1 has no vello_cpu $2: tag its commit published-$2" >&2
  return 1
}

# hottyterm at <ref>
rm -rf "$W/hottyterm"; mkdir -p "$W/hottyterm"
git -C "$HERE" archive "$REF" | tar -x -C "$W/hottyterm"
H="$W/hottyterm"

# Ghostty: base, the set, the branding
at "$(dirname "$HERE")/ghostty" "$W/ghostty" "$(grep -v '^#' "$H/ghostty-ref" | head -1)" hottyterm
apply "$W/ghostty" "$H/mods/ghostty"
"$H/scripts/brand.py" "$W/ghostty"

# hotty-blitz at the pin, and its forks beside it
HB="$CODE/hotty-blitz"
HBREF="$(git -C "$HB/main" rev-parse --verify "${2:-$(grep -v '^#' "$H/hotty-blitz-ref" | head -1)}^{commit}")"
at "$HB/main" "$W/hotty-blitz" "$HBREF" main
B="$W/hotty-blitz/mods"
at "$HB/blitz" "$W/blitz" "$(base_of "$B/blitz/mod.md")" hotty
apply "$W/blitz" "$B/blitz"
at "$HB/parley" "$W/parley" "$(base_of "$B/parley/mod.md")" hotty
apply "$W/parley" "$B/parley"
VC="$(published "$HB/vello_cpu" "$(base_of "$B/vello_cpu/mod.md")")"
at "$HB/vello_cpu" "$W/vello_cpu" "$VC" hotty
apply "$W/vello_cpu" "$B/vello_cpu"
if [ -f "$B/stylo/mod.md" ]; then
  at "$HB/stylo" "$W/stylo" "$(base_of "$B/stylo/mod.md")" hotty
  apply "$W/stylo" "$B/stylo"
fi

# The two checkouts are new paths to mise: their mise.toml are this
# repository's and hotty-blitz's own.
MISE_TRUSTED_CONFIG_PATHS="$H:$W/hotty-blitz${MISE_TRUSTED_CONFIG_PATHS:+:$MISE_TRUSTED_CONFIG_PATHS}" \
HOTTYTERM_GHOSTTY="$W/ghostty" HOTTY_BLITZ_DIR="$W/hotty-blitz" "$H/scripts/build.sh" ReleaseFast
cp -a "$W/ghostty/zig-out/." "$SIDE_DIR/"
echo "compare-build: hottyterm at $(git -C "$HERE" rev-parse --short "$REF"), hotty-blitz at $(git -C "$HB/main" rev-parse --short "$HBREF"), into $SIDE_DIR"
