# Sourced by scripts/build.sh, scripts/build-macos.sh and scripts/compare-build.sh: hotty-blitz at a
# commit, with the forks its Cargo.toml patches in, from the local repositories
# beside this one (git clone --shared), never from the network. Nothing in
# those repositories changes.

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
  echo "no vello_cpu $2 in $1: tag its commit published-$2" >&2
  return 1
}

# hotty-blitz at <commit> in <work>/hotty-blitz, with the forks its mods/
# describe beside it. <root> holds the repositories: main, blitz, parley,
# vello_cpu, stylo. A Git-based vello set carries both vello_cpu and glifo;
# for an older crates.io set, `make blitz` creates the separate glifo fork.
blitz_tree() { # <root> <commit> <work>
  root=$1; commit=$2; tw=$3
  at "$root/main" "$tw/hotty-blitz" "$commit" main
  B="$tw/hotty-blitz/mods"
  at "$root/blitz" "$tw/blitz" "$(base_of "$B/blitz/mod.md")" hotty
  apply "$tw/blitz" "$B/blitz"
  at "$root/parley" "$tw/parley" "$(base_of "$B/parley/mod.md")" hotty
  apply "$tw/parley" "$B/parley"
  vc_base="$(base_of "$B/vello_cpu/mod.md")"
  if printf '%s\n' "$vc_base" | grep -Eq '^[0-9a-f]{40}$'; then
    if ! git -C "$root/vello_cpu" cat-file -e "$vc_base:vello_cpu/Cargo.toml" 2>/dev/null; then
      echo "vello fork at $root/vello_cpu lacks workspace base $vc_base; move the old fork aside and rerun make blitz in hotty-blitz" >&2
      return 1
    fi
    at "$root/vello_cpu" "$tw/vello_cpu" "$vc_base" hotty
    apply "$tw/vello_cpu" "$B/vello_cpu"
    apply "$tw/vello_cpu" "$B/glifo"
    at "$root/vello_cpu" "$tw/glifo" "$vc_base" hotty
    apply "$tw/glifo" "$B/glifo"
  else
    vc="$(published "$root/vello_cpu" "$vc_base")"
    at "$root/vello_cpu" "$tw/vello_cpu" "$vc" hotty
    apply "$tw/vello_cpu" "$B/vello_cpu"
  fi
  if [ -f "$B/stylo/mod.md" ]; then
    at "$root/stylo" "$tw/stylo" "$(base_of "$B/stylo/mod.md")" hotty
    apply "$tw/stylo" "$B/stylo"
  fi
}

# Sets BLITZ to the hotty-blitz tree to build: the work dir at hotty-blitz-ref
# (made on first use), or HOTTY_BLITZ_DIR, a live checkout, with a banner when
# it is not the pin. Needs HERE (this repository); CACHE defaults like
# build.sh's. Shared by build.sh and build-macos.sh.
select_blitz() {
  CACHE="${CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/hotty}"
  pin="$(grep -v '^#' "$HERE/hotty-blitz-ref" | head -1)"
  if [ -n "${HOTTY_BLITZ_DIR:-}" ]; then
    [ -f "$HOTTY_BLITZ_DIR/crates/hotty-blitz/include/hotty_blitz.h" ] || { echo "HOTTY_BLITZ_DIR=$HOTTY_BLITZ_DIR is no hotty-blitz checkout" >&2; exit 1; }
    BLITZ="$(cd "$HOTTY_BLITZ_DIR" && pwd)"
    at="$(git -C "$BLITZ" rev-parse HEAD 2>/dev/null || echo unknown)"
    dirty="$(git -C "$BLITZ" status --porcelain 2>/dev/null)"
    if [ "$at" != "$pin" ] || [ -n "$dirty" ]; then
      {
        echo "################################################################"
        echo "# NOT THE PIN: hotty-blitz is built from HOTTY_BLITZ_DIR, a live checkout."
        echo "#   checkout:        $BLITZ"
        echo "#   at:              $(echo "$at" | cut -c1-7)$([ -n "$dirty" ] && echo ", DIRTY ($(echo "$dirty" | wc -l | tr -d ' ') changed paths)")"
        echo "#   hotty-blitz-ref: $(echo "$pin" | cut -c1-7)"
        echo "# This is not what CI ships; make check proves nothing about the pin."
        echo "################################################################"
      } >&2
    fi
  else
    # The work dir: one per commit, under the cache that already holds
    # blueprint-compiler, so it lives outside the repository and survives
    # clean checkouts; the pin names it, so a moved pin cannot reuse another's.
    HB="$(dirname "$(dirname "$HERE")")/hotty-blitz"
    sha="$(git -C "$HB/main" rev-parse --verify -q "$pin^{commit}" 2>/dev/null)" || {
      echo "hotty-blitz-ref names $pin, which the hotty-blitz repository at $HB/main does not have." >&2
      echo "Fetch it there: git -C $HB/main fetch origin   (nothing here fetches for you)" >&2
      echo "If the fetch fails (SSH), fix that first; or build a live checkout: HOTTY_BLITZ_DIR=<path>." >&2
      exit 1
    }
    W="$CACHE/hottyterm-build/hotty-blitz-$(echo "$sha" | cut -c1-12)"
    if [ ! -f "$W/.ready" ]; then
      rm -rf "$W.tmp"; mkdir -p "$W.tmp"
      blitz_tree "$HB" "$sha" "$W.tmp"
      rm -rf "$W"; mv "$W.tmp" "$W"; echo "$sha" > "$W/.ready"
    fi
    BLITZ="$W/hotty-blitz"
    # A path new to mise: hotty-blitz's own mise.toml.
    export MISE_TRUSTED_CONFIG_PATHS="$BLITZ${MISE_TRUSTED_CONFIG_PATHS:+:$MISE_TRUSTED_CONFIG_PATHS}"
  fi
}
