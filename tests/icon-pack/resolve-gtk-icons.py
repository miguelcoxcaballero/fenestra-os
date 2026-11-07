#!/usr/bin/python3
"""Prints, for every file in DIR, its content type, GIcon and the icon file GTK picks at SIZE px
(the lookup Nautilus does). Run inside a Wayland session, e.g. nautilus-shot.sh resolve DIR SIZE."""
import sys, os, gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gio, Gdk
Gtk.init()
th = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
print('theme', th.get_theme_name(), Gtk.Settings.get_default().props.gtk_icon_theme_name)
d = sys.argv[1]
for n in sorted(os.listdir(d)):
    p = os.path.join(d, n)
    info = Gio.File.new_for_path(p).query_info('standard::icon,standard::content-type', 0, None)
    ic = info.get_icon()
    pt = th.lookup_by_gicon(ic, int(sys.argv[2]) if len(sys.argv) > 2 else 48, 1, Gtk.TextDirection.LTR, 0)
    f = pt.get_file()
    print(n, info.get_content_type(), ic.to_string(), f.get_path() if f else pt.get_icon_name())
