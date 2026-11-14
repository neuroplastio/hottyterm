#!/bin/sh
# Exercise generic set discovery with local synthetic repositories only.
set -eu
HERE=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
LIB=${1:-"$HERE/scripts/lib-blitz.sh"}
case "$LIB" in /*) ;; *) LIB="$HERE/$LIB" ;; esac
scratch=$(mktemp -d "${TMPDIR:-/tmp}/hottyterm-forks.XXXXXXXX")
trap 'rm -rf "$scratch"' EXIT HUP INT TERM
export GIT_AUTHOR_NAME='hotty Agent' GIT_AUTHOR_EMAIL=hotty@neuroplast.io
export GIT_COMMITTER_NAME='hotty Agent' GIT_COMMITTER_EMAIL=hotty@neuroplast.io

mkdir -p "$scratch/root" "$scratch/work"
git init -q "$scratch/root/upstream"
printf 'base\n' > "$scratch/root/upstream/base.txt"
git -C "$scratch/root/upstream" add base.txt
git -C "$scratch/root/upstream" commit -qm base
base=$(git -C "$scratch/root/upstream" rev-parse HEAD)
mkdir -p "$scratch/root/main/mods/alpha" "$scratch/root/main/mods/beta"
printf 'alpha\n' > "$scratch/root/upstream/alpha.txt"
git -C "$scratch/root/upstream" add alpha.txt
git -C "$scratch/root/upstream" commit -qm alpha
git -C "$scratch/root/upstream" format-patch -1 --stdout > "$scratch/root/main/mods/alpha/0001-alpha.patch"
git -C "$scratch/root/upstream" checkout -q --detach "$base"
printf 'beta\n' > "$scratch/root/upstream/beta.txt"
git -C "$scratch/root/upstream" add beta.txt
git -C "$scratch/root/upstream" commit -qm beta
git -C "$scratch/root/upstream" format-patch -1 --stdout > "$scratch/root/main/mods/beta/0001-beta.patch"
cat > "$scratch/root/main/mods/alpha/mod.md" <<EOF
---
url: https://example.test/shared
base: $base
source-path: upstream
fork-path: workspace
additional-sets: beta
---
EOF
cat > "$scratch/root/main/mods/beta/mod.md" <<EOF
---
url: https://example.test/shared
base: $base
source-path: upstream
fork-path: beta
---
EOF
git init -q "$scratch/root/main"
git -C "$scratch/root/main" add mods
git -C "$scratch/root/main" commit -qm host
host=$(git -C "$scratch/root/main" rev-parse HEAD)

. "$LIB"
blitz_tree "$scratch/root" "$host" "$scratch/work"
test "$(cat "$scratch/work/workspace/alpha.txt")" = alpha
test "$(cat "$scratch/work/workspace/beta.txt")" = beta
test "$(cat "$scratch/work/beta/beta.txt")" = beta
test ! -e "$scratch/work/beta/alpha.txt"
if apply "$scratch/work/workspace" "$scratch/root/main/mods/alpha" >"$scratch/apply-error" 2>&1; then
  echo 'a patch that does not apply unexpectedly succeeded' >&2
  exit 1
fi
mv "$scratch/root/upstream" "$scratch/root/moved"
mkdir -p "$scratch/missing"
if blitz_tree "$scratch/root" "$host" "$scratch/missing" 2>"$scratch/error"; then
  echo 'missing repository unexpectedly succeeded' >&2
  exit 1
fi
grep -q 'No local alpha repository' "$scratch/error"
echo 'lib-blitz: metadata-driven forks and missing-repository error pass'
