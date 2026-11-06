"""Fluent-style building blocks: cards, rows, toggles, dropdowns, sliders, dialogs."""
from __future__ import annotations

from gi.repository import Gdk, GLib, GObject, Gtk, Pango

from .i18n import _


def icon(name: str | None, size: int = 20, css: str | None = None) -> Gtk.Image:
    img = Gtk.Image()
    if name:
        if "/" in name:
            img.set_from_file(name)
        else:
            img.set_from_icon_name(name)
    img.set_pixel_size(size)
    if css:
        img.add_css_class(css)
    return img


def label(text: str = "", css: str | list | None = None, wrap=False, xalign=0.0,
          ellipsize=False, selectable=False) -> Gtk.Label:
    lb = Gtk.Label(label=text, xalign=xalign)
    if wrap:
        lb.set_wrap(True)
        lb.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
    if ellipsize:
        lb.set_ellipsize(Pango.EllipsizeMode.END)
    if selectable:
        lb.set_selectable(True)
    if css:
        for c in ([css] if isinstance(css, str) else css):
            lb.add_css_class(c)
    return lb


def clear(box: Gtk.Widget):
    child = box.get_first_child()
    while child is not None:
        nxt = child.get_next_sibling()
        box.remove(child)
        child = nxt


class Clamp(Gtk.Widget):
    """Limits its child to a maximum width (left aligned, like the reference UI)."""
    __gtype_name__ = "FsClamp"

    def __init__(self, child: Gtk.Widget, maximum: int = 1000, center=False):
        super().__init__()
        self.maximum = maximum
        self.center = center
        self.child = child
        child.set_parent(self)

    def do_dispose(self):
        if self.child is not None:
            self.child.unparent()
            self.child = None
        Gtk.Widget.do_dispose(self)

    def do_get_request_mode(self):
        return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH

    def do_measure(self, orientation, for_size):
        if self.child is None:
            return 0, 0, -1, -1
        if orientation == Gtk.Orientation.VERTICAL and for_size >= 0:
            for_size = min(for_size, self.maximum)
        mn, nat, _a, _b = self.child.measure(orientation, for_size)
        if orientation == Gtk.Orientation.HORIZONTAL:
            nat = max(mn, min(nat, self.maximum))
        return mn, nat, -1, -1

    def do_size_allocate(self, width, height, baseline):
        if self.child is None:
            return
        w = min(width, self.maximum)
        mn, _n, _a, _b = self.child.measure(Gtk.Orientation.HORIZONTAL, -1)
        w = max(w, mn)
        x = (width - w) // 2 if self.center else 0
        alloc = Gdk.Rectangle()
        alloc.x, alloc.y, alloc.width, alloc.height = x, 0, w, height
        self.child.size_allocate(alloc, -1)


# --------------------------------------------------------------------------- controls

class ToggleSwitch(Gtk.Box):
    """'On'/'Off' label + Fluent toggle. on_toggled(bool) fires only on user action."""

    def __init__(self, active=False, on_toggled=None, show_label=True, sensitive=True):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.add_css_class("toggle-box")
        self._cb = on_toggled
        self._silent = False
        self.lbl = label("", "toggle-label")
        self.lbl.set_visible(show_label)
        self.lbl.set_width_chars(3)
        self.lbl.set_xalign(1.0)
        self.sw = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.sw.add_css_class("fluent-toggle")
        c = self.sw.get_first_child()
        while c is not None:  # drop the built-in on/off glyphs
            if isinstance(c, Gtk.Image):
                c.set_visible(False)
            c = c.get_next_sibling()
        self.append(self.lbl)
        self.append(self.sw)
        self.set_valign(Gtk.Align.CENTER)
        self.set_active(active)
        self.sw.connect("notify::active", self._on_notify)
        self.set_sensitive(sensitive)

    def _on_notify(self, *_):
        self._update_label()
        if not self._silent and self._cb:
            self._cb(self.sw.get_active())

    def _update_label(self):
        self.lbl.set_label(_("On") if self.sw.get_active() else _("Off"))

    def set_active(self, v: bool):
        self._silent = True
        self.sw.set_active(bool(v))
        self._silent = False
        self._update_label()

    def get_active(self) -> bool:
        return self.sw.get_active()

    def toggle(self):
        self.sw.set_active(not self.sw.get_active())


class Dropdown(Gtk.DropDown):
    """String dropdown. options: list of (id, label). on_changed(id) on user action."""

    def __init__(self, options, selected=None, on_changed=None, width=-1):
        self._ids = [o[0] for o in options]
        model = Gtk.StringList.new([o[1] for o in options])
        super().__init__(model=model)
        self.add_css_class("fluent-dropdown")
        self.set_valign(Gtk.Align.CENTER)
        if width > 0:
            self.set_size_request(width, -1)
        self._cb = on_changed
        self._silent = False
        self.select(selected)
        self.connect("notify::selected", self._on_sel)

    def set_options(self, options, selected=None):
        self._silent = True
        self._ids = [o[0] for o in options]
        self.set_model(Gtk.StringList.new([o[1] for o in options]))
        self._silent = False
        self.select(selected)

    def select(self, ident):
        self._silent = True
        if ident in self._ids:
            self.set_selected(self._ids.index(ident))
        elif self._ids and ident is None:
            self.set_selected(0)
        self._silent = False

    def selected_id(self):
        i = self.get_selected()
        return self._ids[i] if 0 <= i < len(self._ids) else None

    def _on_sel(self, *_):
        if not self._silent and self._cb:
            self._cb(self.selected_id())


class Slider(Gtk.Box):
    """Fluent slider with optional leading icon and value label."""

    def __init__(self, lo, hi, value, on_changed=None, step=1, icon_name=None,
                 show_value=True, fmt="{:.0f}", width=-1, debounce_ms=120):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.set_valign(Gtk.Align.CENTER)
        self.set_hexpand(False)
        if icon_name:
            self.append(icon(icon_name, 16, "row-icon"))
        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, step)
        self.scale.add_css_class("fluent-slider")
        self.scale.set_draw_value(False)
        self.scale.set_hexpand(True)
        self.scale.set_size_request(width if width > 0 else 200, -1)
        self.fmt = fmt
        self.value_lbl = label("", "slider-value", xalign=1.0)
        self.value_lbl.set_width_chars(4)
        self.value_lbl.set_visible(show_value)
        self.append(self.scale)
        self.append(self.value_lbl)
        self._cb = on_changed
        self._silent = False
        self._timer = 0
        self._debounce = debounce_ms
        self.set_value(value)
        self.scale.connect("value-changed", self._on_changed)

    def set_value(self, v):
        self._silent = True
        self.scale.set_value(v)
        self._silent = False
        self.value_lbl.set_label(self.fmt.format(self.scale.get_value()))

    def get_value(self):
        return self.scale.get_value()

    def _on_changed(self, *_):
        self.value_lbl.set_label(self.fmt.format(self.scale.get_value()))
        if self._silent or not self._cb:
            return
        if self._timer:
            GLib.source_remove(self._timer)
        self._timer = GLib.timeout_add(self._debounce, self._fire)

    def _fire(self):
        self._timer = 0
        self._cb(self.scale.get_value())
        return False


def button(text, on_click=None, accent=False, css=None, icon_name=None, sensitive=True):
    b = Gtk.Button()
    if icon_name:
        box = Gtk.Box(spacing=8)
        box.append(icon(icon_name, 16))
        box.append(Gtk.Label(label=text))
        b.set_child(box)
    else:
        b.set_label(text)
    b.add_css_class("fluent-button")
    if accent:
        b.add_css_class("accent")
    if css:
        b.add_css_class(css)
    b.set_valign(Gtk.Align.CENTER)
    b.set_sensitive(sensitive)
    if on_click:
        b.connect("clicked", lambda *_: on_click())
    return b


def link(text, on_click=None):
    b = Gtk.Button(label=text)
    b.add_css_class("hyperlink")
    b.set_halign(Gtk.Align.START)
    b.set_valign(Gtk.Align.CENTER)
    if on_click:
        b.connect("clicked", lambda *_: on_click())
    return b


def spinner(size=16):
    s = Gtk.Spinner()
    s.set_size_request(size, size)
    s.start()
    s.add_css_class("fluent-spinner")
    return s


def progress(fraction=0.0, css=None):
    p = Gtk.ProgressBar()
    p.add_css_class("fluent-progress")
    if css:
        p.add_css_class(css)
    p.set_fraction(max(0.0, min(1.0, fraction)))
    p.set_valign(Gtk.Align.CENTER)
    return p


# --------------------------------------------------------------------------- rows & cards

class SettingRow(Gtk.Box):
    """A single settings card row.

    icon | title / subtitle | [control] [chevron]
    """

    def __init__(self, title, subtitle=None, icon_name=None, control=None, on_click=None,
                 chevron=False, key=None, external=False, icon_size=20, css=None,
                 image: Gtk.Widget | None = None, wrap_control=False):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.add_css_class("setting-row")
        if css:
            self.add_css_class(css)
        self.key = key
        self._on_click = on_click
        self.set_hexpand(True)

        if image is not None:
            image.set_valign(Gtk.Align.CENTER)
            image.add_css_class("row-lead")
            self.append(image)
        elif icon_name:
            ic = icon(icon_name, icon_size, "row-icon")
            ic.add_css_class("row-lead")
            ic.set_valign(Gtk.Align.CENTER)
            self.append(ic)
        else:
            self.add_css_class("no-icon")

        texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        texts.set_valign(Gtk.Align.CENTER)
        texts.set_hexpand(True)
        self.title_lbl = label(title, "row-title", wrap=True)
        texts.append(self.title_lbl)
        self.subtitle_lbl = label(subtitle or "", "row-subtitle", wrap=True)
        self.subtitle_lbl.set_visible(bool(subtitle))
        texts.append(self.subtitle_lbl)
        self.texts = texts
        self.append(texts)
        if subtitle:
            self.add_css_class("two-line")

        self.suffix = Gtk.Box(spacing=12, valign=Gtk.Align.CENTER)
        self.suffix.add_css_class("row-suffix")
        self.append(self.suffix)
        self.control = control
        if control is not None:
            self.suffix.append(control)
        if isinstance(control, ToggleSwitch):
            self.add_css_class("has-toggle")  # toggle rows are 1 px taller in the reference
        if chevron or external:
            self.suffix.append(icon("fs-open-symbolic" if external else "fs-chevron-right-symbolic",
                                    20 if not external else 16, "row-chevron"))

        if on_click is not None:
            self.add_css_class("activatable")
            self.set_cursor_from_name("default")
            g = Gtk.GestureClick()
            g.connect("pressed", lambda *_: self.add_css_class("pressed"))
            g.connect("released", self._released)
            g.connect("stopped", lambda *_: self.remove_css_class("pressed"))
            self.add_controller(g)
        elif isinstance(control, ToggleSwitch):
            # Clicking the row body does not toggle in the reference UI; keep it inert.
            pass

    def _released(self, gesture, n, x, y):
        self.remove_css_class("pressed")
        w = self.pick(x, y, Gtk.PickFlags.DEFAULT)
        # Ignore clicks that land on interactive controls inside the row.
        while w is not None and w is not self:
            if isinstance(w, (Gtk.Button, Gtk.Switch, Gtk.DropDown, Gtk.Scale, Gtk.Entry)):
                return
            w = w.get_parent()
        if self._on_click:
            self._on_click()

    def set_subtitle(self, text):
        self.subtitle_lbl.set_label(text or "")
        self.subtitle_lbl.set_visible(bool(text))
        if text:
            self.add_css_class("two-line")
        else:
            self.remove_css_class("two-line")

    def set_title(self, text):
        self.title_lbl.set_label(text)

    def set_control(self, w):
        if self.control is not None:
            self.suffix.remove(self.control)
        self.control = w
        if w is not None:
            self.suffix.prepend(w)
        if isinstance(w, ToggleSwitch):
            self.add_css_class("has-toggle")

    def flash(self):
        self.add_css_class("highlight")
        GLib.timeout_add(1800, lambda: (self.remove_css_class("highlight"), False)[1])


class ExpanderRow(Gtk.Box):
    """Expandable card (header + revealed nested rows)."""

    def __init__(self, title, subtitle=None, icon_name=None, control=None, key=None,
                 expanded=False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.add_css_class("expander")
        self.key = key
        self.chev = icon("fs-chevron-down-symbolic", 16, "row-chevron")
        self.header = SettingRow(title, subtitle, icon_name, control, on_click=self.toggle,
                                 key=key)
        self.header.suffix.append(self.chev)
        self.header.add_css_class("expander-header")
        self.append(self.header)
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.content.add_css_class("expander-content")
        self.revealer = Gtk.Revealer(child=self.content,
                                     transition_type=Gtk.RevealerTransitionType.SLIDE_DOWN,
                                     transition_duration=180)
        self.append(self.revealer)
        self.set_expanded(expanded)

    def add(self, w):
        w.add_css_class("nested")
        self.content.append(w)
        return w

    def clear(self):
        clear(self.content)

    def toggle(self):
        self.set_expanded(not self.revealer.get_reveal_child())

    def set_expanded(self, v):
        self.revealer.set_reveal_child(v)
        if v:
            self.add_css_class("expanded")
        else:
            self.remove_css_class("expanded")

    def flash(self):
        self.header.flash()


class Group(Gtk.Box):
    """A vertical stack of cards separated by a 2px gap, optionally with a heading."""

    def __init__(self, title=None, css=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add_css_class("group")
        if css:
            self.add_css_class(css)
        if title:
            self.append(label(title, "section-title"))
        self.rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self.rows.add_css_class("group-rows")
        self.append(self.rows)

    hidden_keys: set = frozenset()  # row keys hidden in this session (set by Page.group())

    def add(self, w):
        self.rows.append(w)
        if getattr(w, "key", None) in self.hidden_keys:
            w.set_visible(False)
            w.session_hidden = True
        return w

    def clear(self):
        clear(self.rows)


def not_available_row(title, reason=None, icon_name="fs-info-symbolic"):
    r = SettingRow(title, reason or _("Not available on this device"), icon_name,
                   control=label(_("Not available"), "row-value"))
    r.add_css_class("dim")
    return r


def card(css=None) -> Gtk.Box:
    b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    b.add_css_class("card")
    if css:
        b.add_css_class(css)
    return b


def value_label(text):
    return label(text, "row-value", xalign=1.0)


# --------------------------------------------------------------------------- dialogs

class ContentDialog(Gtk.Box):
    """In-window modal dialog (smoke layer handled by the window overlay)."""

    def __init__(self, title, body=None, primary=None, secondary=None, close=_("Cancel"),
                 on_response=None, extra: Gtk.Widget | None = None, destructive=False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.add_css_class("content-dialog")
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)
        self.set_size_request(448, -1)
        self._cb = on_response
        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        top.add_css_class("dialog-body")
        top.append(label(title, "dialog-title", wrap=True))
        if body:
            b = label(body, "dialog-text", wrap=True)
            b.set_max_width_chars(52)
            top.append(b)
        if extra is not None:
            top.append(extra)
        self.append(top)
        foot = Gtk.Box(spacing=8, homogeneous=True)
        foot.add_css_class("dialog-footer")
        if primary:
            self.primary_btn = button(primary, lambda: self.respond("primary"), accent=True)
            if destructive:
                self.primary_btn.add_css_class("destructive")
            foot.append(self.primary_btn)
        if secondary:
            foot.append(button(secondary, lambda: self.respond("secondary")))
        if close:
            foot.append(button(close, lambda: self.respond("close")))
        self.append(foot)
        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self._key)
        self.add_controller(key)

    def _key(self, _c, keyval, _code, _state):
        if keyval == Gdk.KEY_Escape:
            self.respond("close")
            return True
        return False

    def respond(self, resp):
        win = self.get_root()
        if win is not None and hasattr(win, "close_dialog"):
            win.close_dialog(self)
        if self._cb:
            self._cb(resp)


def show_dialog(widget: Gtk.Widget, dialog: ContentDialog):
    win = widget.get_root()
    if win is not None and hasattr(win, "show_dialog"):
        win.show_dialog(dialog)


def confirm(widget, title, body, primary, on_yes, destructive=False):
    dlg = ContentDialog(title, body, primary=primary, close=_("Cancel"),
                        on_response=lambda r: on_yes() if r == "primary" else None,
                        destructive=destructive)
    show_dialog(widget, dlg)


def info(widget, title, body):
    show_dialog(widget, ContentDialog(title, body, close=_("OK")))


def toast(widget, text, ms=3000):
    win = widget.get_root()
    if win is not None and hasattr(win, "toast"):
        win.toast(text, ms)


GObject.type_ensure(Clamp)
