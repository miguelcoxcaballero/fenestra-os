#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Inside the bench container, as the user (see run.sh).
cd
rm -rf ~/.config/gtk-4.0; mkdir -p ~/.config; cp -r /src/desktop/skel/.config/gtk-4.0 ~/.config/
cp /src/desktop/gtk/caption-buttons-gtk4.css ~/.config/gtk-4.0/fenestra-caption-buttons.css
printf '@define-color fenestra_accent_dark #4cc2ff;\n@define-color fenestra_accent_light #0067c0;\n@define-color fenestra_accent_dark_fg #000000;\n@define-color fenestra_accent_light_fg #ffffff;\n' > ~/.config/gtk-4.0/fenestra-accent.css
rm -rf Desktop Documents Downloads Music Pictures Public Templates Videos Projects yyy
mkdir -p Escritorio Descargas Documentos Imágenes Música Vídeos
mkdir -p ~/.config; cat > ~/.config/user-dirs.dirs <<'DIRS'
XDG_DESKTOP_DIR="$HOME/Escritorio"
XDG_DOWNLOAD_DIR="$HOME/Descargas"
XDG_TEMPLATES_DIR="$HOME/Plantillas"
XDG_PUBLICSHARE_DIR="$HOME/Público"
XDG_DOCUMENTS_DIR="$HOME/Documentos"
XDG_MUSIC_DIR="$HOME/Música"
XDG_PICTURES_DIR="$HOME/Imágenes"
XDG_VIDEOS_DIR="$HOME/Vídeos"
DIRS
mkdir -p ~/.config/gtk-3.0; for d in Escritorio Documentos Música Imágenes Vídeos Descargas; do echo "file://$HOME/$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' $d)"; done > ~/.config/gtk-3.0/bookmarks
# Same contents as the reference VM: Documentos has a text file (extension hidden there) and a .md.
printf 'Informe trimestral\n' > "Documentos/Informe trimestral.txt"
printf '# Notas\n' > "Documentos/Notas de la reunión.md"
head -c 600 /dev/zero > Música/demo-tono.wav
touch -d '2026-11-07 02:00' Documentos/*
python3 - <<'PY'
import gi, os, time
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib
home = os.path.expanduser('~')
def entry(path, mime, stamp):
    uri = GLib.filename_to_uri(path)
    t = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(stamp))
    return f'''  <bookmark href="{uri}" added="{t}" modified="{t}" visited="{t}">
    <info><metadata owner="http://freedesktop.org"><mime:mime-type type="{mime}"/>
    <bookmark:applications><bookmark:application name="fenestra" exec="&apos;true %u&apos;" modified="{t}" count="1"/></bookmark:applications>
    </metadata></info></bookmark>'''
loc = lambda s: time.mktime(time.strptime(s, '%d/%m/%Y %H:%M'))
xml = ['<?xml version="1.0" encoding="UTF-8"?>',
       '<xbel version="1.0" xmlns:bookmark="http://www.freedesktop.org/standards/desktop-bookmarks" xmlns:mime="http://www.freedesktop.org/standards/shared-mime-info">',
       entry(f'{home}/Documentos/Informe trimestral.txt', 'text/plain', loc('06/11/2026 21:11')),
       entry(f'{home}/Música/demo-tono.wav', 'audio/x-wav', loc('06/11/2026 17:38')), '</xbel>']
os.makedirs(f'{home}/.local/share', exist_ok=True)
open(f'{home}/.local/share/recently-used.xbel', 'w').write('\n'.join(xml))
PY
python3 - <<'PY'
from gi.repository import Gio
s = Gio.Settings.new("org.gnome.shell")
s.set_strv("enabled-extensions", ["explorerqa@local"]); s.set_boolean("disable-user-extensions", False)
Gio.Settings.sync()
PY
gsettings set org.gnome.desktop.interface color-scheme prefer-dark
gsettings set org.gnome.desktop.background picture-options none
gsettings set org.gnome.desktop.background primary-color '#1f1f1f'
gsettings set org.gnome.desktop.interface enable-animations false
export WAYLAND_DISPLAY=w0
dbus-update-activation-environment WAYLAND_DISPLAY XDG_SESSION_TYPE XDG_CURRENT_DESKTOP LANG LC_ALL TZ
gnome-shell --headless --virtual-monitor=1920x1080 --wayland --wayland-display=w0 > /tmp/shell.log 2>&1 &
for i in $(seq 120); do grep -q 'SHOTQA ready' /tmp/shell.log && break; sleep 0.5; done
grep -q "SHOTQA ready" /tmp/shell.log || { echo "shell did not start"; grep -a -i -E "explorerqa|extension|JS ERROR" /tmp/shell.log | head; cp /tmp/shell.log /out/; exit 1; }
for job in /out/jobs/*; do
  name=$(basename "$job"); scheme=dark; open=$HOME; rm -f ~/.config/fenestra-explorer/view.json
  views='{}'
  while read -r k a b; do
    case $k in
      @scheme) scheme=$a ;;
      @open) case $a in /*|*:*) open=$a ;; *) open=$HOME/$a ;; esac ;;
      @view) views=$(python3 -c "import json,sys,os;d=json.loads(sys.argv[1]);d[__import__('gi.repository.Gio',fromlist=['Gio']).File.new_for_path(os.path.expanduser('~/'+sys.argv[2])).get_uri()]=sys.argv[3];print(json.dumps(d))" "$views" "$a" "$b") ;;
    esac
  done < "$job"
  mkdir -p ~/.config/fenestra-explorer; echo "{\"folders\": $views}" > ~/.config/fenestra-explorer/view.json
  gsettings set org.gnome.desktop.interface color-scheme prefer-$scheme
  pkill -f libexec/fenestra/nautilus; sleep 0.5
  /usr/libexec/fenestra/fenestra-nautilus --new-window "$open" > /tmp/nautilus-$name.log 2>&1 &
  sleep 4
  { echo "win 408 206 1123 632"; echo "move 1900 30"; echo "wait 1500"; grep -v '^@' "$job"; } > /tmp/shotreq/$name.tmp
  mv /tmp/shotreq/$name.tmp /tmp/shotreq/$name
  for i in $(seq 240); do [ -f /out/$name.done ] && break; sleep 0.5; done
  rm -f /out/$name.done
  grep -a -E 'Error building template|Traceback|CRITICAL' /tmp/nautilus-$name.log | head -5
done
grep -a -E 'SHOTQA (win|fail)|JS ERROR' /tmp/shell.log | tail -40
cp /tmp/nautilus-*.log /out/ 2>/dev/null
{ ls ~; cat ~/.config/user-dirs.dirs ~/.config/gtk-3.0/bookmarks; } > /out/home.txt 2>&1
