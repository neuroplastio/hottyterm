# Sourced by scripts/build.sh and scripts/compare-build.sh: hotty-blitz at a
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

# hotty-blitz at <commit> in <work>/hotty-blitz, with the Blitz, parley and
# vello_cpu forks from its own mods/ beside it, and the Stylo fork where its
# mods/ has that set. <root> holds the repositories: main, blitz, parley,
# vello_cpu, stylo. (glifo is not cloned: hotty-blitz's `make blitz` makes it
# from the published package.)
blitz_tree() { # <root> <commit> <work>
  root=$1; commit=$2; tw=$3
  at "$root/main" "$tw/hotty-blitz" "$commit" main
  B="$tw/hotty-blitz/mods"
  at "$root/blitz" "$tw/blitz" "$(base_of "$B/blitz/mod.md")" hotty
  apply "$tw/blitz" "$B/blitz"
  at "$root/parley" "$tw/parley" "$(base_of "$B/parley/mod.md")" hotty
  apply "$tw/parley" "$B/parley"
  vc="$(published "$root/vello_cpu" "$(base_of "$B/vello_cpu/mod.md")")"
  at "$root/vello_cpu" "$tw/vello_cpu" "$vc" hotty
  apply "$tw/vello_cpu" "$B/vello_cpu"
  if [ -f "$B/stylo/mod.md" ]; then
    at "$root/stylo" "$tw/stylo" "$(base_of "$B/stylo/mod.md")" hotty
    apply "$tw/stylo" "$B/stylo"
  fi
}
