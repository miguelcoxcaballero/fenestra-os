#!/bin/bash
# sudo tools/install-privacy-root.sh — what the Fenestra RPM installs for privacy and biometrics,
# for a system running Fenestra from the repo:
#  * block recording (Samsung firmware) switchable without a password + applied now,
#  * face set-up with the user's own password (org.fenestra.hello.enroll) instead of an admin's,
#  * face sign-in on the lock screen (fenestra-lock-hello enable).
set -eu
[ "$(id -u)" = 0 ] || { echo "Run with sudo." >&2; exit 1; }
R=$(cd "$(dirname "$0")/.." && pwd)
install -Dm644 "$R/desktop/privacy/70-fenestra-recording-block.rules" /etc/udev/rules.d/70-fenestra-recording-block.rules
f=/sys/class/firmware-attributes/samsung-galaxybook/attributes/block_recording/current_value
[ -e "$f" ] && { chgrp wheel "$f"; chmod 0664 "$f"; echo "block recording: switchable by wheel"; }
install -Dm755 "$R/packaging/privacy/fenestra-hello-enroll" /usr/libexec/fenestra/fenestra-hello-enroll
install -Dm644 "$R/desktop/privacy/org.fenestra.hello.policy" /usr/share/polkit-1/actions/org.fenestra.hello.policy
install -Dm644 "$R/desktop/privacy/50-fenestra-enroll.rules" /etc/polkit-1/rules.d/50-fenestra-enroll.rules
restorecon -F /etc/polkit-1/rules.d/50-fenestra-enroll.rules /etc/udev/rules.d/70-fenestra-recording-block.rules /usr/libexec/fenestra/fenestra-hello-enroll /usr/share/polkit-1/actions/org.fenestra.hello.policy 2>/dev/null || true
# Face sign-in on the lock screen stays off until the lock screen runs it in its own worker
# (pam_howdy in the password chain locked the user out when the camera hung).
"$R/packaging/lockscreen/fenestra-lock-hello" disable || true
echo "Done."
