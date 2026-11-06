#!/bin/bash
# Builds fenestra-shell RPMs from this checkout into OUT (default: packaging/out).
#   packaging/build-rpm.sh [OUT]     (needs rpm-build and the BuildRequires; or run it in
#   the KWin lab image: docker run --rm -v $PWD:/src fenestra-kwinlab bash /src/packaging/build-rpm.sh /src/packaging/out)
set -eu
REPO=$(cd "$(dirname "$0")/.." && pwd)
OUT=${1:-$REPO/packaging/out}
VER=$(sed -n 's/^Version: *//p' "$REPO/packaging/fenestra-shell.spec")
TOP=$(mktemp -d)
mkdir -p "$TOP"/{SOURCES,SPECS,BUILD,RPMS,SRPMS} "$OUT"
tar -C "$REPO" --transform "s,^,fenestra-shell-$VER/," -czf "$TOP/SOURCES/fenestra-shell-$VER.tar.gz" \
    shell session kwin lnf migrator design tools/build-aurorae-theme.py LICENSE
rpmbuild --define "_topdir $TOP" -bb "$REPO/packaging/fenestra-shell.spec"
find "$TOP/RPMS" -name '*.rpm' -exec cp {} "$OUT/" \;
ls -1 "$OUT"
