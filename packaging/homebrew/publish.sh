#!/usr/bin/env bash
#
# Publish hottyterm's Homebrew cask to the org tap `neuroplastio/homebrew-tap`
# (installed with `brew install --cask neuroplastio/tap/hottyterm`).
#
#   packaging/homebrew/publish.sh <release> [--push]
#
# <release> is a hottyterm release (26.10.06-dev.a6cdd4d). The script downloads
# that release's macOS app and SHA256SUMS, checks one against the other, renders
# `Casks/hottyterm.rb` from `packaging/homebrew/hottyterm.rb` with the app's
# sha256, and (with `--push`) commits and pushes it to the tap.
#
# Needs curl, sha256sum (or shasum) and git. On --push it uses HOMEBREW_TAP_TOKEN
# when set (the CI path), and your own git credentials otherwise.
set -euo pipefail

if [ $# -lt 1 ] || [ $# -gt 2 ] || { [ $# -eq 2 ] && [ "$2" != --push ]; }; then
	echo "usage: $0 <release> [--push]" >&2
	exit 2
fi
release=$1 push=${2:-}
here=$(cd "$(dirname "$0")" && pwd)
tap=neuroplastio/homebrew-tap
urlbase="https://github.com/neuroplastio/hottyterm/releases/download/$release"
app="hottyterm-$release-macos-arm64.zip"

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

sum() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }

curl -fsSL "$urlbase/$app" -o "$work/$app"
curl -fsSL "$urlbase/SHA256SUMS" -o "$work/SHA256SUMS"
sha256=$(sum "$work/$app")
if ! grep -qx "$sha256  $app" "$work/SHA256SUMS"; then
	echo "publish: $app does not match the release's SHA256SUMS" >&2
	exit 1
fi

if [ -n "$push" ] && [ -n "${HOMEBREW_TAP_TOKEN:-}" ]; then
	remote="https://x-access-token:$HOMEBREW_TAP_TOKEN@github.com/$tap.git"
else
	remote="https://github.com/$tap.git"
fi
git clone -q "$remote" "$work/tap"
mkdir -p "$work/tap/Casks"
sed -e "s/@VERSION@/$release/" -e "s/@SHA256@/$sha256/" "$here/hottyterm.rb" > "$work/tap/Casks/hottyterm.rb"

cd "$work/tap"
git add Casks/hottyterm.rb
if git diff --cached --quiet; then
	echo "hottyterm $release: the cask is unchanged; nothing to publish"
	exit 0
fi
git --no-pager diff --cached --stat
if [ -z "$push" ]; then
	echo "(not pushed: run with --push to publish)"
	exit 0
fi
git -c user.name="HOTTY Agent" -c user.email="hotty@neuroplast.io" \
	commit -q -m "hottyterm $release"
# Other projects publish to the tap too: one may land first.
branch=$(git symbolic-ref --short HEAD)
for attempt in 1 2 3; do
	git push -q origin HEAD && break
	[ "$attempt" -lt 3 ] || exit 1
	git pull -q --rebase origin "$branch"
done
echo "published https://github.com/$tap"
