#!/bin/sh
# Only on a probe-macos CI runner: exercise AppKit's real watched preference.
# UI scripting changes the setting so NSWorkspace emits its notification.
set -eu
[ "${GITHUB_ACTIONS:-}" = true ] && [ "${RUNNER_OS:-}" = macOS ] || {
    echo 'Run through probe-macos.yml with reduced_motion=true, on its macOS runner.' >&2
    exit 1
}
APP="$1"
OUT="$2/motion"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
python3 -m venv "$OUT/venv"
"$OUT/venv/bin/pip" -q install pillow
set_motion() {
    open 'x-apple.systempreferences:com.apple.Accessibility-Settings.extension?Display'
    osascript - "$1" <<'APPLESCRIPT'
on run argv
    set wanted to (item 1 of argv) as integer
    tell application "System Events"
        tell process "System Settings"
            repeat 60 times
                try
                    repeat with control in (entire contents of window 1)
                        if role of control is "AXCheckBox" and name of control is "Reduce motion" then
                            if (value of control as integer) is not wanted then click control
                            return
                        end if
                    end repeat
                end try
                delay 0.5
            end repeat
            error "Cannot find the Reduce motion checkbox in Accessibility / Display"
        end tell
    end tell
end run
APPLESCRIPT
    osascript -e 'tell application "System Settings" to close every window'
}
wait_for() {
    n=0
    until [ -f "$1" ]; do
        n=$((n + 1))
        [ "$n" -lt 100 ] || { echo "FAIL waiting for $1" >&2; exit 1; }
        sleep .1
    done
    sleep 2
}
shot() {
    open -a "$APP"
    sleep 2
    screencapture -x "$OUT/$1.png"
    "$OUT/venv/bin/python" "$HERE/scripts/reduced-motion-check.py" --assert "$OUT/$1.png" "$2" "$3"
}
# This is the disposable CI runner's config and accessibility setting.
set_motion 1
mkdir -p "$HOME/.config/ghostty"
cat > "$HOME/.config/ghostty/config" <<CFG
command = /usr/bin/python3 $HERE/scripts/reduced-motion-check.py --program $OUT
window-width = 60
window-height = 20
confirm-close-surface = false
quit-after-last-window-closed = true
CFG
open -n -a "$APP"
trap 'osascript -e '\''tell application "hottyterm" to quit'\'' || true' EXIT
wait_for "$OUT/ready"
shot initial reduce 1
set_motion 0
shot changed no-preference 1
touch "$OUT/late"
wait_for "$OUT/late-ready"
shot later no-preference 2
set_motion 1
shot restored reduce 2
