"""Reusable OOBE controls: searchable list, setting rows, option rows."""

import unicodedata

from gi.repository import Gdk, GLib, GObject, Graphene, Gtk

from ..i18n import _


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).casefold()


class ListPicker(Gtk.Box):
    """Plain single-selection list like the reference OOBE: 58 px rows,
    the suggested item pinned on top, type-ahead instead of a search box."""

    __gtype_name__ = "FenestraListPicker"
    __gsignals__ = {
        "changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "activated": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    TYPEAHEAD_RESET_MS = 900

    def __init__(self, items, selected=None, pin_selected=True):
        """``items`` is a list of ``(id, label)`` or ``(id, label, detail)``."""
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.add_css_class("list-picker")
        self.set_vexpand(True)
        self._rows = {}
        self._typed = ""
        self._typed_time = 0
        self.search = None  # kept for API compatibility
        items = list(items)
        if pin_selected and selected is not None:
            pinned = [i for i in items if i[0] == selected]
            items = pinned + [i for i in items if i[0] != selected]

        self.listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.listbox.add_css_class("oobe-list")
        self.listbox.set_activate_on_single_click(False)
        for item in items:
            row = self._make_row(*item)
            self.listbox.append(row)
            self._rows[item[0]] = row
        self.listbox.connect("row-selected", self._on_selected)
        self.listbox.connect("row-activated", lambda _l, r: self.emit("activated", r.item_id))
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.listbox.add_controller(keys)

        self.scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER,
                                           vexpand=True, child=self.listbox)
        self.scroller.add_css_class("oobe-list-frame")
        self.append(self.scroller)
        if selected is not None:
            self.select(selected)
        self.connect("map", lambda *_: GLib.idle_add(self._scroll_to_selected))

    @staticmethod
    def _make_row(item_id, label, detail=None):
        row = Gtk.ListBoxRow()
        row.item_id = item_id
        row.search_key = _norm(label)
        box = Gtk.Box(spacing=12)
        lab = Gtk.Label(label=label, xalign=0, hexpand=True, ellipsize=3)
        box.append(lab)
        if detail:
            box.append(Gtk.Label(label=detail, css_classes=["dim"], xalign=1))
        row.set_child(box)
        return row

    def _on_key(self, _ctl, keyval, _code, mods):
        if mods & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK):
            return False
        ch = Gdk.keyval_to_unicode(keyval)
        if not ch or not chr(ch).isprintable() or chr(ch) == " " and not self._typed:
            return False
        now = GLib.get_monotonic_time() // 1000
        if now - self._typed_time > self.TYPEAHEAD_RESET_MS:
            self._typed = ""
        self._typed_time = now
        self._typed += _norm(chr(ch))
        i = 0
        while (r := self.listbox.get_row_at_index(i)) is not None:
            if r.search_key.startswith(self._typed):
                self.listbox.select_row(r)
                r.grab_focus()
                GLib.idle_add(self._scroll_to_selected)
                break
            i += 1
        return True

    def _on_selected(self, _lb, row):
        if row is not None:
            self.emit("changed", row.item_id)

    def select(self, item_id):
        row = self._rows.get(item_id)
        if row is not None:
            self.listbox.select_row(row)
            GLib.idle_add(self._scroll_to_selected)

    def get_selected(self):
        row = self.listbox.get_selected_row()
        return row.item_id if row is not None else None

    def _scroll_to_selected(self):
        row = self.listbox.get_selected_row()
        if row is None or not row.get_mapped():
            return False
        ok, pt = row.compute_point(self.listbox, Graphene.Point().init(0, 0))
        if ok:
            adj = self.scroller.get_vadjustment()
            if pt.y < adj.get_value() or pt.y + row.get_height() > adj.get_value() + adj.get_page_size():
                adj.set_value(max(0, min(pt.y, adj.get_upper() - adj.get_page_size())))
        return False


class RingSpinner(Gtk.Widget):
    """Indeterminate ring: light grey track with an accent arc that grows,
    shrinks and rotates (reference OOBE progress ring)."""

    __gtype_name__ = "FenestraRingSpinner"

    def __init__(self, size=64, thickness=6):
        super().__init__(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        self.size = size
        self.thickness = thickness
        self.phase = 0.35
        self._tick = 0
        self._start = None

    def do_measure(self, orientation, for_size):
        return (self.size, self.size, -1, -1)

    def start(self):
        if not self._tick:
            self._start = None
            self._tick = self.add_tick_callback(self._on_tick)

    def stop(self):
        if self._tick:
            self.remove_tick_callback(self._tick)
            self._tick = 0

    def _on_tick(self, _w, clock):
        t = clock.get_frame_time() / 1_000_000
        if self._start is None:
            self._start = t - 0.35 * 2.0
        self.phase = ((t - self._start) / 2.0) % 1.0
        self.queue_draw()
        return True

    def do_snapshot(self, snapshot):
        import math
        s, th = self.size, self.thickness
        cr = snapshot.append_cairo(Graphene.Rect().init(0, 0, s, s))
        r = (s - th) / 2
        cr.set_line_width(th)
        cr.set_source_rgba(0.78, 0.78, 0.80, 1.0)
        cr.arc(s / 2, s / 2, r, 0, 2 * math.pi)
        cr.stroke()
        if not self._tick:
            # Not animating (e.g. screenshots): a half ring on the left side.
            length, head = math.pi * 1.02, math.pi * 1.5
        else:
            p = self.phase
            length = (0.08 + 0.55 * math.sin(math.pi * p) ** 2) * 2 * math.pi
            head = -math.pi / 2 + p * 4 * math.pi + length
        cr.set_source_rgba(0.0, 0.404, 0.753, 1.0)  # #0067c0
        cr.set_line_cap(1)  # round
        cr.arc(s / 2, s / 2, r, head - length, head)
        cr.stroke()


class ToggleSwitch(Gtk.ToggleButton):
    """Pill toggle switch (Gtk.Switch triggers baseline warnings on GTK 4.20)."""

    __gtype_name__ = "FenestraToggleSwitch"

    def __init__(self, active=False, **kwargs):
        super().__init__(css_classes=["toggle-switch"], **kwargs)
        self.knob = Gtk.Box(css_classes=["knob"], valign=Gtk.Align.CENTER, halign=Gtk.Align.START)
        self.set_child(self.knob)
        self.connect("notify::active", lambda *_: self._sync())
        self.set_active(active)
        self._sync()

    def _sync(self):
        self.knob.set_halign(Gtk.Align.END if self.get_active() else Gtk.Align.START)


class SettingRow(Gtk.Box):
    """Icon + title + description + Yes/No switch (privacy page)."""

    __gtype_name__ = "FenestraSettingRow"

    def __init__(self, icon_name, title, description, active=True):
        super().__init__(spacing=16, css_classes=["setting-row"])
        icon = Gtk.Image(icon_name=icon_name, pixel_size=20, valign=Gtk.Align.START,
                         css_classes=["setting-icon"])
        self.append(icon)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        text.append(Gtk.Label(label=title, xalign=0, css_classes=["setting-title"], wrap=True))
        desc = Gtk.Label(label=description, xalign=0, wrap=True, css_classes=["setting-desc"])
        desc.set_max_width_chars(48)
        text.append(desc)
        self.append(text)
        sw_box = Gtk.Box(spacing=8, valign=Gtk.Align.START)
        self.switch = ToggleSwitch(active=active, valign=Gtk.Align.CENTER)
        self.switch.update_property([Gtk.AccessibleProperty.LABEL], [title])
        self.state_label = Gtk.Label(css_classes=["switch-state"], width_chars=3, xalign=0)
        sw_box.append(self.switch)
        sw_box.append(self.state_label)
        self.append(sw_box)
        self.switch.connect("notify::active", lambda *_: self._sync())
        self._sync()

    def _sync(self):
        self.state_label.set_label(_("Yes") if self.switch.get_active() else _("No"))

    @property
    def active(self):
        return self.switch.get_active()


class CheckRow(Gtk.Box):
    """Checkbox card with an icon (customize page)."""

    __gtype_name__ = "FenestraCheckRow"

    def __init__(self, icon_name, title, description=""):
        super().__init__(spacing=14, css_classes=["check-row"])
        self.check = Gtk.CheckButton(valign=Gtk.Align.CENTER)
        self.check.update_property([Gtk.AccessibleProperty.LABEL], [title])
        self.append(self.check)
        self.append(Gtk.Image(icon_name=icon_name, pixel_size=20, css_classes=["check-icon"]))
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True,
                       valign=Gtk.Align.CENTER)
        text.append(Gtk.Label(label=title, xalign=0, css_classes=["check-title"]))
        if description:
            text.append(Gtk.Label(label=description, xalign=0, wrap=True, css_classes=["check-desc"]))
        self.append(text)
        click = Gtk.GestureClick()
        click.connect("released", self._on_click)
        self.add_controller(click)
        self.check.connect("notify::active", lambda *_: self._sync())

    def _on_click(self, gesture, _n, x, y):
        picked = self.pick(x, y, Gtk.PickFlags.DEFAULT)
        w = picked
        while w is not None and w is not self:
            if w is self.check:
                return
            w = w.get_parent()
        self.check.set_active(not self.check.get_active())

    def _sync(self):
        if self.check.get_active():
            self.add_css_class("checked")
        else:
            self.remove_css_class("checked")

    @property
    def active(self):
        return self.check.get_active()


class ChoiceRow(Gtk.Box):
    """Large selectable option with title and description (radio-like)."""

    __gtype_name__ = "FenestraChoiceRow"

    def __init__(self, title, description, group=None):
        super().__init__(spacing=14, css_classes=["choice-row"])
        self.radio = Gtk.CheckButton(group=group, valign=Gtk.Align.START)
        self.append(self.radio)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
        text.append(Gtk.Label(label=title, xalign=0, css_classes=["check-title"]))
        text.append(Gtk.Label(label=description, xalign=0, wrap=True, css_classes=["check-desc"]))
        self.append(text)
        click = Gtk.GestureClick()
        click.connect("released", lambda *_: self.radio.set_active(True))
        self.add_controller(click)
