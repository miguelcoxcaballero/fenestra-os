#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# tests/lockscreen/host-check.sh [seconds]: on the real PC, WITHOUT locking anything: runs
# kscreenlocker_greet --testing (a window, not a lock; it ends when this script kills it or when you
# unlock it) with the installed lock screen and the real PAM services, and checks that
#   * both PAM workers start and answer (kde = password, kde-fingerprint = face + fingerprint),
#   * the password worker asks for the password at once (nothing in front of it),
#   * the lock screen QML loads without errors.
# Typing your password into the test window and pressing Enter proves the unlock itself.
set -u
T=${1:-10}
LOG=$(mktemp)
QT_FORCE_STDERR_LOGGING=1 QT_LOGGING_RULES='kscreenlocker*.debug=true;qml.debug=true;js.debug=true' \
    /usr/libexec/kscreenlocker_greet --testing > "$LOG" 2>&1 &
pid=$!
for _ in $(seq $((T * 10))); do kill -0 $pid 2>/dev/null || break; sleep 0.1; done
kill $pid 2>/dev/null; sleep 0.5; kill -9 $pid 2>/dev/null
pkill -P $pid 2>/dev/null
ok=0; fail=0
c() { if grep -q "$2" "$LOG"; then echo "CHECK $1 PASS"; ok=$((ok+1)); else echo "CHECK $1 FAIL"; fail=$((fail+1)); fi; }
n() { if grep -q "$2" "$LOG"; then echo "CHECK $1 FAIL"; fail=$((fail+1)); else echo "CHECK $1 PASS"; ok=$((ok+1)); fi; }
c worker-kde-started 'Starting PAM worker for service "kde"'
c worker-fingerprint-started 'Starting PAM worker for service "kde-fingerprint"'
[ "$(grep -c 'Ping received' "$LOG")" -ge 2 ] && { echo "CHECK workers-answer PASS"; ok=$((ok+1)); } || { echo "CHECK workers-answer FAIL"; fail=$((fail+1)); }
c password-asked 'Echo-off prompt'
n no-qml-errors '\.qml:[0-9]*:.*\(Error\|TypeError\|is not\)'
n no-dead-worker 'worker not initialized\|Worker did not terminate'
echo "log: $LOG"
[ $fail = 0 ] && echo "HOST_CHECK PASS" || { echo "HOST_CHECK FAIL"; exit 1; }
