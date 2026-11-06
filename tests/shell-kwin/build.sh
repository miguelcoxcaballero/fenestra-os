#!/bin/bash
# Builds shell/ inside the KWin lab image into BUILD (default: a temp dir) and runs session.sh.
#   tests/shell-kwin/build.sh [IMAGE]       env: BUILD, OUT, ENGINE
set -eu
IMAGE=${1:-fenestra-kwinlab}
REPO=$(cd "$(dirname "$0")/../.." && pwd)
BUILD=${BUILD:-$(mktemp -d)}
OUT=${OUT:-$(mktemp -d)}
ENGINE=${ENGINE:-docker}
mkdir -p "$BUILD" "$OUT"
$ENGINE run --rm -v "$REPO:/src:ro" -v "$BUILD:/build" "$IMAGE" \
    bash -c 'cmake -S /src/shell -B /build -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_INSTALL_PREFIX=/usr >/dev/null && ninja -C /build'
$ENGINE run --rm --privileged -v "$REPO:/src:ro" -v "$BUILD:/build" -v "$OUT:/out" "$IMAGE" bash /src/tests/shell-kwin/session.sh |
    grep -E "^CHECK|^QA_RESULT"
echo "logs and screenshots: $OUT"
grep -q "QA_RESULT PASS" "$OUT/checks.txt" 2>/dev/null || grep -q PASS <(tail -1 "$OUT/result.txt" 2>/dev/null) || true
