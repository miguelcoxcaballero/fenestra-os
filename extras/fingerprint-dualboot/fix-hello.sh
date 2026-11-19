#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# sudo extras/fingerprint-dualboot/fix-hello.sh: face and fingerprint sign-in on a dual-boot PC.
#  1. Fingerprints: Windows deletes from the sensor every template it did not make, so prints
#     enrolled in Linux vanish after each Windows session. Linux now uses the ones Windows Hello
#     keeps (probe.py adopt): touch each finger registered in Windows when asked; nothing is
#     enrolled or deleted on the sensor.
#  2. Face: the lock screen's module logs every attempt (journalctl -t pam_fenestra_hello) and
#     Howdy looks for up to 9 s (was 6) inside a 10 s window (was 7).
# Log: /var/log/fenestra-fingerprint.log. Undo of 2: packaging/lockscreen/fenestra-lock-hello disable.
set -u
[ "$(id -u)" = 0 ] || exec sudo bash "$(readlink -f "$0")" "$@"
D=$(dirname "$(readlink -f "$0")")
R=$(cd "$D/../.." && pwd)
U=${SUDO_USER:-$(logname)}
LOG=/var/log/fenestra-fingerprint.log
say() { echo "$@" > /dev/tty 2>/dev/null || echo "$@"; }
echo "=================== $(date -Is) fix-hello for $U" >> "$LOG"; chmod 644 "$LOG"

say "== Cara: módulo de la pantalla de bloqueo y tiempo de Howdy"
bash "$R/packaging/lockscreen/fenestra-lock-hello" enable >> "$LOG" 2>&1 && say "   módulo instalado" || say "   NO se pudo instalar el módulo (detalle en $LOG)"
if [ -f /etc/howdy/config.ini ] && grep -q '^timeout = [0-8]$' /etc/howdy/config.ini; then
    cp -p /etc/howdy/config.ini /etc/howdy/config.ini.before-fenestra-timeout
    sed -i 's/^timeout = [0-8]$/timeout = 9/' /etc/howdy/config.ini
    say "   Howdy busca la cara hasta 9 s"
fi

say "== Huellas: usar las de Windows Hello"
timeout 12 systemctl stop fprintd 2>/dev/null || { systemctl kill -s KILL fprintd; sleep 1; }
G_MESSAGES_DEBUG=all timeout 120 python3 "$D/probe.py" adopt "$U" >> "$LOG" 2>&1
rc=$?
case $rc in
0) say "   Listo: desbloquea con ese dedo (también sigue funcionando en Windows)." ;;
4) say "   El lector no tiene ninguna huella de Windows Hello. Registra tus dedos en Windows"
   say "   (Configuración > Cuentas > Opciones de inicio de sesión > Huella digital), vuelve a"
   say "   Linux y ejecuta esto otra vez." ;;
5) say "   No se ha adoptado ninguna huella (ningún dedo coincidió). Vuelve a ejecutarlo." ;;
6) say "   Todas las huellas del lector ya se usan en Linux: no hay nada más que adoptar."
   say "   (Si las registraste desde Linux, Windows las borrará la próxima vez que lo arranques.)" ;;
*) say "   Ha fallado (código $rc). Detalle en $LOG" ;;
esac
echo "fix-hello exit $rc" >> "$LOG"
