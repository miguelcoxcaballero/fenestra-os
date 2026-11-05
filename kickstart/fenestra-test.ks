# Fenestra unattended install for VM testing. WIPES THE WHOLE DISK.
zerombr
clearpart --all --initlabel
autopart --type=btrfs --nohome
poweroff
