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
        self.icon_name, self.text = icon_name, text
        box = Gtk.Box(spacing=6)
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
        self.text = text
        self.lbl.set_text(text)


class ToolSlot(Gtk.Widget):
    """Command-bar primary commands, right-aligned.  Like the WinUI CommandBar, commands
    that do not fit move (from the end) into the "See more" menu instead of forcing the
    window wider."""
    __gtype_name__ = "FenestraTaskToolSlot"
    LEFT_RESERVE = 220

    def __init__(self):
        super().__init__()
        self.overflow = []

    def kids(self):
        out, c = [], self.get_first_child()
        while c is not None:
            out.append(c)
            c = c.get_next_sibling()
        return out

    def append(self, w):
        w.set_parent(self)

    def remove(self, w):
        w.unparent()

    def do_measure(self, orientation, for_size):
        mn = nat = 0
        for c in self.kids():
            if not c.get_visible():
                continue
            a, b, _x, _y = c.measure(orientation, -1)
            if orientation == Gtk.Orientation.HORIZONTAL:
                nat += b
            else:
                mn, nat = max(mn, a), max(nat, b)
        return (0 if orientation == Gtk.Orientation.HORIZONTAL else mn), nat, -1, -1

    def do_size_allocate(self, w, h, baseline):
        from gi.repository import Graphene, Gsk
        kids = [c for c in self.kids() if c.get_visible()]
        widths = [c.measure(Gtk.Orientation.HORIZONTAL, -1)[1] for c in kids]
        n, total = len(kids), sum(widths)
        # the command bar never reaches into the left ~220 px of the page header
        # (measured: Services/Startup overflow their last command at 764 px)
        par = self.get_parent()
        limit = min(w, par.get_width() - self.LEFT_RESERVE) if par is not None and par.get_width() > 0 else w
        while n > 0 and total > limit:
            n -= 1
            total -= widths[n]
        self.overflow = [c for c in kids[n:] if isinstance(c, ToolButton)]
        x = w - total
        for i, c in enumerate(kids):
            c.set_child_visible(i < n)
            if i < n:
                ch = min(h, c.measure(Gtk.Orientation.VERTICAL, widths[i])[1])
                p = Graphene.Point()
                p.x, p.y = x, (h - ch) // 2 if c.get_valign() == Gtk.Align.CENTER else 0
                ch = ch if c.get_valign() == Gtk.Align.CENTER else h
                c.allocate(widths[i], ch, -1, Gsk.Transform().translate(p))
                x += widths[i]


def separator():
    s = Gtk.Box()
    s.add_css_class("tool-sep")
    s.set_valign(Gtk.Align.CENTER)
    return s


def _children(w):
    c = w.get_first_child()
    while c is not None:
        yield c
        c = c.get_next_sibling()


class Menu(Gtk.Popover):
    """Fluent context/flyout menu built from plain buttons (avoids GMenu styling)."""

    last = None         # most recent menu
    shot_window = None  # screenshot mode: menus are drawn inside this window instead of a popup
    shot_point = None   # screenshot mode: window point where a context menu opens

    def __init__(self, parent, classic=False):
        """classic=True: the Win32 context menu Task Manager shows for list rows and graphs
        (square, 1 px grey border, 24 px items, 12 px text)."""
        super().__init__()
        Menu.last = self
        self.add_css_class("classic-menu" if classic else "fluent-menu")
        self.set_has_arrow(False)
        self.set_parent(parent)
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(self.box)
        self.connect("closed", lambda *_: GLib.idle_add(self._cleanup))

    def _cleanup(self):
        if self.get_parent() is not None:
            self.unparent()
        return False

    def add(self, text, cb=None, icon_name=None, sensitive=True, check=None, shortcut=None, default=False,
            selected=None):
        """selected (True/False): combo-box list item, the current one marked with an accent pill."""
        b = Gtk.Button()
        b.add_css_class("menu-item")
        box = Gtk.Box(spacing=12)
        if selected is not None:
            box.set_spacing(7)
            pill = Gtk.Box(css_classes=["menu-pill"], valign=Gtk.Align.CENTER)
            box.append(pill)
            if selected:
                b.add_css_class("selected")
                self.selected_index = len(list(_children(self.box)))
        elif check is not None:
            im = icon("tm-check-symbolic", 20)
            im.set_opacity(1.0 if check else 0.0)
            box.append(im)
        elif icon_name is not None:
            box.append(icon(icon_name, 20))
        else:
            sp = Gtk.Box()
            sp.set_size_request(20, 16)  # same width as a check mark or icon
            box.append(sp)
        box.append(label(text, "menu-default" if default else None))
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
        self._at = (x, y)
        r = Gdk.Rectangle()
        r.x, r.y, r.width, r.height = int(x), int(y), 1, 1
        self.set_pointing_to(r)
        self.set_position(Gtk.PositionType.BOTTOM)
        self.set_halign(Gtk.Align.START)
        self.popup()

    def popup(self):
        win = Menu.shot_window
        if win is None:
            return Gtk.Popover.popup(self)
        # screenshot mode: a headless compositor cannot capture popups, so the menu is drawn
        # inside the window, where the popup would open
        frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        frame.add_css_class("menu-shot")
        frame.add_css_class("classic-menu" if self.has_css_class("classic-menu") else "fluent-menu")
        self.set_child(None)
        frame.append(self.box)
        frame.selected_index = getattr(self, "selected_index", None)
        if self.has_css_class("combo-menu"):
            frame.add_css_class("combo-menu")
        layer = getattr(win, "_shot_layer", None)
        if layer is None:
            layer = win._shot_layer = ShotLayer()
            win.overlay.add_overlay(layer)
        if Menu.shot_point is not None:
            layer.add(frame, win, Menu.shot_point)
        else:
            layer.add(frame, self.get_parent(), None)


class ShotLayer(Gtk.Widget):
    """Screenshot mode only: places menus next to their anchor during layout."""
    __gtype_name__ = "FenestraTaskShotLayer"

    def __init__(self):
        super().__init__()
        self.items = []
        self.set_can_target(False)

    def add(self, frame, anchor, point):
        frame.set_parent(self)
        self.items.append((frame, anchor, point))
        self.queue_resize()

    def do_measure(self, orientation, for_size):
        return 0, 0, -1, -1

    def do_size_allocate(self, w, h, baseline):
        from gi.repository import Graphene, Gsk
        for frame, anchor, point in self.items:
            if point is not None:
                p = Graphene.Point()
                p.x, p.y = point
                ok, q = anchor.compute_point(self, p)
                x, y = (q.x, q.y) if ok else point
            else:
                ok, b = anchor.compute_bounds(self)
                x, y = (b.get_x(), b.get_y() + b.get_height() + 8) if ok else (0, 0)
            fw = frame.measure(Gtk.Orientation.HORIZONTAL, -1)[1]
            fh = frame.measure(Gtk.Orientation.VERTICAL, fw)[1]
            idx = getattr(frame, "selected_index", None)
            if point is None and idx is not None and ok:
                # a combo box list opens over its button, the current item on top of it
                x, y = b.get_x() + 2, b.get_y() - 8 - 37 * idx
            if point is None:  # flyouts stay inside the window; context menus may overhang it
                x, y = max(0, min(x, w - fw)), max(0, min(y, h - fh))
            p = Graphene.Point()
            p.x, p.y = int(x), int(y)
            frame.allocate(fw, fh, -1, Gsk.Transform().translate(p))


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
