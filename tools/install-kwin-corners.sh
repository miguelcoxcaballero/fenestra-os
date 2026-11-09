#!/bin/bash
# tools/install-kwin-corners.sh [PLUGIN.so]: installs the Fenestra rounded-corners KWin effect
# (kwin/plugins/fenestra-corners, built for the installed KWin) and loads it into the running
# KWin, no restart or logout. Needs root for the plugin directory: KWin only loads effect plugins
# from Qt's plugin path (/usr/lib64/qt6/plugins/kwin/effects/plugins); there is no per-user one
# (kwin_wayland has file capabilities, so it ignores QT_PLUGIN_PATH).
# The RPM (packaging/fenestra-shell.spec) installs the same file; this is for a running system.
set -eu
SO=${1:-$HOME/.local/share/fenestra/kwin-plugins/fenestra-corners.so}
DEST=/usr/lib64/qt6/plugins/kwin/effects/plugins/fenestra-corners.so
want=$(rpm -q --qf '%{VERSION}' kwin 2>/dev/null || true)
built=$(strings "$SO" | grep -m1 -oE 'org\.kde\.kwin\.EffectPluginFactory[0-9.]+' | sed 's/.*Factory//')
if [ -n "$want" ] && [ -n "$built" ] && [ "$want" != "$built" ]; then
    echo "fenestra-corners.so was built for KWin $built, this system runs $want: rebuild it" >&2
    exit 1
fi
sudo install -Dm755 "$SO" "$DEST"
# The window motion effect works with this plugin (X11 windows crop their old picture through it):
# both go live together. Unload first: an effect already loaded would keep its old code.
REPO=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$HOME/.local/share/kwin/effects"
cp -r "$REPO/kwin/effects/fenestra-window-motion" "$HOME/.local/share/kwin/effects/"
for effect in fenestra-corners fenestra-window-motion; do
    gdbus call --session -d org.kde.KWin -o /Effects -m org.kde.kwin.Effects.unloadEffect "$effect" >/dev/null
    gdbus call --session -d org.kde.KWin -o /Effects -m org.kde.kwin.Effects.loadEffect "$effect"
done
