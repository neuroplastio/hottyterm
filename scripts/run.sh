#!/bin/sh
# Runs the built hottyterm. Its application id is its own, so it runs next
# to an installed Ghostty.
#
#   scripts/run.sh [ghostty args...]    e.g. scripts/run.sh -e python3 ../../hotty/main/examples/dash.py
set -eu
HERE="$(cd "$(dirname "$0")/.." && pwd)"
FORK="${HOTTYTERM_GHOSTTY:-$(dirname "$HERE")/ghostty}"
exec "$FORK/zig-out/bin/hottyterm" "$@"
