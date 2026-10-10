#!/bin/sh
# Probes a focused text input in hottyterm on macOS, on a CI runner:
#
#   scripts/probe-macos.sh /Applications/hottyterm.app <out dir> [remap]
#   scripts/probe-macos.sh /Applications/hottyterm.app <out dir> regions [baseline.app]
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
# A program shows a HOTTY surface with one focused <input> (a red caret) and
# logs what the terminal sends it. The probe then
#   - screenshots it 16 times, 0.3 s apart: a caret that blinks shows in some
#     shots and not in others;
#   - types "abc", then Backspace, with System Events: the input events the
#     program hears carry the input's value, "a", "ab", "abc", "ab";
#   - presses the keys Ghostty's macOS bindings and menu would take, which
#     the field is offered first as pressed, Cmd as Meta (HOTTY SPEC §10.2,
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
#   - prints hottyterm's log lines about HOTTY.
# The runner's own settings decide whether screenshots and keystrokes are
# allowed; the probe says when they are not.
set -u
APP="$1"
OUT="$2"
MODE="${3:-}"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"

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
