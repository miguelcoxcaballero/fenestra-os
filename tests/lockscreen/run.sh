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

# 1. Password: a wrong one shows Windows' message and OK; the right one unlocks.
$C face fail; $C sh "echo 1 > /tmp/face-delay"
start
$C shot 01-clock
$C key 57; sleep 2; $C shot 02-signin
check L-reveal-smooth python3 - "$OUT/greet.log" <<'PY'
import sys
L=[l.split() for l in open(sys.argv[1]) if 'FENESTRA_FRAME' in l]
d=[float(x[3]) for x in L[1:] if 0 < float(x[4]) < 620]
sys.exit(0 if d and max(d) <= 25 else 1)
PY
$C type wrongpass; $C key 28; sleep 3.5; $C shot 03-wrong
check L-wrong-password-message has "FENESTRA_LOCK failed 0"
check L-still-locked-after-wrong running
$C key 28; sleep 1; $C type Fenestra1; sleep 0.3; $C key 28
check L-unlock-password exited

# 2. Face (Howdy stand-in in the kde PAM service): the search animation, then the smile and unlock.
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
d=[float(x[3]) for x in L[1:-1]]   # the last one is the greeter quitting after the smile
late=[(x[3], x[4], x[5]) for x in L[1:-1] if float(x[3]) > 25]
print("hello frames", len(d), "late", late, file=sys.stderr)
sys.exit(0 if len(d) > 60 and not late else 1)
PY

# Pictures of the same, separately.
$C face wait; start; $C key 57; sleep 2.5; $C shot 04-face-search
$C face success; sleep 0.4; $C shot 05-face-smile; exited >/dev/null

# 3. Fingerprint (kde-fingerprint stand-in) unlocks from the clock view.
$C face fail; $C sh "echo 1 > /tmp/face-delay"
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
check L-a11y-magnifier has "invokeShortcut view_zoom_in"
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
echo "screenshots and logs: $OUT"
[ $FAILS = 0 ] && echo "QA_RESULT PASS" || { echo "QA_RESULT FAIL ($FAILS)"; exit 1; }
