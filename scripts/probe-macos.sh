#!/bin/sh
# Probes a focused text input in hottyterm on macOS, on a CI runner:
#
#   scripts/probe-macos.sh /Applications/hottyterm.app <out dir> [remap]
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
