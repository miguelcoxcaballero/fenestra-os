#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Ask the FileChooser portal for a dialog, like a browser's "Save as" does.
import sys
from gi.repository import Gio, GLib
bus = Gio.bus_get_sync(Gio.BusType.SESSION)
method = sys.argv[1] if len(sys.argv) > 1 else 'SaveFile'
opts = {'handle_token': GLib.Variant('s', 't1')}
if method == 'SaveFile':
    opts['current_name'] = GLib.Variant('s', 'informe-trimestral.pdf')
    opts['filters'] = GLib.Variant('a(sa(us))', [('Documento PDF', [(0, '*.pdf')]), ('Todos los archivos', [(0, '*')])])
else:
    opts['filters'] = GLib.Variant('a(sa(us))', [('Imágenes', [(1, 'image/png'), (1, 'image/jpeg')]), ('Todos los archivos', [(0, '*')])])
title = 'Guardar como' if method == 'SaveFile' else 'Abrir'
r = bus.call_sync('org.freedesktop.portal.Desktop', '/org/freedesktop/portal/desktop', 'org.freedesktop.portal.FileChooser',
                  method, GLib.Variant('(ssa{sv})', ('', title, opts)), None, 0, 60000, None)
print('request', r.unpack(), flush=True)
loop = GLib.MainLoop()
GLib.timeout_add_seconds(int(sys.argv[2]) if len(sys.argv) > 2 else 8, loop.quit)
loop.run()
