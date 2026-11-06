"""Small Fluent-style building blocks: icons, labels, flyout menus, content dialogs."""
from __future__ import annotations

from gi.repository import Gdk, GLib, Gtk

from .i18n import _


def icon(name, size=16, css=None):
    img = Gtk.Image.new_from_icon_name(name)
    img.set_pixel_size(size)
    if css:
        for c in css.split():
            img.add_css_class(c)
    return img


def label(text, css=None, xalign=0.0, ellipsize=False, wrap=False, selectable=False):
    lb = Gtk.Label(label=text)
    lb.set_xalign(xalign)
    if css:
        for c in css.split():
            lb.add_css_class(c)
    if ellipsize:
        from gi.repository import Pango
        lb.set_ellipsize(Pango.EllipsizeMode.END)
    if wrap:
        lb.set_wrap(True)
        lb.set_natural_wrap_mode(Gtk.NaturalWrapMode.WORD)
    if selectable:
        lb.set_selectable(True)
    return lb


def flat_button(child, css="flat-btn", tooltip=None, cb=None):
    b = Gtk.Button()
    for c in css.split():
        b.add_css_class(c)
    if isinstance(child, str):
        child = icon(child, 16)
    b.set_child(child)
    if tooltip:
        b.set_tooltip_text(tooltip)
    if cb:
        b.connect("clicked", lambda *_: cb())
    b.set_focus_on_click(False)
    return b


class MenuItem(Gtk.Button):
    __gtype_name__ = "FenestraNotepadMenuItem"


class Menu(Gtk.Popover):
    """Fluent flyout menu built from plain buttons (no GMenu styling).

    Items: add(text, cb, shortcut=, check=, sensitive=, icon_name=), add_submenu(text, build_cb),
    add_separator(), add_widget(w)."""

    def __init__(self, parent=None, checks=False, css=None, scroll=False):
        super().__init__()
        self.add_css_class("fluent-menu")
        if css:
            self.add_css_class(css)
        self.set_has_arrow(False)
        self.checks = checks
        self.sub = None
        # shortcuts are right-aligned (WinUI default); the reference File menu instead shows them
        # as a left-aligned column after the widest label: set shortcut_column = True for that
        self.shortcut_column = False
        self.label_group = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
        self.shortcut_group = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.box.add_css_class("menu-box")
        if scroll:
            sw = Gtk.ScrolledWindow()
            sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            sw.set_propagate_natural_height(True)
            sw.set_propagate_natural_width(True)
            sw.set_max_content_height(420)
            sw.set_child(self.box)
            self.set_child(sw)
            self.scroller = sw
        else:
            self.set_child(self.box)
        self.on_closed = None
        if parent is not None:
            self.set_parent(parent)
        self.connect("closed", self._closed)

    def _closed(self, *_):
        if self.sub is not None:
            self.sub.popdown()
        if self.on_closed:
            self.on_closed()

    def _row(self, text, shortcut=None, check=None, icon_name=None, chevron=False):
        b = MenuItem()
        b.add_css_class("menu-item")
        box = Gtk.Box()
        if self.checks:
            b.add_css_class("check-item")     # check menus have a 32 px pitch, others 33
            im = icon("np-check-symbolic", 14, "menu-check")
            im.set_opacity(1.0 if check else 0.0)
            box.append(im)
        elif icon_name:
            box.append(icon(icon_name, 16, "menu-icon"))
        lb = label(text, "menu-label")
        if chevron or not self.shortcut_column:
            lb.set_hexpand(True)
        else:
            self.label_group.add_widget(lb)
        box.append(lb)
        if shortcut:
            sc = label(shortcut, "menu-shortcut", xalign=0.0 if self.shortcut_column else 1.0)
            if self.shortcut_column:
                self.shortcut_group.add_widget(sc)
            box.append(sc)
        if chevron:
            box.append(icon("np-chevron-right-symbolic", 12, "menu-chevron"))
        b.set_child(box)
        b.connect("state-flags-changed", lambda w, _prev: self._hovered(w))
        return b

    def _hovered(self, b):
        if not (b.get_state_flags() & Gtk.StateFlags.PRELIGHT):
            return
        owner = getattr(b, "_submenu_builder", None)
        if self.sub is not None and self.sub.get_parent() is not b:
            self.sub.popdown()
        if owner is not None and (self.sub is None or self.sub.get_parent() is not b or not self.sub.get_visible()):
            GLib.timeout_add(250, self._hover_open, b)

    def _hover_open(self, b):
        if b.get_state_flags() & Gtk.StateFlags.PRELIGHT and self.get_visible():
            self.open_submenu(b)
        return False

    def add(self, text, cb=None, shortcut=None, check=None, sensitive=True, icon_name=None):
        b = self._row(text, shortcut, check, icon_name)
        b.set_sensitive(sensitive)

        def clicked(*_):
            self.popdown_all()
            if cb:
                GLib.idle_add(lambda: (cb(), False)[1], priority=GLib.PRIORITY_DEFAULT)
        b.connect("clicked", clicked)
        self.box.append(b)
        return b

    def add_submenu(self, text, build, sensitive=True):
        """build(menu) fills the submenu each time it opens."""
        b = self._row(text, chevron=True)
        b.add_css_class("has-submenu")
        b._submenu_builder = build
        b.set_sensitive(sensitive)
        b.connect("clicked", lambda *_: self.open_submenu(b))
        self.box.append(b)
        return b

    def open_submenu(self, b):
        if self.sub is not None:
            if self.sub.get_parent() is b and self.sub.get_visible():
                return self.sub
            self.sub.popdown()
            if self.sub.get_parent() is not None:
                self.sub.unparent()
        m = Menu(b)
        m.parent_menu = self
        b._submenu_builder(m)
        m.set_position(Gtk.PositionType.RIGHT)
        m.set_valign(Gtk.Align.START)
        m.set_offset(0, 0)
        self.sub = m

        def closed():
            if self.sub is m:
                self.sub = None
            GLib.idle_add(lambda: (m.unparent() if m.get_parent() is not None else None, False)[1], priority=GLib.PRIORITY_DEFAULT)
        m.on_closed = closed
        m.popup()
        return m

    def popdown_all(self):
        m = self
        while getattr(m, "parent_menu", None) is not None:
            m = m.parent_menu
        m.popdown()

    def add_separator(self):
        s = Gtk.Box()
        s.add_css_class("menu-sep")
        self.box.append(s)
        return s

    def add_widget(self, w):
        self.box.append(w)
        return w

    def clear(self):
        while (c := self.box.get_first_child()) is not None:
            self.box.remove(c)

    def popup_at(self, x, y):
        r = Gdk.Rectangle()
        r.x, r.y, r.width, r.height = int(x), int(y), 1, 1
        self.set_pointing_to(r)
        self.set_position(Gtk.PositionType.BOTTOM)
        self.set_halign(Gtk.Align.START)
        self.popup()


def menu_shortcut(text):
    """Localise modifier names of a shortcut label (Ctrl+Shift+N -> Ctrl+Mayús+N)."""
    parts = text.split("+")
    names = {"Ctrl": _("Ctrl"), "Shift": _("Shift"), "Alt": _("Alt"), "Del": _("Del")}
    return "+".join(names.get(p, p) for p in parts)


class Dropdown(Gtk.Button):
    """Fluent ComboBox: a button showing the current choice, opening a check menu."""
    __gtype_name__ = "FenestraNotepadDropdown"

    def __init__(self, choices, value, on_change, css="combo"):
        super().__init__()
        self.add_css_class(css)
        self.choices = choices          # list of (value, label)
        self.value = value
        self.on_change = on_change
        box = Gtk.Box(spacing=8)
        self.lbl = label("", "combo-label")
        self.lbl.set_hexpand(True)
        box.append(self.lbl)
        box.append(icon("np-chevron-down-symbolic", 12, "combo-chevron"))
        self.set_child(box)
        self.set_value(value)
        self.connect("clicked", self._open)

    def set_value(self, value):
        self.value = value
        self.lbl.set_label(next((t for v, t in self.choices if v == value), str(value)))

    def _open(self, *_):
        m = Menu(self, checks=True, css="combo-menu", scroll=len(self.choices) > 14)
        cur = None
        for v, t in self.choices:
            b = m.add(t, (lambda v=v: self._pick(v)), check=(v == self.value))
            if v == self.value:
                cur = b
        if cur is not None and len(self.choices) > 14:
            GLib.idle_add(lambda: (cur.grab_focus(), False)[1], priority=GLib.PRIORITY_DEFAULT)
        m.set_position(Gtk.PositionType.BOTTOM)
        m.on_closed = lambda: GLib.idle_add(lambda: (m.unparent() if m.get_parent() else None, False)[1], priority=GLib.PRIORITY_DEFAULT)
        m.popup()

    def _pick(self, v):
        self.set_value(v)
        if self.on_change:
            self.on_change(v)


class ContentDialog(Gtk.Box):
    """Windows 11 ContentDialog drawn over the window (smoke layer).

    buttons: list of (label, callback, kind) where kind is "accent" or "std"; a callback
    returning True keeps the dialog open."""
    __gtype_name__ = "FenestraNotepadDialog"

    def __init__(self, window, title, body=None, buttons=(), width=448, on_cancel=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        self.on_cancel = on_cancel
        self.add_css_class("dialog-card")
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        self.set_size_request(width, -1)
        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        top.add_css_class("dialog-top")
        if title:
            top.append(label(title, "dialog-title", wrap=True))
        if isinstance(body, str):
            top.append(label(body, "dialog-body", wrap=True))
        elif body is not None:
            top.append(body)
        self.content = top
        self.append(top)
        foot = Gtk.Box(spacing=8, homogeneous=True)
        foot.add_css_class("dialog-foot")
        self.buttons = []
        for text, cb, kind in buttons:
            b = Gtk.Button(label=text)
            b.add_css_class("accent-button" if kind == "accent" else "std-button")
            b.connect("clicked", lambda _b, cb=cb: self._done(cb))
            foot.append(b)
            self.buttons.append(b)
        self.append(foot)
        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self._key)
        self.add_controller(key)

    def _key(self, _c, keyval, _code, _state):
        name = Gdk.keyval_name(keyval)
        if name == "Escape":
            self.close()
            if self.on_cancel:
                self.on_cancel()
            return True
        return False

    def _done(self, cb):
        keep = cb() if cb else None
        if keep is not True:
            self.close()

    def present(self, focus=None):
        self.window.show_dialog(self)
        w = focus or (self.buttons[0] if self.buttons else None)
        if w is not None:
            w.grab_focus()

    def close(self):
        self.window.hide_dialog(self)
