#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# sudo tools/install-session-root.sh: the session files the Fenestra RPM installs, for a system
# running Fenestra from the repo: the session scripts (one sign-in screen: the session tells GDM
# its display is up, so GDM never opens its own over Fenestra's lock screen) and the shell's unit.
set -eu
[ "$(id -u)" = 0 ] || exec sudo bash "$(readlink -f "$0")" "$@"
R=$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)
for f in fenestra-session fenestra-session-inner; do
    [ -f /usr/libexec/fenestra/$f ] && [ ! -f /usr/libexec/fenestra/$f.fenestra-orig ] && cp -p /usr/libexec/fenestra/$f /usr/libexec/fenestra/$f.fenestra-orig
    install -Dm755 "$R/session/libexec/$f" /usr/libexec/fenestra/$f
done
install -Dm644 "$R/session/systemd/fenestra-shell.service" /usr/lib/systemd/user/fenestra-shell.service
restorecon -F /usr/libexec/fenestra/fenestra-session /usr/libexec/fenestra/fenestra-session-inner 2>/dev/null || true
echo "Done. It applies from the next sign-in."
