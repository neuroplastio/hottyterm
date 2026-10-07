#!/usr/bin/env bash
#
# Publish hottyterm-bin to the AUR: a hottyterm release's Linux build.
#
#   packaging/aur/publish.sh <release> [--push]
#
# <release> is a hottyterm release (26.10.06-dev.a6cdd4d), whose commit this
# checkout has: the package's version counts the commits up to it. The
# package moves when the release does, or when packaging/aur/PKGBUILD changes:
#
#   • the AUR has no hottyterm-bin yet, or another version: <pkgver>-1;
#   • the same version and another PKGBUILD: the next pkgrel;
#   • otherwise there is nothing to publish.
#
# Either way the package is built as a user's makepkg would build it, from the
# GitHub release, before anything is pushed. Without --push it stops there and
# shows what it would publish. Needs makepkg, so an Arch system. --push writes
# with AUR_SSH_PRIVATE_KEY when set (the CI path: a key of the AUR account the
# package belongs to), and with your own SSH setup otherwise.
set -euo pipefail

if [ $# -lt 1 ] || [ $# -gt 2 ] || { [ $# -eq 2 ] && [ "$2" != --push ]; }; then
	echo "usage: $0 <release> [--push]" >&2
	exit 2
fi
release=$1 push=${2:-}
here=$(cd "$(dirname "$0")" && pwd)
pkg=hottyterm-bin
tarball="hottyterm-$release-linux-x86_64.tar.gz"

# 26.10.06-dev.a6cdd4d is 26.10.06.r<commits>.a6cdd4d.
day=${release%%-dev.*} short=${release##*-dev.}
case "$release" in
[0-9][0-9].[0-9][0-9].[0-9][0-9]-dev.[0-9a-f]*) ;;
*) echo "publish: $release is not a hottyterm release (YY.MM.DD-dev.<commit>)" >&2; exit 1 ;;
esac
commit=$(git -C "$here" rev-parse --verify -q "$short^{commit}") ||
	{ echo "publish: this checkout has no commit $short" >&2; exit 1; }
pkgver="$day.r$(git -C "$here" rev-list --count "$commit").$short"

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

sha256=$(curl -fsSL "https://github.com/neuroplastio/hottyterm/releases/download/$release/SHA256SUMS" |
	awk -v f="$tarball" '$2 == f { print $1 }')
[ -n "$sha256" ] || { echo "publish: $release's SHA256SUMS names no $tarball" >&2; exit 1; }

if [ -n "$push" ]; then
	if [ -n "${AUR_SSH_PRIVATE_KEY:-}" ]; then
		printf '%s\n' "$AUR_SSH_PRIVATE_KEY" > "$work/key"
		chmod 600 "$work/key"
		# The AUR's host key; its fingerprint is on https://aur.archlinux.org.
		echo "aur.archlinux.org ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEuBKrPzbawxA/k2g6NcyV5jmqwJ2s+zpgZGZ7tpLIcN" > "$work/known_hosts"
		export GIT_SSH_COMMAND="ssh -i $work/key -o IdentitiesOnly=yes -o UserKnownHostsFile=$work/known_hosts"
	fi
	remote=ssh://aur@aur.archlinux.org/$pkg.git
else
	remote=https://aur.archlinux.org/$pkg.git
fi
# A package nobody has published yet clones as an empty repository, and has
# no .SRCINFO.
git -c init.defaultBranch=master -c advice.defaultBranchName=false \
	clone -q "$remote" "$work/aur" 2>&1 | grep -v 'cloned an empty repository' >&2 || true
test -d "$work/aur/.git"

srcinfo() {
	[ -f "$work/aur/.SRCINFO" ] || return 0
	sed -n "s/^\t$1 = //p" "$work/aur/.SRCINFO" | head -n 1
}
cur_ver=$(srcinfo pkgver)
cur_rel=$(srcinfo pkgrel)

render() {
	sed -e "s/@PKGVER@/$1/" -e "s/@PKGREL@/$2/" -e "s/@RELEASE@/$release/" -e "s/@SHA256@/$sha256/" \
		"$here/PKGBUILD"
}

if [ -z "$cur_ver" ]; then
	rel=1 why="hottyterm-bin's first version"
elif [ "$pkgver" != "$cur_ver" ]; then
	rel=1 why="hottyterm $release"
elif render "$cur_ver" "$cur_rel" | cmp -s - "$work/aur/PKGBUILD"; then
	echo "hottyterm-bin $cur_ver-$cur_rel is hottyterm $release already; nothing to publish"
	exit 0
else
	rel=$((cur_rel + 1)) why="the PKGBUILD changed; still hottyterm $release"
fi

render "$pkgver" "$rel" > "$work/aur/PKGBUILD"
cd "$work/aur"
makepkg --printsrcinfo > .SRCINFO

# Build it as a user's makepkg would: fetched from the GitHub release, its
# sha256 checked, packaged. Everything makepkg writes stays in $work.
PKGDEST="$work/out" SRCDEST="$work/src" BUILDDIR="$work/build" \
	makepkg --force --nodeps --noconfirm >"$work/makepkg.log" 2>&1 ||
	{ cat "$work/makepkg.log" >&2; exit 1; }
built=$(ls "$work/out"/*.pkg.tar.*)
bsdtar -tf "$built" > "$work/files"
for f in usr/bin/hottyterm usr/lib/hottyterm/bin/hottyterm usr/lib/hottyterm/lib/libhotty_blitz.so \
	usr/lib/hottyterm/share/ghostty/themes/ \
	usr/share/applications/io.github.neuroplastio.hottyterm.desktop \
	usr/share/dbus-1/services/io.github.neuroplastio.hottyterm.service \
	usr/lib/systemd/user/app-io.github.neuroplastio.hottyterm.service \
	usr/share/licenses/hottyterm-bin/THIRD-PARTY-NOTICES.txt; do
	grep -qx "$f" "$work/files" || { echo "$built has no $f" >&2; exit 1; }
done
# The desktop's files name the installed command, not where CI built it.
mkdir "$work/pkg"
bsdtar -xf "$built" -C "$work/pkg" usr/share usr/lib/systemd
if grep -rl "zig-out" "$work/pkg"; then
	echo "$built still names the build's path in the files above" >&2
	exit 1
fi

echo "hottyterm-bin $pkgver-$rel: $why"
git add --intent-to-add PKGBUILD .SRCINFO
git --no-pager diff --stat
if [ -z "$push" ]; then
	git --no-pager diff
	echo "(not pushed: run with --push to publish)"
	exit 0
fi
git add PKGBUILD .SRCINFO
git -c user.name="HOTTY Agent" -c user.email="hotty@neuroplast.io" \
	commit -q -m "$pkgver-$rel: $why"
git push -q origin HEAD:master
echo "published https://aur.archlinux.org/packages/$pkg"
