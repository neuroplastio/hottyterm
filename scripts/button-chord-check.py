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
            'style="height:100vh;background:#28527a;touch-action:none">Drag here</div>',
        )
        host.place("chord", 40, 12, move_cursor=False)
        while True:
            host.read(0.5)
            messages, _ = host.take()
            for message in messages:
                if message["a"] == "ev" and message["s"] == "chord":
                    print(json.dumps([message["e"], message.body]), file=log)


def inject(events):
    sys.path.insert(0, str(Path(__file__).resolve().parent / "feel"))
    from blackbox import BUTTONS, Rig, ms_clock, u32

    rig = Rig(SimpleNamespace(
        settle_ms=0, timeout_ms=5000, hold_ms=0, seed=0, any_display=False,
        output=None, jitter_ms=0, builtin_keymap=False,
    ))
    try:
        def move(x, y):
            rig.wl.send_timed(rig.motion(x, y))

        def button(name, pressed):
            rig.wl.send_timed([
                rig.wl.msg(rig.ptr, 2, u32(ms_clock(), BUTTONS[name], pressed)),
                rig.wl.msg(rig.ptr, 4),
            ])

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
    finally:
        rig.close()


def check():
    script = Path(__file__).resolve()
    repo = script.parent.parent
    fork = Path(os.environ.get("HOTTYTERM_GHOSTTY", repo.parent / "ghostty"))
    binary = fork / "zig-out/bin/hottyterm"
    headless = Path(os.environ["HOTTY_BLITZ_DIR"]) / "scripts/headless.sh"
    cached_sway = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "hotty/sway/root"
    with tempfile.TemporaryDirectory(prefix="hotty-button-chord-") as tmp:
        work = Path(tmp)
        sway = work / "cache/hotty/sway"
        sway.mkdir(parents=True)
        (sway / "root").symlink_to(cached_sway)
        gtk = work / "config/gtk-4.0"
        gtk.mkdir(parents=True)
        (gtk / "settings.ini").write_text("[Settings]\ngtk-enable-primary-paste=false\n")
        os.environ.update(
            XDG_CACHE_HOME=str(work / "cache"), XDG_CONFIG_HOME=str(work / "config"),
            GTK_A11Y="none", GDK_BACKEND="wayland", HOTTY_FRAME_LOG=str(work / "frames"),
        )
        for var in ("DISPLAY", "WAYLAND_DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE"):
            os.environ.pop(var, None)
        subprocess.run([headless, "start"], check=True)
        try:
            os.environ["WAYLAND_DISPLAY"] = (sway / "display").read_text().strip()
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
    print("ok GTK primary drag survives a middle-button chord with primary paste disabled")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--fixture":
        fixture(Path(sys.argv[2]))
    else:
        check()
