#!/bin/sh
# What hottyterm costs on a HOTTY surface, counted per thread (see
# docs/performance.md): runs one of the hotty repository's examples on a
# private headless display (hotty-blitz's scripts/headless.sh), and after a
# warm-up counts its user-space instructions and cycles per thread
# (`perf stat`) and the process's CPU time.
#
#   scripts/perf.sh [rounds] [name=dir]...
#   scripts/perf.sh                                  # the build, one round
#   scripts/perf.sh 5 now= pool=../hotty-blitz/x/target/release
#   scripts/perf.sh 3 before=<unpacked release>/hottyterm now=/usr/lib/hottyterm
#
# Each name is a variant. Its dir is either a build or release with
# bin/hottyterm in it, which runs as it is, or a directory with a
# libhotty_blitz.so, which the binary below runs with (LD_LIBRARY_PATH; an
# empty dir keeps the binary's own). Variants alternate within each round,
# so a change in the machine's load reaches all of them.
# The counts go to out/perf/<name>.<round>.{stat,cpu,log}, and
# scripts/perf-sum.py prints them.
#
# HOTTYTERM_BIN is that binary: the fork's build by default, or a release's
# (the installed /usr/lib/hottyterm/bin/hottyterm takes a library the same
# way, ahead of its RUNPATH).
# PERF_EXAMPLE (dash), PERF_WARMUP (4) and PERF_SECS (10) set the rest.
set -eu
HERE="$(cd "$(dirname "$0")/.." && pwd)"
FORK="${HOTTYTERM_GHOSTTY:-$(dirname "$HERE")/ghostty}"
find_dir() {  # find_dir <file inside> <candidates...>
  f=$1; shift
  for d in "$@"; do [ -n "$d" ] && [ -f "$d/$f" ] && { (cd "$d" && pwd); return; }; done
  return 1
}
BLITZ="$(find_dir crates/hotty-blitz/include/hotty_blitz.h "${HOTTY_BLITZ_DIR:-}" "$(dirname "$HERE")/../hotty-blitz/main")" || { echo "no hotty-blitz checkout: set HOTTY_BLITZ_DIR" >&2; exit 1; }
HOTTY="$(find_dir SPEC.md "${HOTTY_DIR:-}" "$(dirname "$HERE")/../hotty/main")" || { echo "no hotty checkout: set HOTTY_DIR" >&2; exit 1; }
BIN="${HOTTYTERM_BIN:-$FORK/zig-out/bin/hottyterm}"
command -v perf >/dev/null || { echo "perf is not installed" >&2; exit 1; }
EX="${PERF_EXAMPLE:-dash}"; WARM="${PERF_WARMUP:-4}"; SECS="${PERF_SECS:-10}"
ROUNDS=1
case "${1:-}" in [0-9]*) ROUNDS=$1; shift ;; esac
[ $# -gt 0 ] || set -- "build="
for v in "$@"; do
  d=${v#*=}
  [ -n "$d" ] && [ -x "$d/bin/hottyterm" ] && continue
  [ -x "$BIN" ] || { echo "no hottyterm at $BIN: make build, or set HOTTYTERM_BIN" >&2; exit 1; }
done

OUT="$HERE/out/perf"; mkdir -p "$OUT"
SWAY="${XDG_CACHE_HOME:-$HOME/.cache}/hotty/sway"
started=""
if [ ! -f "$SWAY/display" ] || [ ! -S "$XDG_RUNTIME_DIR/$(cat "$SWAY/display")" ]; then
  "$BLITZ/scripts/headless.sh" start >/dev/null; started=1
fi
export WAYLAND_DISPLAY="$(cat "$SWAY/display")"
unset DISPLAY HYPRLAND_INSTANCE_SIGNATURE

cpu() { awk '{print $14 + $15}' "/proc/$1/stat"; }
runs=""
r=0
while [ $r -lt "$ROUNDS" ]; do
  for v in "$@"; do
    name=${v%%=*}; dir=${v#*=}; bin=$BIN; lib=""
    [ -z "$dir" ] || dir="$(cd "$dir" && pwd)"
    if [ -n "$dir" ] && [ -x "$dir/bin/hottyterm" ]; then bin="$dir/bin/hottyterm"; else lib=$dir; fi
    o="$OUT/$name.$r"
    LD_LIBRARY_PATH="$lib" "$bin" --gtk-single-instance=false \
      --window-decoration=false -e python3 "$HOTTY/examples/$EX.py" 2>"$o.log" &
    pid=$!
    sleep "$WARM"
    a=$(cpu $pid)
    perf stat -e instructions:u,cycles:u --per-thread -x, -o "$o.stat" -p $pid -- sleep "$SECS" 2>/dev/null || true
    b=$(cpu $pid)
    echo "cpu_ticks $((b - a)) tick_hz $(getconf CLK_TCK) secs $SECS load $(cut -d' ' -f1 /proc/loadavg) threads $(ls /proc/$pid/task | wc -l)" >"$o.cpu"
    kill $pid 2>/dev/null || true; wait $pid 2>/dev/null || true
    runs="$runs $o"
  done
  r=$((r + 1))
done
[ -n "$started" ] && "$BLITZ/scripts/headless.sh" stop >/dev/null
python3 "$HERE/scripts/perf-sum.py" $runs
