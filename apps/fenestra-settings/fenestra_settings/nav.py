"""Left navigation pane: user card, search box, category list."""
from __future__ import annotations

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk  # noqa: E402

from . import search
from .backends.accounts import current_user
from .i18n import _
from .pages.base import NAV_ORDER, PAGES
from .widgets import icon, label


class Avatar(Gtk.Box):
    def __init__(self, size=64):
        super().__init__()
        self.size = size
        self.add_css_class("avatar")
        self.set_size_request(size, size)
        self.set_overflow(Gtk.Overflow.HIDDEN)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)

    def set_user(self, user):
        child = self.get_first_child()
        if child:
            self.remove(child)
        if user.icon_file:
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(user.icon_file, self.size * 2,
                                                             self.size * 2, False)
                img = Gtk.Image.new_from_paintable(Gdk.Texture.new_for_pixbuf(pb))
                img.set_pixel_size(self.size)
                self.append(img)
                self.remove_css_class("initials")
                return
            except Exception:  # noqa: BLE001 - any loader error -> initials
                pass
        self.add_css_class("initials")
        lb = Gtk.Label(label=user.initials())
        lb.set_size_request(self.size, self.size)
        lb.add_css_class("avatar-initials")
        if self.size < 48:
            lb.add_css_class("small")
        self.append(lb)


class NavPane(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.add_css_class("nav-pane")
        self.window = window
        self.compact = False

        # --- user card
        user = current_user()
        self.user_card = Gtk.Box(spacing=16)
        self.user_card.add_css_class("user-card")
        self.avatar = Avatar(64)
        self.avatar.set_user(user)
        self.user_card.append(self.avatar)
        tb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        self.name_lbl = label(user.real_name, "user-name", ellipsize=True)
        tb.append(self.name_lbl)
        tb.append(label(_("Local Account"), "user-sub", ellipsize=True))
        self.user_texts = tb
        self.user_card.append(tb)
        click = Gtk.GestureClick()
        click.connect("released", lambda *_: window.navigate("yourinfo"))
        self.user_card.add_controller(click)
        self.append(self.user_card)

        # --- search
        self.entry = Gtk.Entry()
        self.entry.set_placeholder_text(_("Find a setting"))
        self.entry.add_css_class("search-entry")
        self.entry.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "fs-search-symbolic")
        self.entry.connect("changed", self._on_search_changed)
        self.entry.connect("activate", self._on_search_activate)
        self.entry.connect("icon-press", lambda *_: self._on_search_activate(self.entry))
        keyc = Gtk.EventControllerKey()
        keyc.connect("key-pressed", self._on_search_key)
        self.entry.add_controller(keyc)
        self.search_wrap = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.search_wrap.add_css_class("search-wrap")
        self.search_wrap.append(self.entry)
        self.append(self.search_wrap)

        self.popover = Gtk.Popover()
        self.popover.add_css_class("search-popover")
        self.popover.set_autohide(False)
        self.popover.set_has_arrow(False)
        self.popover.set_position(Gtk.PositionType.BOTTOM)
        self.popover.set_can_focus(False)
        self.results = Gtk.ListBox()
        self.results.add_css_class("search-results")
        self.results.set_selection_mode(Gtk.SelectionMode.BROWSE)
        self.results.connect("row-activated", self._on_result)
        self.popover.set_child(self.results)
        self.popover.set_parent(self.entry)
        self._index = None
        self._result_entries = []

        # --- nav list
        self.list = Gtk.ListBox()
        self.list.add_css_class("nav-list")
        self.list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.rows = {}
        for pid in NAV_ORDER:
            cls = PAGES[pid]
            row = Gtk.ListBoxRow()
            row.page_id = pid
            row.add_css_class("nav-item")
            ov = Gtk.Overlay()
            box = Gtk.Box(spacing=16)
            box.add_css_class("nav-item-box")
            box.append(icon(f"fs-nav-{pid}", 20, "nav-icon"))
            lb = label(_(cls.title), "nav-label", ellipsize=True)
            lb.set_hexpand(True)
            box.append(lb)
            row.nav_label = lb
            ov.set_child(box)
            pill = Gtk.Box()
            pill.add_css_class("nav-pill")
            pill.set_halign(Gtk.Align.START)
            pill.set_valign(Gtk.Align.CENTER)
            pill.set_size_request(3, 16)
            ov.add_overlay(pill)
            row.set_child(ov)
            row.set_tooltip_text(_(cls.title))
            self.list.append(row)
            self.rows[pid] = row
        self.list.connect("row-activated", self._on_row)
        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sc.set_overlay_scrolling(True)
        sc.set_vexpand(True)
        sc.set_child(self.list)
        sc.add_css_class("nav-scroll")
        self.append(sc)

    # -------------------------------------------------------------- nav
    def select(self, pid):
        row = self.rows.get(pid)
        if row is not None and self.list.get_selected_row() is not row:
            self.list.select_row(row)

    def _on_row(self, _lb, row):
        self.window.navigate(row.page_id, from_nav=True)

    def set_compact(self, compact):
        if compact == self.compact:
            return
        self.compact = compact
        if compact:
            self.add_css_class("compact")
        else:
            self.remove_css_class("compact")
        self.user_texts.set_visible(not compact)
        self.search_wrap.set_visible(not compact)
        for row in self.rows.values():
            row.nav_label.set_visible(not compact)
        self.avatar.set_visible(not compact)

    def refresh_user(self):
        u = current_user()
        u._load()
        self.avatar.set_user(u)
        self.name_lbl.set_label(u.real_name)

    # -------------------------------------------------------------- search
    def _on_search_changed(self, entry):
        text = entry.get_text()
        if self._index is None:
            self._index = search.build_index()
        res = search.query(self._index, text)
        child = self.results.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.results.remove(child)
            child = nxt
        self._result_entries = res
        if not text.strip():
            self.popover.popdown()
            return
        if not res:
            row = Gtk.ListBoxRow(activatable=False, selectable=False)
            row.set_child(label(_("No results found"), "search-empty"))
            self.results.append(row)
        for e in res:
            row = Gtk.ListBoxRow()
            row.entry = e
            b = Gtk.Box(spacing=12)
            b.add_css_class("search-result")
            b.append(icon(e.icon, 16))
            tb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            t = label(e.title, "search-title", ellipsize=True)
            tb.append(t)
            if e.key is not None or "›" in e.where:
                tb.append(label(e.where, "search-where", ellipsize=True))
            b.append(tb)
            row.set_child(b)
            self.results.append(row)
        w = self.entry.get_width()
        self.results.set_size_request(max(w, 240), -1)
        self.popover.popup()

    def _on_search_key(self, _c, keyval, _code, _state):
        if keyval == Gdk.KEY_Down and self.popover.get_visible():
            row = self.results.get_row_at_index(0)
            if row:
                self.results.select_row(row)
                row.grab_focus()
            return True
        if keyval == Gdk.KEY_Escape:
            self.entry.set_text("")
            self.popover.popdown()
            return True
        return False

    def _on_search_activate(self, _entry):
        if self._result_entries:
            self._go(self._result_entries[0])

    def _on_result(self, _lb, row):
        e = getattr(row, "entry", None)
        if e:
            self._go(e)

    def _go(self, e):
        self.popover.popdown()
        self.window.navigate(e.page_id, e.key)
        GLib.idle_add(lambda: (self.entry.set_text(""), False)[1])
