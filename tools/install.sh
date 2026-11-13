#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# tools/install.sh [--tidy] [--no-root]: brings this PC's Fenestra to this checkout, every part,
# in one command, and then checks that what runs is what was built. Until the packages carry
# everything, a system running Fenestra from the repo was a mosaic of separate scripts and
# hand-copied folders; a part that was forgotten kept its old code without anyone noticing.
#   user parts (no password): the shell, the lock screen, Settings, the file manager's extension,
#     GTK's Fenestra stylesheet, KWin's scripted effects, the start-up check, the KWin plugin's build
#   root part (one password, tools/install-root.sh): session, battery tuning, KWin plugin
# env: JOBS (2), ENGINE (podman), IMAGE (fenestra-kwinlab)
set -u
REPO=$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)
ENGINE=${ENGINE:-podman}; IMAGE=${IMAGE:-fenestra-kwinlab}
DATA=${XDG_DATA_HOME:-$HOME/.local/share}; CONF=${XDG_CONFIG_HOME:-$HOME/.config}
TIDY=; ROOT=1
for a in "$@"; do case $a in --tidy) TIDY=--tidy ;; --no-root) ROOT= ;; esac; done
ok=(); bad=()
step() { local name=$1; shift; echo "== $name"; if "$@"; then ok+=("$name"); else bad+=("$name"); fi; }

settings() {
    local d=$DATA/fenestra-settings
    [ -d "$d" ] || return 0   # this PC takes Settings from its package
    rm -rf "$d/fenestra_settings.new" && cp -r "$REPO/apps/fenestra-settings/fenestra_settings" "$d/fenestra_settings.new" \
        && find "$d/fenestra_settings.new" -name __pycache__ -type d -prune -exec rm -rf {} + \
        && rm -rf "$d/fenestra_settings" && mv "$d/fenestra_settings.new" "$d/fenestra_settings" \
        && cp "$REPO/apps/fenestra-settings/data/style.css" "$d/data/style.css"
}
store() {
    local d=$DATA/fenestra-store
    [ -d "$d" ] || return 0   # this PC takes the Store from its package
    rm -rf "$d/fenestra_store.new" && cp -r "$REPO/apps/fenestra-store/fenestra_store" "$d/fenestra_store.new" \
        && find "$d/fenestra_store.new" -name __pycache__ -type d -prune -exec rm -rf {} + \
        && rm -rf "$d/fenestra_store" && mv "$d/fenestra_store.new" "$d/fenestra_store"
}
files() {
    local d=$DATA/nautilus-python/extensions
    mkdir -p "$d" && cp "$REPO"/desktop/nautilus/python/*.py "$d/"
}
gtkcss() {
    # Fenestra's GTK 4 stylesheet; the user's own theme import (their second line) stays.
    local f=$CONF/gtk-4.0/gtk.css src=$REPO/desktop/skel/.config/gtk-4.0/gtk.css keep=
    [ -f "$src" ] || return 0
    mkdir -p "$(dirname "$f")"
    [ -f "$f" ] && keep=$(sed -n '2{/^@import url(".*\/themes\//p}' "$f")
    if [ -n "$keep" ]; then { sed -n 1p "$src"; echo "$keep"; sed -n '3,$p' "$src"; } > "$f.new"; else cp "$src" "$f.new"; fi
    mv "$f.new" "$f"
}
bootcheck() {
    # Without root: the units in the user's own systemd directory, pulled in by the session target.
    local n
    mkdir -p "$CONF/systemd/user/fenestra-session.target.d"
    for n in fenestra-boot-check fenestra-sleep-log; do
        install -Dm755 "$REPO/session/libexec/$n" "$HOME/.local/libexec/fenestra/$n" || return 1
        sed "s|^ExecStart=.*|ExecStart=$HOME/.local/libexec/fenestra/$n|" "$REPO/session/systemd/$n.service" > "$CONF/systemd/user/$n.service"
    done
    printf '[Unit]\nWants=fenestra-boot-check.service fenestra-sleep-log.service\n' > "$CONF/systemd/user/fenestra-session.target.d/boot-check.conf"
    systemctl --user daemon-reload
    systemctl --user restart fenestra-sleep-log.service
}
kwinplugin() {
    # Built for the KWin of the lab image (the same Fedora as this PC); root installs it.
    local b=$HOME/.cache/fenestra-corners-build out=$DATA/fenestra/kwin-plugins
    mkdir -p "$b" "$out"
    $ENGINE run --rm --security-opt label=disable -v "$REPO:/src:ro" -v "$b:/build" "$IMAGE" bash -c '
        rpm -q libepoxy-devel libdrm-devel >/dev/null 2>&1 || dnf install -y -q libepoxy-devel libdrm-devel >/dev/null 2>&1
        cmake -S /src/kwin/plugins/fenestra-corners -B /build -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo >/dev/null && ninja -C /build >/dev/null' \
        && strip -o "$out/fenestra-corners.so" "$b/fenestra-corners.so"
}
shell() {
    JOBS=${JOBS:-2} ENGINE=$ENGINE IMAGE=$IMAGE bash "$REPO/tools/install-shell-user.sh" && systemctl --user restart fenestra-shell
}

step "shell" shell
step "lock screen" bash "$REPO/tools/install-lockscreen-user.sh"
step "settings" settings
step "store" store
step "file manager" files
step "gtk stylesheet" gtkcss
step "start-up check and sleep log" bootcheck
step "kwin plugin (build)" kwinplugin
if [ -n "$ROOT" ]; then
    step "root part" bash "$REPO/tools/install-root.sh" $TIDY
    # The running KWin takes the new plugin and effects without a restart.
    for e in fenestra-corners fenestra-window-motion; do
        gdbus call --session -d org.kde.KWin -o /Effects -m org.kde.kwin.Effects.unloadEffect "$e" >/dev/null 2>&1
        gdbus call --session -d org.kde.KWin -o /Effects -m org.kde.kwin.Effects.loadEffect "$e" >/dev/null 2>&1
    done
fi

# ---- what runs is what was built
verify() {
    local pid exe r=0
    sleep 3
    pid=$(systemctl --user show fenestra-shell -p MainPID --value)
    exe=$(readlink "/proc/$pid/exe" 2>/dev/null)
    # A binary replaced after the process started reads "... (deleted)"; one older than the build
    # (to the second) was never replaced.
    local bin=$HOME/.local/opt/fenestra-shell/bin/fenestra-shell
    if [ "$exe" != "$bin" ] || [ "$(stat -c %Y "$bin" 2>/dev/null || echo 0)" -lt "$(stat -c %Y "$HOME/.cache/fenestra-shell-user-build/fenestra-shell" 2>/dev/null || echo 0)" ]; then
        echo "the running shell ($exe) is not this build"; r=1
    fi
    grep -q "$(git -C "$REPO" rev-parse --short HEAD)" "$CONF/systemd/user/fenestra-shell.service.d/50-user-build.conf" || { echo "the shell's unit names another commit"; r=1; }
    diff -rq -x __pycache__ "$REPO/desktop/nautilus/python" "$DATA/nautilus-python/extensions" >/dev/null || { echo "file manager extension differs"; r=1; }
    [ ! -d "$DATA/fenestra-settings" ] || diff -rq -x __pycache__ "$REPO/apps/fenestra-settings/fenestra_settings" "$DATA/fenestra-settings/fenestra_settings" >/dev/null || { echo "Settings differs"; r=1; }
    diff -rq "$REPO/shells/org.fenestra.desktop/contents" "$DATA/plasma/shells/org.fenestra.desktop/contents" >/dev/null 2>&1 || { echo "lock screen differs"; r=1; }
    if [ -n "$ROOT" ]; then
        cmp -s "$REPO/session/libexec/fenestra-session-inner" /usr/libexec/fenestra/fenestra-session-inner || { echo "session script differs"; r=1; }
        cmp -s "$DATA/fenestra/kwin-plugins/fenestra-corners.so" /usr/lib64/qt6/plugins/kwin/effects/plugins/fenestra-corners.so || { echo "KWin plugin differs"; r=1; }
    fi
    return $r
}
step "verification" verify
mkdir -p "${XDG_STATE_HOME:-$HOME/.local/state}/fenestra"
echo "$(date -Is) $(git -C "$REPO" rev-parse --short HEAD) ok: ${ok[*]:-none}${bad[*]:+ FAILED: ${bad[*]}}" >> "${XDG_STATE_HOME:-$HOME/.local/state}/fenestra/install.log"
echo
echo "ok: ${ok[*]:-none}"
[ ${#bad[@]} -eq 0 ] || { echo "FAILED: ${bad[*]}"; exit 1; }
