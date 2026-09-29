#!/bin/sh
# Runs the built hottyterm next to any Ghostty already running: its own
# application id, no single-instance hand-off.
#
#   scripts/run.sh [ghostty args...]    e.g. scripts/run.sh -e python3 ../../hotty/main/examples/dash.py
set -eu
HERE="$(cd "$(dirname "$0")/.." && pwd)"
FORK="${HOTTYTERM_GHOSTTY:-$(dirname "$HERE")/ghostty}"
exec "$FORK/zig-out/bin/ghostty" --class=io.github.neuroplastio.hottyterm --gtk-single-instance=false "$@"
