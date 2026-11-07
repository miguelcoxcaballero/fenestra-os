#!/usr/bin/env python3
"""clients.py KIND TITLE [--hover=minimize|maximize|close] [--pressed=...] : test windows for the
frame bench.  KIND: gtk4-adw (libadwaita, like Nautilus), gtk4 (Gtk.HeaderBar, like the Fenestra
apps), gtk3-csd (GtkHeaderBar), gtk3-ssd (plain GtkWindow: KWin server-side frame; with
GDK_BACKEND=x11 an Xwayland window).  --hover/--pressed put that caption button in the state."""
import sys
kind, title = sys.argv[1], sys.argv[2]
opts = dict(a[2:].split('=', 1) for a in sys.argv[3:] if a.startswith('--') and '=' in a)
import gi
if kind.startswith('gtk4'):
    gi.require_version('Gtk', '4.0')
    if kind == 'gtk4-adw':
        gi.require_version('Adw', '1')
        from gi.repository import Adw
else:
    gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

def body():
    l = Gtk.Label(label='%s\nThe quick brown fox jumps over the lazy dog' % title)
    l.set_vexpand(True)
    return l

def walk(w):
    yield w
    if kind.startswith('gtk4'):
        c = w.get_first_child()
        while c:
            yield from walk(c)
            c = c.get_next_sibling()
    elif isinstance(w, Gtk.Container):
        for c in w.get_children():
            yield from walk(c)
        if isinstance(w, Gtk.HeaderBar):  # title buttons are internal children
            w.forall(lambda c: None)

def dump(win):
    """--dump: the header bar's widget path (CSS names, classes, bounds) to stderr."""
    def rec(w, depth):
        ok, r = w.compute_bounds(win)
        print('  ' * depth + w.get_css_name() + ''.join('.' + c for c in w.get_css_classes()),
              '%.0f,%.0f %.0fx%.0f' % (r.origin.x, r.origin.y, r.size.width, r.size.height) if ok else '', file=sys.stderr)
        if depth < 16:
            c = w.get_first_child()
            while c:
                rec(c, depth + 1); c = c.get_next_sibling()
    rec(win, 0)
    return False


def apply_state(win):
    for state, flag in (('hover', Gtk.StateFlags.PRELIGHT), ('pressed', Gtk.StateFlags.PRELIGHT | Gtk.StateFlags.ACTIVE)):
        which = opts.get(state)
        if not which:
            continue
        for w in walk(win):
            if isinstance(w, Gtk.Button) and w.get_style_context().has_class(which) and \
               (w.get_style_context().has_class('titlebutton') or (w.get_parent() and w.get_parent().get_css_name() == 'windowcontrols')):
                w.set_state_flags(flag, False)
    return False

if kind.startswith('gtk4'):
    def activate(app):
        if kind == 'gtk4-adw':
            win = Adw.ApplicationWindow(application=app, title=title)
            tv = Adw.ToolbarView(); tv.add_top_bar(Adw.HeaderBar()); tv.set_content(body())
            win.set_content(tv)
        else:
            win = Gtk.ApplicationWindow(application=app, title=title)
            win.set_titlebar(Gtk.HeaderBar()); win.set_child(body())
        win.set_default_size(560, 300)
        win.present()
        GLib.timeout_add(800, apply_state, win)
        if 'dump' in sys.argv[3:] or '--dump' in sys.argv[3:]:
            GLib.timeout_add(1500, dump, win)
    App = Adw.Application if kind == 'gtk4-adw' else Gtk.Application
    app = App(application_id='org.fenestra.FrameBench.' + kind.replace('-', '_'))
    app.connect('activate', activate)
    app.run([])
else:
    win = Gtk.Window(title=title)
    if kind == 'gtk3-csd':
        hb = Gtk.HeaderBar(); hb.set_show_close_button(True); hb.set_title(title); win.set_titlebar(hb)
    win.add(body()); win.set_default_size(560, 300)
    win.connect('destroy', Gtk.main_quit)
    win.show_all()
    if kind == 'gtk3-csd':
        def gtk3state():
            for state, flag in (('hover', Gtk.StateFlags.PRELIGHT), ('pressed', Gtk.StateFlags.PRELIGHT | Gtk.StateFlags.ACTIVE)):
                which = opts.get(state)
                if not which: continue
                found = []
                def visit(w):
                    if isinstance(w, Gtk.Button) and w.get_style_context().has_class(which): found.append(w)
                    if isinstance(w, Gtk.Container): w.forall(visit)
                hb.forall(visit)
                for b in found: b.set_state_flags(flag, False)
            return False
        GLib.timeout_add(800, gtk3state)
    if '--dump' in sys.argv[3:]:
        def dump3():
            def rec(w, depth):
                a = w.get_allocation(); xy = w.translate_coordinates(win, 0, 0) or (0, 0)
                ctx = w.get_style_context()
                print('  ' * depth + ctx.get_path().to_string().split(' ')[-1], xy, a.width, a.height, file=sys.stderr)
                if isinstance(w, Gtk.Container):
                    w.forall(lambda c: rec(c, depth + 1))
            rec(win.get_titlebar() or win, 0)
            return False
        GLib.timeout_add(1500, dump3)
    Gtk.main()
