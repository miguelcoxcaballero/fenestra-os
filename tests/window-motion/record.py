#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""record.py OUT CLIENT... (inside session.sh): for each client window, frames of open, minimize,
restore, maximize, unmaximize and close, captured with KWin's ScreenShot2 (CaptureArea, logical
pixels) as fast as KWin answers. OUT/<client>-<action>/fNNN.png + times.json (ms from the
trigger: the client's start for open, the KWin script call for the others)."""
import json, os, subprocess, sys, time
from gi.repository import Gio, GLib
from PIL import Image

out = sys.argv[1]
bus = Gio.bus_get_sync(Gio.BusType.SESSION)
W, H = 1920, 1200  # logical (2880x1800 at 1.5)

def shot(area):
    x, y, w, h = area
    r, wfd = os.pipe(); fdl = Gio.UnixFDList.new(); idx = fdl.append(wfd); os.close(wfd)
    opts = {'native-resolution': GLib.Variant('b', False), 'include-cursor': GLib.Variant('b', False)}
    res, _ = bus.call_with_unix_fd_list_sync('org.kde.KWin', '/org/kde/KWin/ScreenShot2', 'org.kde.KWin.ScreenShot2', 'CaptureArea',
                                             GLib.Variant('(iiuua{sv}h)', (x, y, w, h, opts, idx)), None, 0, 5000, fdl, None)
    for fd in fdl.steal_fds(): os.close(fd)
    data = bytearray()
    while True:
        c = os.read(r, 1 << 22)
        if not c: break
        data += c
    os.close(r)
    return bytes(data), res.unpack()[0]

SEQ = [0]
def script(name, code):
    SEQ[0] += 1; name = f'{name}{SEQ[0]}'
    p = f'/tmp/{name}.js'; open(p, 'w').write(code)
    try:
        bus.call_sync('org.kde.KWin', '/Scripting', 'org.kde.kwin.Scripting', 'unloadScript', GLib.Variant('(s)', (name,)), None, 0, 2000, None)
    except Exception:
        pass
    sid = bus.call_sync('org.kde.KWin', '/Scripting', 'org.kde.kwin.Scripting', 'loadScript', GLib.Variant('(ss)', (p, name)), None, 0, 2000, None).unpack()[0]
    t = time.monotonic()
    bus.call_sync('org.kde.KWin', f'/Scripting/Script{sid}', 'org.kde.kwin.Script', 'run', None, None, 0, 2000, None)
    return (t + time.monotonic()) / 2

def record(name, area, ms, trigger):
    frames = []
    frames.append((shot(area), -1.0))
    t0 = trigger()
    while (time.monotonic() - t0) * 1000 < ms:
        a = time.monotonic(); s = shot(area)
        frames.append((s, ((a + time.monotonic()) / 2 - t0) * 1000))
    d = f'{out}/{name}'; os.makedirs(d, exist_ok=True)
    for i, ((data, m), t) in enumerate(frames):
        raw = 'RGBA' if m.get('format') in (16, 17, 18) else 'BGRA'
        Image.frombuffer('RGBA', (m['width'], m['height']), data, 'raw', raw, m['stride'], 1).convert('RGB').save(f'{d}/f{i:03d}.png')
    ts = [round(t, 1) for _, t in frames]; ts[0] = round(ts[1] - 50, 1)
    json.dump({'times_ms': ts, 'area': area}, open(f'{d}/times.json', 'w'))
    gaps = [b - a for a, b in zip(ts[1:], ts[2:])]
    print(name, len(frames), 'frames, median interval', sorted(gaps)[len(gaps) // 2] if gaps else 0, flush=True)

FIND = 'const w = workspace.windowList().find(c => c.caption === "%s");\n'
for client in sys.argv[2:]:
    title = {'qt': 'Motion Qt', 'gtk3-x11': 'Motion X11', 'x11-csd': 'Motion CSD'}[client]
    cmd = {'qt': ['/usr/lib64/qt6/bin/qml', '/src/tests/window-motion/client.qml'],
           'gtk3-x11': ['python3', '/src/tests/window-motion/client_gtk.py'],
           'x11-csd': ['python3', '/src/tests/window-motion/client_gtk.py', 'csd']}[client]
    env = dict(os.environ, QT_QPA_PLATFORM='wayland', GDK_BACKEND='x11' if client in ('gtk3-x11', 'x11-csd') else 'wayland')
    # Around the centred window, down to the bottom edge (minimize goes there); maximize: all.
    area = (560, 300, 800, 900)
    if os.environ.get('SHELL_BUILD'):
        area = (0, 0, W, H)  # areas come back black while the shell runs; the whole screen does not
    proc = None
    def start():
        global proc
        t = time.monotonic(); proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=open(f'{out}/{client}.log', 'w')); return t
    record(f'{client}-open', area, 1500, start)
    time.sleep(0.8)
    # Centre it (KWin may place it elsewhere) and settle.
    script('centre', FIND % title + 'if (w) { const a = workspace.clientArea(KWin.MaximizeArea, w); w.frameGeometry = {x: Math.round(a.x + (a.width - w.frameGeometry.width) / 2), y: Math.round(a.y + (a.height - w.frameGeometry.height) / 2), width: w.frameGeometry.width, height: w.frameGeometry.height}; workspace.activeWindow = w; }')
    time.sleep(0.8)
    record(f'{client}-minimize', area, 600, lambda: script('min', FIND % title + 'if (w) w.minimized = true;'))
    time.sleep(0.5)
    record(f'{client}-restore', area, 600, lambda: script('res', FIND % title + 'if (w) { w.minimized = false; workspace.activeWindow = w; }'))
    time.sleep(0.5)
    record(f'{client}-maximize', (0, 0, W, H), 700, lambda: script('max', FIND % title + 'if (w) w.setMaximize(true, true);'))
    time.sleep(0.5)
    record(f'{client}-unmaximize', (0, 0, W, H), 700, lambda: script('unmax', FIND % title + 'if (w) w.setMaximize(false, false);'))
    time.sleep(0.5)
    script('activate', FIND % title + 'if (w) workspace.activeWindow = w;')
    time.sleep(0.5)
    record(f'{client}-snap', (0, 0, W, H), 700, lambda: script('snap', 'workspace.slotWindowQuickTileLeft();'))
    time.sleep(0.5)
    record(f'{client}-unsnap', (0, 0, W, H), 700, lambda: script('unsnap', FIND % title + 'if (w) w.tile = null;'))
    time.sleep(0.5)
    record(f'{client}-close', area, 600, lambda: script('close', FIND % title + 'if (w) w.closeWindow();'))
    time.sleep(0.5)
    if proc and proc.poll() is None: proc.kill()

# The preview shown while a window is dragged to a screen edge (the left half of the work area).
record('outline', (0, 0, W, H), 400, lambda: script('outline', 'workspace.showOutline(0, 0, 960, 1152);'))
