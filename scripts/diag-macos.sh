#!/bin/sh
# What hottyterm costs a Mac while it looks idle, for a bug report. Run it
# on the Mac where hottyterm uses the CPU:
#
#   sh diag-macos.sh           # the hottyterm that is running, as it is
#   sh diag-macos.sh --trace   # and then a traced one you start your programs in
#   sh diag-macos.sh --trace-dir DIR   # the running one, started traced:
#       open -a hottyterm --env HOTTY_TRACE=DIR
#
# It writes hottyterm-diag-<time>/ and a .tar.gz of it in the current
# directory, holding hottyterm's own numbers only:
#   about.txt    hottyterm's version, when it started, the displays' refresh
#   <phase>/     cpu.txt (its CPU over the phase, per thread, wakeups) and
#                sample.txt (macOS `sample` of hottyterm alone, call stacks)
#   trace/       with --trace: hottyterm's and hotty-blitz's stage stamps
#                (docs/trace.md): names, times and sizes, no contents
# No screenshots, nothing about other programs, no environment. The home
# folder, the user name and the Mac's names are replaced, and `sample`'s
# list of loaded libraries is left out. Read it before you send it.
#
# The phases, each SECS (15) long, wait for Enter: shown (the window as it
# is when it's slow) and hidden (minimised). No root needed.
set -u
SECS="${SECS:-15}"
TRACE=0
TRACE_DIR=
case "${1:-}" in
--trace) TRACE=1 ;;
--trace-dir) TRACE_DIR="${2:?--trace-dir needs the directory HOTTY_TRACE named}" ;;
esac
[ "$(uname)" = Darwin ] || { echo "This is for macOS." >&2; exit 1; }

OUT="$PWD/hottyterm-diag-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"

pids() { pgrep -f "${APP:-hottyterm.app}/Contents/MacOS/"; }
cputime() { ps -o time= -p "$1" | awk -F'[:.]' '{ s = 0; for (i = 1; i < NF; i++) s = s * 60 + $i; printf "%.2f", s + $NF / 100 }'; }
# DIAG_YES=1 (the probe runner) waits for nobody, and minimises by itself.
wait_enter() {
    if [ -n "${DIAG_YES:-}" ]; then
        case "$1" in *minimise*) osascript -e 'tell application "System Events" to keystroke "m" using command down' >/dev/null 2>&1; sleep 3 ;; esac
        return
    fi
    printf '%s\n  then press Enter: ' "$1"; read -r _ </dev/tty
}

# Measures pid $1 into $OUT/$2: CPU over SECS, threads, wakeups, a sample.
measure() {
    pid="$1"; dir="$OUT/$2"; mkdir -p "$dir"
    echo "  measuring $2 for ${SECS}s..."
    a=$(cputime "$pid")
    top -l 2 -s "$SECS" -pid "$pid" -stats pid,cpu,th,wq,idlew,power > "$dir/top.txt" 2>&1
    b=$(cputime "$pid")
    {
        echo "$2: $(echo "$a $b $SECS" | awk '{printf "%.2f s of CPU over %d s (%.1f%%)", $2 - $1, $3, 100 * ($2 - $1) / $3}')"
        echo "top (second sample is the phase; IDLEW = wakeups):"
        awk '/^PID/ { n++ } n == 2' "$dir/top.txt"
        echo "threads:"
        ps -M -p "$pid"
    } > "$dir/cpu.txt" 2>&1
    rm -f "$dir/top.txt"
    sample "$pid" 10 -mayDie -file "$dir/sample.txt" >/dev/null 2>&1 || echo "  (sample failed)"
    head -1 "$dir/cpu.txt" | sed 's/^/  /'
}

PID=$(pids | tail -1)
if [ -n "$PID" ]; then
    BIN=$(ps -o comm= -p "$PID")
    APP=${BIN%%/Contents/MacOS/*}
else
    APP=/Applications/hottyterm.app
fi
[ -d "$APP" ] || { echo "No hottyterm running and none at $APP." >&2; exit 1; }

{
    echo "app version: $(defaults read "$APP/Contents/Info.plist" CFBundleShortVersionString 2>/dev/null)"
    echo "app installed: $(stat -f %Sm -t '%Y-%m-%d %H:%M' "$APP")"
    [ -n "$PID" ] && echo "running since: $(ps -o lstart= -p "$PID")"
    echo "macOS: $(sw_vers -productVersion) on $(sysctl -n machdep.cpu.brand_string)"
    echo "displays:"
    system_profiler SPDisplaysDataType 2>/dev/null | grep -E 'Resolution|Refresh|ProMotion' | sed 's/^ */  /'
} > "$OUT/about.txt"
cat "$OUT/about.txt"
started=
[ -n "$PID" ] && started=$(date -j -f '%a %b %e %T %Y' "$(ps -o lstart= -p "$PID" | tr -s ' ')" +%s 2>/dev/null)
if [ -n "$started" ] && [ "$(stat -f %m "$APP")" -gt "$started" ]; then
    echo "NOTE: this hottyterm started before the app was last updated: it may be the old version. Quit it (Cmd+Q) and start it again first."
fi

if [ -n "$PID" ]; then
    echo
    echo "1. The hottyterm that is running (pid $PID)."
    wait_enter "  Leave it as it is when it's slow (don't touch it while it's measured),"
    measure "$PID" shown
    wait_enter "  Now minimise every hottyterm window (Cmd+M),"
    measure "$PID" hidden
fi

if [ -n "$TRACE_DIR" ] && [ -n "$PID" ]; then
    # The running hottyterm's own stamps, named by its pid.
    mkdir -p "$OUT/trace"
    for f in "$TRACE_DIR"/hottyterm-"$PID".jsonl "$TRACE_DIR"/blitz-"$PID".jsonl; do
        [ -f "$f" ] && cp "$f" "$OUT/trace/"
    done
    [ -n "$(ls "$OUT/trace")" ] || echo "  No trace of pid $PID in $TRACE_DIR: was it started with HOTTY_TRACE=$TRACE_DIR?"
fi

if [ "$TRACE" = 1 ]; then
    echo
    echo "2. A traced hottyterm, in a window of its own."
    mkdir -p "$OUT/trace"
    before=$(pids | tr '\n' ' ')
    open -n -a "$APP" --env "HOTTY_TRACE=$OUT/trace"
    sleep 3
    TPID=
    for p in $(pids); do
        case " $before " in *" $p "*) ;; *) TPID=$p ;; esac
    done
    if [ -z "$TPID" ]; then
        echo "  The traced hottyterm did not start."
    else
        wait_enter "  In the new window, start what you usually run there (plx...) until it's slow,"
        measure "$TPID" traced-shown
        wait_enter "  Now minimise that window (Cmd+M),"
        measure "$TPID" traced-hidden
        kill -TERM "$TPID" 2>/dev/null
        sleep 2
        echo "  The traced hottyterm was closed."
    fi
    # Only hottyterm's and hotty-blitz's stamps: programs started in the
    # traced window wrote their own, which stay out.
    find "$OUT/trace" -type f ! -name 'hottyterm-*.jsonl' ! -name 'blitz-*.jsonl' -delete
fi

# What could name the Mac or its user goes.
user=$(id -un)
names="$(scutil --get ComputerName 2>/dev/null)
$(scutil --get LocalHostName 2>/dev/null)
$(hostname -s)
$(hostname)"
for f in $(find "$OUT" -name '*.txt'); do
    awk '/^Binary Images:/ { exit } !/^(Path|Parent Process|Responsible|User ID|Date\/Time|Launch Time|Analysis Tool|Physical footprint|Report Version):/' "$f" > "$f.tmp"
    mv "$f.tmp" "$f"
done
for f in $(find "$OUT" -type f); do
    sed -i '' -e "s#$HOME#~#g" -e "s#/Users/$user#~#g" -e "s#[[:<:]]$user[[:>:]]#<user>#g" "$f"
    echo "$names" | sort -u | while read -r n; do
        [ -n "$n" ] && sed -i '' -e "s#$n#<mac>#g" "$f"
    done
done

COPYFILE_DISABLE=1 tar -czf "$OUT.tar.gz" -C "$(dirname "$OUT")" "$(basename "$OUT")"
echo
echo "Done: $OUT.tar.gz ($(du -h "$OUT.tar.gz" | cut -f1)). Look through $OUT before you send it."
