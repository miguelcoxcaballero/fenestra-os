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
{
    echo "=================== $(date -Is) install $RPM"
    timeout 12 systemctl stop fprintd 2>/dev/null || { systemctl kill -s KILL fprintd; sleep 1; echo "fprintd had to be killed"; }
    rpm -Uvh --force "$RPM"
    # The local repository the system updates from keeps the same build.
    if [ -d /var/local/fenestra-repo/45 ]; then
        rm -f /var/local/fenestra-repo/45/libfprint-1*.rpm; cp "$RPM" /var/local/fenestra-repo/45/
        command -v createrepo_c >/dev/null && createrepo_c -q /var/local/fenestra-repo/45
    fi
    rpm -q libfprint
} >> "$LOG" 2>&1
chmod 644 "$LOG"
say "Controlador instalado. Probando (no toques el lector, unos 30 s)..."
echo "--- phase stress ($(date +%T))" >> "$LOG"
G_MESSAGES_DEBUG=all timeout 60 python3 "$D/probe.py" stress >> "$LOG" 2>&1
A=$?
echo "--- phase stress exit $A" >> "$LOG"
# Through fprintd, as the lock screen: fprintd-verify killed without warning, four times.
B=0
{
    echo "--- phase fprintd ($(date +%T))"
    for i in 1 2 3 4; do
        timeout -s KILL 2 runuser -u "$U" -- fprintd-verify; echo "killed client $i"
        sleep 1.5
    done
    out=$(timeout 4 runuser -u "$U" -- fprintd-verify 2>&1); echo "$out"
    echo "$out" | grep -qi "already claimed\|failed to claim" && B=1
    journalctl -u fprintd --since "-40s" --no-pager -o cat | grep -i "assertion\|critical" && B=1
    echo "--- phase fprintd result $B"
} >> "$LOG" 2>&1
timeout 12 systemctl stop fprintd 2>/dev/null || { systemctl kill -s KILL fprintd; echo "fprintd hung at the end" >> "$LOG"; B=1; }
if [ "$A" = 0 ] && [ "$B" = 0 ]; then say "PRUEBA SUPERADA"; echo "RESULT PASS" >> "$LOG"; else say "LA PRUEBA HA FALLADO (detalle en $LOG)"; echo "RESULT FAIL stress=$A fprintd=$B" >> "$LOG"; fi
