#!/bin/bash
# Runs inside the KWin lab container: headless KWin (--virtual) + Fenestra Shell with a fake
# colour light sensor (FENESTRA_ALS_PATH), walks through ambient scenes and records every
# colour temperature KWin's Night light commits (recorder.py) -> /out/curve.tsv, /out/report.txt.
#   /src repo (ro)   /build CMake build dir of shell/   /out results
set -u
export KWIN_COMPOSE=Q LIBGL_ALWAYS_SOFTWARE=1 QT_FORCE_STDERR_LOGGING=1 QT_QUICK_BACKEND=software LANG=C.UTF-8
export FENESTRA_SHELL_TEST=1 FENESTRA_SHELL_NO_ACTIVATION=1 XDG_RUNTIME_DIR=/tmp/xdg QT_QPA_PLATFORM=wayland XDG_CURRENT_DESKTOP=Fenestra XDG_SESSION_TYPE=wayland
# Local noon (whatever the bench's clock says), so Night light's 06:00-18:00 schedule is "day".
export TZ=$(python3 -c "import time; h=(12-time.gmtime().tm_hour)%24; h=h-24 if h>12 else h; print(f'Etc/GMT{-h:+d}' if h else 'UTC')")
mkdir -p -m700 "$XDG_RUNTIME_DIR" /out
cmake --install /build --prefix /usr >/dev/null
rm -f /run/dbus/pid; mkdir -p /run/dbus; dbus-daemon --system --fork 2>/dev/null
mkdir -p ~/.config/fenestra
printf '[General]\nSource=Times\n[Times]\nSunriseStart=06:00:00\nSunsetStart=18:00:00\nTransitionDuration=1800\n' > ~/.config/knighttimerc
rm -f ~/.config/kwinrc ~/.config/fenestra/shell.conf

# Fake IIO device, the attributes of the Galaxy Book4 Pro's HID sensor ("als").
ALS=/tmp/als/iio:device0
mkdir -p $ALS
echo als > $ALS/name
echo 0.001000000 > $ALS/in_chromaticity_scale
echo 0.001000000 > $ALS/in_colortemp_scale
echo 0.001000000 > $ALS/in_illuminance_scale
echo 0 > $ALS/in_colortemp_offset
# als CCT LUX: a Planckian light of CCT kelvin at LUX lux (written in place, as sysfs files are
# the same inode across reads).
als() {
    python3 - "$1" "$2" <<'EOF'
import sys
t, lux = float(sys.argv[1]), float(sys.argv[2])
t2, t3 = t * t, t ** 3
x = (-0.2661239e9 / t3 - 0.2343589e6 / t2 + 0.8776956e3 / t + 0.179910) if t <= 4000 else \
    (-3.0258469e9 / t3 + 2.1070379e6 / t2 + 0.2226347e3 / t + 0.240390)
if t <= 2222:
    y = -1.1063814 * x**3 - 1.34811020 * x**2 + 2.18555832 * x - 0.20219683
elif t <= 4000:
    y = -0.9549476 * x**3 - 1.37418593 * x**2 + 2.09137015 * x - 0.16748867
else:
    y = 3.0817580 * x**3 - 5.87338670 * x**2 + 3.75112997 * x - 0.37001483
d = "/tmp/als/iio:device0/"
for n, v in (("in_chromaticity_x_raw", round(x * 1000)), ("in_chromaticity_y_raw", round(y * 1000)),
             ("in_colortemp_raw", round(t * 1000)), ("in_illuminance_raw", round(lux * 1000))):
    with open(d + n, "r+" if __import__("os").path.exists(d + n) else "w") as f:
        f.seek(0); f.truncate(); f.write(f"{v}\n")
EOF
}
scene() { echo "$*" > /tmp/scene; echo "$(date +%T) scene: $*" >> /out/scenes.txt; }
conf() { printf '%s\n' "$@" > ~/.config/fenestra/shell.conf.tmp && mv ~/.config/fenestra/shell.conf.tmp ~/.config/fenestra/shell.conf; }
wait_for() { local i; for i in $(seq 1 "${2:-40}"); do eval "$1" && return 0; sleep 0.5; done; return 1; }
nl() { gdbus call --session -d org.kde.KWin -o /org/kde/KWin/NightLight -m org.freedesktop.DBus.Properties.Get org.kde.KWin.NightLight "$1" | tr -dc '0-9a-z'; }
kwinrc() { kwriteconfig6 --file kwinrc --group NightColor "$@" --notify; }
thread_cpu() { # utime+stime ticks of the shell's adaptive-color thread and of the whole process
    local pid=$1 t
    for t in /proc/$pid/task/*; do [ "$(cat $t/comm)" = adaptive-color ] && awk '{print $14+$15}' $t/stat; done
}

run() {
    export WAYLAND_DISPLAY=wayland-fen
    als 6500 400
    kwin_wayland --virtual --socket wayland-fen --width 1920 --height 1080 > /out/kwin.log 2>&1 &
    KWIN=$!
    wait_for '[ -S $XDG_RUNTIME_DIR/wayland-fen ]' 60 || { echo "kwin did not start"; return 1; }
    python3 /src/tests/adaptive-color/recorder.py 900 > /out/curve.tsv 2>/out/recorder.err &
    REC=$!
    sleep 2
    scene "start: daylight 6500K 400lx (Night light off)"
    FENESTRA_ALS_PATH=/tmp/als QT_LOGGING_RULES="fenestra.adaptivecolor.debug=true" fenestra-shell > /out/shell.log 2>&1 &
    SHELL_PID=$!
    wait_for 'grep -q FENESTRA_SHELL_READY /out/shell.log' 60
    sleep 12
    scene "office 4000K 300lx"; als 4000 300; sleep 30
    scene "warm lamp 2700K 100lx"; als 2700 100; sleep 30
    scene "cool office 5000K 500lx"; als 5000 500; sleep 30
    scene "dim warm 3000K 10lx"; als 3000 10; sleep 30
    scene "daylight 6500K 400lx"; als 6500 400; sleep 30
    scene "strobe: 2700K/6500K switched every 0.5 s"
    for i in $(seq 1 60); do als 2700 300; sleep 0.25; als 6500 300; sleep 0.25; done
    sleep 10
    scene "sensor noise: 4500K +-150K random every 0.3 s"
    for i in $(seq 1 100); do als $((4350 + RANDOM % 300)) 300; sleep 0.3; done
    sleep 10
    scene "outdoor 6000K 1500lx"; als 6000 1500; sleep 25
    scene "office 4000K 300lx, then Adaptive color off in shell.conf"; als 4000 300; sleep 30
    conf '[Display]' 'AdaptiveColor=false'; sleep 15
    scene "Adaptive color back on"; conf '[Display]' 'AdaptiveColor=true'; sleep 20
    # CPU of the sampling thread and of the whole shell over 60 s of steady light.
    scene "cpu: steady 4000K 300lx, 60 s"
    local a0 p0 a1 p1
    a0=$(thread_cpu $SHELL_PID); p0=$(awk '{print $14+$15}' /proc/$SHELL_PID/stat)
    sleep 60
    a1=$(thread_cpu $SHELL_PID); p1=$(awk '{print $14+$15}' /proc/$SHELL_PID/stat)
    echo "cpu adaptive-color thread: $((a1 - a0)) ticks in 60 s; whole shell (software rendering): $((p1 - p0)) ticks (CLK_TCK $(getconf CLK_TCK))" >> /out/report.txt
    # Night light on, schedule 06:00-18:00 and local noon: daytime -> DayTemperature path.
    scene "Night light on (day): DayTemperature path"; kwinrc --key Active true; kwinrc --key Mode DarkLight; sleep 6
    echo "night light: running=$(nl running) daylight=$(nl daylight)" >> /out/report.txt
    sleep 14
    echo "kwinrc NightColor (day, adaptive on): $(grep -A8 '^\[NightColor\]' ~/.config/kwinrc | tr '\n' ' ')" >> /out/report.txt
    scene "Night light on (day): warm lamp 2700K 100lx"; als 2700 100; sleep 30
    scene "Night light on (day): daylight 6500K 400lx"; als 6500 400; sleep 30
    # Constant Night light: Night light's own temperature applies, Adaptive color holds.
    scene "Night light Constant 4500K: Night light wins"; kwinrc --key NightTemperature 4500; kwinrc --key Mode Constant; sleep 6
    als 2700 100; sleep 25
    scene "Night light off again"; kwinrc --key Active false; kwinrc --key Mode DarkLight; sleep 25
    scene "quit shell"; kill $SHELL_PID; sleep 6
    echo "kwinrc NightColor after the shell quit: $(grep -A8 '^\[NightColor\]' ~/.config/kwinrc | tr '\n' ' ')" >> /out/report.txt
    echo "night light after quit: current=$(nl currentTemperature)" >> /out/report.txt
    kill $REC $KWIN 2>/dev/null
}
export -f run als scene conf wait_for nl kwinrc thread_cpu
: > /out/report.txt; : > /out/scenes.txt
timeout "${TIMEOUT:-900}" dbus-run-session -- bash -c run
python3 /src/tests/adaptive-color/analyse.py /out/curve.tsv >> /out/report.txt
cat /out/report.txt
