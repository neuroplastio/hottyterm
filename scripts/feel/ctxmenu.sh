#!/bin/sh
# ctxmenu.sh: a right-click over a hotty surface opens hottyterm's context
# menu, and the terminal keeps working (hottyterm's ctxmenu-deadlock).
#
#   scripts/feel/ctxmenu.sh [--gdb] [--cells] [--out DIR]
#
# On a private headless sway of its own (no desktop of anyone's, no feel
# lock: it times nothing), it runs `ctxprog` in the built fork: one
# document filling the window with scroll=1 (as hotty-pot's Tasks has it),
# rows that take a click, mouse reporting off. Then:
#
#   1. a right press and release at the window's middle: the menu opens;
#   2. a grim screenshot of it (DIR/menu.png);
#   3. Escape closes it, and left clicks on two rows follow.
#
# PASS: the program heard those clicks (DIR/events.log), so the terminal
# read the program's output and sent the surface's events after the menu.
# FAIL: it did not; with --gdb the process ran under gdb, and every
# thread's stack is in DIR/stacks.txt (a SIGINT to the hung process stops
# it, ptrace_scope being 1).
#
# --cells: the program is a shell with text in the cells and no surface: the
# stock right-click (the menu opens, the word under the pointer is selected),
# which must stay as it was. It passes when the menu opens (the screenshot
# differs from the one before) and a key typed after Escape reaches the shell.
#
# HOTTYTERM_BIN is the build to run (default: ../ghostty/zig-out, or
# HOTTYTERM_GHOSTTY's). Runs under the cap (~/.cache/neuroplastio/bin/capped)
# and `isolated`, and stops its sway, bus, portals and at-spi on exit.
set -eu
HERE="$(cd "$(dirname "$0")/../.." && pwd)"

if [ "${1:-}" != "--inner" ]; then
  GDB=0; CELLS=0; CONTROL=0; OUT="${XDG_CACHE_HOME:-$HOME/.cache}/hotty/runs/ctxmenu"
  while [ $# -gt 0 ]; do
    case "$1" in
      --gdb) GDB=1 ;;
      --cells) CELLS=1 ;;
      --control) CONTROL=1 ;;
      --out) shift; OUT="$1" ;;
      *) echo "usage: ctxmenu.sh [--gdb] [--cells] [--control] [--out DIR]" >&2; exit 2 ;;
    esac
    shift
  done
  FORK="${HOTTYTERM_GHOSTTY:-$(dirname "$HERE")/ghostty}"
  BIN="${HOTTYTERM_BIN:-$FORK/zig-out/bin/hottyterm}"
  [ -x "$BIN" ] || { echo "not built: $BIN" >&2; exit 1; }
  [ -x "$HERE/scripts/feel/ctxprog/ctxprog" ] || (cd "$HERE/scripts/feel/ctxprog" && mise x -- go build -o ctxprog .)
  RUN="$OUT/run"; mkdir -p "$OUT"
  cleanup() {
    for p in $(pgrep -u "$USER" -x 'dbus-daemon|xdg-desktop-por|xdg-permission-|xdg-document-po|at-spi-bus-laun|at-spi2-registr|sway|gdb|hottyterm' 2>/dev/null); do
      if tr '\0' '\n' 2>/dev/null < "/proc/$p/environ" | grep -qx "XDG_RUNTIME_DIR=$RUN/runtime"; then kill "$p" 2>/dev/null || true; fi
    done
  }
  trap cleanup EXIT
  rc=0
  # dbus-run-session starts a bus of its own, so no portal or settings daemon
  # of the maintainer's is reached (gsettings, dconf and the portal are never
  # used: a setting would only go in the run's own config dir).
  ~/.cache/neuroplastio/bin/capped ~/.cache/neuroplastio/bin/isolated "$RUN" \
    dbus-run-session -- env CTX_GDB=$GDB CTX_CELLS=$CELLS CTX_CONTROL=$CONTROL CTX_OUT="$OUT" CTX_BIN="$BIN" \
    SWAY_ROOT="${SWAY_ROOT:-$HOME/.cache/hotty/sway/root}" CTX_REAL_HOME="$HOME" \
    sh "$0" --inner || rc=$?
  exit "$rc"
fi

# ---- inside the isolated run: HOME, XDG_* and the bus are the run's own ----
echo "run: HOME=$HOME XDG_CONFIG_HOME=$XDG_CONFIG_HOME XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR"
case "$HOME$XDG_CONFIG_HOME$XDG_RUNTIME_DIR" in *"$CTX_REAL_HOME/.config"*|/run/user/*) echo "not isolated" >&2; exit 3 ;; esac
OUT="$CTX_OUT"; BIN="$CTX_BIN"
SWAYSH="$HERE/scripts/feel/sway.sh"
PROG="$HERE/scripts/feel/ctxprog/ctxprog"
LOG="$OUT/events.log"; STACKS="$OUT/stacks.txt"
rm -f "$LOG" "$STACKS" "$OUT/menu.png" "$OUT/before.png" "$OUT/after.png" "$OUT"/*.txt

stop() {
  "$SWAYSH" stop >/dev/null 2>&1 || true
}
trap stop EXIT
"$SWAYSH" start 1 >/dev/null
export WAYLAND_DISPLAY="$(cat "$XDG_CACHE_HOME/hotty/sway-feel/display")"
unset DISPLAY

# The program: ctxprog (a surface), or a shell with text (--cells).
if [ "$CTX_CELLS" = 1 ]; then
  cat > "$OUT/cells.sh" <<'EOF'
#!/bin/sh
printf '\033[2J\033[Hhello world hello world\n'
while read -r l; do printf 'got %s\n' "$l" >> "$CTX_LOG"; done
EOF
  chmod +x "$OUT/cells.sh"
  CMD="env CTX_LOG=$LOG sh $OUT/cells.sh"
else
  printf '#!/bin/sh\nexec %s --event-log %s 2> %s\n' "$PROG" "$LOG" "$OUT/prog.err" > "$OUT/prog.sh"
  chmod +x "$OUT/prog.sh"
  CMD="$OUT/prog.sh"
fi

if [ "$CTX_GDB" = 1 ]; then
  gdb -batch -nx -ex 'set pagination off' -ex 'set debuginfod enabled off' -ex 'set print thread-events off' \
    -ex 'handle SIGPIPE nostop noprint pass' -ex 'handle SIGUSR1 nostop noprint pass' -ex 'handle SIGUSR2 nostop noprint pass' \
    -ex run -ex 'echo \n=== STACKS ===\n' -ex 'thread apply all bt 30' -ex kill \
    --args "$BIN" --gtk-single-instance=false --window-decoration=false -e $CMD \
    > "$OUT/gdb.log" 2>&1 &
  GDBPID=$!
else
  "$BIN" --gtk-single-instance=false --window-decoration=false -e $CMD > "$OUT/term.log" 2>&1 &
  GDBPID=$!
fi
termpid() {
  if [ "$CTX_GDB" = 1 ]; then pgrep -P "$GDBPID" -x hottyterm || true; else echo "$GDBPID"; fi
}

# Wait for the program to be up (events.log is made by feelprog on its first
# draw; the cells program writes on its first line).
i=0
while [ ! -s "$LOG" ] && [ "$CTX_CELLS" = 0 ]; do
  i=$((i + 1)); [ $i -gt 200 ] && { echo "FAIL the program never came up"; tail -20 "$OUT/gdb.log" "$OUT/term.log" "$OUT/prog.err" 2>/dev/null; exit 1; }
  sleep 0.1
done
sleep 2

BB="python3 $HERE/scripts/feel/blackbox.py --settle-ms 150 --timeout-ms 1500 --json"
W=2400; H=1500
X=$((W / 2)); Y=$((H / 2))
[ "$CTX_CELLS" = 1 ] && { X=100; Y=10; }   # over "world", the first row
grim "$OUT/before.png"

# 1. The right click: press, hold, release.
if [ "$CTX_CONTROL" = 1 ]; then   # the control: no right click
  printf '%s\n' "{\"move\":[$X,$Y],\"untimed\":true}" '{"sleep_ms":1500}' | $BB - > "$OUT/step1.json" 2>&1 || true
else
  printf '%s\n' \
    "{\"move\":[$X,$Y],\"untimed\":true}" \
    "{\"click\":[$X,$Y],\"button\":\"right\",\"hold_ms\":80,\"untimed\":true}" \
    "{\"sleep_ms\":1500}" | $BB - > "$OUT/step1.json" 2>&1 || true
fi
grim "$OUT/menu.png"

# 2. Escape closes the menu; two left clicks on rows (or a key into the shell).
if [ "$CTX_CELLS" = 1 ]; then
  printf '%s\n' '{"key":"Escape","untimed":true}' '{"sleep_ms":500}' '{"keys":"abc\n","untimed":true}' '{"sleep_ms":800}' | $BB - > "$OUT/step2.json" 2>&1 || true
else
  n0=$(grep -c ' event click' "$LOG" || true)
  printf '%s\n' '{"key":"Escape","untimed":true}' '{"sleep_ms":500}' \
    '{"click":[900,420],"untimed":true}' '{"sleep_ms":600}' '{"click":[1500,620],"untimed":true}' '{"sleep_ms":800}' | $BB - > "$OUT/step2.json" 2>&1 || true
fi
grim "$OUT/after.png"

verdict=PASS
if [ "$CTX_CELLS" = 1 ]; then
  cmp -s "$OUT/before.png" "$OUT/menu.png" && { echo "FAIL the menu did not open over the cells"; verdict=FAIL; }
  grep -q 'got abc' "$LOG" 2>/dev/null || { echo "FAIL a key after the menu never reached the shell"; verdict=FAIL; }
else
  n1=$(grep -c ' event click' "$LOG" || true)
  if [ "$n1" -gt "$n0" ]; then
    echo "ok   the program heard $((n1 - n0)) click(s) after the menu"
  else
    echo "FAIL the program heard no click after the menu"; verdict=FAIL
    # Hung: stop it, and with gdb get every thread's stack.
    pid="$(termpid)"
    [ "$CTX_GDB" = 1 ] && [ -n "$pid" ] && { kill -INT "$pid" 2>/dev/null || true; i=0; while kill -0 "$GDBPID" 2>/dev/null && [ $i -lt 600 ]; do sleep 0.1; i=$((i + 1)); done; }
    [ -f "$OUT/gdb.log" ] && sed -n '/=== STACKS ===/,$p' "$OUT/gdb.log" > "$STACKS"
    [ -s "$STACKS" ] && echo "     stacks: $STACKS"
  fi
fi
kill -TERM "$(termpid)" 2>/dev/null || true
kill "$GDBPID" 2>/dev/null || true
wait "$GDBPID" 2>/dev/null || true
echo "$verdict (screenshots and logs in $OUT)"
[ "$verdict" = PASS ]
