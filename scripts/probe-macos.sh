#!/bin/sh
# Probes a focused text input in hottyterm on macOS, on a CI runner:
#
#   scripts/probe-macos.sh /Applications/hottyterm.app <out dir> [remap]
#   scripts/probe-macos.sh /Applications/hottyterm.app <out dir> regions [baseline.app]
#   scripts/probe-macos.sh /Applications/hottyterm.app <out dir> latency [baseline.app]
#   scripts/probe-macos.sh /Applications/hottyterm.app <out dir> latency plx <bundle>
#
# `latency` times input through hottyterm's stage stamps (gov R-22,
# docs/trace.md), there being no screen copies here: in each of
# LATENCY_ROUNDS rounds (3), for the app and then the baseline (the order
# turning each round), the rig's programs (scripts/feel/prog) e1 (shell
# echo), e2 (a key in a hotty field) and e3 (the pointer across :hover
# rows) run under HOTTY_TRACE, and scripts/feel/cgevent.py posts
# LATENCY_N (60) keys or pointer moves with CoreGraphics, stamping each.
# Each run's trace goes to <out dir>/latency/<side>-<scenario>-r<round>/,
# and scripts/feel/report.py --end term.contents sums them up: from the
# input to the main thread setting the layer's contents. It needs Go.
# LATENCY_DRY=1 posts nothing (cgevent.py --dry). If the runner refuses
# CoreGraphics the first key, keys go through System Events from then on
# (cgevent.py --via osascript), and e3, which has no pointer then, is left
# out.
#
# `latency plx <bundle>` runs plx's scenarios in a throwaway plx instead, for
# plx's own probe workflow: <bundle> is plx's feel bundle unpacked (bin/plx
# and bin/plx-script with their stamps, scripts/perf/plx-run.sh, its setup
# scripts and feel/E7.json and E7K.json). Each run's command is plx-run.sh
# with the scenario's argv and setup from the bundle, it waits for
# plx-run.sh's plx-pane.json rather than a layout, and cgevent.py plays the
# scenario file (its keys; the screen is the trace's term.contents). The
# app alone, no baseline; each file's n unless LATENCY_N is set. The
# report then has plx's shares beside hottyterm's.
#
# `regions` probes partial frames instead (kitty frame edits drawn into the
# image's texture, renderer `texture_region_updates`): a program colours one
# cell of a grid a step, by a CSS variable, and the probe screenshots each
# step: the new colour must show and the earlier ones stay, counted against
# the shot before so the menu bar and the Dock don't count. The colours are
# saturated: macOS's colour conversion moves pale ones past the tolerance
# (#80ff80 was captured as #38ff6d). Then the program
# changes 4 cells' text at 10 Hz for 15 s and the probe reads the app's CPU
# time over 12 s of it, and the same for a baseline app when given.
#
# A program shows a hotty surface with one focused <input> (a red caret) and
# logs what the terminal sends it. The probe then
#   - screenshots it 16 times, 0.3 s apart: a caret that blinks shows in some
#     shots and not in others;
#   - types "abc", then Backspace, with System Events: the input events the
#     program hears carry the input's value, "a", "ab", "abc", "ab";
#   - presses the keys Ghostty's macOS bindings and menu would take, which
#     the field is offered first as pressed, Cmd as Meta (hotty SPEC §10.2,
#     §10.4): " cd", Option+Left (Alt+ArrowLeft: word back), "X", Cmd+Left
#     (Meta+ArrowLeft: line start), "Y", Cmd+Shift+Right (selects to the
#     line's end), "Z", Cmd+A (select all), "W", Cmd+Backspace (delete to
#     line start), then Control+s, which the field leaves to the program.
#     The values go "ab cd", "ab Xcd", "Yab Xcd", "YZ", "W", "", and the
#     program hears 0x13;
#   - with `remap`, Cmd and Ctrl swapped (key-remap) instead: Cmd+A (Control+a:
#     select all), "Z", Cmd+H (Control+h: the program hears 0x08, and the
#     app does not hide), Cmd+C (Control+c: the program hears 0x03, nothing
#     is copied), Ctrl+Backspace (Meta+Backspace: delete to line start). The
#     values go "Z", "", and the program hears 0x08 0x03;
#   - prints hottyterm's log lines about hotty.
# The runner's own settings decide whether screenshots and keystrokes are
# allowed; the probe says when they are not.
#
# Every mode first prints the runner's cores: the CPU, and each performance
# level with its logical CPUs (gov R-22: on Apple silicon a thread's QoS
# class chooses the level it runs on, so it shows only where there are two).
set -u
APP="$1"
OUT="$2"
MODE="${3:-}"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"

levels=$(sysctl -n hw.nperflevels 2>/dev/null || echo 1)
echo "== cpu: $(sysctl -n machdep.cpu.brand_string 2>/dev/null), $levels performance level(s): $(
  l=0; while [ "$l" -lt "$levels" ]; do
    [ "$l" -gt 0 ] && printf ', '
    printf '%s %s CPUs' "$(sysctl -n hw.perflevel$l.name 2>/dev/null || echo "level $l")" "$(sysctl -n hw.perflevel$l.logicalcpu 2>/dev/null || sysctl -n hw.logicalcpu 2>/dev/null || echo ?)"
    l=$((l + 1))
  done)"

if [ "$MODE" = regions ]; then
BASE="${4:-}"
cat > "$OUT/regions.py" <<'EOF'
import base64, os, select, sys, time, tty
out = sys.argv[1]
fd = sys.stdin.fileno()
tty.setraw(fd)
def cmd(head, payload=b""):
    os.write(1, f"\x1b]7279;{head};{base64.b64encode(payload).decode()}\x1b\\".encode())
def drain(t):
    r, _, _ = select.select([fd], [], [], t)
    if r:
        os.read(fd, 4096)
def wait(name):
    while not os.path.exists(os.path.join(out, name)):
        drain(0.05)
COLORS = ["#00c800", "#0000ff", "#ffff00", "#00ffff", "#ff00ff", "#ff8000",
          "#8000ff", "#008080", "#808000", "#ff0000", "#ff0080", "#0080ff"]
cells = "".join(f"<div class=c id=c{i}><span id=t{i}>{i}</span></div>" for i in range(24))
html = ("<style>body{margin:0;background:#222;color:#ddd;font:14px monospace}"
        "#g{display:grid;grid-template-columns:repeat(6,60px);gap:8px;padding:8px}"
        ".c{height:40px;background:var(--bg,#333)}</style><div id=g>" + cells + "</div>")
os.write(1, b"\x1b[2J\x1b[H")
cmd("a=doc:s=x:q=2", html.encode())
cmd("a=place:s=x:c=60:r=12:q=2")
open(os.path.join(out, "ready"), "w").close()
for k, c in enumerate(COLORS):
    wait(f"go{k}")
    cmd(f"a=delta:s=x:op=var:t=c{2 * k}:k=bg:q=2", c.encode())
    open(os.path.join(out, f"step{k}"), "w").close()
wait("load")
end, n = time.time() + 15, 0
while time.time() < end:
    n += 1
    os.write(1, b"\x1b[?2026h")
    for j in range(4):
        i = (n + 6 * j) % 24
        cmd(f"a=delta:s=x:op=text:t=t{i}:q=2", str((n * 7 + i) % 1000).encode())
    os.write(1, b"\x1b[?2026l")
    drain(0.1)
while True:
    drain(1)
EOF
python3 -m venv "$OUT/venv" >/dev/null && "$OUT/venv/bin/pip" -q install pillow >/dev/null
mkdir -p "$HOME/.config/ghostty"
cputime() { ps -o time= -p "$1" | awk -F'[:.]' '{ s = 0; for (i = 1; i < NF; i++) s = s * 60 + $i; printf "%.2f", s + $NF / 100 }'; }
regions() {
  app="$1"; tag="$2"; dir="$OUT/$tag"; mkdir -p "$dir"
  cat > "$HOME/.config/ghostty/config" <<CFG
command = /usr/bin/python3 $OUT/regions.py $dir
font-size = 16
window-width = 80
window-height = 20
confirm-close-surface = false
quit-after-last-window-closed = true
CFG
  echo "== regions: $tag ($app)"
  open -n -a "$app"
  for _ in $(seq 1 30); do [ -f "$dir/ready" ] && break; sleep 1; done
  [ -f "$dir/ready" ] || { echo "the program never started"; return; }
  sleep 3
  pid=$(pgrep -n -f "$app/Contents/MacOS/")
  screencapture -x "$dir/start.png" 2>&1
  for k in $(seq 0 11); do
    touch "$dir/go$k"
    for _ in $(seq 1 50); do [ -f "$dir/step$k" ] && break; sleep 0.1; done
    sleep 0.5
    screencapture -x "$dir/step$k.png" 2>&1
  done
  touch "$dir/load"
  sleep 3
  a=$(cputime "$pid"); sleep 12; b=$(cputime "$pid")
  echo "cpu: $(echo "$a $b" | awk '{printf "%.2f s over 12 s (%.1f%%)", $2 - $1, 100 * ($2 - $1) / 12}')"
  screencapture -x "$dir/load.png" 2>&1
  kill "$pid" 2>/dev/null; sleep 2
  "$OUT/venv/bin/python" - "$dir" <<'PY'
import sys
from PIL import Image
COLORS = ["#00c800", "#0000ff", "#ffff00", "#00ffff", "#ff00ff", "#ff8000",
          "#8000ff", "#008080", "#808000", "#ff0000", "#ff0080", "#0080ff"]
rgb = [tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) for c in COLORS]
def count(path, want):
    im = Image.open(path).convert("RGB")
    return sum(1 for p in im.get_flattened_data() if all(abs(a - b) <= 40 for a, b in zip(p, want)))
d = sys.argv[1]
shots = [f"{d}/start.png"] + [f"{d}/step{k}.png" for k in range(12)]
seen = [count(shots[k + 1], rgb[k]) - count(shots[k], rgb[k]) for k in range(12)]
kept = [count(shots[12], rgb[k]) - count(shots[0], rgb[k]) for k in range(12)]
print("each step's colour, px more than the shot before:", " ".join(map(str, seen)))
print("all colours at the end, px more than at the start:", " ".join(map(str, kept)))
print("regions:", "ok" if min(seen) > 500 and min(kept) > 500 else "MISSING")
PY
}
regions "$APP" new
[ -n "$BASE" ] && regions "$BASE" baseline
exit 0
fi

if [ "$MODE" = latency ]; then
BASE="${4:-}"
PLX=""
if [ "$BASE" = plx ]; then
  BASE=""
  PLX="${5:-}"
  [ -x "${PLX:-/nonexistent}/scripts/perf/plx-run.sh" ] || { echo "latency plx: no plx bundle at ${PLX:-(none given)}"; exit 0; }
  PLX="$(cd "$PLX" && pwd)"
fi
REPO="$(cd "$(dirname "$0")/.." && pwd)"
N="${LATENCY_N:-60}"
ROUNDS="${LATENCY_ROUNDS:-3}"
if [ -n "$PLX" ]; then
  SCS="E7 E7K"
  echo "== latency: $ROUNDS round(s) of E7 E7K in plx, $( [ -n "${LATENCY_N:-}" ] && echo "$N timed keys" || echo "each file's n") each"
else
  SCS="e1 e2 e3"
  echo "== latency: $ROUNDS round(s) of e1 e2 e3, $N inputs each"
  go build -C "$REPO/scripts/feel/prog" -o "$OUT/feelprog" . || { echo "feelprog does not build"; exit 0; }
fi
python3 -m venv "$OUT/venv" >/dev/null && "$OUT/venv/bin/pip" -q install pyobjc-framework-Quartz >/dev/null
system_profiler SPDisplaysDataType 2>/dev/null | grep -iE 'resolution|refresh|retina' | sed 's/^ */display: /'
mkdir -p "$HOME/.config/ghostty"
# One run: the app runs feelprog's scenario (or plx-run.sh with a plx
# scenario's program) with HOTTY_TRACE, cgevent.py types or moves the
# pointer, and the trace stays in the run's dir.
VIA=cgevent
# Stops a run's app the same way whatever happened: TERM, up to 5 s to
# exit, then KILL; in plx 2 s more, plx-run.sh stopping its session within
# 1.5 s of the terminal's hangup, so the next run starts on a clean slate.
stop_app() { # <pid>
  [ -n "$1" ] || return 0
  kill "$1" 2>/dev/null
  for _ in $(seq 1 10); do kill -0 "$1" 2>/dev/null || break; sleep 0.5; done
  kill -9 "$1" 2>/dev/null
  [ -n "$PLX" ] && sleep 2
  return 0
}
latency() { # <app> <side> <e1|e2|e3|E7|E7K> <round>
  app="$1"; side="$2"; sc="$3"; r="$4"
  dir="$OUT/latency/$side-$sc-r$r"; mkdir -p "$dir"
  if [ -n "$PLX" ]; then
    spec="$PLX/scripts/perf/feel/$sc.json"
    ready="$dir/plx-pane.json"
    # The scenario's argv, in plx-run.sh with the bundle's build and the
    # bundle's copy of the scenario's setup.
    cmd="$(python3 -I - "$spec" "$PLX" <<'PY'
import json, os, shlex, sys
spec, plx = json.load(open(sys.argv[1])), sys.argv[2]
run = [os.path.join(plx, "scripts/perf/plx-run.sh"), "--bin", os.path.join(plx, "bin")]
if spec.get("setup"):
    run += ["--setup", os.path.join(plx, "scripts/perf", os.path.basename(spec["setup"]))]
print(shlex.join(run + ["--", *spec["argv"]]))
PY
)" || { echo "latency plx: no scenario $spec"; return 1; }
  else
    ready="$dir/layout.json"
    cmd="$OUT/feelprog $sc --layout $dir/layout.json"
  fi
  cat > "$HOME/.config/ghostty/config" <<CFG
command = $cmd
font-size = 16
window-width = 80
window-height = 24
window-padding-x = 0
window-padding-y = 0
macos-titlebar-style = hidden
cursor-style-blink = false
confirm-close-surface = false
quit-after-last-window-closed = true
CFG
  printf '{"host": "%s", "sc": "%s", "round": %d%s}\n' "$side" "$(echo "$sc" | tr a-z A-Z)" "$r" \
    "$( [ -n "$PLX" ] && echo ', "plx": true')" > "$dir/meta.json"
  echo "-- $side $sc r$r"
  open -n -a "$app" --env "HOTTY_TRACE=$dir"
  # plx starts its session and runs the setup first.
  for _ in $(seq 1 60); do [ -s "$ready" ] && break; sleep 1; done
  pid=$(pgrep -n -f "$app/Contents/MacOS/")
  if [ ! -s "$ready" ] || [ -z "$pid" ]; then
    # Which of them didn't come up: the app, or the program in it (in plx,
    # plx-run.sh writes plx-pane.json once its session and setup are done).
    echo "the program never started: $( [ -n "$pid" ] && echo "the app runs (pid $pid)" || echo "no app process"), no $(basename "$ready") after 60 s; the run's dir holds: $(ls "$dir" | tr '\n' ' ')"
    stop_app "$pid"; return 1
  fi
  sleep 2
  # A build from before the stamps writes no trace, even with its program
  # drawn, and cgevent.py would take its first input for a refused one.
  if ! ls "$dir"/hottyterm-*.jsonl >/dev/null 2>&1; then
    echo "no hottyterm trace: the build has no stamps, or HOTTY_TRACE did not reach it"
    stop_app "$pid"; mkdir -p "$OUT/unstamped" && mv "$dir" "$OUT/unstamped/"; return 4
  fi
  grep -qs '"n":"term.contents"' "$dir"/hottyterm-*.jsonl \
    || echo "no term.contents yet: the build has no macOS stamps, and the report no end for its inputs"
  echo "front: $(lsappinfo info -only name "$(lsappinfo front)" 2>/dev/null)"
  if [ -n "$PLX" ]; then
    "$OUT/venv/bin/python" -I "$REPO/scripts/feel/cgevent.py" "$dir" "$spec" --pid "$pid" \
      ${LATENCY_N:+--n "$N"} --seed "$r" --via "$VIA" ${LATENCY_DRY:+--dry}
  else
    "$OUT/venv/bin/python" -I "$REPO/scripts/feel/cgevent.py" "$dir" "$sc" --pid "$pid" \
      --layout "$dir/layout.json" --n "$N" --seed "$r" --via "$VIA" ${LATENCY_DRY:+--dry}
  fi
  rc=$?
  sleep 1
  stop_app "$pid"
  # A refused run's trace is set aside, out of the report.
  [ $rc -eq 3 ] && mkdir -p "$OUT/refused" && mv "$dir" "$OUT/refused/"
  return $rc
}
# The sides alternate, first one then the other, so that drift on the
# runner falls on both.
k=1
unstamped=""
while [ "$k" -le "$ROUNDS" ]; do
  if [ -z "$BASE" ]; then sides="new"; elif [ $((k % 2)) -eq 1 ]; then sides="new base"; else sides="base new"; fi
  for who in $sides; do
    case " $unstamped " in *" $who "*) continue ;; esac
    which="$APP"; [ "$who" = base ] && which="$BASE"
    for what in $SCS; do
      if [ "$what" = e3 ] && [ "$VIA" = osascript ]; then echo "-- $who e3 r$k: left out, no pointer"; continue; fi
      latency "$which" "$who" "$what" "$k"
      rc=$?
      if [ $rc -eq 4 ]; then echo "-- $who: left out, it writes no stamps"; unstamped="$unstamped $who"; break; fi
      [ $rc -eq 3 ] || continue
      if [ "$VIA" = osascript ]; then echo "== latency: stopped, no input is delivered here"; exit 0; fi
      echo "== latency: CoreGraphics refused, keys go through System Events from here"
      VIA=osascript
      [ "$what" = e3 ] || latency "$which" "$who" "$what" "$k"
    done
  done
  k=$((k + 1))
done
"$OUT/venv/bin/python" -I "$REPO/scripts/feel/report.py" "$OUT"/latency/*/ --end term.contents --md "$OUT/latency/report.md" \
  && cat "$OUT/latency/report.md"
exit 0
fi

cat > "$OUT/prog.py" <<'EOF'
import base64, os, select, sys, termios, time, tty
out = sys.argv[1]
log = open(os.path.join(out, "replies.log"), "ab", buffering=0)
fd = sys.stdin.fileno()
tty.setraw(fd)
html = ("<style>body{margin:0;background:#223;color:#eee}"
        "input{font:20px monospace;width:300px;background:#fff;color:#000;caret-color:#f00}</style>"
        "<input id=t data-on=input>")
b64 = base64.b64encode(html.encode()).decode()
os.write(1, ("\x1b[2J\x1b[H"
             f"\x1b]7279;a=doc:s=x:q=2;{b64}\x1b\\"
             "\x1b]7279;a=place:s=x:c=40:r=2:q=2\x1b\\"
             "\x1b]7279;a=focus:s=x:t=t:q=2\x1b\\").encode())
open(os.path.join(out, "ready"), "w").close()
end = time.time() + 300
while time.time() < end:
    r, _, _ = select.select([fd], [], [], 0.2)
    if r:
        log.write(os.read(fd, 4096))
EOF

mkdir -p "$HOME/.config/ghostty"
cat > "$HOME/.config/ghostty/config" <<EOF
command = /usr/bin/python3 $OUT/prog.py $OUT
font-size = 16
window-width = 80
window-height = 20
confirm-close-surface = false
quit-after-last-window-closed = true
EOF
if [ "$MODE" = remap ]; then
  printf 'key-remap = super=ctrl\nkey-remap = ctrl=super\n' >> "$HOME/.config/ghostty/config"
fi

python3 -m venv "$OUT/venv" >/dev/null && "$OUT/venv/bin/pip" -q install pillow >/dev/null

echo "== launch"
open -a "$APP"
for _ in $(seq 1 30); do [ -f "$OUT/ready" ] && break; sleep 1; done
[ -f "$OUT/ready" ] && echo "the program is up" || echo "the program never started"
sleep 3
osascript -e 'tell application "hottyterm" to activate' 2>&1
sleep 1

echo "== blink: red caret pixels per shot"
for i in $(seq -w 1 16); do
  screencapture -x "$OUT/shot$i.png" 2>&1
  sleep 0.3
done
"$OUT/venv/bin/python" - "$OUT" <<'EOF'
import glob, sys
from PIL import Image
counts = []
for p in sorted(glob.glob(sys.argv[1] + "/shot*.png")):
    im = Image.open(p).convert("RGB")
    counts.append(sum(1 for r, g, b in im.get_flattened_data() if r > 200 and g < 80 and b < 80))
print(" ".join(map(str, counts)) or "no screenshots")
# The window's close button is red too: a caret that blinks shows as the
# count going up and down by the caret's few pixels, not as zeroes.
lo, hi = min(counts, default=0), max(counts, default=0)
print("no caret seen" if hi == 0 else f"blinks ({hi - lo} px)" if hi - lo >= 8 else "does not blink")
EOF

echo "== keys: abc, then Backspace"
osascript -e 'tell application "System Events" to keystroke "abc"' 2>&1
sleep 0.5
osascript -e 'tell application "System Events" to key code 51' 2>&1
sleep 1

se() { osascript -e "tell application \"System Events\" to $1" 2>&1; sleep 0.5; }
if [ "$MODE" = remap ]; then
echo "== keys: Cmd and Ctrl swapped, the menu sees them swapped"
se 'keystroke "a" using command down'
se 'keystroke "Z"'
se 'keystroke "h" using command down'
se 'keystroke "c" using command down'
se 'key code 51 using control down'
else
echo "== keys: offered to the field first, before Ghostty's bindings and menu"
se 'keystroke " cd"'
se 'key code 123 using option down'
se 'keystroke "X"'
se 'key code 123 using command down'
se 'keystroke "Y"'
se 'key code 124 using {command down, shift down}'
se 'keystroke "Z"'
se 'keystroke "a" using command down'
se 'keystroke "W"'
se 'key code 51 using command down'
se 'keystroke "s" using control down'
fi
sleep 1
screencapture -x "$OUT/after-keys.png" 2>&1
python3 - "$OUT/replies.log" <<'EOF'
import base64, re, sys
data = open(sys.argv[1], "rb").read() if __import__("os").path.exists(sys.argv[1]) else b""
evs = re.findall(rb"\x1b\]7279;a=ev:([^;\x07\x1b]*);([A-Za-z0-9+/=]*)", data)
for head, body in evs:
    print(head.decode(), base64.b64decode(body).decode(errors="replace"))
rest = re.sub(rb"\x1b\]7279;[^\x07\x1b]*(\x07|\x1b\\)", b"", data)
print("the program heard otherwise:", repr(rest) if rest else "nothing")
EOF

echo "== hottyterm's log"
log show --last 5m --style compact --predicate 'process == "ghostty"' 2>/dev/null | grep -i 'hotty\|blitz\|warn\|error' | tail -40

osascript -e 'tell application "hottyterm" to quit' 2>/dev/null
exit 0
