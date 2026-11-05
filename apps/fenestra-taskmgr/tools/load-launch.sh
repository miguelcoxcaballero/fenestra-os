#!/bin/bash
# Launch-to-first-frame under full CPU saturation.  Starts N busy loops (default: one per
# CPU) in their own transient scope inside fenestra-tests.slice, then launches Task Manager
# on the headless test compositor (sandboxed, read-only) RUNS times, with the default CPU
# weight and with CPUWeight=1000 (what bin/fenestra-taskmgr asks systemd for).
# Only the busy-loop scope this script created is stopped at the end.
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
N=${N:-$(nproc)}
RUNS=${RUNS:-3}
UNIT="tm-busy-$$"
systemd-run --user --scope --quiet --slice=fenestra-tests.slice --unit="$UNIT" -p CPUWeight=100 \
    bash -c "for i in \$(seq $N); do python3 -c 'while 1: pass' & done; wait" &
trap 'systemctl --user stop "$UNIT.scope" 2>/dev/null' EXIT
sleep 3
run() {  # label, extra systemd-run properties
    local label=$1; shift
    for ((r = 1; r <= RUNS; r++)); do
        local t0 out
        t0=$(date +%s.%N)
        out=$(systemd-run --user --scope --quiet --slice=fenestra-tests.slice "$@" \
            env -u DISPLAY WAYLAND_DISPLAY="${WAYLAND_DISPLAY_TEST:-fenestra-test}" GDK_BACKEND=wayland \
            FENESTRA_TASKMGR_TEST_ALLOW_PIDS="" FENESTRA_TASKMGR_EXIT_AFTER_FIRST_FRAME=1 \
            FENESTRA_TASKMGR_NO_BOOST=1 FENESTRA_TASKMGR_NON_UNIQUE=1 \
            timeout 60 python3 "$HERE/bin/fenestra-taskmgr" --read-only --timing 2>/dev/null | grep "first frame")
        local ep=${out##*epoch }; ep=${ep%)}
        local inner=${out#*after }; inner=${inner%% ms*}
        awk -v a="$t0" -v b="$ep" -v l="$label" -v r="$r" -v i="$inner" 'BEGIN{printf "%-22s run %d: launch -> first frame %4.0f ms (python start -> frame %s ms)\n", l, r, (b-a)*1000, i}'
    done
}
echo "busy loops: $N on $(nproc) CPUs"
run "default weight" -p CPUWeight=100
run "CPUWeight=1000" -p CPUWeight=1000 -p IOWeight=1000
