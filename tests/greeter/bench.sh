#!/bin/bash
# Greeter / lock-screen bench: runs every scenario of run.sh in fresh containers and checks
# each verdict against the expected one. Exit code 0 only when all match, including the
# "broken" scenario, which must FAIL (proves the bench detects the Fedora 45 black screen).
#   tests/greeter/bench.sh [IMAGE]        (default image: fenestra-greeterlab)
#   ONLY=broken tests/greeter/bench.sh    only the scenarios whose name matches
# The image: Fedora N + gnome-shell + gdm + accountsservice + python3-pillow
# (extras/fedora-upgrade/f45-lab/Containerfile, plus: dnf install gdm accountsservice).
set -u
IMAGE=${1:-fenestra-greeterlab}
REPO=$(cd "$(dirname "$0")/../.." && pwd)
OUT=${OUT:-$(mktemp -d)}
BROKEN=$OUT/broken
mkdir -p "$BROKEN"
# Versions before the GNOME 51 fix (3a03758): Meta.Background.set_file, no fail-safe.
for e in fenestra-login fenestra-spotlight fenestra-lock-clock; do
    (cd "$REPO" && git archive 3a03758^ "desktop/extensions/$e@fenestra-os.github.io") | tar -x -C "$BROKEN" --strip-components=2
done
ENGINE=$(command -v podman || command -v docker)
fails=0
run() {  # name expected env...
    local name=$1 want=$2; shift 2
    case "$name" in *${ONLY:-}*) ;; *) return ;; esac
    mkdir -p "$OUT/$name"
    local args=()
    for kv in "$@"; do args+=(-e "$kv"); done
    $ENGINE run --rm --privileged "${args[@]}" -v "$REPO:/src:ro" -v "$BROKEN:/broken:ro" -v "$OUT/$name:/out" \
        "$IMAGE" bash /src/tests/greeter/run.sh > "$OUT/$name/qa.txt" 2>&1
    local got; got=$(sed -n 's/.*QA_RESULT \(PASS\|FAIL\).*/\1/p' "$OUT/$name/qa.txt" | tail -1)
    got=${got:-NONE}
    if [ "$got" = "$want" ]; then echo "ok    $name: $got"; else echo "WRONG $name: $got (expected $want)"; fails=$((fails+1)); fi
}
run gdm-system-ok        PASS EXTSET=system SCENARIO=ok   MODE=gdm
run gdm-system-nobg      PASS EXTSET=system SCENARIO=nobg MODE=gdm
run gdm-system-step1     PASS EXTSET=system SCENARIO=ok   MODE=gdm "EXTS_OVERRIDE='windows-spotlight@local'"   # restore-login-extensions.sh step 1
run gdm-repo-ok          PASS EXTSET=repo   SCENARIO=ok   MODE=gdm
run gdm-repo-nobg        PASS EXTSET=repo   SCENARIO=nobg MODE=gdm
run gdm-broken-ok        FAIL EXTSET=broken SCENARIO=ok   MODE=gdm
run user-system-lock     PASS EXTSET=system SCENARIO=ok   MODE=user
run user-repo-lock       PASS EXTSET=repo   SCENARIO=ok   MODE=user
run user-broken-lock     FAIL EXTSET=broken SCENARIO=ok   MODE=user
echo "logs and screenshots: $OUT"
exit $fails
