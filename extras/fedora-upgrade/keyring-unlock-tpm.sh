#!/usr/bin/bash
# Fedora 45 replaced gnome-keyring with oo7. pam_oo7 unlocks the "Login" keyring with the
# password typed at login, so after a face (Howdy) or fingerprint login nothing unlocks it and
# every app that needs a secret asks for the keyring password.
# This seals the keyring password with the laptop's TPM as the systemd user credential
# oo7.keyring-encryption-password, which oo7-daemon imports and uses at every login
# (documented in /usr/share/doc/oo7-daemon/README.md). Like Windows Hello + Credential Manager:
# the secret is bound to this machine's TPM. Anyone running as you (or root) can decrypt it.
#   bash keyring-unlock-tpm.sh        (as your user, not sudo; run again after a password change)
set -uo pipefail
[ "$(id -u)" != 0 ] || { echo "Ejecuta sin sudo"; exit 1; }
DIR=${XDG_CONFIG_HOME:-$HOME/.config}/credstore.encrypted
CRED=$DIR/oo7.keyring-encryption-password
REPO=$HOME/Projects/fenestra-os
mkdir -p "$DIR"; chmod 700 "$DIR"

echo "== 1. Llavero: escribe la contraseña de tu cuenta (es la del llavero). No se muestra."
while true; do
    read -rs -p "Contraseña: " p1; echo
    read -rs -p "Repite la contraseña: " p2; echo
    if [ -z "$p1" ]; then echo "Está vacía, otra vez."; continue; fi
    if [ "$p1" != "$p2" ]; then echo "No coinciden, otra vez."; continue; fi
    break
done
tmp=$(mktemp "$DIR/.new.XXXXXX")
if printf '%s' "$p1" | systemd-creds encrypt --user --name=oo7.keyring-encryption-password - "$tmp"; then
    unset p1 p2
    chmod 600 "$tmp"; mv "$tmp" "$CRED"
    echo "Guardada cifrada con el TPM: $CRED"
else
    unset p1 p2; rm -f "$tmp"; echo "ERROR: no se pudo cifrar"; exit 1
fi

echo "Comprobando: reinicio el servicio de contraseñas y miro si el llavero se abre solo..."
systemctl --user restart oo7-daemon.service
sleep 2
locked=$(busctl --user get-property org.freedesktop.secrets /org/freedesktop/secrets/aliases/default \
         org.freedesktop.Secret.Collection Locked 2>/dev/null | awk '{print $2}')
if [ "$locked" = false ]; then
    echo "OK: el llavero se abre solo con la credencial del TPM."
else
    echo "AVISO: el llavero sigue bloqueado (Locked=$locked). Puede que la contraseña del llavero"
    echo "no sea la de tu cuenta. Quito la credencial para no dejarla mal:"
    mv "$CRED" "$DIR/.wrong-password.bak"; echo "movida a $DIR/.wrong-password.bak"
    journalctl --user -u oo7-daemon -n 15 --no-pager | grep -iE "credential|unlock|password" || true
fi

echo FIN
