"""Floating Find / Replace card (Windows 11 Notepad style)."""
from __future__ import annotations

from gi.repository import Gdk, GLib, Gtk

from . import util
from .i18n import _
from .widgets import Menu, flat_button, icon


class FindCard(Gtk.Box):
    __gtype_name__ = "FenestraNotepadFindCard"

    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        self.add_css_class("find-card")
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.START)
        self.set_visible(False)
        self.replace_mode = False

        row1 = Gtk.Box()
        row1.add_css_class("find-row")
        self.toggle = flat_button(icon("np-chevron-up-20-symbolic", 20), "find-btn find-toggle",
                                  _("Toggle replace"), lambda: self.set_replace(not self.replace_mode))
        row1.append(self.toggle)
        self.entry = Gtk.Entry()
        self.entry.add_css_class("find-entry")
        self.entry.set_placeholder_text(_("Find"))
        self.entry.set_hexpand(True)
        self.entry.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "np-search-symbolic")
        self.entry.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, _("Find next"))
        self.entry.connect("icon-press", lambda *_: self.win.find_next())
        self.entry.connect("changed", self._changed)
        self.entry.connect("activate", lambda *_: self.win.find_next())
        row1.append(self.entry)
        self.next_btn = flat_button(icon("np-arrow-down-symbolic", 20), "find-btn",
                                    _("Find next") + " (F3)", lambda: self.win.find_next())
        self.prev_btn = flat_button(icon("np-arrow-up-symbolic", 20), "find-btn",
                                    _("Find previous") + " (" + _("Shift") + "+F3)", lambda: self.win.find_previous())
        self.opt_btn = flat_button(icon("np-options-symbolic", 18), "find-btn", _("Options"), self._options)
        self.close_btn = flat_button(icon("np-dismiss-20-symbolic", 18), "find-btn",
                                     _("Close") + " (Esc)", self.close_card)
        self.toggle.set_valign(Gtk.Align.CENTER)
        for b in (self.next_btn, self.prev_btn, self.opt_btn, self.close_btn):
            b.set_valign(Gtk.Align.CENTER)
            row1.append(b)
        self.append(row1)

        self.row2 = Gtk.Box()
        self.row2.add_css_class("find-row")
        self.row2.add_css_class("replace-row")
        self.rentry = Gtk.Entry()
        self.rentry.add_css_class("find-entry")
        self.rentry.set_placeholder_text(_("Replace"))
        self.rentry.set_hexpand(True)
        self.rentry.connect("activate", lambda *_: self.win.replace_one(self.rentry.get_text()))
        self.row2.append(self.rentry)
        self.rbtn = Gtk.Button(label=_("Replace"))
        self.rbtn.add_css_class("std-button")
        self.rbtn.add_css_class("replace-btn")
        self.rbtn.connect("clicked", lambda *_: self.win.replace_one(self.rentry.get_text()))
        self.rall = Gtk.Button(label=_("Replace all"))
        self.rall.add_css_class("std-button")
        self.rall.add_css_class("replace-btn")
        self.rall.connect("clicked", lambda *_: self.win.replace_all(self.rentry.get_text()))
        self.row2.append(self.rbtn)
        self.row2.append(self.rall)
        self.row2.set_visible(False)
        self.append(self.row2)

        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self._key)
        self.add_controller(key)
        self._apply_settings()

    def _apply_settings(self):
        s = util.settings()
        for d in self.win.documents():
            self.configure(d)
        return s

    def configure(self, doc):
        s = util.settings()
        ss = doc.search_settings
        ss.set_case_sensitive(s["match_case"])
        ss.set_at_word_boundaries(s["whole_word"])
        ss.set_wrap_around(s["wrap_around"])
        ss.set_regex_enabled(False)

    def _options(self):
        s = util.settings()
        m = Menu(self.opt_btn, checks=True, css="options-menu")

        def flip(k):
            s.set(k, not s[k])
            self._apply_settings()
            self.win.search_text_changed()
        m.add(_("Match case"), lambda: flip("match_case"), check=s["match_case"])
        m.add(_("Wrap around"), lambda: flip("wrap_around"), check=s["wrap_around"])
        # the reference opens it above the card, centred on the button
        m.set_position(Gtk.PositionType.TOP)
        m.set_offset(0, -6)
        m.on_closed = lambda: GLib.idle_add(lambda: (m.unparent() if m.get_parent() else None, False)[1], priority=GLib.PRIORITY_DEFAULT)
        m.popup()
        self.options_menu = m

    def _changed(self, *_):
        self.entry.remove_css_class("no-match")
        self.win.search_text_changed()

    def _key(self, _c, keyval, _code, state):
        name = Gdk.keyval_name(keyval)
        if name == "Escape":
            self.close_card()
            return True
        if name in ("Return", "KP_Enter") and state & Gdk.ModifierType.SHIFT_MASK:
            self.win.find_previous()
            return True
        return False

    def set_no_match(self, on):
        if on:
            self.entry.add_css_class("no-match")
        else:
            self.entry.remove_css_class("no-match")

    @property
    def text(self):
        return self.entry.get_text()

    def set_replace(self, on):
        self.replace_mode = on
        self.row2.set_visible(on)
        self.toggle.set_child(icon("np-chevron-down-20-symbolic" if on else "np-chevron-up-20-symbolic", 20))

    def open_card(self, replace=False, seed=None):
        self.set_replace(replace)
        self.set_visible(True)
        if seed:
            self.entry.set_text(seed)
        self.entry.grab_focus()
        self.entry.select_region(0, -1)

    def close_card(self):
        if self.get_visible():
            self.set_visible(False)
            self.win.focus_editor()
