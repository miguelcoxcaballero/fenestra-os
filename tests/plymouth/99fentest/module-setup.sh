#!/bin/bash
# Test only (tests/plymouth): drive plymouthd through Fenestra's screens.
check() { return 0; }
depends() { echo plymouth systemd; }
install() {
    inst_simple "$moddir/fentest.sh" /usr/bin/fentest.sh
    chmod +x "$initdir/usr/bin/fentest.sh"
    cat > "$initdir/$systemdsystemunitdir/fentest.service" <<'U'
[Unit]
DefaultDependencies=no
After=plymouth-start.service systemd-udev-trigger.service
Wants=plymouth-start.service
[Service]
Type=oneshot
ExecStart=/usr/bin/fentest.sh
StandardOutput=tty
TTYPath=/dev/ttyS0
U
    mkdir -p "$initdir/$systemdsystemunitdir/sysinit.target.wants"
    ln -sf ../fentest.service "$initdir/$systemdsystemunitdir/sysinit.target.wants/fentest.service"
    inst_multiple sleep
}
