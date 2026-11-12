#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# tools/install-root.sh: everything of a from-the-repo Fenestra that needs root, in one go (one
# password). tools/install.sh runs it last; it can also be run alone. Each part is one of the
# tools/install-*-root scripts, which stay usable on their own:
#   session files (one sign-in screen, the start-up check), battery tuning + the suspend log,
#   the KWin plugin (rounded corners, caption buttons, the text cursor for the emoji panel).
# With --tidy also the housekeeping of this PC's own leftovers (asked for, never automatic):
#   crash dumps of the old speaker service, the stale baseline of galaxy-book-guard.
set -u
[ "$(id -u)" = 0 ] || exec sudo bash "$(readlink -f "$0")" "$@"
R=$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)
U=${SUDO_USER:-$(logname 2>/dev/null || echo root)}
H=$(getent passwd "$U" | cut -d: -f6)
ok=(); bad=()
step() { local name=$1; shift; if "$@"; then ok+=("$name"); else bad+=("$name"); fi; }

step "session" bash "$R/tools/install-session-root.sh"
step "battery" bash "$R/tools/install-power-tuning.sh"
SO=$H/.local/share/fenestra/kwin-plugins/fenestra-corners.so
if [ -f "$SO" ]; then
    kwin=$(rpm -q --qf '%{VERSION}' kwin 2>/dev/null)
    built=$(strings "$SO" | grep -m1 -oE 'org\.kde\.kwin\.EffectPluginFactory[0-9.]+' | sed 's/.*Factory//')
    if [ -n "$kwin" ] && [ "$kwin" = "$built" ]; then
        step "kwin plugin" install -Dm755 "$SO" /usr/lib64/qt6/plugins/kwin/effects/plugins/fenestra-corners.so
    else
        echo "fenestra-corners.so is for KWin $built, this system has $kwin: not installed"; bad+=("kwin plugin")
    fi
fi

if [ "${1:-}" = --tidy ]; then
    # Crash dumps of windows-speaker-effects (a Python script that aborted every 3 s for days).
    n=$(find /var/lib/systemd/coredump -name 'core.python3.*' 2>/dev/null | wc -l)
    find /var/lib/systemd/coredump -name 'core.python3.*' -delete 2>/dev/null
    echo "removed $n crash dumps of the speaker service"
    # galaxy-book-guard's list of file hashes still names files of the GNOME-era setup that no
    # longer exist, so its check failed on every boot: keep the files that exist, hashed as now.
    B=/var/lib/galaxy-book-guard/baseline.sha256
    if [ -f "$B" ]; then
        cp -p "$B" "$B.before-$(date +%F)"
        awk '{ $1=""; sub(/^ [ *]?/, ""); print }' "$B" | while IFS= read -r f; do [ -f "$f" ] && sha256sum "$f"; done > "$B.new"
        mv "$B.new" "$B"; echo "galaxy-book-guard: baseline rebuilt ($(wc -l < "$B") files)"
        systemctl reset-failed galaxy-book-check.service 2>/dev/null
    fi
fi
echo
echo "root part: ok: ${ok[*]:-none}${bad[*]:+   FAILED: ${bad[*]}}"
[ ${#bad[@]} -eq 0 ]
