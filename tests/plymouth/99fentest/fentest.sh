#!/bin/sh
# Test only: drive plymouthd through Fenestra's screens, announce each on the serial port.
say() { echo "FENSHOT $1" > /dev/ttyS0; sleep ${2:-8}; }
P=/usr/bin/plymouth
sleep 6
say boot 10
$P change-mode --system-upgrade; $P system-update --progress=0; say upgrade0 8
$P system-update --progress=42; say upgrade42 8
$P change-mode --updates; $P system-update --progress=87; say updates87 8
$P quit; sleep 1
/usr/sbin/plymouthd --mode=reboot --attach-to-session; $P show-splash; sleep 4; say reboot 8
$P quit; sleep 1
/usr/sbin/plymouthd --mode=shutdown --attach-to-session; $P show-splash; sleep 4; say shutdown 8
$P quit
echo FENSHOT done > /dev/ttyS0
echo o > /proc/sysrq-trigger
