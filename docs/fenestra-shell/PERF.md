# Performance and battery

## Protocol

`tests/perf/shell-idle.sh [SECONDS] [RUNS]` inside a Fenestra session (or in the KWin bench:
`PERF=1 tests/shell-kwin/build.sh`). For every run it restarts the shell and measures:
- time from start to the shell's ready marker;
- PSS (`/proc/PID/smaps_rollup`);
- CPU % and context switches per second over SECONDS of idle desktop (no input, nothing changing),
  a proxy for wake-ups;
- with `FENESTRA_SHELL_TEST=1`, the time from the Start request to Start being shown.

On the laptop add, under the same conditions (same power profile, brightness 50 %, Wi-Fi on,
nothing else running, 10 minutes idle, 3 runs each, Fenestra-GNOME vs Fenestra Shell):
`powertop --csv` (wake-ups, estimated W), `upower -i $(upower -e | grep BAT)` energy-rate over
the same 10 minutes, RAPL (`/sys/class/powercap/intel-rapl:0/energy_uj` delta), `smem -P
'gnome-shell|fenestra-shell|kwin'` PSS, login → usable desktop from the journal. Battery life is
only stated with those measurements, never extrapolated from the container.

## Results

### Container (KWin 6.8.2 --virtual, QPainter, Qt Quick software renderer, 1920 × 1080)

| run | ready ms | PSS MB | idle CPU % | switches / s | Start open ms |
|---|---|---|---|---|---|
| 1 | 230 | 70.2 | 0.00 | 0.07 | 18 |
| 2 | 263 | 70.2 | 0.00 | 0.03 | 19 |
| 3 | 258 | 70.2 | 0.00 | 0.03 | 22 |

Idle seconds: 30 per run. Shell process only (KWin not included). The software renderer
differs from a GPU session in memory and CPU, so these numbers say "the shell does not wake up
when idle" but not how it compares with GNOME on the laptop. **Pending:** laptop and VM
measurements of both sessions with the protocol above.
