#!/bin/sh
# Render every page in demo mode on the headless test compositor and build
# side-by-side comparisons with the Windows 11 captures (tests/vm/shots/win11).
# usage: tools/compare-all.sh [OUTDIR]   (default: screenshots/)
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
REF="$HERE/../../tests/vm/shots/win11"
OUT="${1:-$HERE/screenshots}"
mkdir -p "$OUT"
shot() {  # name, args...
    n=$1; shift
    (cd "$HERE" && env -u DISPLAY WAYLAND_DISPLAY="${WAYLAND_DISPLAY_TEST:-fenestra-test}" GDK_BACKEND=wayland \
        GSK_RENDERER=gl timeout 30 python3 -m fenestra_taskmgr --screenshot "$OUT/$n.png" "$@" 2>&1 | grep -v MESA || true)
}
MAX="--size 1920x1032 --maximized"
WIN="--size 764x580"
shot processes-windowed --page processes $WIN
shot processes $MAX --page processes
shot performance-cpu $MAX --page performance --expanded
shot performance-cpu-collapsed $MAX --page performance
shot performance-memory $MAX --page performance --perf memory --expanded
shot performance-disk $MAX --page performance --perf disk --expanded
shot performance-ethernet $MAX --page performance --perf ethernet --expanded
shot performance-windowed --page performance --expanded $WIN
shot apphistory $MAX --page apphistory
shot startup $MAX --page startup
shot users $MAX --page users
shot details $MAX --page details
shot services $MAX --page services
shot settings $MAX --page settings
shot processes-light $MAX --page processes --light
shot processes-es $MAX --page processes --lang es
cmp() { python3 "$HERE/tools/compare.py" "$REF/$1.png" "$2" "$OUT/$3.png" "$OUT/compare-$3.png"; }
cmp tm-1 60,53,764,580 processes-windowed
cmp tm-processes 0,0,1920,1032 processes
cmp tm-performance-expanded 0,0,1920,1032 performance-cpu
cmp tm-performance 0,0,1920,1032 performance-cpu-collapsed
cmp tm-perf-memory 0,0,1920,1032 performance-memory
cmp tm-perf-disk 0,0,1920,1032 performance-disk
cmp tm-perf-ethernet 0,0,1920,1032 performance-ethernet
cmp tm-window-performance 60,53,764,580 performance-windowed
cmp tm-apphistory 0,0,1920,1032 apphistory
cmp tm-startup 0,0,1920,1032 startup
cmp tm-users 0,0,1920,1032 users
cmp tm-details 0,0,1920,1032 details
cmp tm-services 0,0,1920,1032 services
cmp tm-settings 0,0,1920,1032 settings
echo "done: $OUT"
