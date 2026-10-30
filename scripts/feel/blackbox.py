#!/usr/bin/env python3
"""blackbox.py: the latency rig's timer, from an input to its pixels (gov R-22).

    scripts/feel/blackbox.py [--roi X,Y,W,H] [--settle-ms 200] [--timeout-ms 3000]
                             [--scenario E1] [--warmup N] [--json] [--output NAME]
                             [--hold-ms 30] [--builtin-keymap] [--ipc SOCKET]
                             [STEPS.jsonl ... | -]

It plays steps on the display in $WAYLAND_DISPLAY (the perf sway,
scripts/feel/sway.sh; when unset, the one in ~/.cache/hotty/sway-feel/display)
as a user would, and times each from the input to the first frame of the
output that shows it. It is a Wayland client on the raw wire protocol, stdlib
only (as hotty-blitz's scripts/vpointer.py is), and it holds for its whole life:

- a virtual keyboard (zwp_virtual_keyboard_v1) with a "us" XKB keymap, from
  `xkbcli compile-keymap --layout us` or built in. The display has a
  keyboard, and so a focused window, only while a virtual keyboard exists,
  and Ghostty takes a click without one as a focus click. A fresh virtual
  keyboard drops its first key, so it starts with a Shift press and release;
- a virtual pointer (zwlr_virtual_pointer_v1) on the output;
- a screencopy (zwlr_screencopy_v1, no cursor overlaid) of the output, or of
  the step's region of interest, into two wl_shm buffers;
- with a focus step, the compositor's IPC (sway's i3-ipc): --ipc, or the
  perf sway's, from ~/.cache/hotty/sway-feel/ipc, and never $SWAYSOCK. Its
  peer must be the process the Wayland socket's is.

It refuses a display that isn't a headless output, or that is Hyprland's.

Steps
-----
JSON lines from the files named, or from stdin ("-", or no file). Blank lines
and lines that start with "#" are skipped. A step is an object with one action:

  {"key": "a"}                     press a key; release it --hold-ms (30) later
  {"key": "A"}                     a character that needs Shift gets Shift
  {"key": "Return"}                a key by its keysym name: Return, Tab,
                                   BackSpace, Escape, space, Delete, Insert,
                                   Home, End, Prior (Page_Up), Next (Page_Down),
                                   Up, Down, Left, Right, F1..F12, Shift_L,
                                   Control_L, Alt_L, Super_L, Menu, minus, ...
  {"key": "b", "mods": ["ctrl"]}   with modifiers: ctrl, shift, alt, super.
                                   Each mod's key goes down (and the modifier
                                   state with it) in order, then the key; after
                                   the hold, the key comes up, then the mods in
                                   reverse
  {"keys": "hello"}                a key step per character ("\\n" is Return,
                                   "\\t" Tab); its other fields apply to each
  {"move": [x, y]}                 the pointer to x, y
  {"click": [x, y]}                move there, press the left button and
                                   release it after the hold; "button": "right"
                                   or "middle" for another
  {"wheel": [x, y, n]}             move there, then n notches of the wheel at
                                   once (n > 0 scrolls down, n < 0 up)
  {"focus": 17}                    the keyboard focus to the window whose
                                   container id (sway's con_id) this is, by the
                                   IPC's `[con_id=17] focus`; its input is sent
                                   when sway's reply comes. Every focus step's
                                   window must exist before the first step
  {"sleep_ms": 500}                wait; nothing is sent, nothing is timed

Any of them may add:

  "hold_ms": 10                    with key, keys or click: how long it stays
                                   down, instead of --hold-ms
  "untimed": true                  a setup step: sent but not timed; the next
                                   step waits until the screen has settled
                                   after it (not with sleep_ms)
  "settle": false                  with untimed: the next step starts as soon
                                   as this one's input is all sent (a key's or
                                   a click's release, its hold after the
                                   press; a focus's reply), the screen
                                   settled or not
  "quiet": false                   on a timed step: sent as soon as the step
                                   before it is done, without waiting for its
                                   ROI to be quiet first and without the
                                   jitter (Timing, 1 and 2): what it times is
                                   an input that follows another, as typing
                                   does. Its --json line's quiet_before is null
  "mark": "open"                   a name ([a-z0-9_.-], at most 40): when its
                                   input is sent (a sleep: when it starts),
                                   rig.mark is stamped, warmup or not, and
                                   the next timed step's --json line gives
                                   since_mark, {name: ms from the latest such
                                   mark to its input}, for the marks since the
                                   timed step before it
  "roi": [x, y, w, h]              where this step's change shows, instead of
                                   --roi
  "roi_frac": [fx, fy, fw, fh]     the same in fractions of the output's
                                   logical size, so one scenario fits every
                                   scale
  "note": "..."                    ignored

x, y and the ROI are logical px of the output from its top left: 1200x750 at
scale 2, 1500x937 at 1.6. A timed step without a ROI of its own uses --roi
(the whole output by default). An untimed step or a sleep without one watches
the next timed step's ROI, so its settle is on the pixels the next
measurement compares.

A leader sequence is {"key": "b", "mods": ["ctrl"], "untimed": true} followed
by {"key": "2"}: the leader's own redraw settles before "2" takes its baseline.

Two keys typed fast, the second timed, are {"key": "colon", "untimed": true,
"settle": false} followed by {"key": "a", "quiet": false}: "a" goes down as
":" comes up, its hold (--hold-ms, or its hold_ms) after its press, whatever
":" is drawing then.

Timing
------
For each timed step:
1. The ROI must have been quiet (no frame changed it) for --settle-ms. When
   the step's ROI isn't the one being captured, the capture moves to it, its
   first frame is the new baseline, and the quiet counts from that frame.
   The capture moves before a step is sent, timed or not, so a step that
   doesn't wait ("quiet": false) should share the ROI of the steps before it
   that don't either, or the move costs it a frame.
2. It waits a random time, uniform in [0, --jitter-ms) (one refresh period
   by default; seeded by --seed). The quiet ends at a frame's time plus
   --settle-ms, and 200 ms is 12 frames at 60 Hz, so without the wait every
   input would land at the same point of the output's frame, and the
   numbers would be that one phase's, not the spread a person meets.
   The --json line's since_frame is how far into the output's frame the
   input landed, in ms: the time since the last frame captured (with
   --on-demand, frames come only with damage, so then it is not).
3. rig.input: t is CLOCK_MONOTONIC, read right before the request leaves.
4. Frames come by plain copies, one per output frame: each copy asks the
   output for a frame, so the headless output draws at its refresh, as a
   display does. Without them it would draw on demand, the moment a client
   commits, and a client that commits at once would gain up to a frame no
   display gives it. --on-demand copies with damage instead. The ready
   event carries the commit's time on wlroots' presentation clock, which
   must be CLOCK_MONOTONIC (wp_presentation says so; it is checked). A frame stamped at or before the input shows the
   screen before it: if it differs, it becomes the baseline, so a frame
   already in flight can't count. The first frame stamped after the input
   whose ROI bytes differ from the baseline (memcmp; damage alone isn't a
   change) is rig.pixels, with t = that frame's ready time.
5. Then it waits until no frame has changed the ROI for --settle-ms (at most
   --timeout-ms) before the next step. Without a change within --timeout-ms
   the step is a miss: rig.miss.

--warmup N: the first N timed steps run like the rest but aren't stamped and
don't count; their --json lines say "warmup": true. Stamped inputs count i
from 0.

Output
------
- With $HOTTY_TRACE set: $HOTTY_TRACE/rig-<pid>.jsonl in the trace format
  hotty/1 (docs/trace.md): rig.input, rig.pixels and rig.miss, each with a.i,
  a.sc and a.kind, and rig.mark (a.mark, a.sc, a.kind) for a step's mark;
  written after each timed step, at exit and on SIGTERM.
- On stdout, a summary: the inputs, the misses, p50/p95/p99 of pixels − input
  in ms (nearest rank), what a copy costs and the frame rate kept. With
  --json, stdout is JSON lines only: one per timed step, then
  {"summary": ...}; warnings and errors go into them too.
"""
import argparse
import ctypes
import heapq
import json
import math
import mmap
import os
import random
import re
import select
import shutil
import signal
import socket
import struct
import subprocess
import sys
import time

GRACE = 50_000_000  # ns past the timeout for a frame still being copied
CLOCK_MONOTONIC = 1  # wp_presentation.clock_id's value for it on Linux
BUTTONS = {"left": 0x110, "right": 0x111, "middle": 0x112}
ALLOWED = {"key", "keys", "mods", "move", "click", "button", "wheel", "focus", "sleep_ms", "hold_ms",
           "untimed", "settle", "quiet", "mark", "roi", "roi_frac", "note"}
ACTIONS = ("key", "keys", "move", "click", "wheel", "focus", "sleep_ms")
MARK = re.compile(r"^[a-z0-9_.-]{1,40}$")


def now():
    return time.clock_gettime_ns(time.CLOCK_MONOTONIC)


def ms_clock():
    return (now() // 1_000_000) & 0xFFFFFFFF


class Fatal(Exception):
    pass


class Stop(Exception):
    pass


# ---- the "us" keyboard: evdev code, XKB key name, keysym, keysym with Shift

KEYS = [
    (1, "ESC", "Escape", None),
    *[(2 + k, f"AE{k + 1:02d}", d, s) for k, (d, s) in enumerate(zip("1234567890", "!@#$%^&*()"))],
    (12, "AE11", "-", "_"), (13, "AE12", "=", "+"), (14, "BKSP", "BackSpace", None),
    (15, "TAB", "Tab", "ISO_Left_Tab"),
    *[(16 + k, f"AD{k + 1:02d}", c, c.upper()) for k, c in enumerate("qwertyuiop")],
    (26, "AD11", "[", "{"), (27, "AD12", "]", "}"), (28, "RTRN", "Return", None),
    (29, "LCTL", "Control_L", None),
    *[(30 + k, f"AC{k + 1:02d}", c, c.upper()) for k, c in enumerate("asdfghjkl")],
    (39, "AC10", ";", ":"), (40, "AC11", "'", '"'), (41, "TLDE", "`", "~"),
    (42, "LFSH", "Shift_L", None), (43, "BKSL", "\\", "|"),
    *[(44 + k, f"AB{k + 1:02d}", c, c.upper()) for k, c in enumerate("zxcvbnm")],
    (51, "AB08", ",", "<"), (52, "AB09", ".", ">"), (53, "AB10", "/", "?"),
    (54, "RTSH", "Shift_R", None), (56, "LALT", "Alt_L", "Meta_L"), (57, "SPCE", "space", None),
    (58, "CAPS", "Caps_Lock", None),
    *[(59 + k, f"FK{k + 1:02d}", f"F{k + 1}", None) for k in range(10)],
    (87, "FK11", "F11", None), (88, "FK12", "F12", None), (97, "RCTL", "Control_R", None),
    (100, "RALT", "Alt_R", "Meta_R"), (102, "HOME", "Home", None), (103, "UP", "Up", None),
    (104, "PGUP", "Prior", None), (105, "LEFT", "Left", None), (106, "RGHT", "Right", None),
    (107, "END", "End", None), (108, "DOWN", "Down", None), (109, "PGDN", "Next", None),
    (110, "INS", "Insert", None), (111, "DELE", "Delete", None), (125, "LWIN", "Super_L", None),
    (126, "RWIN", "Super_R", None), (127, "COMP", "Menu", None),
]
SYM = {"!": "exclam", "@": "at", "#": "numbersign", "$": "dollar", "%": "percent",
       "^": "asciicircum", "&": "ampersand", "*": "asterisk", "(": "parenleft",
       ")": "parenright", "-": "minus", "_": "underscore", "=": "equal", "+": "plus",
       "[": "bracketleft", "{": "braceleft", "]": "bracketright", "}": "braceright",
       ";": "semicolon", ":": "colon", "'": "apostrophe", '"': "quotedbl", "`": "grave",
       "~": "asciitilde", "\\": "backslash", "|": "bar", ",": "comma", "<": "less",
       ".": "period", ">": "greater", "/": "slash", "?": "question"}
# The keymap's real modifiers: the key that sets each and its mask bit.
MODS = {"shift": (42, 1 << 0), "ctrl": (29, 1 << 2), "alt": (56, 1 << 3), "super": (125, 1 << 6)}
ALIASES = {"Enter": "Return", "Esc": "Escape", "Backspace": "BackSpace", "Del": "Delete",
           "Page_Up": "Prior", "PageUp": "Prior", "Page_Down": "Next", "PageDown": "Next",
           "Space": "space"}


def key_tables():
    chars, names = {" ": (57, False), "\n": (28, False), "\t": (15, False)}, {}
    for code, _, base, shifted in KEYS:
        for sym, shift in ((base, False), (shifted, True)):
            if sym is None:
                continue
            if len(sym) == 1:
                chars.setdefault(sym, (code, shift))
                names.setdefault(SYM.get(sym, sym), (code, shift))
            else:
                names.setdefault(sym, (code, shift))
    for alias, sym in ALIASES.items():
        names[alias] = names[sym]
    return chars, names


CHARS, NAMES = key_tables()


def lookup_key(k):
    """A key step's key: (evdev code, needs Shift)."""
    if not isinstance(k, str) or not k:
        raise ValueError(f"not a key: {k!r}")
    if len(k) == 1 and k in CHARS:
        return CHARS[k]
    if k in NAMES:
        return NAMES[k]
    raise ValueError(f"no key {k!r} on the us keymap")


def builtin_keymap():
    """A complete "us" keymap for the keys in KEYS, in XKB's text format."""
    def sym(s):
        return SYM.get(s, s)
    codes = "\n".join(f"    <{name}> = {code + 8};" for code, name, _, _ in KEYS)
    syms = []
    for _, name, base, shifted in KEYS:
        if shifted is None:
            syms.append(f"    key <{name}> {{ type = \"ONE_LEVEL\", [ {sym(base)} ] }};")
        else:
            kind = "ALPHABETIC" if base.isalpha() and len(base) == 1 else "TWO_LEVEL"
            syms.append(f"    key <{name}> {{ type = \"{kind}\", [ {sym(base)}, {sym(shifted)} ] }};")
    syms = "\n".join(syms)
    return f"""xkb_keymap {{
  xkb_keycodes "blackbox" {{
    minimum = 8;
    maximum = 255;
{codes}
    indicator 1 = "Caps Lock";
  }};
  xkb_types "blackbox" {{
    virtual_modifiers Alt,Super;
    type "ONE_LEVEL" {{ modifiers = none; level_name[Level1] = "Any"; }};
    type "TWO_LEVEL" {{ modifiers = Shift; map[Shift] = Level2;
      level_name[Level1] = "Base"; level_name[Level2] = "Shift"; }};
    type "ALPHABETIC" {{ modifiers = Shift+Lock; map[Shift] = Level2; map[Lock] = Level2;
      level_name[Level1] = "Base"; level_name[Level2] = "Caps"; }};
  }};
  xkb_compat "blackbox" {{
    virtual_modifiers Alt,Super;
    interpret Shift_L {{ action = SetMods(modifiers=Shift); }};
    interpret Shift_R {{ action = SetMods(modifiers=Shift); }};
    interpret Control_L {{ action = SetMods(modifiers=Control); }};
    interpret Control_R {{ action = SetMods(modifiers=Control); }};
    interpret Alt_L {{ virtualModifier = Alt; action = SetMods(modifiers=modMapMods); }};
    interpret Alt_R {{ virtualModifier = Alt; action = SetMods(modifiers=modMapMods); }};
    interpret Super_L {{ virtualModifier = Super; action = SetMods(modifiers=modMapMods); }};
    interpret Super_R {{ virtualModifier = Super; action = SetMods(modifiers=modMapMods); }};
    interpret Caps_Lock {{ action = LockMods(modifiers=Lock); }};
    indicator "Caps Lock" {{ modifiers = Lock; }};
  }};
  xkb_symbols "blackbox" {{
    name[Group1] = "English (US)";
{syms}
    modifier_map Shift {{ <LFSH>, <RTSH> }};
    modifier_map Lock {{ <CAPS> }};
    modifier_map Control {{ <LCTL>, <RCTL> }};
    modifier_map Mod1 {{ <LALT>, <RALT> }};
    modifier_map Mod4 {{ <LWIN>, <RWIN> }};
  }};
}};
"""


def keymap(builtin):
    """The keymap text and where it came from."""
    xkbcli = shutil.which("xkbcli")
    if xkbcli and not builtin:
        try:
            r = subprocess.run([xkbcli, "compile-keymap", "--layout", "us"], capture_output=True,
                               timeout=10, check=True)
            if b"xkb_keymap" in r.stdout:
                return r.stdout, "xkbcli"
        except (OSError, subprocess.SubprocessError):
            pass
    return builtin_keymap().encode(), "built in"


# ---- steps

def load_steps(paths):
    """The steps, checked and expanded: a "keys" string becomes key steps."""
    sources = paths or ["-"]
    out = []
    for path in sources:
        if path == "-":
            if sys.stdin.isatty():
                raise Fatal("steps come on stdin or from files; see --help")
            lines, name = sys.stdin.read().splitlines(), "stdin"
        else:
            with open(path) as f:
                lines, name = f.read().splitlines(), path
        for n, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                out += expand(json.loads(line))
            except (ValueError, TypeError) as e:
                raise Fatal(f"{name}:{n}: {e}")
    return out


def expand(st):
    if not isinstance(st, dict):
        raise ValueError("a step is a JSON object")
    unknown = set(st) - ALLOWED
    if unknown:
        raise ValueError(f"unknown fields {sorted(unknown)}")
    acts = [a for a in ACTIONS if a in st]
    if len(acts) != 1:
        raise ValueError(f"a step has one action of {list(ACTIONS)}, not {acts or 'none'}")
    act = acts[0]
    untimed = st.get("untimed", False)
    if not isinstance(untimed, bool):
        raise ValueError("untimed is true or false")
    roi = roi_spec(st)
    mods = st.get("mods", [])
    if not isinstance(mods, list) or any(m not in MODS for m in mods):
        raise ValueError(f"mods is a list of {sorted(MODS)}")
    if mods and act not in ("key", "keys"):
        raise ValueError("mods go with key or keys")
    if "button" in st and act != "click":
        raise ValueError("button goes with click")
    settle, quiet, mark = st.get("settle", True), st.get("quiet", True), st.get("mark")
    for k, v in (("settle", settle), ("quiet", quiet)):
        if not isinstance(v, bool):
            raise ValueError(f"{k} is true or false")
    if "settle" in st and (act == "sleep_ms" or not untimed):
        raise ValueError("settle goes with untimed: a timed step always settles, and a sleep never")
    if "quiet" in st and (act == "sleep_ms" or untimed):
        raise ValueError("quiet goes with a timed step")
    if mark is not None and not (isinstance(mark, str) and MARK.match(mark)):
        raise ValueError("mark is a name of [a-z0-9_.-], at most 40 long")
    hold = st.get("hold_ms")
    if hold is not None:
        if act not in ("key", "keys", "click"):
            raise ValueError("hold_ms goes with key, keys or click")
        if isinstance(hold, bool) or not isinstance(hold, (int, float)) or hold < 0:
            raise ValueError("hold_ms is a number of ms")
    base = {"untimed": untimed, "roi": roi, "settle": settle, "quiet": quiet, "mark": mark, "hold_ms": hold}
    if act == "sleep_ms":
        ms = st["sleep_ms"]
        if isinstance(ms, bool) or not isinstance(ms, (int, float)) or ms < 0:
            raise ValueError("sleep_ms is a number of ms")
        if untimed:
            raise ValueError("a sleep is never timed: no untimed")
        return [{**base, "kind": "sleep", "untimed": True, "ms": ms}]
    if act == "focus":
        con = st["focus"]
        if isinstance(con, bool) or not isinstance(con, int) or con < 1:
            raise ValueError("focus is a window's container id (sway's con_id): a positive int")
        return [{**base, "kind": "focus", "con": con}]
    if act in ("key", "keys"):
        chars = [st["key"]] if act == "key" else list(st["keys"]) if isinstance(st["keys"], str) else None
        if not chars:
            raise ValueError("keys is a non-empty string")
        steps = []
        for k in chars:
            code, shift = lookup_key(k)
            m = list(mods) + (["shift"] if shift and "shift" not in mods else [])
            steps.append({**base, "kind": "key", "key": k, "code": code, "mods": m})
        return steps
    if act in ("move", "click"):
        xy = st[act]
        if not (isinstance(xy, list) and len(xy) == 2 and all(isinstance(v, (int, float)) for v in xy)):
            raise ValueError(f"{act} is [x, y]")
        b = st.get("button", "left")
        if b not in BUTTONS:
            raise ValueError(f"button is one of {sorted(BUTTONS)}")
        return [{**base, "kind": act, "xy": xy, "button": BUTTONS[b]}]
    w = st["wheel"]
    if not (isinstance(w, list) and len(w) == 3 and all(isinstance(v, (int, float)) for v in w)
            and int(w[2]) == w[2] and w[2] != 0):
        raise ValueError("wheel is [x, y, notches], notches a non-zero int")
    return [{**base, "kind": "wheel", "xy": w[:2], "notches": int(w[2])}]


def roi_spec(st):
    if "roi" in st and "roi_frac" in st:
        raise ValueError("roi or roi_frac, not both")
    for k in ("roi", "roi_frac"):
        if k in st:
            v = st[k]
            if not (isinstance(v, list) and len(v) == 4 and all(isinstance(x, (int, float)) for x in v)):
                raise ValueError(f"{k} is [x, y, w, h]")
            return (k, tuple(v))
    return None


def parse_roi(s):
    try:
        v = [float(x) for x in s.split(",")]
    except ValueError:
        v = []
    if len(v) != 4:
        raise argparse.ArgumentTypeError("--roi is x,y,w,h")
    return ("roi", tuple(v))


# ---- the wire

def u32(*v):
    return struct.pack(f"<{len(v)}I", *(x & 0xFFFFFFFF for x in v))


def i32(*v):
    return struct.pack(f"<{len(v)}i", *v)


def fixed(x):
    return struct.pack("<i", round(x * 256))


def wstr(s):
    b = s.encode() + b"\0"
    return struct.pack("<I", len(b)) + b + b"\0" * (-len(b) % 4)


def rstr(body, off):
    n = struct.unpack_from("<I", body, off)[0]
    return body[off + 4:off + 4 + max(n - 1, 0)].decode(errors="replace"), off + 4 + ((n + 3) & ~3)


class Wire:
    """One Wayland connection: requests out, events to a handler per object."""

    def __init__(self, path):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self.sock.connect(path)
        except OSError as e:
            raise Fatal(f"can't connect to {path}: {e}")
        self.next_id = 2
        self.handlers = {1: self.on_display}
        self.names = {1: "wl_display"}
        self.inbuf = b""
        self.out = []

    def new(self, name, handler=None):
        oid = self.next_id
        self.next_id += 1
        self.names[oid] = name
        if handler:
            self.handlers[oid] = handler
        return oid

    def drop(self, oid):
        self.handlers.pop(oid, None)

    @staticmethod
    def msg(obj, op, args=b""):
        return struct.pack("<IHH", obj, op, 8 + len(args)) + args

    def req(self, obj, op, args=b""):
        self.out.append(self.msg(obj, op, args))

    def flush(self):
        if self.out:
            data = b"".join(self.out)
            self.out.clear()
            self.sock.sendall(data)

    def send_timed(self, msgs):
        """Sends msgs at once; returns CLOCK_MONOTONIC read right before."""
        self.flush()
        data = b"".join(msgs)
        t = now()
        self.sock.sendall(data)
        return t

    def send_fd(self, obj, op, args, fd):
        self.flush()
        socket.send_fds(self.sock, [self.msg(obj, op, args)], [fd])

    def on_display(self, op, body):
        if op == 0:  # error(object, code, message)
            obj, code = struct.unpack_from("<II", body)
            raise Fatal(f"protocol error on {self.names.get(obj, '?')}@{obj}: {code} {rstr(body, 8)[0]}")

    def read(self):
        try:
            chunk = self.sock.recv(1 << 20, socket.MSG_DONTWAIT)
        except BlockingIOError:
            return
        if not chunk:
            raise Fatal("the compositor closed the connection")
        buf, off = self.inbuf + chunk, 0
        while len(buf) - off >= 8:
            obj, op, size = struct.unpack_from("<IHH", buf, off)
            if size < 8:
                raise Fatal("a malformed event")
            if len(buf) - off < size:
                break
            body = buf[off + 8:off + size]
            off += size
            h = self.handlers.get(obj)
            if h:
                h(op, body)
        self.inbuf = buf[off:]

    def roundtrip(self, timeout=5.0):
        done = []
        cb = self.new("wl_callback", lambda op, body: done.append(op))
        self.req(1, 0, u32(cb))  # wl_display.sync
        self.flush()
        end = time.monotonic() + timeout
        while not done:
            left = end - time.monotonic()
            if left <= 0:
                raise Fatal("the compositor didn't answer")
            if select.select([self.sock], [], [], left)[0]:
                self.read()
        self.drop(cb)


def peer_pid(sock):
    """The pid of the process at the other end of a unix socket (SO_PEERCRED)."""
    pid, _, _ = struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED,
                                                    struct.calcsize("3i")))
    return pid


def perf_sway_ipc():
    """The perf sway's IPC socket (scripts/feel/sway.sh writes its path)."""
    f = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")),
                     "hotty", "sway-feel", "ipc")
    try:
        with open(f) as fh:
            path = fh.read().strip()
    except OSError:
        raise Fatal(f"no perf sway's IPC socket in {f} (scripts/feel/sway.sh start)")
    if not path:
        raise Fatal(f"{f} is empty: is the perf sway running?")
    return path


class SwayIPC:
    """sway's IPC (the i3-ipc framing: "i3-ipc", the payload's length and the
    message's type as native u32s, then the payload): commands, and the
    tree's windows. Never $SWAYSOCK, which may be a session's own sway."""
    MAGIC = b"i3-ipc"
    RUN_COMMAND, GET_TREE = 0, 4

    def __init__(self, path=None):
        self.path = path or perf_sway_ipc()
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(5)
        try:
            self.sock.connect(self.path)
        except OSError as e:
            raise Fatal(f"can't connect to sway's IPC at {self.path}: {e}")
        self.pid = peer_pid(self.sock)

    def recv(self, n):
        b = b""
        while len(b) < n:
            try:
                chunk = self.sock.recv(n - len(b))
            except socket.timeout:
                raise Fatal("sway's IPC didn't answer in 5 s")
            if not chunk:
                raise Fatal("sway closed its IPC connection")
            b += chunk
        return b

    def call(self, kind, payload=b""):
        """Sends one message; returns when it went out and the reply."""
        msg = self.MAGIC + struct.pack("=II", len(payload), kind) + payload
        t = now()
        self.sock.sendall(msg)
        head = self.recv(len(self.MAGIC) + 8)
        n, got = struct.unpack("=II", head[len(self.MAGIC):])
        if head[:len(self.MAGIC)] != self.MAGIC or got != kind:
            raise Fatal(f"sway's IPC answered type {got} to {kind}")
        return t, json.loads(self.recv(n))

    def command(self, cmd):
        """Runs a sway command; returns when it went out. Fatal if it failed."""
        t, r = self.call(self.RUN_COMMAND, cmd.encode())
        bad = [x for x in r if not x.get("success")]
        if bad:
            raise Fatal(f"sway: {cmd!r}: {bad[0].get('error', 'failed')}")
        return t

    def windows(self):
        """Every window in the tree, in its order: {"id", "pid", "focused",
        "rect": [x, y, w, h] of its content in logical px of the layout}."""
        _, tree = self.call(self.GET_TREE)
        out = []

        def walk(n):
            if n.get("pid"):
                r, w = n["rect"], n.get("window_rect") or {"x": 0, "y": 0, "width": n["rect"]["width"],
                                                          "height": n["rect"]["height"]}
                out.append({"id": n["id"], "pid": n["pid"], "focused": bool(n.get("focused")),
                            "rect": [r["x"] + w["x"], r["y"] + w["y"], w["width"], w["height"]]})
            for c in n.get("nodes", []) + n.get("floating_nodes", []):
                walk(c)
        walk(tree)
        return out


# ---- the rig

def pct(xs, q):
    """Nearest rank, as report.py takes it."""
    s = sorted(xs)
    return s[max(0, math.ceil(q * len(s)) - 1)] if s else None


def r2(x):
    return None if x is None else round(x, 2)


class Rig:
    def __init__(self, args):
        self.args = args
        self.settle = int(args.settle_ms * 1e6)
        self.timeout = int(args.timeout_ms * 1e6)
        self.hold = int(args.hold_ms * 1e6)
        self.rng = random.Random(args.seed)
        self.jitter = 0  # ns; set from the output's refresh
        self.sched = []  # (due ns, seq, fn)
        self.seq = 0
        self.warnings = []
        self.frame = None  # the capture in flight
        self.roi = "unset"  # the logical box being captured; None: the whole output
        self.ref = None  # the buffer holding the latest content
        self.last_change = None  # ready time of the frame that last changed it
        self.armed = False
        self.t_in = 0
        self.hit, self.changed_after, self.changed_before = None, 0, 0
        self.failures = 0
        self.alloc = None
        self.stats = {}  # buffer (w, h) -> {"lag": [...], "cmp": [...]}
        self.frame_times = []
        self.records = []
        self.trace = None
        self.trace_lines = []
        self.pending = 0  # releases scheduled and not sent yet
        self.ipc = None  # sway's IPC, for focus steps
        self.marks = {}  # name -> when, since the last timed step
        self.load = [loadavg()]
        self.connect()
        self.libc_memcmp()
        if os.environ.get("HOTTY_TRACE"):
            d = os.environ["HOTTY_TRACE"]
            os.makedirs(d, exist_ok=True)
            self.trace = open(os.path.join(d, f"rig-{os.getpid()}.jsonl"), "a")
            self.trace.write(json.dumps({"trace": "hotty/1", "proc": "rig", "pid": os.getpid(),
                                         "clock": "monotonic"}) + "\n")
            self.trace.flush()

    # -- setup

    def connect(self):
        disp = os.environ.get("WAYLAND_DISPLAY")
        if not disp:
            f = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")),
                             "hotty", "sway-feel", "display")
            if not os.path.exists(f):
                raise Fatal("no WAYLAND_DISPLAY, and no perf sway (scripts/feel/sway.sh start)")
            disp = open(f).read().strip()
        self.display = disp
        path = disp if disp.startswith("/") else os.path.join(os.environ["XDG_RUNTIME_DIR"], disp)
        wl = self.wl = Wire(path)
        globs = []

        def on_global(op, body):
            if op == 0:
                name = struct.unpack_from("<I", body)[0]
                iface, off = rstr(body, 4)
                globs.append((name, iface, struct.unpack_from("<I", body, off)[0]))
        reg = wl.new("wl_registry", on_global)
        wl.req(1, 1, u32(reg))  # wl_display.get_registry
        wl.roundtrip()
        if any(i.startswith("hyprland_") for _, i, _ in globs) and not self.args.any_display:
            raise Fatal(f"{disp} is a Hyprland session, not the perf sway")
        have = {}
        for name, iface, ver in globs:
            have.setdefault(iface, (name, ver))

        def bind(iface, want, handler=None, name=None, need=True, least=1):
            if name is None:
                if iface not in have:
                    if need:
                        raise Fatal(f"the display has no {iface}")
                    return None, 0
                name, ver = have[iface]
            else:
                ver = next(v for n, i, v in globs if n == name)
            ver = min(ver, want)
            if ver < least:
                raise Fatal(f"{iface} is version {ver}; the rig needs {least}")
            oid = wl.new(iface, handler)
            wl.req(reg, 0, u32(name) + wstr(iface) + u32(ver, oid))  # wl_registry.bind
            return oid, ver

        self.shm_formats = []
        self.shm, _ = bind("wl_shm", 1, lambda op, b: op == 0 and self.shm_formats.append(
            struct.unpack_from("<I", b)[0]))
        self.seat, _ = bind("wl_seat", 1)
        self.clock = []
        self.pres, _ = bind("wp_presentation", 1, lambda op, b: op == 0 and self.clock.append(
            struct.unpack_from("<I", b)[0]), need=False)
        self.scm, self.scm_ver = bind("zwlr_screencopy_manager_v1", 3, least=2)
        self.vpm, self.vpm_ver = bind("zwlr_virtual_pointer_manager_v1", 2)
        self.vkm, _ = bind("zwp_virtual_keyboard_manager_v1", 1)
        xom, _ = bind("zxdg_output_manager_v1", 3, need=False)
        outputs = []
        for name, iface, ver in globs:
            if iface == "wl_output":
                info = {"mode": None, "scale": 1, "name": None, "logical": None}
                oid, _ = bind("wl_output", 4, lambda op, b, info=info: self.on_output(info, op, b), name=name)
                info["id"] = oid
                outputs.append(info)
        wl.roundtrip()
        if xom:
            for info in outputs:
                xo = wl.new("zxdg_output_v1", lambda op, b, info=info: self.on_xdg_output(info, op, b))
                wl.req(xom, 1, u32(xo, info["id"]))  # get_xdg_output
            wl.roundtrip()
        if not outputs:
            raise Fatal("the display has no output")
        if self.args.output:
            out = next((o for o in outputs if o["name"] == self.args.output), None)
            if not out:
                raise Fatal(f"no output {self.args.output}: {[o['name'] for o in outputs]}")
        else:
            out = outputs[0]
        if not (out["name"] or "").startswith("HEADLESS-") and not self.args.any_display:
            raise Fatal(f"output {out['name']} isn't headless: is {disp} the perf sway?")
        if out["mode"] is None:
            raise Fatal(f"output {out['name']} has no current mode")
        self.out = out
        self.output = out["id"]
        j = self.args.jitter_ms
        self.jitter = int((1e12 / out["mode"][2]) if j is None else j * 1e6)  # mode's refresh is in mHz
        if out["logical"]:
            self.lw, self.lh = out["logical"]
        else:
            self.lw, self.lh = out["mode"][0] // out["scale"], out["mode"][1] // out["scale"]
        if self.clock and self.clock[0] != CLOCK_MONOTONIC:
            raise Fatal(f"the presentation clock is {self.clock[0]}, not CLOCK_MONOTONIC")
        if self.clock:
            self.clock_src = "monotonic (wp_presentation)"
        else:
            self.clock_src = "monotonic (each frame against ours)"
            self.warn("no wp_presentation clock: the ready times are checked only against ours")
        # The pointer, mapped to the output.
        if self.vpm_ver >= 2:
            self.ptr = wl.new("zwlr_virtual_pointer_v1")
            wl.req(self.vpm, 2, u32(self.seat, self.output, self.ptr))  # create_virtual_pointer_with_output
        else:
            self.ptr = wl.new("zwlr_virtual_pointer_v1")
            wl.req(self.vpm, 0, u32(self.seat, self.ptr))
        # The keyboard, with its keymap through a memfd.
        self.kb = wl.new("zwp_virtual_keyboard_v1")
        wl.req(self.vkm, 0, u32(self.seat, self.kb))  # create_virtual_keyboard
        text, self.keymap_src = keymap(self.args.builtin_keymap)
        fd = os.memfd_create("blackbox-keymap", os.MFD_CLOEXEC)
        os.write(fd, text + b"\0")
        wl.send_fd(self.kb, 0, u32(1, len(text) + 1), fd)  # keymap(XKB_V1, fd, size)
        os.close(fd)
        wl.roundtrip()

    def on_output(self, info, op, b):
        if op == 1:  # mode(flags, width, height, refresh)
            flags, w, h, refresh = struct.unpack_from("<Iiii", b)
            if flags & 1:
                info["mode"] = (w, h, refresh)
        elif op == 3:
            info["scale"] = struct.unpack_from("<i", b)[0]
        elif op == 4:
            info["name"] = rstr(b, 0)[0]

    def on_xdg_output(self, info, op, b):
        if op == 1:  # logical_size
            info["logical"] = struct.unpack_from("<ii", b)
        elif op == 3 and not info["name"]:
            info["name"] = rstr(b, 0)[0]

    def libc_memcmp(self):
        try:
            libc = ctypes.CDLL(None)
            f = libc.memcmp
            f.restype = ctypes.c_int
            f.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
            self.memcmp = f
        except (OSError, AttributeError):
            self.memcmp = None

    def warn(self, text):
        self.warnings.append(text)
        if self.args.json:
            print(json.dumps({"warn": text}), flush=True)
        else:
            print(f"blackbox: {text}", file=sys.stderr, flush=True)

    # -- the loop

    def later(self, delay, fn):
        self.seq += 1
        heapq.heappush(self.sched, (now() + delay, self.seq, fn))

    def run_due(self, everything=False):
        while self.sched and (everything or self.sched[0][0] <= now()):
            heapq.heappop(self.sched)[2]()

    def poll(self, timeout_ns):
        if self.sched:
            timeout_ns = min(timeout_ns, self.sched[0][0] - now())
        if select.select([self.wl.sock], [], [], max(0, timeout_ns) / 1e9)[0]:
            self.wl.read()
        self.run_due()

    def pump_until(self, t):
        while now() < t:
            self.poll(t - now())

    def wait_quiet(self, since=0, cap=None):
        """Until no frame has changed the ROI for the settle time, counted
        from since at the earliest. False when cap comes first."""
        while True:
            start = max(self.last_change or 0, since)
            t = now()
            if t - start >= self.settle:
                return True
            if cap is not None and t >= cap:
                return False
            end = start + self.settle if cap is None else min(start + self.settle, cap)
            self.poll(end - t)

    # -- screencopy

    def box(self, roi):
        """A step's ROI as a box of whole logical px inside the output; None is all of it."""
        if roi is None:
            return None
        kind, (x, y, w, h) = roi
        if kind == "roi_frac":
            x, y, w, h = x * self.lw, y * self.lh, w * self.lw, h * self.lh
        x0, y0 = max(0, math.floor(x)), max(0, math.floor(y))
        x1, y1 = min(self.lw, math.ceil(x + w)), min(self.lh, math.ceil(y + h))
        if x1 <= x0 or y1 <= y0:
            raise Fatal(f"the ROI {roi[1]} is outside the output ({self.lw}x{self.lh})")
        if (x0, y0, x1, y1) == (0, 0, self.lw, self.lh):
            return None
        return (x0, y0, x1 - x0, y1 - y0)

    def capture(self, damage=True):
        f = {"damage": damage and self.args.on_demand, "shm": None, "buf": None}
        fid = f["id"] = self.wl.new("zwlr_screencopy_frame_v1", lambda op, b: self.on_frame_event(f, op, b))
        if self.roi is None:
            self.wl.req(self.scm, 0, u32(fid) + i32(0) + u32(self.output))  # capture_output
        else:
            self.wl.req(self.scm, 1, u32(fid) + i32(0) + u32(self.output) + i32(*self.roi))  # capture_output_region
        self.wl.flush()
        self.frame = f

    def drop_frame(self):
        if self.frame is not None:
            self.wl.req(self.frame["id"], 1)  # destroy
            self.wl.drop(self.frame["id"])
            self.frame = None

    def on_frame_event(self, f, op, b):
        if op == 0:  # buffer(format, width, height, stride): wl_shm
            f["shm"] = struct.unpack_from("<IIII", b)
            if self.scm_ver < 3:
                self.start_copy(f)
        elif op == 6:  # buffer_done
            self.start_copy(f)
        elif op == 2:  # ready(tv_sec_hi, tv_sec_lo, tv_nsec)
            hi, lo, ns = struct.unpack_from("<III", b)
            ts = ((hi << 32) | lo) * 1_000_000_000 + ns
            t_recv = now()
            self.wl.req(f["id"], 1)
            self.wl.drop(f["id"])
            self.frame = None
            self.failures = 0
            self.capture(True)  # the next one goes out before this one is looked at
            self.on_frame(f, ts, t_recv)
        elif op == 3:  # failed
            self.wl.req(f["id"], 1)
            self.wl.drop(f["id"])
            self.frame = None
            self.failures += 1
            if self.failures > 50:
                raise Fatal("screencopy keeps failing")
            self.later(20_000_000, lambda: self.frame is None and self.capture(False))

    def start_copy(self, f):
        if f["shm"] is None:
            raise Fatal("screencopy offers no wl_shm buffer")
        self.ensure_buffers(f["shm"])
        f["buf"] = 0 if self.ref is None else 1 - self.ref
        self.wl.req(f["id"], 2 if f["damage"] else 0, u32(self.alloc["bufs"][f["buf"]]))  # copy_with_damage / copy
        self.wl.flush()

    def ensure_buffers(self, shm):
        if self.alloc and self.alloc["shm"] == shm:
            return
        fmt, w, h, stride = shm
        if self.alloc:
            for b in self.alloc["bufs"]:
                self.wl.req(b, 0)  # wl_buffer.destroy
            self.wl.req(self.alloc["pool"], 1)  # wl_shm_pool.destroy
            self.alloc["mm"].close()
            os.close(self.alloc["fd"])
            self.ref = None  # its content was in the old buffers
        size = stride * h
        fd = os.memfd_create("blackbox-shm", os.MFD_CLOEXEC)
        os.ftruncate(fd, 2 * size)
        mm = mmap.mmap(fd, 2 * size)
        pool = self.wl.new("wl_shm_pool")
        self.wl.send_fd(self.shm, 0, u32(pool) + i32(2 * size), fd)  # create_pool(id, fd, size)
        bufs = []
        for k in range(2):
            b = self.wl.new("wl_buffer")
            self.wl.req(pool, 0, u32(b) + i32(k * size, w, h, stride) + u32(fmt))  # create_buffer
            bufs.append(b)
        base = ctypes.addressof(ctypes.c_char.from_buffer(mm)) if self.memcmp else None
        self.alloc = {"shm": shm, "fd": fd, "mm": mm, "pool": pool, "bufs": bufs, "size": size, "base": base}
        self.stats.setdefault((w, h), {"lag": [], "cmp": [], "fmt": fmt})

    def same(self, a, b):
        al = self.alloc
        n = al["size"]
        if al["base"] is not None:
            return self.memcmp(al["base"] + a * n, al["base"] + b * n, n) == 0
        mv = memoryview(al["mm"])
        try:
            if n % 8 == 0:
                return mv[a * n:(a + 1) * n].cast("Q") == mv[b * n:(b + 1) * n].cast("Q")
            return mv[a * n:(a + 1) * n] == mv[b * n:(b + 1) * n]
        finally:
            mv.release()

    def on_frame(self, f, ts, t_recv):
        lag = t_recv - ts
        if lag < -5_000_000 or lag > 60_000_000_000:
            raise Fatal(f"a frame's ready time is {lag / 1e6:.1f} ms from our CLOCK_MONOTONIC: "
                        "not the same clock")
        _, w, h, _ = f["shm"]
        st = self.stats[(w, h)]
        st["lag"].append(lag)
        self.frame_times.append(ts)
        idx = f["buf"]
        if self.ref is None:
            self.ref, self.last_change = idx, ts  # a baseline, never an answer
            return
        c0 = time.perf_counter_ns()
        same = self.same(idx, self.ref)
        st["cmp"].append(time.perf_counter_ns() - c0)
        if same:
            return
        self.ref, self.last_change = idx, ts
        if self.armed:
            if ts > self.t_in:
                self.changed_after += 1
                if self.hit is None:
                    self.hit = ts
            else:
                self.changed_before += 1

    def use_roi(self, roi):
        """Captures this box from now on; its first frame is the baseline."""
        if roi == self.roi and self.ref is not None:
            return
        self.drop_frame()
        self.roi, self.ref, self.last_change = roi, None, None
        self.capture(False)  # a plain copy: the next frame, damaged or not
        end = now() + max(self.timeout, 3_000_000_000)
        while self.ref is None:
            if now() > end:
                raise Fatal("no frame from screencopy")
            self.poll(end - now())

    # -- input

    def kb_key(self, code, state):
        return self.wl.msg(self.kb, 1, u32(ms_clock(), code, state))

    def kb_mods(self, mask):
        return self.wl.msg(self.kb, 2, u32(mask, 0, 0, 0))

    def key_down(self, code, mods):
        msgs, mask = [], 0
        for m in mods:
            mc, bit = MODS[m]
            mask |= bit
            msgs += [self.kb_key(mc, 1), self.kb_mods(mask)]
        return msgs + [self.kb_key(code, 1)]

    def key_up(self, code, mods):
        msgs = [self.kb_key(code, 0)]
        mask = sum(MODS[m][1] for m in mods)
        for m in reversed(mods):
            mc, bit = MODS[m]
            mask &= ~bit
            msgs += [self.kb_key(mc, 0), self.kb_mods(mask)]
        return msgs

    def motion(self, x, y):
        sub = 16  # 1/16 px
        ex, ey = self.lw * sub, self.lh * sub
        px = min(max(round(x * sub), 0), ex)
        py = min(max(round(y * sub), 0), ey)
        return [self.wl.msg(self.ptr, 1, u32(ms_clock(), px, py, ex, ey)), self.wl.msg(self.ptr, 4)]

    def send_later(self, delay, build):
        self.pending += 1

        def send():
            self.pending -= 1
            self.wl.send_timed(build())
        self.later(delay, send)

    def sent(self):
        """Until every release scheduled has gone out."""
        while self.pending:
            self.poll(self.hold + 1_000_000_000)

    def inject(self, st):
        """Sends a step's input; returns when its first and its last bytes go out."""
        kind = st["kind"]
        if kind == "focus":
            t = self.ipc.command(f"[con_id={st['con']}] focus")
            return t, now()
        hold = self.hold if st.get("hold_ms") is None else int(st["hold_ms"] * 1e6)
        if kind == "key":
            t = self.wl.send_timed(self.key_down(st["code"], st["mods"]))
            self.send_later(hold, lambda: self.key_up(st["code"], st["mods"]))
            return t, t + hold
        if kind == "move":
            t = self.wl.send_timed(self.motion(*st["xy"]))
            return t, t
        if kind == "click":
            b = st["button"]
            t = self.wl.send_timed(self.motion(*st["xy"]) + [
                self.wl.msg(self.ptr, 2, u32(ms_clock(), b, 1)), self.wl.msg(self.ptr, 4)])
            self.send_later(hold, lambda: [self.wl.msg(self.ptr, 2, u32(ms_clock(), b, 0)),
                                           self.wl.msg(self.ptr, 4)])
            return t, t + hold
        if kind == "wheel":
            n = st["notches"]
            sign = 1 if n > 0 else -1
            msgs = self.motion(*st["xy"])
            for _ in range(abs(n)):
                msgs += [self.wl.msg(self.ptr, 5, u32(0)),  # axis_source(wheel)
                         self.wl.msg(self.ptr, 7, u32(ms_clock(), 0) + fixed(15 * sign) + i32(sign)),  # axis_discrete
                         self.wl.msg(self.ptr, 4)]
            t = self.wl.send_timed(msgs)
            return t, t
        raise AssertionError(kind)

    def warm_keyboard(self):
        """A fresh virtual keyboard drops its first key: spend it on Shift."""
        code, bit = MODS["shift"]
        self.wl.send_timed([self.kb_key(code, 1), self.kb_mods(bit)])
        self.send_later(self.hold, lambda: [self.kb_key(code, 0), self.kb_mods(0)])
        self.pump_until(now() + self.hold + 300_000_000)

    # -- a run

    def stamp(self, t, name, a):
        if self.trace:
            tr = "input" if name in ("rig.input", "rig.mark") else "pixels"
            self.trace_lines.append(json.dumps({"t": t, "n": name, "tr": tr, "a": a}))

    def mark(self, st, t):
        """A step's mark, sent at t."""
        if st["mark"]:
            self.marks[st["mark"]] = t
            self.stamp(t, "rig.mark", {"mark": st["mark"], "sc": self.args.scenario, "kind": st["kind"]})

    def connect_ipc(self, steps):
        """sway's IPC, when a step moves the focus: the display's own
        compositor, with every window the steps name."""
        cons = sorted({st["con"] for st in steps if st["kind"] == "focus"})
        if not cons:
            return
        self.ipc = SwayIPC(self.args.ipc)
        wl_pid = peer_pid(self.wl.sock)
        if self.ipc.pid != wl_pid:
            raise Fatal(f"the IPC at {self.ipc.path} is pid {self.ipc.pid}'s and the display {self.display} "
                        f"pid {wl_pid}'s: not one compositor")
        have = {w["id"] for w in self.ipc.windows()}
        missing = [c for c in cons if c not in have]
        if missing:
            raise Fatal(f"no window with con_id {', '.join(map(str, missing))} in sway's tree")

    def flush_trace(self):
        if self.trace and self.trace_lines:
            self.trace.write("\n".join(self.trace_lines) + "\n")
            self.trace.flush()
            self.trace_lines.clear()

    def run(self, steps):
        a = self.args
        # Each step's box; an untimed step or a sleep without one takes the next timed step's.
        nxt = self.box(a.roi)
        for st in reversed(steps):
            own = self.box(st["roi"]) if st["roi"] else None
            if st["untimed"]:
                st["box"] = own if st["roi"] else nxt
            else:
                st["box"] = own if st["roi"] else self.box(a.roi)
                nxt = st["box"]
        self.connect_ipc(steps)
        self.warm_keyboard()
        self.use_roi(steps[0]["box"] if steps else self.box(a.roi))
        self.wait_quiet(cap=now() + self.timeout)
        timed = measured = 0
        for st in steps:
            self.use_roi(st["box"])
            if st["kind"] == "sleep":
                self.mark(st, now())
                self.pump_until(now() + int(st["ms"] * 1e6))
                continue
            if st["untimed"]:
                t, t_end = self.inject(st)
                self.mark(st, t)
                if not st["settle"]:
                    self.pump_until(t_end)
                    self.sent()
                elif not self.wait_quiet(since=t_end, cap=t_end + self.timeout):
                    self.warn(f"the screen didn't settle after an untimed {st['kind']}")
                continue
            warm = timed < a.warmup
            timed += 1
            i = None if warm else measured
            measured += 0 if warm else 1
            self.timed_step(st, i)

    def timed_step(self, st, i):
        quiet = None
        if st["quiet"]:
            quiet = self.wait_quiet(cap=now() + self.timeout)
            if not quiet:
                self.warn(f"timed {st['kind']} sent on a screen that didn't settle in --timeout-ms")
            if self.jitter:
                self.pump_until(now() + int(self.rng.uniform(0, self.jitter)))
        self.hit, self.changed_after, self.changed_before = None, 0, 0
        sa = {"i": i, "sc": self.args.scenario, "kind": st["kind"]}
        t_in = self.inject(st)[0]
        self.t_in, self.armed = t_in, True
        self.mark(st, t_in)
        marks, self.marks = self.marks, {}
        since = t_in - self.frame_times[-1] if self.frame_times else None
        if i is not None:
            self.stamp(t_in, "rig.input", sa)
        deadline = t_in + self.timeout
        try:
            while self.hit is None and now() < deadline + GRACE:
                self.poll(deadline + GRACE - now())
            hit = self.hit if self.hit is not None and self.hit <= deadline else None
            settled = self.wait_quiet(cap=hit + self.timeout) if hit is not None else True
        finally:
            self.armed = False
        rec = {"i": i, "sc": self.args.scenario, "kind": st["kind"], "warmup": i is None,
               "t_input": t_in, "t_pixels": hit, "ms": r2((hit - t_in) / 1e6) if hit else None,
               "miss": hit is None, "frames": self.changed_after,
               "last_ms": r2((self.last_change - t_in) / 1e6) if hit else None,
               "before": self.changed_before, "settled": settled, "quiet_before": quiet,
               "roi": list(st["box"]) if st["box"] else None,
               "since_frame": r2(since / 1e6) if since is not None else None}
        if st["kind"] == "key":
            rec["key"] = st["key"]
        if st["kind"] == "focus":
            rec["focus"] = st["con"]
        if marks:
            rec["since_mark"] = {k: r2((t_in - t) / 1e6) for k, t in marks.items()}
        if i is not None:
            if hit is not None:
                self.stamp(hit, "rig.pixels", {**sa, "frames": self.changed_after})
            else:
                self.stamp(deadline, "rig.miss", sa)
            self.records.append(rec)
        self.flush_trace()
        if self.args.json:
            print(json.dumps(rec), flush=True)

    def close(self):
        """Lets go of every key and button still held."""
        try:
            self.run_due(everything=True)
            self.wl.flush()
        except OSError:
            pass
        self.flush_trace()

    def summary(self, stopped):
        hits = [r["ms"] for r in self.records if not r["miss"]]
        self.load.append(loadavg())
        copies = []
        for (w, h), st in self.stats.items():
            if not st["lag"]:
                continue
            lag = [x / 1e6 for x in st["lag"]]
            cmp = [x / 1e6 for x in st["cmp"]]
            copies.append({"w": w, "h": h, "mb": round(w * h * 4 / 1e6, 2), "frames": len(lag),
                           "lag_p50": r2(pct(lag, .5)), "lag_p95": r2(pct(lag, .95)), "lag_max": r2(max(lag)),
                           "cmp_p50": r2(pct(cmp, .5)) if cmp else None})
        ts = sorted(self.frame_times)
        peak, lo = 0, 0
        for hi in range(len(ts)):
            while ts[hi] - ts[lo] >= 1_000_000_000:
                lo += 1
            peak = max(peak, hi - lo + 1)
        m = self.out["mode"]
        return {"sc": self.args.scenario, "n": len(self.records), "miss": len(self.records) - len(hits),
                "p50": r2(pct(hits, .5)), "p95": r2(pct(hits, .95)), "p99": r2(pct(hits, .99)),
                "min": r2(min(hits)) if hits else None, "max": r2(max(hits)) if hits else None,
                "copies": copies, "peak_fps": peak, "refresh_hz": round(m[2] / 1000, 2),
                "keeps_refresh": all(c["lag_p95"] + (c["cmp_p50"] or 0) < 1e6 / m[2] for c in copies),
                "output": {"name": self.out["name"], "mode": f"{m[0]}x{m[1]}", "logical": [self.lw, self.lh],
                           "display": self.display},
                "keymap": self.keymap_src, "clock": self.clock_src, "load": self.load,
                "stopped": stopped, "warnings": self.warnings}


def loadavg():
    with open("/proc/loadavg") as f:
        return " ".join(f.read().split()[:3])


def text_summary(s):
    out = [f"blackbox {s['sc']}: n={s['n']} misses={s['miss']}"
           + (f"  p50 {s['p50']} ms  p95 {s['p95']} ms  p99 {s['p99']} ms  (min {s['min']}, max {s['max']})"
              if s["p50"] is not None else "")]
    for c in s["copies"]:
        out.append(f"  {c['frames']} copies of {c['w']}x{c['h']} px ({c['mb']} MB): commit to ready here "
                   f"p50 {c['lag_p50']} ms p95 {c['lag_p95']} ms max {c['lag_max']} ms; compare p50 {c['cmp_p50']} ms")
    period = 1000 / s["refresh_hz"] if s["refresh_hz"] else 0
    worst = max((c["lag_p95"] + (c["cmp_p50"] or 0) for c in s["copies"]), default=0)
    out.append(f"  at most {s['peak_fps']} frames in 1 s; {s['refresh_hz']} Hz "
               + ("kept" if s["keeps_refresh"] else "NOT kept") + f": p95 copy + compare {worst:.2f} ms of {period:.2f}")
    out.append(f"  {s['output']['name']} {s['output']['mode']}, logical {s['output']['logical'][0]}x"
               f"{s['output']['logical'][1]}, keymap {s['keymap']}, clock {s['clock']}, load {s['load'][0]} -> {s['load'][-1]}")
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog="Step format: see the top of this file.")
    p.add_argument("steps", nargs="*", help="JSON-lines files of steps; - or none: stdin")
    p.add_argument("--roi", type=parse_roi, help="x,y,w,h in logical px (default: the whole output)")
    p.add_argument("--settle-ms", type=float, default=200)
    p.add_argument("--timeout-ms", type=float, default=3000)
    p.add_argument("--hold-ms", type=float, default=30, help="how long a key or button stays down")
    p.add_argument("--jitter-ms", type=float, help="a random wait before each timed input, "
                   "uniform in [0, this) (default: one refresh period; 0: none)")
    p.add_argument("--seed", type=int, default=22, help="the jitter's seed")
    p.add_argument("--on-demand", action="store_true", help="copies with damage: the output draws only "
                   "when a client commits, at once, which no display does (default: plain copies, each "
                   "asking for a frame, so the output draws at its refresh like a display)")
    p.add_argument("--scenario", default="adhoc", help="a.sc in the stamps")
    p.add_argument("--warmup", type=int, default=0, help="timed steps that run first and don't count")
    p.add_argument("--json", action="store_true", help="a JSON line per step and a JSON summary")
    p.add_argument("--output", help="the output to watch (default: the first)")
    p.add_argument("--builtin-keymap", action="store_true", help="skip xkbcli's keymap")
    p.add_argument("--any-display", action="store_true", help="don't insist on a headless output")
    p.add_argument("--ipc", help="sway's IPC socket, for focus steps (default: the perf sway's, "
                   "from ~/.cache/hotty/sway-feel/ipc; never $SWAYSOCK)")
    args = p.parse_args()
    rig = None
    stopped = False

    def on_term(*_):
        raise Stop()
    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGINT, on_term)
    try:
        steps = load_steps(args.steps)
        rig = Rig(args)
        try:
            rig.run(steps)
        except Stop:
            stopped = True
        finally:
            rig.close()
        s = rig.summary(stopped)
    except (Fatal, OSError) as e:
        if rig:
            rig.close()
        if args.json:
            print(json.dumps({"error": str(e)}), flush=True)
        else:
            print(f"blackbox: {e}", file=sys.stderr, flush=True)
        sys.exit(2)
    except Stop:
        sys.exit(143)
    if args.json:
        print(json.dumps({"summary": s}), flush=True)
    else:
        print(text_summary(s), flush=True)
    sys.exit(143 if stopped else 0)


if __name__ == "__main__":
    main()
