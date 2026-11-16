#!/bin/sh
# Only on a probe-macos CI runner (emoji=true): hottyterm draws
# scripts/probe/emoji.stream, a row of emoji in the cells and the same row in
# a hotty surface, and the window is captured to <out dir>/emoji/emoji.png.
# The cells' emoji should be Noto Color Emoji's, drawn by CoreText from the
# sbix copy (mods/ghostty/emoji-noto.md), not Apple's; the surface's are
# hotty-blitz's. Judged by eye: Apple's emoji are on the runner too, so a
# missing sbix would still draw in colour.
#
#   scripts/probe-macos-emoji.sh /Applications/hottyterm.app <out dir>
set -eu
[ "${GITHUB_ACTIONS:-}" = true ] && [ "${RUNNER_OS:-}" = macOS ] || {
    echo 'Run through probe-macos.yml with emoji=true, on its macOS runner.' >&2
    exit 1
}
APP="$1"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$2/emoji"
OUT="$(cd "$2/emoji" && pwd)"

python3 -m venv "$OUT/venv"
"$OUT/venv/bin/pip" -q install pyobjc-framework-Quartz

mkdir -p "$HOME/.config/ghostty"
cat > "$HOME/.config/ghostty/config" <<CFG
command = /bin/sh -c 'cat $HERE/scripts/probe/emoji.stream; sleep 120'
window-width = 80
window-height = 8
background = #1b1b1e
confirm-close-surface = false
quit-after-last-window-closed = true
CFG
"$APP/Contents/MacOS/ghostty" >"$OUT/app.log" 2>&1 &
pid=$!
trap 'kill $pid 2>/dev/null || true' EXIT
sleep 8

# The app's largest on-screen window.
wid=$("$OUT/venv/bin/python" -I - "$pid" <<'PY'
import sys
import Quartz
pid = int(sys.argv[1])
wins = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID)
mine = [w for w in wins if w.get("kCGWindowOwnerPID") == pid and w.get("kCGWindowLayer") == 0]
if not mine:
    sys.exit("no window for pid %d" % pid)
area = lambda w: w["kCGWindowBounds"]["Width"] * w["kCGWindowBounds"]["Height"]
print(max(mine, key=area)["kCGWindowNumber"])
PY
)
screencapture -x -o -l "$wid" "$OUT/emoji.png"
grep -iE 'font|emoji|hotty' "$OUT/app.log" | head -40 || true
echo "captured window $wid: $OUT/emoji.png"
