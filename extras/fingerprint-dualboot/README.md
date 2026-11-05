# Fingerprint dual boot (match-on-chip sensors)

On laptops whose fingerprint reader stores templates on the sensor itself (e.g. Egis
ETU905A80, many Synaptics/Goodix MoC readers), fprintd erases the whole sensor before the
first Linux enrolment ("clear storage before first enrollment"). On a dual-boot machine that
deletes the fingerprints Windows Hello stored on the same sensor.

`keep-storage.c` is an `LD_PRELOAD` shim for fprintd that turns that wipe into a no-op (deleting
a single print still works). Build and install (root):

```bash
gcc -shared -fPIC -O2 -o libfprintd-keep-storage.so keep-storage.c $(pkg-config --cflags --libs gio-2.0)
sudo ./install.sh
```

Then enrol in Windows first, then in Linux. If Windows itself wipes unknown templates at boot,
this cannot be fixed from Linux.
