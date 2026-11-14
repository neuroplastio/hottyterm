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
  if [ -e "$1" ]; then git -C "$dir" am -q "$@"; fi
}
base_of() { sed -n 's/^base:[[:space:]]*\([^[:space:]#]*\).*/\1/p' "$1"; }
field_of() { sed -n "s/^$2:[[:space:]]*\\([^[:space:]#]*\\).*/\\1/p" "$1"; }
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
# describe beside it. A set's URL basename names its local repository and
# checkout unless mod.md specifies source-path or fork-path; additional-sets
# are applied to the same checkout after that set.
blitz_tree() { # <root> <commit> <work>
  root=$1; commit=$2; tw=$3
  at "$root/main" "$tw/hotty-blitz" "$commit" main || return 1
  B="$tw/hotty-blitz/mods"
  for set_path in "$B"/*/mod.md; do
    [ -f "$set_path" ] || continue
    set_name=$(basename "$(dirname "$set_path")")
    set_url=$(field_of "$set_path" url)
    set_repo=${set_url%/}; set_repo=${set_repo##*/}; set_repo=${set_repo%.git}
    set_source=$(field_of "$set_path" source-path)
    set_fork=$(field_of "$set_path" fork-path)
    set_extra=$(field_of "$set_path" additional-sets)
    set_base=$(base_of "$set_path")
    [ -n "$set_repo" ] && [ -n "$set_base" ] || { echo "Missing url or base in $set_path" >&2; return 1; }

    # Pins predating these metadata fields used a Vello workspace with two
    # sets and a local repository called vello_cpu, not the URL's basename.
    if [ "$set_repo" = vello ] && [ -z "$set_source" ] && [ -z "$set_fork" ]; then
      case "$set_name" in
        vello_cpu) set_source=vello_cpu; set_fork=vello_cpu; [ ! -f "$B/glifo/mod.md" ] || set_extra=glifo ;;
        glifo) set_source=vello_cpu; set_fork=glifo ;;
      esac
      # The older crates.io layout used a separate glifo fork created by
      # hotty-blitz's own setup, rather than a shared Git workspace.
      if ! printf '%s\n' "$set_base" | grep -Eq '^[0-9a-f]{40}$'; then
        [ "$set_name" != glifo ] || continue
        [ "$set_name" != vello_cpu ] || set_extra=
      fi
    fi
    set_source=${set_source:-$set_repo}
    set_fork=${set_fork:-$set_repo}
    for set_relative in "$set_source" "$set_fork"; do
      case "$set_relative" in /*|..|../*|*/../*|*/..) echo "Invalid fork path $set_relative in $set_path" >&2; return 1 ;; esac
    done
    if ! git -C "$root/$set_source" rev-parse --git-dir >/dev/null 2>&1; then
      echo "No local $set_name repository at $root/$set_source; clone $set_url there before building this hotty-blitz pin." >&2
      return 1
    fi
    if ! printf '%s\n' "$set_base" | grep -Eq '^[0-9a-f]{40}$'; then
      if [ "$set_name" != vello_cpu ]; then echo "Invalid base $set_base in $set_path" >&2; return 1; fi
      set_base=$(published "$root/$set_source" "$set_base") || return 1
    fi
    at "$root/$set_source" "$tw/$set_fork" "$set_base" hotty || return 1
    apply "$tw/$set_fork" "$(dirname "$set_path")" || return 1
    set_list=$(printf '%s' "$set_extra" | tr ',' ' ')
    for extra_name in $set_list; do
      extra_path="$B/$extra_name/mod.md"
      if [ ! -f "$extra_path" ] || [ "$(base_of "$extra_path")" != "$(base_of "$set_path")" ] || [ "$(field_of "$extra_path" url)" != "$set_url" ]; then
        echo "Additional set $extra_name does not share $set_name's source and base" >&2
        return 1
      fi
      apply "$tw/$set_fork" "$B/$extra_name" || return 1
    done
  done
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
