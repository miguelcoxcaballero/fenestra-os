#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# tests/lockscreen/run.sh [OUT]: the lock screen end to end in the nested KWin bench (greeter-gl.sh):
# real kscreenlocker_greet and PAM, input through KWin's fake input, screenshots through
# ScreenShot2. Checks every way out of the lock and every button; prints CHECK lines and
# QA_RESULT. Needs the fenestra-kwinlab image and a render node; one container, stopped at the end.
#   env: HELLO (atlas dir of the user's own Hello frames, optional)
set -u
REPO=$(cd "$(dirname "$0")/../.." && pwd)
OUT=$(realpath -m "${1:-$(mktemp -d)}"); mkdir -p "$OUT"
rm -f "$OUT/ready"   # a reused OUT: wait for this run's KWin, not the last one's
C="$REPO/tests/lockscreen/ctl.sh"
FAILS=0
check() { local name=$1; shift; if "$@"; then echo "CHECK $name PASS"; else echo "CHECK $name FAIL"; FAILS=$((FAILS + 1)); fi; }
log() { grep -c "$1" "$OUT/greet.log" 2>/dev/null; }
has() { grep -q "$1" "$OUT/greet.log"; }
exited() { for _ in $(seq 40); do grep -q "^EXIT 0" "$OUT/greet.log" && return 0; sleep 0.25; done; return 1; }
running() { ! grep -q "^EXIT" "$OUT/greet.log"; }
start() { rm -f "$OUT/pam.log"; $C stop; $C start; sleep 5; }
# Signin view centre / corner buttons at 2880 x 1800, 150 % (logical px).
NET="1780 1157"; A11Y="1827 1157"; POWER="1875 1157"

HELLO=${HELLO:-} "$REPO/tests/lockscreen/greeter-gl.sh" "$OUT" >/dev/null
for _ in $(seq 90); do [ -f "$OUT/ready" ] && break; sleep 1; done
$C sh "sed -i 's/^SigninBlur=.*/SigninBlur=true\nTrace=true/' ~/.config/kscreenlockerrc"

# 0. Never locked out: a camera that never delivers a frame and an fprintd that never answers
#    (face and fingerprint run in the parallel kde-fingerprint worker): the password still unlocks
#    at once (< 1 s after Enter), and both stand-ins are gone afterwards.
$C face hang; $C finger hang
start
$C key 57; sleep 2; $C type Fenestra1
t0=$(date +%s%N); $C key 28; exited >/dev/null; t1=$(date +%s%N)
echo "password unlock with dead camera and hung fprintd: $(( (t1 - t0) / 1000000 )) ms"
check L-no-lockout-dead-camera-hung-fprintd test $(( (t1 - t0) / 1000000 )) -lt 1000
cp "$OUT/greet.log" "$OUT/00-greet.log"; cp "$OUT/pam.log" "$OUT/00-pam.log" 2>/dev/null
# (the hung stand-ins exec "sleep infinity"; the bench's own session holds the only other one)
check L-stand-ins-killed test "$($C sh 'pgrep -x sleep | wc -l')" = 1
$C finger wait

# 1. Password: a wrong one shows Windows' message and OK; the right one unlocks.
$C face fail; $C sh "echo 1 > /tmp/face-delay"
start
$C shot 01-clock
# Nothing is checked on the clock: no camera, no fingerprint reader until the clock is dismissed.
check L-nothing-checked-on-clock bash -c "! grep -qE 'face start|finger start' '$OUT/pam.log' 2>/dev/null"
# No QML warning of the lock screen's own files (stand-ins aside).
check L-no-qml-warnings bash -c "! grep 'org.fenestra.desktop/contents/lockscreen/.*qml:[0-9]' '$OUT/greet.log' | grep -q ."
$C key 57; sleep 2; $C shot 02-signin
check L-reveal-smooth python3 - "$OUT/greet.log" <<'PY'
import sys
L=[l.split() for l in open(sys.argv[1]) if 'FENESTRA_FRAME' in l]
# The frame trace has a line per presented frame; the first one of the reveal also carries the idle
# time before it (nothing is drawn while nothing changes), so it is left out.
d=[float(x[3]) for x in L[1:] if 0 < float(x[4]) < 620][1:]
print("reveal frames", len(d), "max", max(d) if d else None, file=sys.stderr)
sys.exit(0 if d and max(d) <= 25 else 1)
PY
$C type wrongpass; $C key 28; sleep 3.5; $C shot 03-wrong
check L-wrong-password-message has "FENESTRA_LOCK failed 0"
check L-still-locked-after-wrong running
$C key 28; sleep 1; $C type Fenestra1; sleep 0.3; $C key 28
check L-unlock-password exited

# 2. Face (Howdy stand-in through pam_fenestra_hello in kde-fingerprint): the search animation,
#    then the smile and unlock.
#    Timed pass without screenshots (a ScreenShot2 capture itself costs the compositor a frame).
$C face wait; $C sh "echo 20 > /tmp/face-delay"
start
$C key 57; sleep 2.5
check L-face-searching has "Attempting facial authentication"
$C face success
check L-unlock-face exited
check L-hello-smooth python3 - "$OUT/greet.log" <<'PY'
import sys
L=[l.split() for l in open(sys.argv[1]) if 'FENESTRA_FRAME' in l]
# Only frames with the sign-in screen up (t = 620): on the clock view the Hello animation is hidden
# and nothing is drawn between heartbeats. The first is the idle time before it, the last the
# greeter quitting after the smile.
S=[x for x in L[1:-2] if float(x[4]) >= 620][1:]   # (the last two: the smile done, the workers stopped, quitting)
d=[float(x[3]) for x in S]
late=[(x[3], x[4], x[5]) for x in S if float(x[3]) > 25]
print("hello frames", len(d), "late", late, file=sys.stderr)
sys.exit(0 if len(d) > 60 and not late else 1)
PY

# Pictures of the same, separately.
$C face wait; start; $C key 57; sleep 2.5; $C shot 04-face-search
$C face success; sleep 0.4; $C shot 05-face-smile; exited >/dev/null

# 3. Fingerprint (fprintd-verify stand-in) unlocks from the clock view, with a dead camera.
$C face hang
start
$C key 57; sleep 2
check L-fingerprint-offered has "FENESTRA_LOCK ninfo 1"
$C finger success
check L-unlock-fingerprint exited

# 4. Corner buttons and flyouts (plasma-nm / data engines through tests/lockscreen/mock-qml).
start
$C key 57; sleep 2
$C click $NET; sleep 1; $C shot 06-network
$C click 1700 862; sleep 0.8   # second network ("MOVISTAR_5G", new and secured): its key box
$C type secreto; $C key 28; sleep 0.5
check L-network-connect-new has "FENESTRA_NM add /d/wlan0 /ap/2 with-key"
$C click 1602 1061; sleep 0.5   # Wi-Fi tile (the flyout stays open)
check L-network-wifi-toggle has "FENESTRA_NM wireless false"
$C key 1; sleep 0.5
$C click $A11Y; sleep 1; $C shot 07-accessibility
$C click 1867 1040; sleep 0.5   # Sticky keys switch
check L-a11y-sticky has "FENESTRA_EXEC sh -c 'env -u KDE_HOME_READONLY kwriteconfig6 --file kaccessrc --group Keyboard --key StickyKeys true"
$C click 1867 848; sleep 0.5   # Magnifier
check L-a11y-magnifier has "Component.invokeShortcut view_zoom_in"
$C click 1867 944; sleep 0.5   # Narrator
check L-a11y-narrator has "orca --replace"
$C click 1867 992; sleep 0.8; $C shot 08-osk   # On-screen keyboard
$C key 1; sleep 0.3; $C key 1; sleep 0.3
$C click $POWER; sleep 1; $C shot 09-power
check L-power-menu-shown python3 -c "
from PIL import Image; import numpy as np, sys
a=np.asarray(Image.open('$OUT/09-power.png').convert('L')).astype(int)
sys.exit(0 if (a[1520:1700,2700:2870] > 200).sum() > 300 else 1)"
$C click 1840 1031; sleep 0.5   # Sleep (first item)
check L-power-sleep has "FENESTRA_EXEC systemctl suspend"
$C key 57; sleep 1.5; $C click $POWER; sleep 1; $C click 1840 1071; sleep 0.5
check L-power-shutdown has "FENESTRA_EXEC systemctl poweroff"
$C key 57; sleep 1.5; $C click $POWER; sleep 1; $C click 1840 1111; sleep 0.5
check L-power-restart has "FENESTRA_EXEC systemctl reboot"
$C stop
podman rm -f fenestra-lockbench >/dev/null 2>&1

# 5. Boot: the session starts locked (KWin --lockscreen, as fenestra-session after GDM's autologin)
#    and KWin's own screen locker (not --testing) shows this lock screen; the password unlocks it.
rm -f "$OUT/ready"
LOCKED=1 HELLO=${HELLO:-} "$REPO/tests/lockscreen/greeter-gl.sh" "$OUT" >/dev/null
for _ in $(seq 90); do [ -f "$OUT/ready" ] && break; sleep 1; done
$C face hang; $C finger hang; sleep 4
check L-boot-locked test "$($C sh 'pgrep -x kscreenlocker_g | wc -l')" = 1
$C shot 10-boot-lock
$C key 57; sleep 2; $C type Fenestra1; $C key 28; sleep 2
check L-boot-unlocked test "$($C sh 'pgrep -x kscreenlocker_g | wc -l')" = 0

# 6. A dead password worker (kscreenlocker never restarts a cancelled or crashed one: "DBus worker
#    not initialized" for ever, as in the lock-out of 2026-11-08). The lock screen notices and ends
#    its greeter; KWin's locker starts a new one, still locked; the password unlocks.
$C sh "loginctl lock-session 2>/dev/null; dbus-send --session --dest=org.freedesktop.ScreenSaver --type=method_call /ScreenSaver org.freedesktop.ScreenSaver.Lock"; sleep 5
g1=$($C sh 'pgrep -x kscreenlocker_g')
$C sh "pkill -f 'kscreenlocker_worker kde '\$USER'\$' ; pkill -f 'kscreenlocker_worker kde root\$'"; sleep 2
# Nothing is checked while the clock shows, so the dead worker is found once the clock is
# dismissed: the greeter is replaced within seconds (still locked), back on its clock.
$C key 57; sleep 9
g2=$($C sh 'pgrep -x kscreenlocker_g')
echo "greeter before $g1, after $g2"
check L-dead-worker-new-greeter test -n "$g1" -a -n "$g2" -a "$g1" != "$g2"
$C key 57; sleep 2; $C type Fenestra1; $C key 28; sleep 3
check L-dead-worker-unlocked test "$($C sh 'pgrep -x kscreenlocker_g | wc -l')" = 0
podman rm -f fenestra-lockbench >/dev/null 2>&1
echo "screenshots and logs: $OUT"
[ $FAILS = 0 ] && echo "QA_RESULT PASS" || { echo "QA_RESULT FAIL ($FAILS)"; exit 1; }
