#!/bin/sh
# Builds hottyterm: hotty-blitz as a shared library, then the Ghostty fork.
#
#   scripts/build.sh [ReleaseFast|Debug] [zig build args...]
#
# The fork is at ../ghostty (scripts/fork.sh). hotty-blitz is built at the
# commit in hotty-blitz-ref, the one CI and every release build, in a work
# dir of its own: a clone of the local hotty-blitz repository (the sibling
# ../../hotty-blitz/main) with the forks its mods/ describe, as
# scripts/lib-blitz.sh makes them. No checkout of anyone's is built. The
# commit must be in that repository; if it is not, the build stops and says
# how to fetch it. The work dir is kept per commit, so cargo stays
# incremental.
#
# To develop against a live checkout instead: HOTTY_BLITZ_DIR=<path>. It is
# built as it is, working-tree changes included, and the build says loudly
# when that is not the pin. CI sets it to its own checkout, which is the pin.
#
# One workaround for this machine, not needing
# root: blueprint-compiler >= 0.20 is not packaged here, so a checkout is
# cached, one per version. Ghostty runs it as a system command, and a zig
# build step fails on any stderr, so a wrapper passes its stderr on only when
# it fails: it warns about upstream's unused `using Adw 1;` imports.
set -eu
HERE="$(cd "$(dirname "$0")/.." && pwd)"
FORK="${HOTTYTERM_GHOSTTY:-$(dirname "$HERE")/ghostty}"
OPT="${1:-ReleaseFast}"; [ $# -gt 0 ] && shift
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/hotty"
ZIG="$(cd "$HERE" && mise which zig)"

. "$HERE/scripts/lib-blitz.sh"
select_blitz

# 1. blueprint-compiler, configured the way meson would.
# Ghostty's build checks the version (src/apprt/gtk/build/blueprint.zig).
BPC_VERSION=0.20.4
BPC="$CACHE/blueprint-compiler-$BPC_VERSION"
if [ ! -f "$BPC/blueprint-compiler.py" ]; then
  git -c advice.detachedHead=false clone -q --depth 1 --branch "v$BPC_VERSION" \
    https://gitlab.gnome.org/GNOME/blueprint-compiler.git "$BPC"
fi
BIN="$CACHE/hottyterm-bin"; mkdir -p "$BIN"
sed -e "s|^version = \"@VERSION@\"|version = \"$BPC_VERSION\"|" \
    -e "s|^module_path = .*|module_path = r\"$BPC\"|" \
    -e 's|^libdir = .*|libdir = r""|' \
    "$BPC/blueprint-compiler.py" > "$BIN/blueprint-compiler.py"
cat > "$BIN/blueprint-compiler" <<WRAP
#!/bin/sh
err=\$(mktemp); python3 "$BIN/blueprint-compiler.py" "\$@" 2>"\$err"; rc=\$?
[ \$rc -ne 0 ] && cat "\$err" >&2; rm -f "\$err"; exit \$rc
WRAP
chmod +x "$BIN/blueprint-compiler"

# 2. hotty-blitz, as the shared library the fork links.
(cd "$BLITZ" && make -s blitz >/dev/null && mise x -- cargo build -q --release -p hotty-blitz)

# 3. The name a person reads the version by (gov P-5 rule 6), which --version
# and the About window show (mods/ghostty/version-label.md).
LABEL="$("$HERE/scripts/versions.sh" "$BLITZ" | sed -n 's/^label=//p')"

cd "$FORK"
HOTTY_BLITZ_LIB="$BLITZ/target/release" HOTTYTERM_LABEL="$LABEL" PATH="$BIN:$PATH" \
  "$ZIG" build -Doptimize="$OPT" "$@"
echo "built $FORK/zig-out/bin/hottyterm against hotty-blitz $(git -C "$BLITZ" rev-parse --short=7 HEAD) in $BLITZ"
