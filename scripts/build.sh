#!/bin/sh
# Builds hottyterm: hotty-blitz as a shared library, then the Ghostty fork.
#
#   scripts/build.sh [ReleaseFast|Debug] [zig build args...]
#
# The fork is at ../ghostty (scripts/fork.sh), hotty-blitz at HOTTY_BLITZ_DIR
# or next to this repository. Two workarounds for this machine, neither needing
# root:
#   - Zig 0.16's own linker cannot link CachyOS's crt1.o (.sframe relocations),
#     so the build uses a copy of Zig's lib dir whose std.Build defaults to LLVM
#     and LLD, passed with --zig-lib-dir.
#   - blueprint-compiler >= 0.16 is not packaged here; a checkout is cached.
#     Ghostty runs it as a system command, and a zig build step fails on any
#     stderr, so a wrapper passes its stderr on only when it fails: 0.16 warns
#     about upstream's unused `using Adw 1;` imports.
set -eu
HERE="$(cd "$(dirname "$0")/.." && pwd)"
FORK="${HOTTYTERM_GHOSTTY:-$(dirname "$HERE")/ghostty}"
OPT="${1:-ReleaseFast}"; [ $# -gt 0 ] && shift
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/hotty"
ZIG="$(cd "$HERE" && mise which zig)"
ZIG_LIB_SRC="$(dirname "$(readlink -f "$ZIG")")/lib"

blitz_dir() {
  for d in "${HOTTY_BLITZ_DIR:-}" "$(dirname "$HERE")/../hotty-blitz/main" "$(dirname "$HERE")/hotty-blitz"; do
    [ -n "$d" ] && [ -f "$d/crates/hotty-blitz/include/hotty_blitz.h" ] && { (cd "$d" && pwd); return; }
  done
  echo "no hotty-blitz checkout: set HOTTY_BLITZ_DIR" >&2; exit 1
}
BLITZ="$(blitz_dir)"

# 1. Zig lib with LLVM + LLD as the default for every compile step.
LIB="$CACHE/zig-lib-llvm"
if [ ! -f "$LIB/.patched" ]; then
  rm -rf "$LIB"; mkdir -p "$(dirname "$LIB")"; cp -r "$ZIG_LIB_SRC" "$LIB"
  sed -i 's/^\(    use_llvm: ?bool = \)null,/\1true,/; s/^\(    use_lld: ?bool = \)null,/\1true,/' \
    "$LIB/std/Build.zig" "$LIB/std/Build/Step/Compile.zig"
  grep -c 'use_llvm: ?bool = true' "$LIB/std/Build.zig" >/dev/null
  touch "$LIB/.patched"
fi

# 2. blueprint-compiler, configured the way meson would.
BPC="$CACHE/blueprint-compiler"
if [ ! -f "$BPC/blueprint-compiler.py" ]; then
  git clone -q --depth 1 --branch v0.16.0 https://gitlab.gnome.org/GNOME/blueprint-compiler.git "$BPC"
fi
BIN="$CACHE/hottyterm-bin"; mkdir -p "$BIN"
sed -e 's|^version = "@VERSION@"|version = "0.16.0"|' \
    -e "s|^module_path = .*|module_path = r\"$BPC\"|" \
    -e 's|^libdir = .*|libdir = r""|' \
    "$BPC/blueprint-compiler.py" > "$BIN/blueprint-compiler.py"
cat > "$BIN/blueprint-compiler" <<WRAP
#!/bin/sh
err=\$(mktemp); python3 "$BIN/blueprint-compiler.py" "\$@" 2>"\$err"; rc=\$?
[ \$rc -ne 0 ] && cat "\$err" >&2; rm -f "\$err"; exit \$rc
WRAP
chmod +x "$BIN/blueprint-compiler"

# 3. hotty-blitz, as the shared library the fork links.
(cd "$BLITZ" && make -s blitz >/dev/null && mise x -- cargo build -q --release -p hotty-blitz)

cd "$FORK"
HOTTY_BLITZ_LIB="$BLITZ/target/release" PATH="$BIN:$PATH" \
  "$ZIG" build --zig-lib-dir "$LIB" -Doptimize="$OPT" "$@"
echo "built $FORK/zig-out/bin/hottyterm against $BLITZ"
