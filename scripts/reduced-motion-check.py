#!/usr/bin/env python3
"""Reduced-motion probe used by the private GTK display and macOS CI.

--program DIR: two solid panels: red for no-preference, green for reduce.
The second is created when DIR/late appears. No surface update is sent after
that, so changing the preference must repaint both idle surfaces itself.
--assert IMAGE reduce|no-preference COPIES: check the panels in a screenshot.
PPM needs only Python; PNG (the macOS runner) uses Pillow.
"""
import base64
from pathlib import Path
import select
import sys
import termios
import time
import tty
import os

HTML = b'''<style>body{margin:0;background:#ff0000;height:100vh}
@media(prefers-reduced-motion:reduce){body{background:#00ff00}}</style>'''


def program(out):
    out = Path(out)
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setraw(fd)

    def send(head, data=b''):
        os.write(1, b'\x1b]7279;' + head.encode() + b';' + base64.b64encode(data) + b'\x1b\\')

    def panel(name, row):
        send(f'a=doc:s={name}:q=2', HTML)
        os.write(1, f'\x1b[{row};1H'.encode())
        send(f'a=place:s={name}:c=20:r=5:q=2')

    try:
        os.write(1, b'\x1b[2J\x1b[H\x1b[?25l')
        panel('early', 1)
        (out / 'ready').touch()
        late = False
        while True:
            if not late and (out / 'late').exists():
                panel('late', 7)
                late = True
                (out / 'late-ready').touch()
            if select.select([fd], [], [], .05)[0]:
                data = os.read(fd, 4096)
                with (out / 'replies.log').open('ab') as log:
                    log.write(data)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def check(path, preference, copies):
    if path.endswith('.ppm'):
        with open(path, 'rb') as f:
            assert f.readline().strip() == b'P6'
            line = f.readline()
            while line.startswith(b'#'):
                line = f.readline()
            width, height = map(int, line.split())
            assert f.readline().strip() == b'255'
            rgb = f.read()
            assert len(rgb) == width * height * 3
    else:
        from PIL import Image
        rgb = Image.open(path).convert('RGB').tobytes()
    red = green = 0
    for r, g, b in zip(rgb[::3], rgb[1::3], rgb[2::3]):
        red += r > 180 and g < 80 and b < 80
        green += g > 180 and r < 80 and b < 80
    good, bad = (green, red) if preference == 'reduce' else (red, green)
    baseline = Path(path).parent / 'panel-pixels'
    if int(copies) == 1 and not baseline.exists():
        baseline.write_text(str(good))
    minimum = max(10000, int(baseline.read_text()) * int(copies) * .85)
    assert good >= minimum and bad < 1000, (preference, good, bad, minimum)
    print(f'ok {path}: {preference}, {good} matching pixels, {bad} opposite pixels')


if __name__ == '__main__':
    if sys.argv[1] == '--program':
        program(sys.argv[2])
    elif sys.argv[1] == '--assert':
        check(*sys.argv[2:])
    else:
        raise SystemExit(__doc__)
