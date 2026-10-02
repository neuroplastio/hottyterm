#!/bin/sh
# Builds hottyterm.app on macOS (Apple silicon), the way CI does:
#
#   scripts/build-macos.sh              # out/hottyterm.app
#
# 1. hotty-blitz as a static library;
# 2. GhosttyKit, the framework the app links (upstream's build; the HOTTY
#    code in it calls hotty-blitz's C ABI);
# 3. the app with Xcode, in the ReleaseLocal configuration, which signs ad
#    hoc and needs no developer team, linking hotty-blitz's static library.
#
# Needs Xcode 26 (xcode-select), mise (Zig here, Rust in hotty-blitz), the
# fork at ../ghostty (scripts/fork.sh) and hotty-blitz next to this
# repository or at HOTTY_BLITZ_DIR.
set -eu
HERE="$(cd "$(dirname "$0")/.." && pwd)"
FORK="${HOTTYTERM_GHOSTTY:-$(dirname "$HERE")/ghostty}"
ZIG="$(cd "$HERE" && mise which zig)"

blitz_dir() {
  for d in "${HOTTY_BLITZ_DIR:-}" "$(dirname "$HERE")/../hotty-blitz/main" "$(dirname "$HERE")/hotty-blitz"; do
    [ -n "$d" ] && [ -f "$d/crates/hotty-blitz/include/hotty_blitz.h" ] && { (cd "$d" && pwd); return; }
  done
  echo "no hotty-blitz checkout: set HOTTY_BLITZ_DIR" >&2; exit 1
}
BLITZ="$(blitz_dir)"
LIB="$BLITZ/target/release"

echo "== hotty-blitz"
(cd "$BLITZ" && make -s blitz >/dev/null && mise x -- cargo build --release -p hotty-blitz)

echo "== GhosttyKit"
cd "$FORK"
HOTTY_BLITZ_LIB="$LIB" "$ZIG" build -Doptimize=ReleaseFast -Dcpu=baseline -Demit-macos-app=false -Dxcframework-target=native

echo "== the app"
# hotty-blitz goes into the app's own link, not into GhosttyKit's archive:
# no upstream build change, and libtool's warnings about Rust's empty
# objects would fail zig build. Its Rust standard library also wants
# libiconv, which the app does not link otherwise.
cd "$FORK/macos"
# Apple silicon only: GhosttyKit (-Dxcframework-target=native) and hotty-blitz
# are built for this machine, and ReleaseLocal would also build x86_64.
# Swift packages (Sparkle) are checked out where scripts/notices.py finds
# their licences.
xcodebuild -target Ghostty -configuration ReleaseLocal ARCHS=arm64 ONLY_ACTIVE_ARCH=YES \
  -clonedSourcePackagesDirPath "$FORK/macos/build/SourcePackages" \
  OTHER_LDFLAGS="\$(inherited) -liconv $LIB/libhotty_blitz.a"

NAME="$(python3 -c 'import sys, tomllib; print(tomllib.load(open(sys.argv[1], "rb"))["identity"]["name"])' "$HERE/brand/brand.toml")"
APP="$HERE/out/$NAME.app"
mkdir -p "$HERE/out"
rm -rf "$APP"
cp -R build/ReleaseLocal/Ghostty.app "$APP"

# The licence and the third-party notices go into the app's resources.
cp "$HERE/LICENSE" "$APP/Contents/Resources/LICENSE"
python3 "$HERE/scripts/notices.py" --platform macos-arm64 --target aarch64-apple-darwin \
  --fork "$FORK" --blitz "$BLITZ" \
  --extra Sparkle https://github.com/sparkle-project/Sparkle "$FORK/macos/build/SourcePackages/checkouts/Sparkle" \
  -o "$APP/Contents/Resources/THIRD-PARTY-NOTICES.txt"

# The menu bar shows CFBundleName, which Xcode sets to the product name
# (brand/brand.toml explains). Set it here, then sign again ad hoc, keeping
# the entitlements.
plutil -replace CFBundleName -string "$NAME" "$APP/Contents/Info.plist"
codesign --force --sign - --preserve-metadata=entitlements,requirements,flags,runtime "$APP"
codesign --verify --deep "$APP"
echo "built $APP"
