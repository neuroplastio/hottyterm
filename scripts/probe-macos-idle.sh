#!/bin/sh
# What surfaces that only animate cost hottyterm, on a probe-macos runner:
# probe-macos.yml with idle=true. A program shows surfaces shaped like
# plx's (strips with a pulsing dot, a spinner and typing dots; a sidebar of
# fading miniatures), all infinite CSS animations of opacity and transform,
# and nothing else changes. For each scenario the probe reads the app's CPU
# over IDLE_SECS (10) and takes `sample` of it (the artifact), with the
# per-thread CPU from `ps -M`:
#   static   the same surfaces, no animation;
#   dot      one strip with one pulsing dot;
#   plx      every surface animating;
#   hidden   plx with the window minimized.
set -u
[ "${GITHUB_ACTIONS:-}" = true ] && [ "${RUNNER_OS:-}" = macOS ] || {
    echo 'Run through probe-macos.yml with idle=true, on its macOS runner.' >&2
    exit 1
}
APP="$1"
OUT="$2/idle"
SECS="${IDLE_SECS:-10}"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"

cat > "$OUT/idle.py" <<'EOF'
import base64, os, select, sys, tty
scenario, ready = sys.argv[1], sys.argv[2]
fd = sys.stdin.fileno()
tty.setraw(fd)
def cmd(head, payload=b""):
    os.write(1, f"\x1b]7279;{head};{base64.b64encode(payload).decode()}\x1b\\".encode())
still = scenario == "static"
css = ("body{margin:0;font:13px sans-serif;background:#1b1b1f;color:#ddd}"
       ".bar{display:flex;gap:8px;align-items:center;padding:4px 8px}"
       ".dot{width:8px;height:8px;border-radius:50%;background:#6c6}"
       ".spin{display:inline-flex}"
       ".t i{display:inline-block;width:4px;height:4px;border-radius:50%;background:currentColor;opacity:.35;margin-left:3px}"
       ".mini{position:relative;height:56px;margin:6px;border:1px solid #444}"
       ".tint{position:absolute;inset:0;background:currentColor;opacity:.35}"
       "@keyframes p{0%,100%{opacity:1}50%{opacity:.4}}"
       "@keyframes r{to{transform:rotate(360deg)}}"
       "@keyframes f{50%{opacity:.12}}")
if not still:
    css += (".dot{animation:p 1600ms ease-in-out infinite}"
            ".spin>svg{animation:r 850ms linear infinite}"
            ".d1{animation:p 1200ms linear infinite}"
            ".d2{animation:p 1200ms linear infinite .4s}"
            ".d3{animation:p 1200ms linear infinite .8s}"
            ".tint{animation:f 2000ms ease-in-out infinite}")
style = "<style>" + css + "</style>"
spin = ("<span class=spin><svg width=14 height=14 viewBox='0 0 14 14'><circle cx=7 cy=7 r=5 "
        "stroke='#6af' stroke-width=2 fill=none stroke-dasharray='20 12'/></svg></span>")
typing = "<span class=t><i class=d1></i><i class=d2></i><i class=d3></i></span>"
os.write(1, b"\x1b[2J\x1b[H")
def surface(name, body, c, r, x, y):
    cmd(f"a=doc:s={name}:q=2", (style + body).encode())
    os.write(1, f"\x1b[{y + 1};{x + 1}H".encode())
    cmd(f"a=place:s={name}:c={c}:r={r}:q=2")
if scenario == "dot":
    surface("top", "<div class=bar><span class=dot></span><span>agent working</span></div>", 100, 1, 0, 0)
else:
    surface("top", f"<div class=bar><span class=dot></span>{spin}<span>agent working</span><span>main</span></div>", 100, 1, 0, 0)
    surface("bottom", f"<div class=bar>{typing}<span>agent is typing</span></div>", 100, 1, 0, 29)
    minis = "".join(f"<div class=mini><div class=tint></div>pane {i}</div>" for i in range(6))
    surface("side", minis, 24, 26, 0, 2)
os.write(1, b"\x1b[3;30Hidle terminal")
open(ready, "w").close()
while True:
    r, _, _ = select.select([fd], [], [], 1)
    if r:
        os.read(fd, 4096)
EOF

mkdir -p "$HOME/.config/ghostty"
cputime() { ps -o time= -p "$1" | awk -F'[:.]' '{ s = 0; for (i = 1; i < NF; i++) s = s * 60 + $i; printf "%.2f", s + $NF / 100 }'; }
echo "== displays: $(system_profiler SPDisplaysDataType 2>/dev/null | grep -E 'Resolution|Refresh' | tr -s ' ' | tr '\n' ';')"

run() {
  scenario="$1"; dir="$OUT/$scenario"; mkdir -p "$dir"
  prog=dot; [ "$scenario" = static ] && prog=static; [ "$scenario" = plx ] || [ "$scenario" = hidden ] && prog=plx
  cat > "$HOME/.config/ghostty/config" <<CFG
command = /usr/bin/python3 $OUT/idle.py $prog $dir/ready
font-size = 14
window-width = 100
window-height = 30
confirm-close-surface = false
quit-after-last-window-closed = true
CFG
  open -n -a "$APP"
  for _ in $(seq 1 30); do [ -f "$dir/ready" ] && break; sleep 1; done
  [ -f "$dir/ready" ] || { echo "== $scenario: the program never started"; return; }
  sleep 3
  pid=$(pgrep -n -f "$APP/Contents/MacOS/")
  screencapture -x "$dir/shot.png" 2>&1
  if [ "$scenario" = hidden ]; then
    osascript -e 'tell application "System Events" to keystroke "m" using command down' 2>&1
    sleep 3
  fi
  a=$(cputime "$pid"); sleep "$SECS"; b=$(cputime "$pid")
  echo "== $scenario: $(echo "$a $b $SECS" | awk '{printf "%.2f s over %d s (%.1f%%)", $2 - $1, $3, 100 * ($2 - $1) / $3}')"
  ps -M -p "$pid" > "$dir/threads.txt" 2>&1
  awk 'NR > 1 && $(NF-4) + 0 > 0.5 { print "   thread", $0 }' "$dir/threads.txt" | head -12
  sample "$pid" "$SECS" -mayDie -file "$dir/sample.txt" >/dev/null 2>&1 || echo "   sample failed"
  [ -f "$dir/sample.txt" ] && {
    echo "   heaviest stack frames:"
    sed -n '/Sort by top of stack/,/Binary Images/p' "$dir/sample.txt" | sed -n '2,25p' | sed 's/^/   /'
  }
  kill "$pid" 2>/dev/null; sleep 2
}
for s in static dot plx hidden; do run "$s"; done
exit 0
