#!/bin/sh
# compare-sway.sh: a private headless sway to try a pair in (docs/compare.md),
# never the user's display.
#
#   scripts/compare-sway.sh start      start it (or say it runs)
#   eval "$(scripts/compare-sway.sh env)"
#                                      SWAYSOCK, COMPARE_SWAYMSG, and test
#                                      dirs for COMPARE_CACHE/VERDICTS, with
#                                      COMPARE_NO_DISPATCH=1
#   pairs --wm sway <pair>   (scripts/compare.py)
#   scripts/compare-sway.sh shot F.png a screenshot of it (grim)
#   scripts/compare-sway.sh stop
#
# It runs in a runtime dir of its own, short and under /run/user/<uid> (a
# socket path's limit), with `bus` and `systemd` linked from the user's, so
# `uwsm app` reaches the user manager as it does on the desktop. State is in
# ~/.cache/compare/sway/: runtime, pid, config, sway.log, and the test cache
# and verdicts. `stop` kills only the pid in its pid file, and only while
# that process runs in this runtime dir.
#
# The sway build is the one hotty-blitz's scripts/headless.sh fetches into
# ~/.cache/hotty/sway/root (SWAY_ROOT overrides it).
set -eu
STATE="${XDG_CACHE_HOME:-$HOME/.cache}/compare/sway"
ROOT="${SWAY_ROOT:-${XDG_CACHE_HOME:-$HOME/.cache}/hotty/sway/root}"
UID_RT="/run/user/$(id -u)"
mkdir -p "$STATE"

running() {
  [ -s "$STATE/pid" ] && [ -s "$STATE/runtime" ] || return 1
  p="$(cat "$STATE/pid")"
  kill -0 "$p" 2>/dev/null && tr '\0' '\n' < "/proc/$p/environ" 2>/dev/null |
    grep -qx "XDG_RUNTIME_DIR=$(cat "$STATE/runtime")"
}

case "${1:-}" in
start)
  if running; then echo "compare sway: running (pid $(cat "$STATE/pid"))"; exit 0; fi
  [ -x "$ROOT/usr/bin/sway" ] || { echo "compare-sway.sh: no sway at $ROOT (run hotty-blitz's scripts/headless.sh once)" >&2; exit 1; }
  rt="$(mktemp -d "$UID_RT/cs.XXX")"
  chmod 700 "$rt"
  ln -s "$UID_RT/bus" "$rt/bus"
  ln -s "$UID_RT/systemd" "$rt/systemd"
  echo "$rt" > "$STATE/runtime"
  printf '%s\n' 'output HEADLESS-1 resolution 1920x1080 scale 1' 'default_border none' \
    'focus_follows_mouse no' 'xwayland disable' > "$STATE/config"
  # A clean environment: nothing of the user's session, no PLX_* or terminal state.
  setsid sh -c "echo \$\$ > '$STATE/pid'; exec env -i HOME='$HOME' USER='$USER' LOGNAME='$USER' \
    SHELL=/bin/sh LANG=C.UTF-8 PATH='$HOME/.local/bin:/usr/bin:/bin' XDG_RUNTIME_DIR='$rt' \
    XDG_CURRENT_DESKTOP=sway DBUS_SESSION_BUS_ADDRESS='unix:path=$UID_RT/bus' \
    WLR_BACKENDS=headless WLR_RENDERER=gles2 WLR_LIBINPUT_NO_DEVICES=1 \
    LD_LIBRARY_PATH='$ROOT/usr/lib' '$ROOT/usr/bin/sway' -c '$STATE/config'" \
    > "$STATE/sway.log" 2>&1 < /dev/null &
  i=0
  while ! ls "$rt" | grep -q '^sway-ipc'; do
    i=$((i + 1))
    [ $i -lt 100 ] || { echo "compare-sway.sh: sway didn't start; see $STATE/sway.log" >&2; exit 1; }
    sleep 0.1
  done
  echo "compare sway: started (pid $(cat "$STATE/pid"), runtime $rt)"
  ;;
env)
  running || { echo "compare-sway.sh: not running; start it first" >&2; exit 1; }
  rt="$(cat "$STATE/runtime")"
  mkdir -p "$STATE/cache" "$STATE/verdicts"
  printf 'export SWAYSOCK=%s\n' "$(ls "$rt"/sway-ipc.*.sock | head -1)"
  printf 'export COMPARE_SWAYMSG=%s\n' "$(cd "$(dirname "$0")" && pwd)/compare-sway.sh"
  printf 'export COMPARE_CACHE=%s COMPARE_VERDICTS=%s COMPARE_NO_DISPATCH=1\n' "$STATE/cache" "$STATE/verdicts"
  ;;
shot)
  running || { echo "compare-sway.sh: not running" >&2; exit 1; }
  rt="$(cat "$STATE/runtime")"
  env -u WAYLAND_DISPLAY XDG_RUNTIME_DIR="$rt" WAYLAND_DISPLAY="$(ls "$rt" | grep -E '^wayland-[0-9]+$' | head -1)" grim "${2:?shot needs a file}"
  ;;
stop)
  if running; then kill -TERM "$(cat "$STATE/pid")"; echo "compare sway: stopped"; fi
  rt="$(cat "$STATE/runtime" 2>/dev/null || true)"
  rm -f "$STATE/pid" "$STATE/runtime"
  case "$rt" in "$UID_RT"/cs.*) rm -f "$rt/bus" "$rt/systemd"; rmdir "$rt" 2>/dev/null || true ;; esac
  ;;
*)
  # As COMPARE_SWAYMSG: swaymsg from the same build.
  exec env LD_LIBRARY_PATH="$ROOT/usr/lib" "$ROOT/usr/bin/swaymsg" "$@"
  ;;
esac
