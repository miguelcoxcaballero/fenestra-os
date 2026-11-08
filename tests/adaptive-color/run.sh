#!/bin/bash
# Adaptive color bench (no hardware needed):
#   1. curve table/sweep/follow: the mapping against Microsoft's sample table, the curve over
#      ambient CCT x lux, and the filter on simulated scenes (host compiler, no Qt);
#   2. session.sh in the KWin lab image: the real shell with a fake sensor tree, every
#      temperature KWin commits recorded through ambient scenes, Night light on/off.
# Read the real sensor (read-only): curve live /sys/bus/iio/devices SECONDS
#   tests/adaptive-color/run.sh [IMAGE]    env: BUILD (shell build dir), OUT, ENGINE, JOBS
set -eu
IMAGE=${1:-fenestra-kwinlab}
REPO=$(cd "$(dirname "$0")/../.." && pwd)
ENGINE=${ENGINE:-podman}
BUILD=${BUILD:-$(mktemp -d)}
OUT=${OUT:-$(mktemp -d)}
mkdir -p "$BUILD" "$OUT"
g++ -std=c++20 -O2 -Wall -Wextra -I "$REPO/shell/src/services" "$REPO/tests/adaptive-color/curve.cpp" -o "$OUT/curve"
"$OUT/curve" table | tee "$OUT/table.txt"
"$OUT/curve" sweep > "$OUT/sweep.txt"
"$OUT/curve" follow > "$OUT/follow.txt"
$ENGINE run --rm --security-opt label=disable -v "$REPO:/src:ro" -v "$BUILD:/build" "$IMAGE" \
    bash -c "cmake -S /src/shell -B /build -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_INSTALL_PREFIX=/usr >/dev/null && ninja -j${JOBS:-1} -C /build >/dev/null"
$ENGINE run --rm --privileged --security-opt label=disable -v "$REPO:/src:ro" -v "$BUILD:/build" -v "$OUT:/out" "$IMAGE" bash /src/tests/adaptive-color/session.sh
echo "results: $OUT"
