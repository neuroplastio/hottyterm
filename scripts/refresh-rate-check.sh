#!/bin/sh
# A private headless check that hottyterm paces hotty-blitz to the refresh
# rate of the display its window is on: at start, when the window moves to
# another output, and when that output's mode changes. A program animates a
# surface, and the check reads the rate the terminal hands the host from its
# log, and counts the host's renders a second from HOTTY_TRACE. It ends with
# a graceful close, and fails on any GLib CRITICAL or WARNING.
#
# Run it under a memory cap, e.g.
#   systemd-run --user --scope -q -p MemoryMax=12G -- \
#     env HOTTY_BLITZ_DIR=<hotty-blitz> scripts/refresh-rate-check.sh [out-dir]
set -eu
export GTK_A11Y=none
HERE="$(cd "$(dirname "$0")/.." && pwd)"
FORK="${HOTTYTERM_GHOSTTY:-$(dirname "$HERE")/ghostty}"
: "${HOTTY_BLITZ_DIR:?set HOTTY_BLITZ_DIR}"
OUT="${1:-${XDG_CACHE_HOME:-$HOME/.cache}/hottyterm/refresh-rate}"
rm -rf "$OUT"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}"
# A sway of its own: headless.sh keeps its state under XDG_CACHE_HOME, and
# the sway it fetched is shared.
mkdir -p "$OUT/cache/hotty/sway" "$OUT/config" "$OUT/trace"
ln -sfn "$CACHE/hotty/sway/root" "$OUT/cache/hotty/sway/root"
export XDG_CACHE_HOME="$OUT/cache"
export XDG_CONFIG_HOME="$OUT/config"
pid=""
cleanup() {
    if [ -n "$pid" ]; then kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; fi
    "$HOTTY_BLITZ_DIR/scripts/headless.sh" stop
}
trap cleanup EXIT
"$HOTTY_BLITZ_DIR/scripts/headless.sh" start
export WAYLAND_DISPLAY="$(cat "$XDG_CACHE_HOME/hotty/sway/display")"
export SWAYSOCK="$XDG_RUNTIME_DIR/sway-ipc.$(id -u).$(cat "$XDG_CACHE_HOME/hotty/sway/pid").sock"
unset DISPLAY HYPRLAND_INSTANCE_SIGNATURE
SWAYMSG="env LD_LIBRARY_PATH=$CACHE/hotty/sway/root/usr/lib $CACHE/hotty/sway/root/usr/bin/swaymsg"

LOG="$OUT/terminal.log"
fail() { echo "FAIL: $*" >&2; exit 1; }
# The rate the log says the host was handed last.
rate() { sed -n 's/.*host refresh rate \([0-9]*\) mHz.*/\1/p' "$LOG" | tail -1; }
# expect MHZ WHAT: the host is handed MHZ, and renders the animation at
# that rate a second, within 5% (and no faster).
expect() {
    count=0
    until [ "$(rate)" = "$1" ]; do
        count=$((count + 1))
        [ "$count" -lt 100 ] || fail "$2: the host has $(rate), not $1"
        sleep .1
    done
    sleep .5
    got=$(python3 "$HERE/scripts/refresh-rate-check.py" --renders "$OUT/trace" 2)
    python3 -c "import sys; r, want = float(sys.argv[1]), int(sys.argv[2]) / 1000
sys.exit(0 if .95 * want <= r <= 1.02 * want else 1)" "$got" "$1" ||
        fail "$2: $got renders a second at $1 mHz"
    echo "ok: $2: $1 mHz, $got renders a second"
}

$SWAYMSG -q -- output HEADLESS-1 mode --custom 1200x750@120Hz
$SWAYMSG -q -- create_output
$SWAYMSG -q -- output HEADLESS-2 mode --custom 1200x750@30Hz position 1200 0
HOTTY_TRACE="$OUT/trace" "$FORK/zig-out/bin/hottyterm" --gtk-single-instance=false \
    --window-decoration=false --confirm-close-surface=false --quit-after-last-window-closed=true \
    -e python3 "$HERE/scripts/refresh-rate-check.py" --program "$OUT" >"$OUT/stdout.log" 2>"$LOG" &
pid=$!
i=0
until [ -f "$OUT/ready" ]; do
    i=$((i + 1)); [ "$i" -lt 200 ] || fail "the program did not start"; sleep .1
done
expect 120000 "on the first output"
$SWAYMSG -q -- "[pid=$pid]" move container to output HEADLESS-2
expect 30000 "moved to the second output"
$SWAYMSG -q -- output HEADLESS-2 mode --custom 1200x750@144Hz
expect 144000 "the second output's mode changed"
$SWAYMSG -q -- "[pid=$pid]" move container to output HEADLESS-1
expect 120000 "moved back"

# A graceful close: the window goes, and the surface is finalized.
$SWAYMSG -q -- "[pid=$pid]" kill
i=0
while kill -0 "$pid" 2>/dev/null; do
    i=$((i + 1)); [ "$i" -lt 50 ] || fail "still running 5 s after the window closed"; sleep .1
done
wait "$pid" || true
pid=""
if grep -n 'CRITICAL\|WARNING' "$LOG" | grep -i 'glib\|gtk\|gdk\|gobject'; then
    fail "GLib complained (above)"
fi
echo "ok: closed, with no GLib CRITICAL or WARNING"
