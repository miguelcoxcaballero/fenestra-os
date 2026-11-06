#!/bin/bash
# Fenestra Shell resource use (runs inside a session, or inside the KWin bench container):
#   tests/perf/shell-idle.sh [SECONDS] [RUNS]
# Prints one JSON line per run: start→ready time, PSS, CPU % and context switches per second
# while idle (no input, no windows changing), and the Start open latency through the test probe
# when FENESTRA_SHELL_TEST=1. Compare like with like (same machine, power profile, brightness).
set -u
SECS=${1:-60}; RUNS=${2:-3}
clk=$(getconf CLK_TCK)
probe() { gdbus call --session -d org.fenestra.Shell -o /org/fenestra/Shell/Test -m org.fenestra.Shell.Test.Eval "$1" >/dev/null 2>&1; }
for run in $(seq 1 "$RUNS"); do
    pkill -x fenestra-shell; sleep 1
    t0=$(date +%s%N)
    fenestra-shell > /tmp/perf-shell.log 2>&1 & PID=$!
    for i in $(seq 1 400); do grep -q FENESTRA_SHELL_READY /tmp/perf-shell.log && break; sleep 0.025; done
    ready_ms=$(( ($(date +%s%N) - t0) / 1000000 ))
    sleep 5   # let lazy loading settle
    read -r _ _ _ _ _ _ _ _ _ _ _ _ _ u1 s1 _ < /proc/$PID/stat
    c1=$(awk '/^voluntary_ctxt_switches/{v=$2} /^nonvoluntary_ctxt_switches/{n=$2} END{print v+n}' /proc/$PID/status)
    sleep "$SECS"
    read -r _ _ _ _ _ _ _ _ _ _ _ _ _ u2 s2 _ < /proc/$PID/stat
    c2=$(awk '/^voluntary_ctxt_switches/{v=$2} /^nonvoluntary_ctxt_switches/{n=$2} END{print v+n}' /proc/$PID/status)
    pss_kb=$(awk '/^Pss:/{print $2}' /proc/$PID/smaps_rollup)
    cpu=$(awk -v t=$(( (u2 + s2) - (u1 + s1) )) -v c=$clk -v s=$SECS 'BEGIN{printf "%.2f", 100 * t / c / s}')
    cs=$(awk -v d=$((c2 - c1)) -v s=$SECS 'BEGIN{printf "%.2f", d / s}')
    start_ms=null
    if [ "${FENESTRA_SHELL_TEST:-0}" = 1 ]; then
        t1=$(date +%s%N); probe "ShellState.toggleStart(null, -1)"
        for i in $(seq 1 200); do probe_out=$(gdbus call --session -d org.fenestra.Shell -o /org/fenestra/Shell/Test -m org.fenestra.Shell.Test.Eval "screensView.objectAt(0).start.shown" 2>/dev/null); [[ $probe_out == *true* ]] && break; sleep 0.01; done
        start_ms=$(( ($(date +%s%N) - t1) / 1000000 )); probe "screensView.objectAt(0).start.close()"
    fi
    printf '{"run": %d, "ready_ms": %d, "pss_mb": %.1f, "idle_cpu_percent": %s, "idle_switches_per_s": %s, "start_open_ms": %s, "idle_seconds": %d}\n' \
        "$run" "$ready_ms" "$(awk -v k=$pss_kb 'BEGIN{print k/1024}')" "$cpu" "$cs" "$start_ms" "$SECS"
done
