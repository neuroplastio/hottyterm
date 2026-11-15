#!/bin/sh
# Only on a probe-macos CI runner: use the real system preference, with a
# probe-only injected notification. No System Settings AX tree is involved.
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
: > "$OUT/actions.log"
rm -f "$OUT/probe-signing.log" "$OUT/app.log"
pid=""
refresh_attempted=0
live_mode=real
last_action="setup"
log() {
    last_action="$*"
    printf '%s\n' "$*" | tee -a "$OUT/actions.log"
}
cleanup() {
    rc=$?
    trap - EXIT
    if [ -n "$pid" ]; then kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; fi
    if [ "$rc" -ne 0 ]; then
        printf 'FAIL motion probe (exit %s), last action: %s\n' "$rc" "$last_action" >&2
        defaults read com.apple.universalaccess reduceMotion >&2 || true
        for file in actions.log signing.log probe-signing.log app.log motion-window.json; do
            if [ -f "$OUT/$file" ]; then printf 'Diagnostics: %s\n' "$file" >&2; cat "$OUT/$file" >&2; fi
        done
    fi
    exit "$rc"
}
trap cleanup EXIT
log 'Scope: startup defaults/getter are real. Live checks get ONE bounded system-refresh attempt, then explicitly SIMULATE the getter if it stays stale. Injected notifications test our observer; this does NOT prove macOS posts a notification for a real setting change.'
log "Inspect signing: codesign -d --verbose=4 $APP"
codesign -d --verbose=4 "$APP" 2>"$OUT/signing.log"
cat "$OUT/signing.log"
PROBE_APP="$APP"
if grep -Eq 'flags=.*(runtime|library-validation|restrict)' "$OUT/signing.log"; then
    PROBE_APP="$OUT/hottyterm.app"
    log "Restricted signature: copying $APP to $PROBE_APP and signing the probe copy ad hoc, flags=0"
    ditto "$APP" "$PROBE_APP"
    codesign --force --deep --sign - --options 0 "$PROBE_APP"
    codesign -d --verbose=4 "$PROBE_APP" 2>"$OUT/probe-signing.log"
    cat "$OUT/probe-signing.log"
    if grep -Eq 'flags=.*(runtime|library-validation|restrict)' "$OUT/probe-signing.log"; then
        log 'FAIL: the probe copy still restricts DYLD_INSERT_LIBRARIES'
        exit 1
    fi
else
    log 'Signature permits injection; using the original app without re-signing'
fi
log 'Compile and ad-hoc sign the probe-only AppKit notification helper'
xcrun clang -dynamiclib -fobjc-arc -fblocks -framework AppKit -framework CoreFoundation \
    "$HERE/scripts/probe-macos-motion-notify.m" -o "$OUT/motion-notify.dylib"
codesign --force --sign - "$OUT/motion-notify.dylib"
python3 -m venv "$OUT/venv"
"$OUT/venv/bin/pip" -q install pillow
wait_for() {
    n=0
    until [ -f "$1" ]; do
        n=$((n + 1))
        [ "$n" -lt "${2:-100}" ] || { log "FAIL waiting for $1"; exit 1; }
        sleep .1
    done
}
request_motion() {
    rm -f "$OUT/motion-ack"
    log "Request in-process notification; live getter mode=$live_mode"
    notifyutil -p io.github.neuroplastio.hottyterm.probe.motion
    wait_for "$OUT/motion-ack"
    actual=$(cat "$OUT/motion-ack")
    log "AppKit getter after injected notification => $actual (expected $want; mode=$live_mode)"
}
set_motion() {
    want="$1"
    if [ "$want" = 1 ]; then bool=true; else bool=false; fi
    previous=$(defaults read com.apple.universalaccess reduceMotion 2>&1) || previous="unavailable: $previous"
    log "Setting reduceMotion: previous=$previous; defaults write com.apple.universalaccess reduceMotion -bool $bool"
    defaults write com.apple.universalaccess reduceMotion -bool "$bool"
    actual=$(defaults read com.apple.universalaccess reduceMotion)
    log "defaults read com.apple.universalaccess reduceMotion => $actual (expected $want)"
    [ "$actual" = "$want" ] || { log 'FAIL: defaults did not retain the requested preference'; exit 1; }
    if [ -n "$pid" ]; then
        printf '%s\n' "$want" > "$OUT/motion-value"
        request_motion
        if [ "$actual" != "$want" ] && [ "$refresh_attempted" = 0 ]; then
            refresh_attempted=1
            log 'ONE system-refresh attempt: at most 15 seconds scanning/posting UniversalAccess candidates; never repeated'
            "$OUT/venv/bin/python" "$HERE/scripts/probe-macos-motion-refresh.py" "$OUT/motion-notifications.txt" > "$OUT/motion-refresh.log" 2>&1
            cat "$OUT/motion-refresh.log"
            rm -f "$OUT/motion-refresh-ack"
            notifyutil -p io.github.neuroplastio.hottyterm.probe.motion.refresh
            wait_for "$OUT/motion-refresh-ack" 20
            sleep 1
            request_motion
        fi
        if [ "$actual" != "$want" ] && [ "$live_mode" = real ]; then
            live_mode=simulated
            printf 'simulate\n' > "$OUT/motion-mode"
            log 'SIMULATED macOS live path: system getter stayed stale; swizzling the getter to the probe value and testing ONLY the observer. No more system-refresh attempts.'
            request_motion
        fi
        [ "$actual" = "$want" ] || { log 'FAIL: live observer getter did not return the requested probe value'; exit 1; }
    fi
}
shot() {
    log "Screenshot $1: expect $2 on $3 surface(s)"
    open -a "$PROBE_APP"
    sleep 2
    rm -f "$OUT/motion-window.json"
    notifyutil -p io.github.neuroplastio.hottyterm.probe.motion.bounds
    wait_for "$OUT/motion-window.json"
    cp "$OUT/motion-window.json" "$OUT/motion-$1.json"
    window_id=$("$OUT/venv/bin/python" "$HERE/scripts/probe-macos-motion-crop.py" --window-id "$OUT/motion-$1.json")
    log "Capture window $window_id, then crop to its AppKit content bounds (excluding title bar)"
    screencapture -x -o -l "$window_id" "$OUT/$1.png"
    "$OUT/venv/bin/python" "$HERE/scripts/probe-macos-motion-crop.py" \
        "$OUT/$1.png" "$OUT/motion-$1.json" "$OUT/$1-content.png"
    "$OUT/venv/bin/python" "$HERE/scripts/reduced-motion-check.py" --assert "$OUT/$1-content.png" "$2" "$3"
}
# This is the disposable CI runner's config and accessibility setting.
rm -f "$OUT/ready" "$OUT/late" "$OUT/late-ready" "$OUT/motion-loaded" "$OUT/motion-ack" "$OUT/panel-pixels" \
    "$OUT/motion-mode" "$OUT/motion-value" "$OUT/motion-refresh-ack" "$OUT/motion-refresh.log" "$OUT/motion-notifications.txt"
set_motion 1
mkdir -p "$HOME/.config/ghostty"
cat > "$HOME/.config/ghostty/config" <<CFG
command = /usr/bin/python3 $HERE/scripts/reduced-motion-check.py --program $OUT
window-width = 60
window-height = 20
confirm-close-surface = false
quit-after-last-window-closed = true
CFG
log "Fresh startup: DYLD_INSERT_LIBRARIES=$OUT/motion-notify.dylib $PROBE_APP/Contents/MacOS/ghostty"
HOTTY_MOTION_PROBE_DIR="$OUT" DYLD_INSERT_LIBRARIES="$OUT/motion-notify.dylib" \
    "$PROBE_APP/Contents/MacOS/ghostty" >"$OUT/app.log" 2>&1 &
pid=$!
wait_for "$OUT/motion-loaded"
actual=$(cat "$OUT/motion-loaded")
log "Injected helper loaded; startup AppKit getter => $actual (expected 1)"
[ "$actual" = 1 ] || { log 'FAIL: fresh AppKit process did not read reduceMotion=true'; exit 1; }
wait_for "$OUT/ready"
sleep 2
shot initial reduce 1
set_motion 0
shot changed no-preference 1
touch "$OUT/late"
wait_for "$OUT/late-ready"
shot later no-preference 2
set_motion 1
shot restored reduce 2
log "Result: startup REAL; live getter mode=$live_mode; system-refresh attempts=$refresh_attempted (maximum 1). Live notification delivery was injected."
