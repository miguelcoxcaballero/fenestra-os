"""Small building blocks: icons, labels, toolbar buttons, menus, dialogs."""
from __future__ import annotations

from gi.repository import Gdk, GLib, Gtk, Pango

from ..i18n import _


def icon(name, size=16, css=None):
    img = Gtk.Image.new_from_icon_name(name)
    img.set_pixel_size(size)
    if css:
        img.add_css_class(css)
    return img


def label(text, css=None, xalign=0.0, ellipsize=False, wrap=False, selectable=False):
    lb = Gtk.Label(label=text, xalign=xalign)
    if css:
        for c in css.split():
            lb.add_css_class(c)
    if ellipsize:
        lb.set_ellipsize(Pango.EllipsizeMode.END)
    if wrap:
        lb.set_wrap(True)
        lb.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
    if selectable:
        lb.set_selectable(True)
    return lb


class ToolButton(Gtk.Button):
    """Command-bar button: 16px icon + 12px text, greys out when insensitive."""

    def __init__(self, icon_name, text, cb=None, tooltip=None):
        super().__init__()
        self.add_css_class("tool-button")
        box = Gtk.Box(spacing=8)
        box.append(icon(icon_name, 20))
        if text:
            # ellipsizing labels keep the command bar's minimum width small, so a narrow
            # window never gets a layout wider than its surface
            self.lbl = label(text, ellipsize=True)
            self.lbl.set_width_chars(1)
            box.append(self.lbl)
        else:
            self.add_css_class("icon-only")
        self.set_child(box)
        if tooltip or not text:
            self.set_tooltip_text(tooltip or text)
        if cb:
            self.connect("clicked", lambda *_: cb())

    def set_text(self, text):
        self.lbl.set_text(text)


def separator():
    s = Gtk.Box()
    s.add_css_class("tool-sep")
    s.set_valign(Gtk.Align.CENTER)
    return s


class Menu(Gtk.Popover):
    """Fluent context/flyout menu built from plain buttons (avoids GMenu styling)."""

    def __init__(self, parent):
        super().__init__()
        self.add_css_class("fluent-menu")
        self.set_has_arrow(False)
        self.set_parent(parent)
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(self.box)
        self.connect("closed", lambda *_: GLib.idle_add(self._cleanup))

    def _cleanup(self):
        if self.get_parent() is not None:
            self.unparent()
        return False

    def add(self, text, cb=None, icon_name=None, sensitive=True, check=None, shortcut=None):
        b = Gtk.Button()
        b.add_css_class("menu-item")
        box = Gtk.Box(spacing=12)
        if check is not None:
            im = icon("tm-check-symbolic", 20)
            im.set_opacity(1.0 if check else 0.0)
            box.append(im)
        elif icon_name is not None:
            box.append(icon(icon_name, 20))
        else:
            sp = Gtk.Box()
            sp.set_size_request(16, 16)
            box.append(sp)
        box.append(label(text))
        if shortcut:
            sh = label(shortcut, "menu-shortcut", xalign=1.0)
            sh.set_hexpand(True)
            box.append(sh)
        b.set_child(box)
        b.set_sensitive(sensitive)

        def clicked(*_):
            self.popdown()
            if cb:
                GLib.idle_add(lambda: (cb(), False)[1])
        b.connect("clicked", clicked)
        self.box.append(b)
        return b

    def add_separator(self):
        s = Gtk.Box()
        s.add_css_class("menu-sep")
        self.box.append(s)

    def popup_at(self, x, y):
        r = Gdk.Rectangle()
        r.x, r.y, r.width, r.height = int(x), int(y), 1, 1
        self.set_pointing_to(r)
        self.set_position(Gtk.PositionType.BOTTOM)
        self.set_halign(Gtk.Align.START)
        self.popup()


class Dialog(Gtk.Box):
    """Content dialog shown over the window (smoke layer), Windows 11 style."""

    def __init__(self, window, title, body=None, primary=None, secondary=_("Cancel"), on_primary=None,
                 on_secondary=None, width=440):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        self.add_css_class("dialog-card")
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        self.set_size_request(width, -1)
        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        top.add_css_class("dialog-top")
        top.append(label(title, "dialog-title", wrap=True))
        if isinstance(body, str):
            top.append(label(body, "dialog-body", wrap=True))
        elif body is not None:
            top.append(body)
        self.content = top
        self.append(top)
        foot = Gtk.Box(spacing=8, homogeneous=True)
        foot.add_css_class("dialog-foot")
        self.primary_btn = None
        if primary:
            b = Gtk.Button(label=primary)
            b.add_css_class("accent-button")
            b.connect("clicked", lambda *_: self._done(on_primary))
            foot.append(b)
            self.primary_btn = b
        if secondary:
            b = Gtk.Button(label=secondary)
            b.add_css_class("std-button")
            b.connect("clicked", lambda *_: self._done(on_secondary))
            foot.append(b)
        self.append(foot)
        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self._key)
        self.add_controller(key)

    def _key(self, _c, keyval, *_):
        if Gdk.keyval_name(keyval) == "Escape":
            self.close()
            return True
        return False

    def _done(self, cb):
        keep = cb() if cb else None
        if keep is not True:
            self.close()

    def show(self):
        self.window.show_dialog(self)
        if self.primary_btn:
            self.primary_btn.grab_focus()

    def close(self):
        self.window.hide_dialog(self)
