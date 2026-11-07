#!/usr/bin/env python3
# GTK 3 window under test (GDK_BACKEND=x11: an Xwayland window with KWin's frame).
import colorsys
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
w = Gtk.Window(title='Motion X11'); w.set_default_size(640, 420)
g = Gtk.Grid(); g.set_row_spacing(8); g.set_column_spacing(8); g.set_margin_start(24); g.set_margin_top(24)
css = Gtk.CssProvider(); rules = []
for i in range(40):
    b = Gtk.Label(label=str(i)); b.set_size_request(66, 62); b.get_style_context().add_class(f'c{i}')
    r, g_, b_ = (round(c * 255) for c in colorsys.hls_to_rgb(((i * 49) % 360) / 360, 0.5, 0.6))
    rules.append(f'.c{i} {{ background: rgb({r},{g_},{b_}); color: white; }}')
    g.attach(b, i % 8, i // 8, 1, 1)
css.load_from_data('\n'.join(rules).encode())
Gtk.StyleContext.add_provider_for_screen(w.get_screen(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
w.add(g); w.connect('destroy', Gtk.main_quit); w.show_all(); Gtk.main()
