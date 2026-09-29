#!/bin/sh
# The smoke test: hottyterm renders a HOTTY surface natively.
#
#   scripts/smoke.sh [example] [seconds]    # default: dash 6
#
# Runs one of the hotty repository's examples in the built fork on a private
# headless display (hotty-blitz's scripts/headless.sh), screenshots it to
# out/smoke-<example>.png, and checks:
#   - hotty-blitz rendered frames (HOTTY_FRAME_LOG), so the terminal answered
#     the query and placed the surface;
#   - for dash, most frames were partial: the ticks reach the image as kitty
#     frame edits of the damaged rectangles;
#   - the terminal logged no HOTTY or kitty graphics failure.
set -eu
HERE="$(cd "$(dirname "$0")/.." && pwd)"
FORK="${HOTTYTERM_GHOSTTY:-$(dirname "$HERE")/ghostty}"
EX="${1:-dash}"; SECS="${2:-6}"
find_dir() {  # find_dir <file inside> <candidates...>
  f=$1; shift
  for d in "$@"; do [ -n "$d" ] && [ -f "$d/$f" ] && { (cd "$d" && pwd); return; }; done
  return 1
}
BLITZ="$(find_dir crates/hotty-blitz/include/hotty_blitz.h "${HOTTY_BLITZ_DIR:-}" "$(dirname "$HERE")/../hotty-blitz/main")" || { echo "no hotty-blitz checkout: set HOTTY_BLITZ_DIR" >&2; exit 1; }
HOTTY="$(find_dir SPEC.md "${HOTTY_DIR:-}" "$(dirname "$HERE")/../hotty/main")" || { echo "no hotty checkout: set HOTTY_DIR" >&2; exit 1; }
BIN="$FORK/zig-out/bin/ghostty"
[ -x "$BIN" ] || { echo "not built: make build" >&2; exit 1; }

OUT="$HERE/out"; mkdir -p "$OUT"
SWAY="${XDG_CACHE_HOME:-$HOME/.cache}/hotty/sway"
started=""
if [ ! -f "$SWAY/display" ] || [ ! -S "$XDG_RUNTIME_DIR/$(cat "$SWAY/display")" ]; then
  "$BLITZ/scripts/headless.sh" start >/dev/null; started=1
fi
export WAYLAND_DISPLAY="$(cat "$SWAY/display")"
unset DISPLAY HYPRLAND_INSTANCE_SIGNATURE

frames="$OUT/smoke-$EX.frames.tsv"; log="$OUT/smoke-$EX.log"; shot="$OUT/smoke-$EX.png"
rm -f "$frames" "$log" "$shot"
HOTTY_FRAME_LOG="$frames" "$BIN" --class=io.github.neuroplastio.hottyterm --gtk-single-instance=false \
  --window-decoration=false -e python3 "$HOTTY/examples/$EX.py" 2>"$log" &
pid=$!
sleep "$SECS"
grim "$shot"
kill $pid 2>/dev/null || true; wait $pid 2>/dev/null || true
[ -n "$started" ] && "$BLITZ/scripts/headless.sh" stop >/dev/null

fail=0
n=$(grep -vc '^surface' "$frames" 2>/dev/null || true); n=${n:-0}
if [ "$n" -ge 1 ]; then echo "ok   $n frame(s) rendered"; else echo "FAIL no frames: the surface never rendered"; fail=1; fi
if [ "$EX" = dash ]; then
  # damaged_px is column 9; a partial frame damages under half of the largest.
  partial=$(awk -F'\t' 'NR>1 && $1!="surface" {v[NR]=$9; if ($9>m) m=$9} END {c=0; for (i in v) if (v[i] < m/2) c++; print c+0}' "$frames" 2>/dev/null || echo 0)
  if [ "$partial" -ge 3 ]; then echo "ok   $partial partial frame(s)"; else echo "FAIL $partial partial frame(s): updates are not damage-sized"; fail=1; fi
fi
bad=$(grep -cE 'warning\(hotty\)|error\(hotty\)|erroneous kitty graphics' "$log" || true)
if [ "${bad:-0}" -eq 0 ]; then echo "ok   no HOTTY or kitty graphics failures logged"; else echo "FAIL $bad failure(s) in $log:"; grep -E 'hotty|kitty graphics' "$log" | head -5; fail=1; fi
echo "screenshot: $shot"
exit $fail
