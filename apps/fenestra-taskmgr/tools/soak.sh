#!/bin/bash
# Soak test: real /proc data, High update speed (0.5 s), pages cycling every 5 s, on the
# headless test compositor, sandboxed (no action can touch real processes).  Prints
# RSS / CPU every 30 s.  Run inside the capped slice:
#   ~/.local/bin/fenestra-test-run tools/soak.sh [minutes] [outfile]
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
MIN=${1:-15}
OUT=${2:-/dev/stdout}
TMP=$(mktemp -d)
mkdir -p "$TMP/config/fenestra-taskmgr" "$TMP/state"
echo '{"speed": "high", "nav_expanded": true}' > "$TMP/config/fenestra-taskmgr/settings.json"
env -u DISPLAY WAYLAND_DISPLAY="${WAYLAND_DISPLAY_TEST:-fenestra-test}" GDK_BACKEND=wayland \
    XDG_CONFIG_HOME="$TMP/config" XDG_STATE_HOME="$TMP/state" \
    FENESTRA_TASKMGR_TEST_ALLOW_PIDS="" FENESTRA_TASKMGR_SOAK_CYCLE=5 FENESTRA_TASKMGR_NO_BOOST=1 \
    python3 "$HERE/bin/fenestra-taskmgr" --read-only > "$TMP/app.log" 2>&1 &
APP=$!
CLK=$(getconf CLK_TCK)
prev=0
{
echo "# minute rss_mb cpu%_last30s threads"
for ((i = 0; i <= MIN * 2; i++)); do
    [ -d /proc/$APP ] || { echo "APP DIED"; break; }
    read -r ut st th <<<"$(awk '{print $14, $15, $20}' /proc/$APP/stat)"
    t=$((ut + st))
    rss=$(awk '/VmRSS/{print $2}' /proc/$APP/status)
    cpu=$(awk -v d=$((t - prev)) -v c=$CLK 'BEGIN{printf "%.1f", d / c / 30 * 100}')
    [ $i -eq 0 ] && cpu="-"
    prev=$t
    printf "%5.1f %7.1f %6s %4s\n" "$(awk -v i=$i 'BEGIN{print i/2}')" "$(awk -v r=$rss 'BEGIN{print r/1024}')" "$cpu" "$th"
    [ $i -lt $((MIN * 2)) ] && sleep 30
done
kill $APP 2>/dev/null; wait $APP 2>/dev/null
echo "# app log (errors):"; grep -vE "MESA|gtk.css|^$" "$TMP/app.log" | head -20
} > "$OUT"
rm -rf "$TMP"
