#!/bin/sh
# Run the unchanged hit vectors end to end on a private headless display.
# A second argument of versions checks 0.8/0.7 negotiation instead.
# Invoke under the brief's systemd resource cap, like the other checks.
set -eu
HERE="$(cd "$(dirname "$0")/.." && pwd)"
FORK="${HOTTYTERM_GHOSTTY:-$(dirname "$HERE")/ghostty}"
: "${HOTTY_BLITZ_DIR:?set HOTTY_BLITZ_DIR}"
: "${HOTTY_DIR:?set HOTTY_DIR}"
OUT="${1:-$HOME/.cache/hotty-agent/0.8/hottyterm/hit}"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}"
mkdir -p "$OUT/cache/hotty/sway" "$OUT/config"
ln -sfn "$CACHE/hotty/sway/root" "$OUT/cache/hotty/sway/root"
export XDG_CACHE_HOME="$OUT/cache" XDG_CONFIG_HOME="$OUT/config" GTK_A11Y=none
pid=""
cleanup() {
    if [ -n "$pid" ]; then kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; fi
    "$HOTTY_BLITZ_DIR/scripts/headless.sh" stop
}
trap cleanup EXIT
"$HOTTY_BLITZ_DIR/scripts/headless.sh" start
export WAYLAND_DISPLAY="$(cat "$XDG_CACHE_HOME/hotty/sway/display")"
unset DISPLAY HYPRLAND_INSTANCE_SIGNATURE
rm -f "$OUT/result.json"
"$FORK/zig-out/bin/hottyterm" --gtk-single-instance=false --window-decoration=false \
    -e python3 "$HERE/scripts/hit-check.py" "$OUT/result.json" "${2:-hit}" >"$OUT/stdout.log" 2>"$OUT/terminal.log" &
pid=$!
n=0
until [ -f "$OUT/result.json" ]; do
    n=$((n + 1))
    [ "$n" -lt 400 ] || { echo 'FAIL: hit probe produced no result' >&2; exit 1; }
    sleep .1
done
python3 - "$OUT/result.json" <<'PY'
import json, sys
result = json.load(open(sys.argv[1]))
if not result['ok']:
    raise SystemExit(result['error'])
for case in result['vectors']:
    print(f"ok {case['queries']} queries: {case['name']}")
PY
