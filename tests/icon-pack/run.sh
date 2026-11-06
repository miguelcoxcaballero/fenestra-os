#!/bin/bash
# Imports a synthetic icon pack (made-up artwork, nothing from Windows) into a temporary home and
# checks where the files land and that Fenestra Shell's icon lookup finds them.
#   tests/icon-pack/run.sh [IMAGE]     (IMAGE: the KWin lab image, default fenestra-kwinlab; ENGINE=docker)
set -eu
IMAGE=${1:-fenestra-kwinlab}
ENGINE=${ENGINE:-docker}
REPO=$(cd "$(dirname "$0")/../.." && pwd)
WORK=${WORK:-$(mktemp -d)}
mkdir -p "$WORK/out"
$ENGINE run --rm -v "$REPO:/src:ro" -v "$WORK:/work" "$IMAGE" bash -c '
set -eu
python3 /src/tests/icon-pack/make-synthetic-pack.py /work/synthetic.zip
export XDG_DATA_HOME=/work/home/data XDG_CONFIG_HOME=/work/home/config
rm -rf /work/home
python3 /src/tools/fenestra-import-windows-assets --pack /work/synthetic.zip --no-apply
python3 /src/tests/icon-pack/check-install.py /work/home/data synthetic-test-pack
cmake -S /src/tests/icon-pack/qt -B /work/build -G Ninja >/dev/null && ninja -C /work/build >/dev/null
ln -sfn /work/out /out
export QT_QPA_PLATFORM=offscreen
/work/build/iconpack-test /work/home/data/fenestra/packs/synthetic-test-pack
XDG_DATA_HOME=/work/empty /work/build/iconpack-test --no-pack
'
echo "work dir: $WORK"
