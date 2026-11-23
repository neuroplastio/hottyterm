#!/usr/bin/env python3
"""Check GTK button capture on a private headless display."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace


def wait_for(test, error):
    for _ in range(100):
        if result := test():
            return result
        time.sleep(0.05)
    raise RuntimeError(error)


def fixture(path):
    sys.path.insert(0, str(Path(os.environ["HOTTY_DIR"]) / "clients/python"))
    from hotty import Hotty

    host = Hotty()
    with Hotty.raw(), path.open("w", buffering=1) as log:
        if host.query() is None:
            raise RuntimeError("hotty negotiation failed")
        host.write("\x1b[?1049h\x1b[H")
        host.doc(
            "chord",
            '<div id="pad" data-on="drag aux" '
            'style="height:100vh;background:#28527a;touch-action:none">Drag here</div>'
            '<input id="field" data-on="input" style="position:absolute;top:0;left:20px;width:160px;height:28px">',
        )
        host.place("chord", 40, 12, move_cursor=False)
        while True:
            host.read(0.5)
            messages, keys = host.take()
            if keys:
                print(json.dumps(["pty:" + keys.hex(), None]), file=log)
            for message in messages:
                if message["a"] == "ev" and message["s"] == "chord":
                    print(json.dumps([message["e"], message.body]), file=log)


def inject(events):
    sys.path.insert(0, str(Path(__file__).resolve().parent / "feel"))
    from blackbox import BUTTONS, MODS, Rig, ms_clock, u32

    # Wayland exposes Linux button codes. GTK maps these to buttons 8–11.
    buttons = {**BUTTONS, "side": 0x113, "extra": 0x114, "forward": 0x115, "back": 0x116}
    rig = Rig(SimpleNamespace(
        settle_ms=0, timeout_ms=5000, hold_ms=0, seed=0, any_display=False,
        output=None, jitter_ms=0, builtin_keymap=False,
    ))
    try:
        def move(x, y):
            rig.wl.send_timed(rig.motion(x, y))

        def button(name, pressed):
            rig.wl.send_timed([
                rig.wl.msg(rig.ptr, 2, u32(ms_clock(), buttons[name], pressed)),
                rig.wl.msg(rig.ptr, 4),
            ])

        def modified_middle(mod):
            code, mask = MODS[mod]
            rig.wl.send_timed([rig.kb_key(code, 1), rig.kb_mods(mask)])
            button("middle", 1)
            time.sleep(0.05)
            button("middle", 0)
            rig.wl.send_timed([rig.kb_key(code, 0), rig.kb_mods(0)])

        def key(code):
            rig.wl.send_timed(rig.key_down(code, ()))
            rig.wl.send_timed(rig.key_up(code, ()))

        move(28, 40)
        button("left", 1)
        move(85, 76)
        wait_for(lambda: "dragstart" in events(), "primary press did not start a drag")
        button("middle", 1)
        time.sleep(0.05)
        button("middle", 0)
        before = events().count("drag")
        move(520, 110)
        wait_for(lambda: events().count("drag") > before, "primary drag broke during the middle chord")
        if "dragend" in events():
            raise RuntimeError("middle release ended the primary drag")
        button("left", 0)
        wait_for(lambda: "dragend" in events(), "primary release outside the surface was lost")

        move(40, 40)
        button("middle", 1)
        button("middle", 0)
        wait_for(lambda: "auxclick" in events(), "middle click after the chord was lost")
        if events().count("auxclick") != 1 or events().count("dragend") != 1:
            raise RuntimeError(f"unexpected events during the chord: {events()}")
        print("ok GTK primary drag survives a middle-button chord with primary paste disabled")

        for first, alias in (("side", "back"), ("extra", "forward")):
            for release_first in (True, False):
                start = len(events())

                def chord_events():
                    return events()[start:]

                move(40, 60)
                button(first, 1)
                move(90, 110)
                wait_for(lambda: "dragstart" in chord_events(), f"{first} did not start a drag")
                button(alias, 1)
                time.sleep(0.05)
                if release_first:
                    button(first, 0)
                    wait_for(lambda: "dragend" in chord_events(), f"{first} release was held by {alias}")
                    before = chord_events().count("drag")
                    move(500, 140)
                    time.sleep(0.1)
                    if chord_events().count("drag") != before:
                        raise RuntimeError(f"{alias} continued the ended drag: {chord_events()}")
                    move(60, 65)
                    time.sleep(0.05)
                    button("middle", 1)
                    button("middle", 0)
                    time.sleep(0.1)
                    button(alias, 0)
                else:
                    button(alias, 0)
                    before = chord_events().count("drag")
                    move(500, 140)
                    wait_for(lambda: chord_events().count("drag") > before, f"{alias} stopped {first}'s drag")
                    if "dragend" in chord_events():
                        raise RuntimeError(f"{alias} ended {first}'s drag")
                    button(first, 0)
                    wait_for(lambda: "dragend" in chord_events(), f"{first} release was lost")
                time.sleep(0.1)
                if chord_events().count("dragend") != 1 or "auxclick" in chord_events():
                    raise RuntimeError(f"unexpected events for {first} and {alias}: {chord_events()}")
            print(f"ok GTK {first}/{alias} aliases in both release orders")

        move(40, 15)
        button("left", 1)
        button("left", 0)
        wait_for(lambda: "focus" in events(), "test field did not get focus")
        move(520, 110)
        time.sleep(0.05)
        before = events().count("input")
        modified_middle("shift")
        key(45)
        wait_for(lambda: events().count("input") > before, "Shift+middle took the field's keyboard")
        before = events().count("blur")
        modified_middle("alt")
        wait_for(lambda: events().count("blur") > before, "Alt+middle on the cells did not blur the field")
        key(30)
        wait_for(lambda: "pty:61" in events(), "the program did not receive the key after Alt+middle")
        print("ok GTK Alt+middle on the cells returns the keyboard to the program")
    finally:
        rig.close()


def check():
    script = Path(__file__).resolve()
    repo = script.parent.parent
    fork = Path(os.environ.get("HOTTYTERM_GHOSTTY", repo.parent / "ghostty"))
    binary = fork / "zig-out/bin/hottyterm"
    headless = Path(os.environ["HOTTY_BLITZ_DIR"]) / "scripts/headless.sh"
    with (
        tempfile.TemporaryDirectory(prefix="hotty-button-chord-") as tmp,
        tempfile.TemporaryDirectory(prefix="chord-", dir=os.environ["XDG_RUNTIME_DIR"]) as runtime,
    ):
        work = Path(tmp)
        sway = work / "cache/hotty/sway"
        sway.mkdir(parents=True)
        if root := os.environ.get("SWAY_ROOT"):
            compositor = Path(root).resolve()
            sway_binary = compositor / "usr/bin/sway"
            if not sway_binary.is_file() or not os.access(sway_binary, os.X_OK):
                raise RuntimeError("SWAY_ROOT must contain an executable usr/bin/sway")
            (sway / "root").symlink_to(compositor)
        gtk = work / "config/gtk-4.0"
        gtk.mkdir(parents=True)
        (gtk / "settings.ini").write_text("[Settings]\ngtk-enable-primary-paste=false\n")
        os.environ.update(
            XDG_CACHE_HOME=str(work / "cache"), XDG_CONFIG_HOME=str(work / "config"),
            XDG_RUNTIME_DIR=runtime,
            GTK_A11Y="none", GDK_BACKEND="wayland", HOTTY_FRAME_LOG=str(work / "frames"),
        )
        for var in ("DISPLAY", "WAYLAND_DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE"):
            os.environ.pop(var, None)
        subprocess.run([headless, "start"], check=True)
        try:
            display = (sway / "display").read_text().strip()
            if display == "?":
                raise RuntimeError((sway / "sway.log").read_text())
            os.environ["WAYLAND_DISPLAY"] = display
            with subprocess.Popen([
                binary, "--gtk-single-instance=false", "--window-decoration=false",
                "-e", sys.executable, __file__, "--fixture", str(work / "events"),
            ]) as terminal:
                try:
                    frames = work / "frames"
                    wait_for(lambda: frames.exists() and len(frames.read_text().splitlines()) > 1,
                             "test document did not render")
                    def events():
                        path = work / "events"
                        return [json.loads(line)[0] for line in path.read_text().splitlines()] if path.exists() else []
                    inject(events)
                finally:
                    terminal.terminate()
        finally:
            subprocess.run([headless, "stop"], check=True)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--fixture":
        fixture(Path(sys.argv[2]))
    else:
        check()
