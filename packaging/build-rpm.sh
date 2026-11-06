#!/bin/bash
# Builds fenestra-shell RPMs from this checkout into OUT (default: packaging/out).
#   packaging/build-rpm.sh [OUT]     (needs rpm-build and the BuildRequires; or run it in
#   the KWin lab image: docker run --rm -v $PWD:/src fenestra-kwinlab bash /src/packaging/build-rpm.sh /src/packaging/out)
# The Release carries the commit (FENESTRA_COMMIT / FENESTRA_COMMIT_DATE, else git):
# <commit date UTC>.git<short id>, so newer Fenestra builds are upgrades. Without git: 1.
set -eu
REPO=$(cd "$(dirname "$0")/.." && pwd)
OUT=${1:-$REPO/packaging/out}
VER=$(sed -n 's/^Version: *//p' "$REPO/packaging/fenestra-shell.spec")
git_() { git -c safe.directory="$REPO" -C "$REPO" "$@" 2>/dev/null; }
COMMIT=${FENESTRA_COMMIT:-$(git_ rev-parse HEAD || true)}
COMMIT_DATE=${FENESTRA_COMMIT_DATE:-$(git_ log -1 --format=%cI "$COMMIT" || true)}
DEFINES=()
if [[ $COMMIT =~ ^[0-9a-f]{40}$ && -n $COMMIT_DATE ]]; then
    STAMP=$(date -u -d "$COMMIT_DATE" +%Y%m%d%H%M%S)
    DEFINES=(--define "fenestra_release $STAMP.git${COMMIT:0:7}" --define "fenestra_commit $COMMIT")
fi
TOP=$(mktemp -d)
trap 'rm -rf "$TOP"' EXIT
mkdir -p "$TOP"/{SOURCES,SPECS,BUILD,RPMS,SRPMS} "$OUT"
tar -C "$REPO" --transform "s,^,fenestra-shell-$VER/," -czf "$TOP/SOURCES/fenestra-shell-$VER.tar.gz" \
    shell session kwin lnf design tools/build-aurorae-theme.py LICENSE
rpmbuild --define "_topdir $TOP" "${DEFINES[@]}" -bb "$REPO/packaging/fenestra-shell.spec"
find "$TOP/RPMS" -name '*.rpm' -exec cp {} "$OUT/" \;
ls -1 "$OUT"
