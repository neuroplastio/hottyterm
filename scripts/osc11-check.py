#!/usr/bin/env python3
"""osc11-check.py: a surface that fills with var(--hotty-bg), after OSC 11.

    hottyterm -e python3 scripts/osc11-check.py [colour]    # default #191919

The program sets the terminal's background with OSC 11, fills the screen
with it, and places a surface over the middle that fills with
var(--hotty-bg) and draws a box in var(--hotty-fg). When the host follows
the terminal's colours (SPEC §8) the surface and the cells are one colour;
HT-03 was the surface keeping the configured background beside them.
It waits 2 seconds, then sets a second colour (#2a1a1a), and q quits.
"""
import os
import select
import sys
import termios
import time
import tty

ESC = "\x1b"
ST = ESC + "\\"
HTML = (b"<style>body{margin:0;background:var(--hotty-bg);color:var(--hotty-fg);"
        b"font:16px var(--hotty-font)}div{margin:1rlh;padding:1rlh;"
        b"border:1px solid var(--hotty-fg)}</style><div>This surface fills with "
        b"var(--hotty-bg).</div>")


def b64(b):
    import base64
    return base64.b64encode(b).decode()


def main():
    colour = sys.argv[1] if len(sys.argv) > 1 else "#191919"
    second = "#2a1a1a"
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setraw(fd)
    try:
        cols, rows = os.get_terminal_size()
        w = lambda s: os.write(1, s.encode())
        w(ESC + "[?1049h" + ESC + "[?25l" + f"{ESC}]11;{colour}{ST}" + ESC + "[2J")
        # The cells: a line of text in the terminal's background, to compare.
        w(ESC + "[1;1Hcells, in the background OSC 11 set")
        w(f"{ESC}]7279;a=doc:s=x;{b64(HTML)}{ST}")
        w(f"{ESC}[3;1H{ESC}]7279;a=place:s=x:c={cols}:r={max(rows - 4, 3)}{ST}")
        t0 = time.time()
        changed = False
        while True:
            r, _, _ = select.select([fd], [], [], 0.2)
            if r and os.read(fd, 16) in (b"q", b"\x03"):
                break
            if not changed and time.time() - t0 > 2:
                w(f"{ESC}]11;{second}{ST}" + ESC + "[1;1Hcells, now " + second + "        ")
                changed = True
    finally:
        w(f"{ESC}]111{ST}" + ESC + "[?25h" + ESC + "[?1049l")
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


if __name__ == "__main__":
    main()
