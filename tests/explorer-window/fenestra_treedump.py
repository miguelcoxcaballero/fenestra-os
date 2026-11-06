# SPDX-License-Identifier: GPL-3.0-or-later
"""Test only (copied into the bench container by run.sh, never installed): when the file
/tmp/treedump/NAME appears, write every Nautilus window's widget tree (type, CSS name,
classes, label text, bounds in window coordinates) to /out/NAME.tree.txt."""
import os
import gi
gi.require_version('Nautilus', '4.1')
gi.require_version('Gtk', '4.0')
from gi.repository import GLib, GObject, Gtk, Nautilus

REQ = '/tmp/treedump'


def dump(widget, root, depth, out):
    ok, b = widget.compute_bounds(root)
    geo = f'{b.get_x():.0f},{b.get_y():.0f} {b.get_width():.0f}x{b.get_height():.0f}' if ok else '-'
    extra = ''
    if isinstance(widget, Gtk.Label):
        extra = repr(widget.get_label())
    elif isinstance(widget, Gtk.Image):
        extra = f'icon={widget.get_icon_name()} px={widget.get_pixel_size()}'
    vis = '' if widget.get_visible() else ' HIDDEN'
    out.append(f'{"  " * depth}{GObject.type_name(widget.__gtype__)} <{widget.get_css_name()}> '
               f'.{".".join(widget.get_css_classes())} #{widget.get_name()} [{geo}]{vis} {extra}')
    if not widget.get_visible():
        return
    c = widget.get_first_child()
    while c:
        dump(c, root, depth + 1, out)
        c = c.get_next_sibling()


class FenestraTreeDump(GObject.GObject, Nautilus.MenuProvider):
    def __init__(self):
        super().__init__()
        os.makedirs(REQ, exist_ok=True)
        GLib.timeout_add(300, self._poll)

    def _poll(self):
        try:
            names = os.listdir(REQ)
        except OSError:
            return True
        for n in names:
            os.unlink(os.path.join(REQ, n))
            out = []
            for w in Gtk.Window.list_toplevels():
                if w.get_mapped():
                    dump(w, w, 0, out)
            with open(f'/out/{n}.tree.txt', 'w') as f:
                f.write('\n'.join(out) + '\n')
        return True
