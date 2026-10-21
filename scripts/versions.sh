#!/bin/sh
# What a person reads hottyterm's version by (gov P-5 rule 6), as key=value
# lines: CI appends them to $GITHUB_OUTPUT, the build scripts eval them.
#
#   scripts/versions.sh [<hotty-blitz checkout>]
#
#   version=26.10.21-dev.1e81d70   the release's name, from this checkout's
#                                  HEAD: its UTC day and short commit
#   hotty=0.4                      the hotty version hotty-blitz speaks
#   blitz=0.4.0                    hotty-blitz's version
#   label=26.10.21-dev.1e81d70 · hotty 0.4 (hotty-blitz 0.4.0)
#
# Without a checkout, only version.
set -eu
HERE="$(cd "$(dirname "$0")/.." && pwd)"
version="$(TZ=UTC git -C "$HERE" show -s --date=format-local:%y.%m.%d --format=%cd HEAD)-dev.$(git -C "$HERE" rev-parse --short=7 HEAD)"
echo "version=$version"
[ $# -gt 0 ] || exit 0

BLITZ=$1
[ -f "$BLITZ/crates/hotty-blitz/src/lib.rs" ] || { echo "versions.sh: $BLITZ is no hotty-blitz checkout" >&2; exit 1; }
hotty="$(sed -n 's/^pub const VERSION: &str = "\([^"]*\)";$/\1/p' "$BLITZ/crates/hotty-blitz/src/lib.rs")"
blitz="$(sed -n 's/^version = "\([^"]*\)"$/\1/p' "$BLITZ/Cargo.toml" | head -1)"
[ -n "$hotty" ] || { echo "versions.sh: no VERSION in $BLITZ/crates/hotty-blitz/src/lib.rs" >&2; exit 1; }
[ -n "$blitz" ] || { echo "versions.sh: no workspace version in $BLITZ/Cargo.toml" >&2; exit 1; }
echo "hotty=$hotty"
echo "blitz=$blitz"
echo "label=$version · hotty $hotty (hotty-blitz $blitz)"
