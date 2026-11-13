#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# sudo extras/fingerprint-dualboot/doctor.sh: what the fingerprint reader really holds and answers,
# written to /var/log/fenestra-fingerprint.log (readable without root). Changes nothing on the
# sensor. fprintd is stopped meanwhile and starts again by itself at the next use.
# It asks for a finger once: touch the reader when it says so (or let the 15 s pass).
set -u
[ "$(id -u)" = 0 ] || exec sudo bash "$(readlink -f "$0")" "$@"
D=$(dirname "$(readlink -f "$0")")
LOG=/var/log/fenestra-fingerprint.log
say() { echo "$@" > /dev/tty 2>/dev/null || true; }
{
    echo "=================== $(date -Is) kernel $(uname -r)"
    rpm -q libfprint fprintd
    lsusb | grep -i 1c7a
    echo "--- fprintd storage"; ls -laR --time-style=long-iso /var/lib/fprint 2>&1
    echo "--- fprintd before"; systemctl show fprintd -p ActiveState -p ExecMainStartTimestamp
} >> "$LOG" 2>&1
chmod 644 "$LOG"
say "Parando el servicio de huellas..."
timeout 12 systemctl stop fprintd 2>/dev/null || { systemctl kill -s KILL fprintd; sleep 1; echo "fprintd had to be killed" >> "$LOG"; }
run() {
    echo "--- phase $1 ($(date +%T))" >> "$LOG"
    G_MESSAGES_DEBUG=all timeout 45 python3 "$D/probe.py" "$1" >> "$LOG" 2>&1
    echo "--- phase $1 exit $?" >> "$LOG"
}
say "Leyendo el sensor (1/3)..."; run list
say "Leyendo el sensor (2/3)..."; run list
say ""
say ">>> PON EL DEDO EN EL LECTOR AHORA (tienes 15 segundos) <<<"
run identify
say "Hecho. Resultado en $LOG"
