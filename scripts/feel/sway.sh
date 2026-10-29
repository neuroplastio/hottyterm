#!/bin/sh
# sway.sh: the latency rig's private headless sway (gov R-22, docs/feel.md).
#
#   scripts/feel/sway.sh start [scale]   start it (scale 2 by default); if it
#                                        runs already, only set the scale
#   scripts/feel/sway.sh scale <s>       set the running one's scale (1, 1.6, 2…)
#   scripts/feel/sway.sh status
#   scripts/feel/sway.sh stop
#
# Hold the lock around a whole run, and always with -o:
#
#   mkdir -p ~/.cache/hotty/sway-feel
#   flock -o ~/.cache/hotty/sway-feel/lock sh -c '
#     scripts/feel/sway.sh start 2 && ...run... ; scripts/feel/sway.sh stop'
#
# -o matters: without it, flock leaves the lock's fd open in the command, a
# sway started under the lock inherits it, and the lock stays held for as long
# as that sway lives. (This script also closes fds 3-9 for sway, but the
# terminals a run starts inherit the fd too.) hotty-perf and plx-perf share
# this script and this lock.
#
# State is in ~/.cache/hotty/sway-feel/: display (its WAYLAND_DISPLAY), pid,
# ipc (its IPC socket, sway-ipc.<uid>.<pid>.sock), config, sway.log. It is not
# the screenshot sway (~/.cache/hotty/sway, hotty-blitz's scripts/headless.sh):
# this script never touches that one, nor the user's own session. `stop` kills
# only the pid in its own pid file, and only if that is a sway on this config.
#
# The display: one output, HEADLESS-1, 2400x1500 at 60 Hz. No borders, so one
# window tiles the whole output; focus doesn't follow the mouse; no Xwayland.
# The cursor theme is blank: on a headless output the cursor is always drawn
# into the frame (screencopy's overlay_cursor=0 can't take a software cursor
# out), so a visible one would turn every pointer move into a change of pixels.
# Clients that set cursors by shape (cursor-shape-v1: GTK 4, Chromium) get the
# blank one; a client that uploads its own cursor image would still show it.
set -eu
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/hotty"
STATE="$CACHE/sway-feel"
OUTPUT=HEADLESS-1
mkdir -p "$STATE"

# The sway build: hotty-blitz's headless.sh fetches it (no root) into
# ~/.cache/hotty/sway/root; without that, fetch our own copy.
root() {
  if [ -n "${SWAY_ROOT:-}" ]; then echo "$SWAY_ROOT"; return; fi
  if [ -x "$CACHE/sway/root/usr/bin/sway" ]; then echo "$CACHE/sway/root"; return; fi
  if [ ! -x "$STATE/root/usr/bin/sway" ]; then
    mkdir -p "$STATE/pkgs" "$STATE/root"
    for u in $(pacman -Sp sway wlroots0.20 2>/dev/null); do
      case "$u" in
        file://*) cp "${u#file://}" "$STATE/pkgs/" ;;
        http*) (cd "$STATE/pkgs" && curl -sSfLO "$u") ;;
      esac
    done
    for f in "$STATE"/pkgs/*.pkg.tar.zst; do tar --zstd -C "$STATE/root" -xf "$f"; done
  fi
  echo "$STATE/root"
}
ROOT="$(root)"

swaymsg() {
  LD_LIBRARY_PATH="$ROOT/usr/lib" "$ROOT/usr/bin/swaymsg" -s "$(cat "$STATE/ipc")" "$@"
}

# ours <pid>: that pid is a sway running on our config.
ours() {
  [ -r "/proc/$1/cmdline" ] || return 1
  cmd="$(tr '\0' '\n' < "/proc/$1/cmdline" 2>/dev/null)" || return 1
  printf '%s\n' "$cmd" | head -1 | grep -q '/sway$' || return 1
  printf '%s\n' "$cmd" | grep -qx -- "$STATE/config"
}

running() {
  [ -s "$STATE/pid" ] && ours "$(cat "$STATE/pid")"
}

clean() {
  rm -f "$STATE/pid" "$STATE/display" "$STATE/ipc" "$STATE/ready" "$STATE/ready.tmp"
}

# A cursor theme of one transparent image under every name a client asks by:
# an Xcursor file (header, one table entry, a 16x16 image at nominal size 24,
# its pixels all 0). 16 px, not 1: wlroots divides the image by the scale,
# and a cursor of 0 px aborts sway (wlr_swapchain_create's assertion).
blank_cursors() {
  d="$STATE/icons/feel-blank/cursors"
  mkdir -p "$d"
  printf 'Xcur\020\000\000\000\000\000\001\000\001\000\000\000\002\000\375\377\030\000\000\000\034\000\000\000\044\000\000\000\002\000\375\377\030\000\000\000\001\000\000\000\020\000\000\000\020\000\000\000\000\000\000\000\000\000\000\000\000\000\000\000' > "$d/default"
  head -c 1024 /dev/zero >> "$d/default"
  for n in context-menu help pointer progress wait cell crosshair text vertical-text \
    alias copy move no-drop not-allowed grab grabbing e-resize n-resize ne-resize \
    nw-resize s-resize se-resize sw-resize w-resize ew-resize ns-resize nesw-resize \
    nwse-resize col-resize row-resize all-scroll zoom-in zoom-out dnd-ask all-resize \
    left_ptr xterm hand1 hand2 watch left_ptr_watch fleur question_arrow \
    sb_h_double_arrow sb_v_double_arrow top_left_corner top_right_corner \
    bottom_left_corner bottom_right_corner top_side bottom_side left_side right_side \
    ibeam X_cursor; do
    ln -sf default "$d/$n"
  done
  printf '[Icon Theme]\nName=feel-blank\n' > "$STATE/icons/feel-blank/index.theme"
}

status() {
  if ! running; then echo "perf sway: not running"; return 1; fi
  echo "perf sway: pid $(cat "$STATE/pid"), WAYLAND_DISPLAY=$(cat "$STATE/display"), ipc $(cat "$STATE/ipc")"
  swaymsg -p -t get_outputs | grep -E '^Output|Current mode|Scale factor' | sed 's/^/  /'
}

set_scale() {
  swaymsg output "$OUTPUT" scale "$1" >/dev/null
}

cmd="${1:-start}"
case "$cmd" in
start)
  scale="${2:-2}"
  if running; then
    set_scale "$scale"
    status
    exit 0
  fi
  clean
  blank_cursors
  cat > "$STATE/ready.sh" <<'SH'
#!/bin/sh
# Run by the perf sway once it is up (`exec` in its config): its sockets.
d="$(dirname "$0")"
printf '%s\n%s\n' "$WAYLAND_DISPLAY" "$SWAYSOCK" > "$d/ready.tmp" && mv "$d/ready.tmp" "$d/ready"
SH
  chmod +x "$STATE/ready.sh"
  cat > "$STATE/config" <<CFG
# Written by scripts/feel/sway.sh: the latency rig's perf sway.
output $OUTPUT mode 2400x1500@60Hz scale $scale
default_border none
default_floating_border none
focus_follows_mouse no
xwayland disable
swaybg_command -
seat * xcursor_theme feel-blank 24
exec $STATE/ready.sh
CFG
  (
    # Not the user's session's display, nor any rig or terminal state.
    unset WAYLAND_DISPLAY WAYLAND_SOCKET DISPLAY HYPRLAND_INSTANCE_SIGNATURE SWAYSOCK I3SOCK \
      GHOSTTY_RESOURCES_DIR HOTTY_TRACE
    for v in $(env | sed -n 's/^\(PLX_[A-Za-z0-9_]*\)=.*/\1/p; s/^\(TERM_PROGRAM[A-Za-z0-9_]*\)=.*/\1/p'); do
      unset "$v"
    done
    # A lock fd inherited from a flock without -o would live as long as sway.
    exec 3>&- 4>&- 5>&- 6>&- 7>&- 8>&- 9>&-
    export WLR_BACKENDS=headless WLR_RENDERER=gles2 WLR_LIBINPUT_NO_DEVICES=1
    # The GPU's render node, as a display's compositor has: without one the
    # headless backend has no DRM fd, offers clients no DMABUFs, and GTK
    # hands its frames over in shared memory, which no real display does.
    # SWAY_RENDER_NODE=none runs without.
    node="${SWAY_RENDER_NODE:-$(ls /dev/dri/renderD* 2>/dev/null | head -1)}"
    [ -n "$node" ] && [ "$node" != none ] && export WLR_RENDER_DRM_DEVICE="$node"
    export XCURSOR_PATH="$STATE/icons" LD_LIBRARY_PATH="$ROOT/usr/lib"
    # In a script's background job, setsid execs sway in place: $! is sway.
    setsid "$ROOT/usr/bin/sway" -c "$STATE/config" >"$STATE/sway.log" 2>&1 </dev/null &
    echo $! > "$STATE/pid"
  )
  pid="$(cat "$STATE/pid")"
  i=0
  while [ ! -s "$STATE/ready" ]; do
    if ! kill -0 "$pid" 2>/dev/null || [ $i -ge 200 ]; then
      echo "sway.sh: the perf sway didn't start; the end of $STATE/sway.log:" >&2
      tail -20 "$STATE/sway.log" >&2
      kill "$pid" 2>/dev/null || true
      clean
      exit 1
    fi
    i=$((i + 1))
    sleep 0.05
  done
  sed -n 1p "$STATE/ready" > "$STATE/display"
  sed -n 2p "$STATE/ready" > "$STATE/ipc"
  case "$(cat "$STATE/ipc")" in
    *".$pid.sock") ;;
    *) echo "sway.sh: the IPC socket $(cat "$STATE/ipc") isn't pid $pid's" >&2; exit 1 ;;
  esac
  status
  ;;
scale)
  [ $# -ge 2 ] || { echo "usage: sway.sh scale <s>" >&2; exit 2; }
  running || { echo "sway.sh: the perf sway isn't running" >&2; exit 1; }
  set_scale "$2"
  status
  ;;
status)
  status
  ;;
stop)
  if [ ! -s "$STATE/pid" ]; then echo "perf sway: not running"; clean; exit 0; fi
  pid="$(cat "$STATE/pid")"
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "perf sway: pid $pid is gone"; clean; exit 0
  fi
  if ! ours "$pid"; then
    echo "sway.sh: pid $pid isn't a sway on $STATE/config; not killing it" >&2
    clean
    exit 1
  fi
  kill -TERM "$pid"
  i=0
  while kill -0 "$pid" 2>/dev/null && [ $i -lt 60 ]; do i=$((i + 1)); sleep 0.05; done
  if kill -0 "$pid" 2>/dev/null; then kill -KILL "$pid"; fi
  clean
  echo "perf sway: stopped (pid $pid)"
  ;;
*)
  echo "usage: sway.sh start [scale] | stop | scale <s> | status" >&2
  exit 2
  ;;
esac
