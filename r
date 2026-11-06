#!/bin/bash
# Rescate Fenestra tras actualizar a Fedora 45 / GNOME 51 (pantalla negra en GDM).
# Uso (en la consola de texto):  curl -L <url>/r | sudo bash
# 1) Diagnostica solo leyendo.  2) Si la causa es Meta.Background.set_file,
# desactiva fenestra-login, fenestra-spotlight y fenestra-lock-clock MOVIENDOLAS
# (sin borrar nada; mv conserva las etiquetas SELinux).  Todo queda en el log.
{
LOG=/root/fenestra-rescate.log
exec > >(tee -a "$LOG") 2>&1
[ "$(id -u)" = 0 ] || { echo "Ejecutalo con sudo"; exit 1; }
echo "===== $(date -Is) ====="
echo "== os-release";   grep -E '^(NAME|VERSION|VERSION_ID)=' /etc/os-release
echo "== release-upgrade.json"; cat /var/lib/fenestra/release-upgrade.json 2>&1; echo
echo "== /system-update"; ls -la /system-update 2>&1
echo "== gnome-shell"; gnome-shell --version 2>&1
echo "== journal (ultimos 14 dias)"
J=$(journalctl --no-pager -o short-iso --since -14d 2>/dev/null | grep -E 'set_file is not a function|JS ERROR|fenestra-(login|spotlight|lock-clock)')
echo "$J" | tail -n 40
echo "== extensiones fenestra encontradas"
SYS=/usr/share/gnome-shell
BASES="$SYS /var/lib/gdm/.local/share/gnome-shell $(ls -d /home/*/.local/share/gnome-shell 2>/dev/null)"
for b in $BASES; do ls -d "$b"/extensions/fenestra-* 2>/dev/null; done
if ! echo "$J" | grep -q 'set_file is not a function'; then
  echo; echo ">>> NO aparece 'set_file is not a function'. NO se ha movido nada."
  echo ">>> Pasa $LOG al agente (claude) y que siga RESCATE.md."; exit 1
fi
echo; echo "== causa confirmada: set_file. Moviendo extensiones (reversible)"
for b in $BASES; do
  for e in login spotlight lock-clock; do
    s="$b/extensions/fenestra-$e@fenestra-os.github.io"; d="$b/disabled-fenestra-$e"
    [ -d "$s" ] || continue
    if [ -e "$d" ]; then echo "YA EXISTE $d, no muevo $s"; else mv -v "$s" "$d"; fi
  done
done
echo; echo ">>> Hecho. Log en $LOG.  Ahora:  reboot"
echo ">>> Para deshacer: mv <base>/disabled-fenestra-X <base>/extensions/fenestra-X@fenestra-os.github.io"
}
