#!/usr/bin/env python3
"""Refresh-rate probe for scripts/refresh-rate-check.sh.

--program DIR: places one surface whose background animates without end
(a CSS animation, which hotty-blitz paces to the display's rate), touches
DIR/ready, and reads the terminal's replies until it is closed.
--renders TRACE_DIR SECONDS: counts hotty-blitz's renders (blitz.render, in
HOTTY_TRACE's files) over the next SECONDS, and prints their rate a second.
"""
import base64
import json
import os
from pathlib import Path
import select
import sys
import termios
import time
import tty

HTML = b'''<style>@keyframes go{from{background:#f00}to{background:#00f}}
body{margin:0;height:100vh;animation:go 1s linear infinite alternate}</style>'''


def program(out):
    out = Path(out)
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setraw(fd)

    def send(head, data=b''):
        os.write(1, b'\x1b]7279;' + head.encode() + b';' + base64.b64encode(data) + b'\x1b\\')

    try:
        os.write(1, b'\x1b[2J\x1b[H\x1b[?25l')
        send('a=doc:s=go:q=2', HTML)
        send('a=place:s=go:c=20:r=5:q=2')
        (out / 'ready').touch()
        while True:
            if select.select([fd], [], [], .05)[0]:
                if not os.read(fd, 4096):
                    break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def renders(trace, seconds):
    # The trace's clock is CLOCK_MONOTONIC, as time.monotonic_ns is on Linux.
    t0 = time.monotonic_ns()
    time.sleep(seconds)
    t1 = time.monotonic_ns()
    # The trace is written out every 50 ms.
    time.sleep(.3)
    count = 0
    for f in Path(trace).glob('blitz-*.jsonl'):
        for line in f.open():
            try:
                e = json.loads(line)
            except ValueError:
                continue
            if e.get('n') == 'blitz.render' and t0 <= e.get('t', 0) < t1:
                count += 1
    print(f'{count / seconds:.1f}')


if __name__ == '__main__':
    if sys.argv[1] == '--program':
        program(sys.argv[2])
    elif sys.argv[1] == '--renders':
        renders(sys.argv[2], float(sys.argv[3]))
    else:
        sys.exit(__doc__)
