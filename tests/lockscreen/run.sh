#!/bin/bash
# Lock screen render test (container): tests/lockscreen/run.sh [OUT]  — needs qml (qt6-qtdeclarative).
set -u
REPO=$(cd "$(dirname "$0")/../.." && pwd)
OUT=${1:-$(mktemp -d)}
mkdir -p "$OUT"
export QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software QT_FORCE_STDERR_LOGGING=1 LANG=${LANG:-es_ES.UTF-8}
timeout 60 /usr/lib64/qt6/bin/qml "$REPO/tests/lockscreen/harness.qml" -- \
    "$REPO/lnf/org.fenestra.desktop/contents/lockscreen/LockScreen.qml" \
    "$REPO/assets/generated/wallpapers/fenestra-bloom-dark.jpg" "$OUT" 2>&1 | tee "$OUT/lock.log" | grep LOCK_
ok=1
for s in lock-1-clock lock-2-signin lock-3-wrong; do [ -s "$OUT/$s.png" ] || ok=0; done
grep -q "LOCK_STARTED true" "$OUT/lock.log" || ok=0
grep -q "LOCK_MESSAGE .\+" "$OUT/lock.log" || ok=0
grep -q LOCK_SUCCEEDED "$OUT/lock.log" || ok=0
[ $ok = 1 ] && echo "QA_RESULT PASS" || { echo "QA_RESULT FAIL"; exit 1; }
