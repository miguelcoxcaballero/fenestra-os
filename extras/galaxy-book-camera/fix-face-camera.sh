#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Face sign-in on Galaxy Books whose camera goes through camera-relay (libcamera -> v4l2loopback).
#
# The relay's monitor built before October 2026 never notices a reader on v4l2loopback 0.15
# (it waits on the pre-0.13 usage event, which that kernel module no longer sends): every app,
# Howdy included, gets black frames forever and face sign-in fails with "All frames were too
# dark". Upstream fixed it (samsung-galaxy-book-linux-fixes #118, STREAMON decides). This
# rebuilds the monitor from that fixed source, gives Howdy time for the camera to start
# (the relay shows black frames for 2-3 s while libcamera starts), restarts the relay and
# checks the camera and Howdy for real.
#
#   sudo fix-face-camera.sh
set -euo pipefail
[[ $EUID -eq 0 ]] || exec sudo "$0" "$@"

REPO=Andycodeman/samsung-galaxy-book-linux-fixes
REV=02eb997354450845cbfaa5bcdc77d6e011f3825d   # camera-relay-monitor.c with the #118 fix
USER_NAME=${SUDO_USER:-$(logname 2>/dev/null || echo root)}
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT

echo "1/4 Building the camera relay monitor (fixed upstream version)"
curl -fsSL "https://raw.githubusercontent.com/$REPO/$REV/camera-relay/camera-relay-monitor.c" -o "$work/monitor.c"
gcc -O2 -Wall -o "$work/camera-relay-monitor" "$work/monitor.c"
[[ -e /usr/local/bin/camera-relay-monitor && ! -e /usr/local/bin/camera-relay-monitor.orig ]] &&
    cp -a /usr/local/bin/camera-relay-monitor /usr/local/bin/camera-relay-monitor.orig
install -m755 "$work/camera-relay-monitor" /usr/local/bin/camera-relay-monitor
restorecon -F /usr/local/bin/camera-relay-monitor 2>/dev/null || true

echo "2/4 Giving Howdy time for the camera to start"
if [[ -f /etc/howdy/config.ini ]]; then
    t=$(sed -n 's/^timeout *= *//p' /etc/howdy/config.ini | head -1)
    if [[ -z "$t" || "$t" -lt 6 ]]; then
        sed -i 's/^timeout *=.*/timeout = 6/' /etc/howdy/config.ini
    fi
fi

echo "3/4 Restarting the camera relay"
systemctl restart camera-relay-login.service
systemctl restart camera-relay-watchdog.service 2>/dev/null || true
sleep 2

echo "4/4 Checking: look at the camera for a few seconds"
compare=$(ls /usr/lib/python3*/site-packages/howdy/compare.py 2>/dev/null | head -1)
started=0
( sleep 3; pgrep -x gst-launch-1.0 >/dev/null && touch "$work/started" ) &
if [[ -n "$compare" && -r /etc/howdy/models/$USER_NAME.dat ]]; then
    if timeout 12 runuser -u "$USER_NAME" -- /usr/bin/python3 "$compare" "$USER_NAME" >"$work/howdy" 2>&1; then
        face=ok
    else
        face=fail
    fi
else
    face=none
fi
wait
[[ -e "$work/started" ]] && started=1

echo
if [[ $started -eq 1 && $face == ok ]]; then
    echo "OK: the camera starts and your face was recognised. Face unlock works on the lock screen."
elif [[ $started -eq 1 && $face == none ]]; then
    echo "OK: the camera starts. No face is enrolled yet: add it in Settings > Accounts > Sign-in options."
elif [[ $started -eq 1 ]]; then
    echo "The camera starts now, but Howdy did not recognise you this time:"
    tail -2 "$work/howdy"
    echo "Try the lock screen anyway (Win+L); if it keeps failing, re-enrol the face in Settings."
else
    echo "The camera pipeline did not start. Previous monitor kept as /usr/local/bin/camera-relay-monitor.orig."
    tail -2 "$work/howdy" 2>/dev/null || true
    exit 1
fi
