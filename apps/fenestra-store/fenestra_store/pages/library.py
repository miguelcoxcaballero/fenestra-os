"""Library: installed apps from every source, and Updates (per app, Update all, last checked)."""
from __future__ import annotations

from gi.repository import GLib, Gtk

from .. import util
from ..i18n import N_, _
from ..model import SOURCES
from ..widgets import ActionArea, app_icon, button, clear, icon, label, source_badge
from .base import Page


class LibraryPage(Page):
    id = "library"
    nav = "library"
    title = N_("Library")

    def __init__(self, win):
        super().__init__(win)
        self.tab = "installed"
        self._ticker = 0

    def show(self, arg=None):
        if arg in ("installed", "updates"):
            self.tab = arg
        self.dirty = True
        super().show(arg)

    def build(self, arg):
        self.page_title(_("Library"), _("Apps installed on this computer, from Flathub and from Fedora."))
        tabs = Gtk.Box(spacing=0)
        tabs.add_css_class("segmented")
        tabs.set_halign(Gtk.Align.START)
        self.tab_buttons = {}
        group = None
        for tid in ("installed", "updates"):
            b = Gtk.ToggleButton()
            b.add_css_class("segment")
            if group is None:
                group = b
            else:
                b.set_group(group)
            self.tab_buttons[tid] = b
            b.connect("toggled", lambda btn, tid=tid: btn.get_active() and self._switch(tid))
            tabs.append(b)
        self.box.append(tabs)
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.box.append(self.content)
        self.tab_buttons[self.tab].set_active(True)
        self._labels()
        self._fill()
        if not self._ticker:  # keep "last checked" fresh
            self._ticker = GLib.timeout_add_seconds(30, self._tick)

    def _tick(self):
        lb = getattr(self, "checked_lbl", None)
        if lb is not None and lb.get_mapped():
            lb.set_label(self._checked_text())
        return True

    def _labels(self):
        st = self.store
        self.tab_buttons["installed"].set_label(_("Installed (%d)") % len(st.installed()))
        n = len(st.updates())
        self.tab_buttons["updates"].set_label(_("Updates (%d)") % n if n else _("Updates"))

    def _switch(self, tid):
        if tid != self.tab:
            self.tab = tid
            self.arg = tid
            self._fill()

    def on_updates_changed(self):
        if getattr(self, "content", None) is None:
            return
        self._labels()
        if self.tab == "updates" or not self.store.busy_apps():
            self._fill()

    def _fill(self):
        clear(self.content)
        self.update_all_btn = None
        if self.tab == "installed":
            self._installed()
        else:
            self._updates()

    # ------------------------------------------------------------------ installed
    def _installed(self):
        apps = self.store.installed()
        if not apps:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, halign=Gtk.Align.CENTER)
            box.add_css_class("empty-state")
            box.append(icon("st-library-symbolic", 48, "empty-icon"))
            box.append(label(_("No apps installed yet"), "empty-title", xalign=0.5))
            self.content.append(box)
            return
        lst = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        lst.add_css_class("row-list")
        for a in apps:
            lst.append(self._row(a, installed=True))
        self.content.append(lst)

    def _row(self, app, installed):
        row = Gtk.Box(spacing=16)
        row.add_css_class("lib-row")
        click = Gtk.GestureClick()
        click.connect("released", lambda *_: self.win.show_app(app.uid))
        img = app_icon(app, 40)
        img.add_controller(click)
        row.append(img)
        tb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, hexpand=True)
        name = Gtk.Button(label=app.name)
        name.add_css_class("row-name-link")
        name.set_halign(Gtk.Align.START)
        name.connect("clicked", lambda *_: self.win.show_app(app.uid))
        tb.append(name)
        if installed:
            parts = [_("Version %s") % app.version if app.version else "", util.human_size(app.installed_size)]
        else:
            new = app.update_version if app.update_version != "*" else _("new version")
            parts = [f"{app.version}  →  {new}" if app.version else new, util.human_size(app.download_size)]
        tb.append(label("  ·  ".join(p for p in parts if p), "caption", ellipsize=True))
        row.append(tb)
        row.append(source_badge(app, small=True))
        act = ActionArea(self.win, app, show_open=installed, small=True)
        row.append(act)
        if installed:
            rm = button("", "flat-icon", lambda: self.win.confirm_remove(app.uid), "st-trash-symbolic",
                        _("Uninstall %s") % app.name)
            rm.set_valign(Gtk.Align.CENTER)
            rm.set_sensitive(not app.busy)
            row.append(rm)
        return row

    # ------------------------------------------------------------------ updates
    def _checked_text(self):
        st = self.store
        if st.checking:
            return _("Checking for updates…")
        return _("Last checked: %s") % util.relative_time(st.last_checked)

    def _updates(self):
        st = self.store
        ups = st.updates()
        hero = Gtk.Box(spacing=16)
        hero.add_css_class("update-hero")
        badge = Gtk.Box(valign=Gtk.Align.CENTER)
        badge.add_css_class("update-badge")
        badge.append(icon("st-update-symbolic" if ups else "st-check-symbolic", 24))
        hero.append(badge)
        tb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, hexpand=True)
        if ups:
            title = _("1 update available") if len(ups) == 1 else _("%d updates available") % len(ups)
        else:
            title = _("Your apps are up to date")
        tb.append(label(title, "hero-title"))
        self.checked_lbl = label(self._checked_text(), "caption")
        tb.append(self.checked_lbl)
        hero.append(tb)
        check = button(_("Check for updates"), "fluent-button", st.check_updates)
        check.set_valign(Gtk.Align.CENTER)
        check.set_sensitive(not st.checking)
        if st.checking:
            sp = Gtk.Spinner(spinning=True, valign=Gtk.Align.CENTER)
            sp.add_css_class("fluent-spinner")
            hero.append(sp)
        hero.append(check)
        self.update_all_btn = button(_("Update all"), "fluent-button accent", st.update_all, "st-update-symbolic")
        self.update_all_btn.set_valign(Gtk.Align.CENTER)
        self.update_all_btn.set_sensitive(any(not a.busy for a in ups))
        hero.append(self.update_all_btn)
        self.content.append(hero)
        if ups:
            lst = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            lst.add_css_class("row-list")
            for a in ups:
                lst.append(self._row(a, installed=False))
            self.content.append(lst)
        srcs = sorted({_(SOURCES.get(a.source, a.source)) for a in st.installed()})
        if srcs:
            note = label(_("Updates are checked for apps from: %s.") % ", ".join(srcs), "page-note", wrap=True)
            self.content.append(note)
