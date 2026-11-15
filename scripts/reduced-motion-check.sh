#!/bin/sh
# A private headless GTK check. Run under the brief's systemd resource cap.
# Both startup settings come from XDG_CONFIG_HOME, never the user's config.
# A test-only preload changes GtkSettings in the running process, exercising
# notify::gtk-enable-animations without a desktop portal or a settings daemon.
set -eu
if [ "${HOTTY_TEST_DBUS:-}" != 1 ]; then
    export HOTTY_TEST_DBUS=1
    exec dbus-run-session -- "$0" "$@"
fi
export GTK_A11Y=none
HERE="$(cd "$(dirname "$0")/.." && pwd)"
FORK="${HOTTYTERM_GHOSTTY:-$(dirname "$HERE")/ghostty}"
: "${HOTTY_BLITZ_DIR:?set HOTTY_BLITZ_DIR}"
OUT="${1:-$HOME/.cache/hotty-agent/0.8/hottyterm/reduced-motion}"
mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}"
mkdir -p "$OUT/cache/hotty/sway"
ln -sfn "$CACHE/hotty/sway/root" "$OUT/cache/hotty/sway/root"
export XDG_CACHE_HOME="$OUT/cache"
export GSETTINGS_BACKEND=memory
pid=""
cleanup() {
    if [ -n "$pid" ]; then kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; fi
    "$HOTTY_BLITZ_DIR/scripts/headless.sh" stop
}
trap cleanup EXIT
"$HOTTY_BLITZ_DIR/scripts/headless.sh" start
export WAYLAND_DISPLAY="$(cat "$XDG_CACHE_HOME/hotty/sway/display")"
unset DISPLAY HYPRLAND_INSTANCE_SIGNATURE

cat > "$OUT/settings.c" <<'C'
#include <gtk/gtk.h>
#include <stdio.h>
#include <stdlib.h>
static gboolean poll_setting(gpointer unused) {
    (void)unused;
    static int previous = -1;
    GtkSettings *settings = gtk_settings_get_default();
    static int logged = 0;
    if (settings && !logged) {
        gboolean animations = TRUE;
        g_object_get(settings, "gtk-enable-animations", &animations, NULL);
        fprintf(stderr, "test GtkSettings initial gtk-enable-animations=%d\n", animations);
        logged = 1;
    }
    FILE *f = fopen(getenv("HOTTY_TEST_ANIMATIONS"), "r");
    if (!f) return G_SOURCE_CONTINUE;
    int value = -1;
    int read = fscanf(f, "%d", &value);
    fclose(f);
    if (read == 1 && settings && value != previous) {
        g_object_set(settings, "gtk-enable-animations", value != 0, NULL);
        previous = value;
    }
    return G_SOURCE_CONTINUE;
}
__attribute__((constructor)) static void start(void) {
    g_timeout_add(50, poll_setting, NULL);
}
C
cc -shared -fPIC -o "$OUT/settings.so" "$OUT/settings.c" $(pkg-config --cflags --libs gtk4)
wait_for() {
    count=0
    until [ -f "$1" ]; do
        count=$((count + 1))
        [ "$count" -lt 200 ] || { echo "FAIL waiting for $1" >&2; exit 1; }
        sleep .1
    done
    sleep 1
}
shot() {
    sleep 1
    grim -t ppm "$dir/$1.ppm"
    python3 "$HERE/scripts/reduced-motion-check.py" --assert "$dir/$1.ppm" "$2" "$3"
}
for initial in false true; do
    dir="$OUT/$initial"
    mkdir -p "$dir/config/gtk-4.0"
    rm -f "$dir/ready" "$dir/late" "$dir/late-ready" "$dir/animations" "$dir/panel-pixels"
    printf '[Settings]\ngtk-enable-animations=%s\n' "$initial" > "$dir/config/gtk-4.0/settings.ini"
    XDG_CONFIG_HOME="$dir/config" HOTTY_TEST_ANIMATIONS="$dir/animations" LD_PRELOAD="$OUT/settings.so" \
        "$FORK/zig-out/bin/hottyterm" --gtk-single-instance=false --window-decoration=false \
        -e python3 "$HERE/scripts/reduced-motion-check.py" --program "$dir" >"$dir/stdout.log" 2>"$dir/terminal.log" &
    pid=$!
    wait_for "$dir/ready"
    if [ "$initial" = false ]; then first=reduce; next=no-preference; else first=no-preference; next=reduce; fi
    shot initial "$first" 1
    if [ "$initial" = false ]; then echo 1 > "$dir/animations"; else echo 0 > "$dir/animations"; fi
    shot changed "$next" 1
    touch "$dir/late"
    wait_for "$dir/late-ready"
    shot later "$next" 2
    if [ "$initial" = false ]; then echo 0 > "$dir/animations"; else echo 1 > "$dir/animations"; fi
    shot restored "$first" 2
    kill "$pid"; wait "$pid" 2>/dev/null || true; pid=""
done
