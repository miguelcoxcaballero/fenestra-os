#!/bin/bash
# sudo bash install-watchdog.sh   — installs and starts the camera relay watchdog
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
install -m755 "$HERE/camera-relay-watchdog" /usr/local/bin/camera-relay-watchdog
install -m644 "$HERE/camera-relay-watchdog.service" /etc/systemd/system/camera-relay-watchdog.service
restorecon -F /usr/local/bin/camera-relay-watchdog /etc/systemd/system/camera-relay-watchdog.service 2>/dev/null || true
systemctl daemon-reload
systemctl restart camera-relay-login.service
systemctl enable --now camera-relay-watchdog.service
echo "Camera relay restarted and watchdog enabled."
