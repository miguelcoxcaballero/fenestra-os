#!/bin/sh
# Render every OOBE page to screenshots/<page>.png (and Spanish variants with --es).
set -eu
# Never render on the real desktop: use a headless compositor socket.
export WAYLAND_DISPLAY=${OOBE_WAYLAND_DISPLAY:-fenestra-test}
export GDK_BACKEND=wayland
unset DISPLAY
cd "$(dirname "$0")/.."
OUT=${OUT:-screenshots}
SIZE=${SIZE:-1920x1080}
LANG_ARG=""
SUFFIX=""
if [ "${1:-}" = "--es" ]; then LANG_ARG="--lang es"; SUFFIX="-es"; fi
mkdir -p "$OUT"
for page in $(bin/fenestra-oobe --list-pages); do
    bin/fenestra-oobe $LANG_ARG --size "$SIZE" --page "$page" --screenshot "$OUT/$page$SUFFIX.png" 2>&1 \
        | grep -v -e MESA -e '^$' || true
done
