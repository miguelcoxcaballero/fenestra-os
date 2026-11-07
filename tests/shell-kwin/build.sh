#!/bin/bash
# Builds shell/ inside the KWin lab image into BUILD (default: a temp dir) and runs session.sh.
#   tests/shell-kwin/build.sh [IMAGE]       env: BUILD, OUT, ENGINE
set -u
IMAGE=${1:-fenestra-kwinlab}
REPO=$(cd "$(dirname "$0")/../.." && pwd)
BUILD=${BUILD:-$(mktemp -d)}
OUT=${OUT:-$(mktemp -d)}
ENGINE=${ENGINE:-docker}
mkdir -p "$BUILD" "$OUT"
$ENGINE run --rm -e JOBS="${JOBS:-2}" -v "$REPO:/src:ro" -v "$BUILD:/build" "$IMAGE" \
    bash -c 'cmake -S /src/shell -B /build -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_INSTALL_PREFIX=/usr >/dev/null && ninja -j${JOBS:-2} -C /build'
$ENGINE run --rm --privileged -e OUTPUTS="${OUTPUTS:-1}" -e PERF="${PERF:-}" -e MOTION="${MOTION:-}" -e MOTION_POPUPS="${MOTION_POPUPS:-}" -e PERF_SECONDS="${PERF_SECONDS:-30}" -e PERF_RUNS="${PERF_RUNS:-3}" -e TIMEOUT="${TIMEOUT:-240}" -e WIDTH="${WIDTH:-1920}" -e HEIGHT="${HEIGHT:-1080}" -v "$REPO:/src:ro" -v "$BUILD:/build" -v "$OUT:/out" "$IMAGE" bash /src/tests/shell-kwin/session.sh |
    grep -E "^CHECK|^QA_RESULT|^MOTION"
echo "logs and screenshots: $OUT"
grep -q "QA_RESULT PASS" "$OUT/result.txt"
