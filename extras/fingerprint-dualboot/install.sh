#!/bin/sh
# Installs the fprintd "keep sensor storage" shim (run as root).
set -e
DIR=$(dirname "$(readlink -f "$0")")
install -Dm755 "$DIR/libfprintd-keep-storage.so" /usr/local/lib64/libfprintd-keep-storage.so
mkdir -p /etc/systemd/system/fprintd.service.d
cat > /etc/systemd/system/fprintd.service.d/keep-storage.conf <<'CONF'
[Service]
Environment=LD_PRELOAD=/usr/local/lib64/libfprintd-keep-storage.so
CONF
restorecon -R /usr/local/lib64/libfprintd-keep-storage.so 2>/dev/null || true
systemctl daemon-reload
systemctl stop fprintd.service 2>/dev/null || true
echo "Instalado. fprintd ya no borrará las huellas de Windows del sensor."
