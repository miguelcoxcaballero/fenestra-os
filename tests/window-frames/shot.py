#!/usr/bin/env python3
"""shot.py OUT.png [x y w h] : KWin ScreenShot2 capture of the whole workspace (or an area, logical
coordinates) at native resolution, through the D-Bus pipe protocol.  Needs a .desktop entry for
this interpreter with X-KDE-DBUS-Restricted-Interfaces=org.kde.KWin.ScreenShot2 (session.sh)."""
import os, sys
import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib
from PIL import Image

out = sys.argv[1]
bus = Gio.bus_get_sync(Gio.BusType.SESSION)
r, w = os.pipe()
fdl = Gio.UnixFDList.new()
idx = fdl.append(w)
os.close(w)
opts = {'native-resolution': GLib.Variant('b', True), 'include-cursor': GLib.Variant('b', False)}
if len(sys.argv) > 2:
    x, y, ww, hh = map(int, sys.argv[2:6])
    method, params = 'CaptureArea', GLib.Variant('(iiuua{sv}h)', (x, y, ww, hh, opts, idx))
else:
    method, params = 'CaptureWorkspace', GLib.Variant('(a{sv}h)', (opts, idx))
res, _ = bus.call_with_unix_fd_list_sync('org.kde.KWin', '/org/kde/KWin/ScreenShot2', 'org.kde.KWin.ScreenShot2',
                                         method, params, None, Gio.DBusCallFlags.NONE, 20000, fdl, None)
meta = res.unpack()[0]
for fd in fdl.steal_fds():  # our copies of the write end, or the read never ends
    os.close(fd)
data = b''
while True:
    chunk = os.read(r, 1 << 20)
    if not chunk:
        break
    data += chunk
W, H, stride = meta['width'], meta['height'], meta['stride']
# QImage::Format: 4/5/6 (A)RGB32 = BGRA bytes in memory; 16/17/18 RGBX/RGBA8888 = RGBA bytes.
raw = 'RGBA' if meta.get('format') in (16, 17, 18) else 'BGRA'
im = Image.frombuffer('RGBA', (W, H), data, 'raw', raw, stride, 1).convert('RGB')
im.save(out)
print(out, W, H, meta.get('scale'), meta.get('format'))
