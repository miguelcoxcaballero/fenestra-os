#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# sudo extras/fingerprint-dualboot/install-driver.sh [RPM]: installs Fenestra's build of the
# fingerprint driver (libfprint, egismoc + SDCP, with extras/fedora-upgrade/specs/
# libfprint-egismoc-robust.patch) and proves it on the real reader: the lock screen's pattern
# (start reading, cancel) six times in a row, then through fprintd with its client killed, as
# pam_fenestra_hello does when the face wins. Log: /var/log/fenestra-fingerprint.log.
# Touch nothing while it runs (about 30 s): the test is about readings nobody answers.
set -u
[ "$(id -u)" = 0 ] || exec sudo bash "$(readlink -f "$0")" "$@"
D=$(dirname "$(readlink -f "$0")")
U=${SUDO_USER:-root}
H=$(getent passwd "$U" | cut -d: -f6)
RPM=${1:-$(ls -1t "$H"/.cache/fenestra-wt/libfprint-build/RPMS/x86_64/libfprint-1*.rpm 2>/dev/null | head -1)}
LOG=/var/log/fenestra-fingerprint.log
say() { echo "$@" > /dev/tty 2>/dev/null || echo "$@"; }
[ -f "$RPM" ] || { say "No encuentro el paquete del controlador."; exit 1; }
WANT=$(rpm -qp --nosignature --qf '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}' "$RPM" 2>/dev/null)
# fprintd runs with the system's language, and the bug being fixed depended on it (GLib's
# translated "Operation was cancelled"): the test must speak it too.
SYSLANG=$(sed -n 's/^LANG=//p' /etc/locale.conf 2>/dev/null | tr -d '"'); SYSLANG=${SYSLANG:-C.UTF-8}
stress() {
    echo "--- phase $1 ($(date +%T), LANG=$SYSLANG, $(rpm -q libfprint))" >> "$LOG"
    LANG=$SYSLANG LC_ALL=$SYSLANG G_MESSAGES_DEBUG=all timeout 60 python3 "$D/probe.py" stress >> "$LOG" 2>&1
    local r=$?
    echo "--- phase $1 exit $r" >> "$LOG"
    return $r
}
stopd() { timeout 12 systemctl stop fprintd 2>/dev/null || { systemctl kill -s KILL fprintd; sleep 1; echo "fprintd had to be killed" >> "$LOG"; }; }
# Through fprintd, as the lock screen does it: fprintd-verify killed without warning four times
# (pam_fenestra_hello when the face wins), then one more that must be let in and start reading.
# Fails on a claim that is refused, on assertions in fprintd's journal, on an fprintd that hangs.
through_fprintd() {
    local r=0 out since
    since=$(date +%T)
    {
        echo "--- phase $1 ($since, $(rpm -q libfprint))"
        for i in 1 2 3 4; do
            LC_ALL=C timeout -s KILL 2 fprintd-verify "$U"; echo "killed client $i"
            sleep 1.5
        done
        out=$(LC_ALL=C timeout 4 fprintd-verify "$U" 2>&1); echo "$out"
        echo "$out" | grep -qi "already claimed\|failed to claim" && r=1
        echo "$out" | grep -qi "verify started" || r=1
        sleep 1
        journalctl -u fprintd --since "$since" --no-pager -o cat | grep -i "assertion\|critical" && r=1
        timeout 12 systemctl stop fprintd 2>/dev/null || { systemctl kill -s KILL fprintd; echo "fprintd hung at the end"; r=1; }
        echo "--- phase $1 result $r"
    } >> "$LOG" 2>&1
    return $r
}
echo "=================== $(date -Is) install $RPM" >> "$LOG"
chmod 644 "$LOG"
stopd
if [ "$(rpm -q libfprint)" != "$WANT" ]; then
    say "Probando el controlador actual (no toques el lector, unos 30 s)..."
    stress before; echo "BEFORE (driver being replaced) stress exit $?" >> "$LOG"
    through_fprintd "fprintd-before"; echo "BEFORE (driver being replaced) fprintd result $?" >> "$LOG"
    {
        # Fenestra's own build is not signed; rpm 6 refuses unsigned packages unless told.
        rpm -Uvh --force --define '_pkgverify_level none' "$RPM"
        if [ -d /var/local/fenestra-repo/45 ]; then
            rm -f /var/local/fenestra-repo/45/libfprint-1*.rpm; cp "$RPM" /var/local/fenestra-repo/45/
            command -v createrepo_c >/dev/null && createrepo_c -q /var/local/fenestra-repo/45
        fi
        rpm -q libfprint
    } >> "$LOG" 2>&1
fi
if [ "$(rpm -q libfprint)" != "$WANT" ]; then
    say "NO SE HA PODIDO INSTALAR EL CONTROLADOR (detalle en $LOG)"; echo "RESULT FAIL not installed" >> "$LOG"; exit 1
fi
say "Controlador instalado. Probando (no toques el lector, unos 30 s)..."
stress stress
A=$?
through_fprintd "fprintd"
B=$?
if [ "$A" = 0 ] && [ "$B" = 0 ]; then say "PRUEBA SUPERADA"; echo "RESULT PASS" >> "$LOG"; else say "LA PRUEBA HA FALLADO (detalle en $LOG)"; echo "RESULT FAIL stress=$A fprintd=$B" >> "$LOG"; fi
