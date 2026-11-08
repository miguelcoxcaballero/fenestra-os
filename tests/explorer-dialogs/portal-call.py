#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Ask the FileChooser portal for a dialog, like a browser's "Save as" does.
#   portal-call.py [SaveFile|OpenFile] [SECONDS] [FOLDER] [NAME]
# FOLDER (current_folder) and NAME (current_name) are optional; the defaults are the bench's
# Spanish demo (informe-trimestral.pdf). The portal's reply (response code, uris) is printed.
import sys
from gi.repository import Gio, GLib
bus = Gio.bus_get_sync(Gio.BusType.SESSION)
method = sys.argv[1] if len(sys.argv) > 1 else 'SaveFile'
folder = sys.argv[3] if len(sys.argv) > 3 else ''
name = sys.argv[4] if len(sys.argv) > 4 else 'informe-trimestral.pdf'
opts = {'handle_token': GLib.Variant('s', 't1')}
if folder:
    opts['current_folder'] = GLib.Variant('ay', folder.encode() + b'\0')
if method == 'SaveFile':
    opts['current_name'] = GLib.Variant('s', name)
    if name.endswith('.txt'):
        opts['filters'] = GLib.Variant('a(sa(us))', [('Text documents (*.txt)', [(0, '*.txt')]), ('All files (*.*)', [(0, '*')])])
    else:
        opts['filters'] = GLib.Variant('a(sa(us))', [('Documento PDF', [(0, '*.pdf')]), ('Todos los archivos', [(0, '*')])])
else:
    opts['filters'] = GLib.Variant('a(sa(us))', [('Imágenes', [(1, 'image/png'), (1, 'image/jpeg')]), ('Todos los archivos', [(0, '*')])])
title = 'Guardar como' if method == 'SaveFile' else 'Abrir'
if len(sys.argv) > 4 and name.endswith('.txt'):
    title = 'Save as' if method == 'SaveFile' else 'Open'
loop = GLib.MainLoop()
r = bus.call_sync('org.freedesktop.portal.Desktop', '/org/freedesktop/portal/desktop', 'org.freedesktop.portal.FileChooser',
                  method, GLib.Variant('(ssa{sv})', ('', title, opts)), None, 0, 60000, None)
handle = r.unpack()[0]
print('request', handle, flush=True)
bus.signal_subscribe(None, 'org.freedesktop.portal.Request', 'Response', handle, None, 0,
                     lambda *a: (print('response', a[5].unpack(), flush=True), loop.quit()))
GLib.timeout_add_seconds(int(sys.argv[2]) if len(sys.argv) > 2 else 8, loop.quit)
loop.run()
