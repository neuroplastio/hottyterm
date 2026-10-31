#!/usr/bin/env python3
"""backdrop-demo.py: three panes of text in cells, on a backdrop of cards.

    hottyterm -e python3 scripts/backdrop-demo.py            # cards (b=1)
    hottyterm -e python3 scripts/backdrop-demo.py --boxes    # box-drawing borders
    hottyterm -e python3 scripts/backdrop-demo.py --gutter 1 # cards, gutters 1 column wide
    hottyterm -e python3 scripts/backdrop-demo.py --caps     # the host's features

hotty 0.6's V6-06, as hottyterm draws it with patch 0047
(mods/ghostty/backdrop-placements.md). The panes are text in the cells, on
the default background, with a gutter between them and round the edge, a
row tall and 2 columns wide (--gutter sets the columns). With cards, one
surface the size of the screen is placed as a backdrop, under the cells:
the canvas, a rounded card per pane in the terminal's background reaching
most of the way into the gutters, and a ring on the focused card. The
host carries the backdrop's edges on to the window's, over its padding.
With --boxes, the gutters are box-drawing lines instead, the focused
pane's in the accent, as a terminal multiplexer draws its panes today.

As V6-06 says a program must, it places the backdrop only on a host whose
capabilities list the feature `backdrop` (hotty-blitz lists it where the
terminal draws backdrops), and draws the boxes on any other. --caps shows
the host's features instead.

Tab moves the focus to the next pane; q quits.
"""
import base64
import os
import re
import select
import signal
import sys
import termios
import tty

ESC = "\x1b"
ST = ESC + "\\"

PANES = [
    # Each pane's lines: neutral text, coloured with SGR foregrounds only,
    # so every cell keeps the default background.
    [
        "\x1b[32m~/src/tide\x1b[0m \x1b[1m$\x1b[0m git log --oneline -6",
        "\x1b[33m4f1c2ab\x1b[0m parser: a quoted key keeps its spaces",
        "\x1b[33m9e07d31\x1b[0m lexer: tabs count as one column",
        "\x1b[33m1b55c80\x1b[0m cli: --check exits 2 on a warning",
        "\x1b[33m77a0f2e\x1b[0m docs: the table syntax, with examples",
        "\x1b[33mc3d9b14\x1b[0m parser: arrays of tables nest",
        "\x1b[33m05e6a7d\x1b[0m first commit",
        "",
        "\x1b[32m~/src/tide\x1b[0m \x1b[1m$\x1b[0m make test",
        "go test ./...",
        "\x1b[32mok\x1b[0m   tide/lexer    0.12s",
        "\x1b[32mok\x1b[0m   tide/parser   0.41s",
        "\x1b[32mok\x1b[0m   tide/cli      0.08s",
        "",
        "\x1b[32m~/src/tide\x1b[0m \x1b[1m$\x1b[0m \x1b[7m \x1b[0m",
    ],
    [
        "\x1b[2m 1\x1b[0m \x1b[35mpackage\x1b[0m parser",
        "\x1b[2m 2\x1b[0m",
        "\x1b[2m 3\x1b[0m \x1b[2m// Key reads a key: bare, or quoted with its spaces.\x1b[0m",
        "\x1b[2m 4\x1b[0m \x1b[35mfunc\x1b[0m (p *Parser) \x1b[34mKey\x1b[0m() (\x1b[36mstring\x1b[0m, \x1b[36merror\x1b[0m) {",
        "\x1b[2m 5\x1b[0m     \x1b[35mif\x1b[0m p.peek() == \x1b[32m'\"'\x1b[0m {",
        "\x1b[2m 6\x1b[0m         \x1b[35mreturn\x1b[0m p.quoted()",
        "\x1b[2m 7\x1b[0m     }",
        "\x1b[2m 8\x1b[0m     start := p.pos",
        "\x1b[2m 9\x1b[0m     \x1b[35mfor\x1b[0m p.pos < \x1b[34mlen\x1b[0m(p.src) && bare(p.src[p.pos]) {",
        "\x1b[2m10\x1b[0m         p.pos++",
        "\x1b[2m11\x1b[0m     }",
        "\x1b[2m12\x1b[0m     \x1b[35mreturn\x1b[0m p.src[start:p.pos], \x1b[35mnil\x1b[0m",
        "\x1b[2m13\x1b[0m }",
    ],
    [
        "\x1b[2m12:04:31\x1b[0m \x1b[34mINFO\x1b[0m  watching 14 files",
        "\x1b[2m12:04:33\x1b[0m \x1b[34mINFO\x1b[0m  parser.go changed",
        "\x1b[2m12:04:33\x1b[0m \x1b[34mINFO\x1b[0m  build ok in 0.9s",
        "\x1b[2m12:04:34\x1b[0m \x1b[33mWARN\x1b[0m  lexer.go:88 unused variable col",
        "\x1b[2m12:04:36\x1b[0m \x1b[34mINFO\x1b[0m  tests: 41 passed",
        "\x1b[2m12:05:02\x1b[0m \x1b[34mINFO\x1b[0m  parser.go changed",
        "\x1b[2m12:05:03\x1b[0m \x1b[31mERROR\x1b[0m parser_test.go:120: want \"a b\", got \"a\"",
        "\x1b[2m12:05:03\x1b[0m \x1b[34mINFO\x1b[0m  tests: 40 passed, 1 failed",
    ],
]


def layout(cols, rows, gc=1):
    """The panes' rectangles in cells, (x, y, w, h): a gutter round the edge
    and between them, a row tall and gc columns wide, the first pane on
    the left, the others stacked on the right."""
    g = cols // 2 - gc // 2
    h = rows // 2
    return [
        (gc, 1, g - gc, rows - 2),
        (g + gc, 1, cols - g - 2 * gc, h - 1),
        (g + gc, h + 1, cols - g - 2 * gc, rows - h - 2),
    ]


def osc(control, payload=b""):
    b64 = base64.b64encode(payload).decode()
    out = []
    head = ESC + "]7279;"
    if len(b64) <= 4096:
        return head + control + (";" + b64 if b64 else "") + ST
    for i in range(0, len(b64), 4096):
        piece = b64[i:i + 4096]
        more = "0" if i + 4096 >= len(b64) else "1"
        out.append(head + (control + ":m=1" if i == 0 else "m=" + more) + ";" + piece + ST)
    return "".join(out)


def backdrop_html(panes, focus, gc=1):
    """The backdrop: the canvas, and a card per pane reaching half a gutter
    past its cells less half the gap between cards."""
    cards = []
    for i, (x, y, w, h) in enumerate(panes):
        cls = "card focus" if i == focus else "card"
        cards.append(
            f'<div class="{cls}" style="'
            f"left: calc({x} * var(--cw) - var(--px)); top: calc({y} * var(--ch) - var(--py)); "
            f"width: calc({w} * var(--cw) + 2 * var(--px)); height: calc({h} * var(--ch) + 2 * var(--py));"
            '"></div>'
        )
    return """<style>
:root {
  --cw: var(--hotty-cell-w);
  --ch: var(--hotty-cell-h);
  --gap: 4px;
  --px: calc(""" + str(gc) + """ * var(--cw) / 2 - var(--gap) / 2);
  --py: calc(var(--ch) / 2 - var(--gap) / 2);
  --canvas: color-mix(in srgb, var(--hotty-bg) 70%, black);
  --ring: color-mix(in srgb, var(--hotty-ansi-4) 75%, white);
}
html, body { margin: 0; height: 100%; overflow: hidden; background: var(--canvas); }
.card {
  position: absolute;
  box-sizing: border-box;
  border-radius: 10px;
  background: var(--hotty-bg);
  border: 1px solid rgb(255 255 255 / 0.07);
}
.card.focus { border-color: var(--ring); box-shadow: 0 0 0 1px color-mix(in srgb, var(--ring) 45%, transparent); }
</style>
""" + "\n".join(cards)


def boxes(panes, cols, rows, focus):
    """The gutters as box-drawing lines, rounded at the window's corners; a
    line beside the focused pane in the accent (blue), the rest dim."""
    grid = [[" "] * cols for _ in range(rows)]
    hot = [[False] * cols for _ in range(rows)]
    fx, fy, fw, fh = panes[focus]

    def near_focus(c, r):
        return fx - 1 <= c <= fx + fw and fy - 1 <= r <= fy + fh

    lines = set()
    for c in range(cols):
        lines.add((c, 0))
        lines.add((c, rows - 1))
    for r in range(rows):
        lines.add((0, r))
        lines.add((cols - 1, r))
    g = panes[0][0] + panes[0][2]
    h = panes[1][1] + panes[1][3]
    for r in range(rows):
        lines.add((g, r))
    for c in range(g, cols):
        lines.add((c, h))
    for c, r in lines:
        up = (c, r - 1) in lines
        down = (c, r + 1) in lines
        left = (c - 1, r) in lines
        right = (c + 1, r) in lines
        ch = {
            (False, True, False, True): "╭", (False, True, True, False): "╮",
            (True, False, False, True): "╰", (True, False, True, False): "╯",
            (True, True, False, True): "├", (True, True, True, False): "┤",
            (False, True, True, True): "┬", (True, False, True, True): "┴",
            (True, True, True, True): "┼",
        }.get((up, down, left, right), "│" if up or down else "─")
        grid[r][c] = ch
        hot[r][c] = near_focus(c, r)
    out = []
    for r in range(rows):
        row = []
        for c in range(cols):
            if (c, r) in lines:
                row.append(f"\x1b[{c + 1}G" + ("\x1b[34m" if hot[r][c] else "\x1b[90m") + grid[r][c] + "\x1b[0m")
        out.append(f"\x1b[{r + 1};1H" + "".join(row))
    return "".join(out)


SGR = re.compile(r"\x1b\[[0-9;]*m")


def clip(line, w):
    """line cut to w cells, its SGR kept and reset after the cut: each
    pane's text stays in its pane, whatever the window's size. The
    panes' text is ASCII, a cell a character."""
    out, n, i = [], 0, 0
    while i < len(line) and n < w:
        m = SGR.match(line, i)
        if m:
            out.append(m.group())
            i = m.end()
            continue
        out.append(line[i])
        n += 1
        i += 1
    return "".join(out) + "\x1b[0m"


def text(panes):
    out = []
    for (x, y, w, h), lines in zip(panes, PANES):
        if w <= 0:
            continue
        for i, line in enumerate(lines[:max(h, 0)]):
            out.append(f"\x1b[{y + i + 1};{x + 1}H{clip(line, w)}")
    return "".join(out)


def unpack(b, i=0):
    """The msgpack value at b[i:] and where it ends: the kinds a host's
    capabilities hold (SPEC §3.3)."""
    c = b[i]
    def n(size, at):
        return int.from_bytes(b[at:at + size], "big")
    if c <= 0x7F:
        return c, i + 1
    if c >= 0xE0:
        return c - 0x100, i + 1
    if 0x80 <= c <= 0x8F or c in (0xDE, 0xDF):
        count, i = (c & 0x0F, i + 1) if c <= 0x8F else (n(2, i + 1), i + 3) if c == 0xDE else (n(4, i + 1), i + 5)
        out = {}
        for _ in range(count):
            k, i = unpack(b, i)
            out[k], i = unpack(b, i)
        return out, i
    if 0x90 <= c <= 0x9F or c in (0xDC, 0xDD):
        count, i = (c & 0x0F, i + 1) if c <= 0x9F else (n(2, i + 1), i + 3) if c == 0xDC else (n(4, i + 1), i + 5)
        out = []
        for _ in range(count):
            v, i = unpack(b, i)
            out.append(v)
        return out, i
    if 0xA0 <= c <= 0xBF or c in (0xD9, 0xDA, 0xDB):
        size, at = (c & 0x1F, i + 1) if c <= 0xBF else {0xD9: (n(1, i + 1), i + 2), 0xDA: (n(2, i + 1), i + 3), 0xDB: (n(4, i + 1), i + 5)}[c]
        return b[at:at + size].decode(), at + size
    fixed = {0xC0: (None, 1), 0xC2: (False, 1), 0xC3: (True, 1)}
    if c in fixed:
        v, k = fixed[c]
        return v, i + k
    if c in (0xCA, 0xCB):
        import struct
        return (struct.unpack(">f", b[i + 1:i + 5])[0], i + 5) if c == 0xCA else (struct.unpack(">d", b[i + 1:i + 9])[0], i + 9)
    sizes = {0xCC: 1, 0xCD: 2, 0xCE: 4, 0xCF: 8, 0xD0: 1, 0xD1: 2, 0xD2: 4, 0xD3: 8}
    if c in sizes:
        return int.from_bytes(b[i + 1:i + 1 + sizes[c]], "big", signed=c >= 0xD0), i + 1 + sizes[c]
    raise ValueError(f"msgpack 0x{c:02x} at {i}")


def query(fd):
    """Asks for a host (SPEC §4), fenced with DA1, and waits for the DA1:
    the host's capabilities, or None without one."""
    os.write(1, (osc("a=q:n=1:v=0.5") + ESC + "[c").encode())
    buf = b""
    while not re.search(rb"\x1b\[\?[0-9;]*c", buf):
        r, _, _ = select.select([fd], [], [], 2)
        if not r:
            break
        buf += os.read(fd, 4096)
    m = re.search(rb"\x1b\]7279;a=ok[^;\x1b\x07]*;([A-Za-z0-9+/=]*)", buf)
    if not m:
        return None
    try:
        return unpack(base64.b64decode(m.group(1)))[0]
    except (ValueError, IndexError):
        return {}


def main():
    boxed = "--boxes" in sys.argv
    show_caps = "--caps" in sys.argv
    gc = int(sys.argv[sys.argv.index("--gutter") + 1]) if "--gutter" in sys.argv else 2
    if boxed:
        gc = 1  # the lines are a cell wide
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setraw(fd)
    focus = 0
    # A resize draws again at the new size at once (SIGWINCH): the handler
    # wakes the loop's select through a pipe.
    wake_r, wake_w = os.pipe()
    os.set_blocking(wake_w, False)
    signal.signal(signal.SIGWINCH, lambda *_: os.write(wake_w, b"w"))
    try:
        os.write(1, (ESC + "[?1049h" + ESC + "[?25l" + ESC + "[2J").encode())
        caps = query(fd)
        host = caps is not None and "backdrop" in caps.get("features", [])
        if show_caps:
            features = "none: not a hotty host" if caps is None else ", ".join(caps.get("features", [])) or "none"
            os.write(1, (ESC + "[1;1H" + "the host's features: " + features + "\r\n" +
                         ("backdrop listed" if host else "no backdrop") + "\r\n\r\nq quits").encode())
            while os.read(fd, 64) not in (b"q", b"\x03"):
                pass
            return
        if not host:
            gc = 1  # the boxes' lines are a cell wide
        while True:
            cols, rows = os.get_terminal_size()
            panes = layout(cols, rows, gc)
            out = ESC + "[2J"
            small = cols < 8 * gc + 12 or rows < 7
            if small:
                # Too small for three panes: say so, and wait for a resize.
                out += ESC + "[1;1H" + clip("too small for the panes", cols)
            elif boxed or not host:
                out += boxes(panes, cols, rows, focus)
            else:
                html = backdrop_html(panes, focus, gc).encode()
                out += osc("a=doc:s=backdrop", html)
                out += ESC + "[1;1H" + osc(f"a=place:s=backdrop:c={cols}:r={rows}:b=1:C=1")
            if not small:
                out += text(panes)
            os.write(1, out.encode())
            r, _, _ = select.select([fd, wake_r], [], [])
            if wake_r in r:
                os.read(wake_r, 64)
                continue
            key = os.read(fd, 64)
            if key in (b"q", b"\x03"):
                break
            if key == b"\t":
                focus = (focus + 1) % len(panes)
    finally:
        os.write(1, (ESC + "[?25h" + ESC + "[?1049l").encode())
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


if __name__ == "__main__":
    main()
