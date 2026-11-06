"""Library: installed apps from every source, and Updates (per app, Update all, last checked)."""
from __future__ import annotations

from gi.repository import GLib, Gtk, Pango

from .. import util
from ..i18n import N_, _
from ..model import SOURCES
from ..widgets import ActionArea, app_icon, button, clear, icon, label
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

    def nav_for(self, arg):
        return "updates" if (arg or self.tab) == "updates" else "library"

    def build(self, arg):
        self.tab_buttons = {}
        self.head_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.box.append(self.head_box)
        self.content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.box.append(self.content)
        self._fill()
        if not self._ticker:  # keep "last checked" fresh
            self._ticker = GLib.timeout_add_seconds(30, self._tick)

    def _tick(self):
        lb = getattr(self, "checked_lbl", None)
        if lb is not None and lb.get_mapped():
            lb.set_label(self._checked_text())
        return True

    def _labels(self):
        pass

    def _switch(self, tid):
        if tid != self.tab:
            self.tab = tid
            self.arg = tid
            self._fill()
            self.win._select_nav(self.nav_for(tid))

    def on_updates_changed(self):
        if getattr(self, "content", None) is None:
            return
        self._labels()
        if self.tab == "updates" or not self.store.busy_apps():
            self._fill()

    def _fill(self):
        clear(self.content)
        clear(self.head_box)
        self.update_all_btn = None
        if self.tab == "installed":
            self._installed()
        else:
            self._updates()

    # ------------------------------------------------------------------ installed
    def _head(self, title, end=None):
        box = self.box
        self.box = self.head_box
        self.page_title(title, end=end)
        self.box = box

    def _installed(self):
        apps = self.store.installed()
        self._head(_("Library"))
        if not apps:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, halign=Gtk.Align.CENTER)
            box.add_css_class("empty-state")
            box.append(icon("st-library-symbolic", 48, "empty-icon"))
            box.append(label(_("No apps installed yet"), "empty-title", xalign=0.5))
            self.content.append(box)
            return
        self.content.append(label(_("Installed apps"), "list-heading"))
        lst = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        lst.add_css_class("row-list")
        for a in apps:
            lst.append(self._row(a, installed=True))
        self.content.append(lst)

    def _row(self, app, installed):
        """72 px row: icon + name/developer | source | version and size | action | more."""
        row = Gtk.Box(spacing=0)
        row.add_css_class("lib-row")
        click = Gtk.GestureClick()
        click.connect("released", lambda *_: self.win.show_app(app.uid))
        img = app_icon(app, 48)
        img.add_css_class("lib-row-icon")
        img.set_valign(Gtk.Align.CENTER)
        img.add_controller(click)
        row.append(img)
        tb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        tb.add_css_class("lib-col-name")
        tb.set_size_request(269, -1)
        name = Gtk.Button(label=app.name)
        name.add_css_class("row-name-link")
        name.set_halign(Gtk.Align.START)
        name.get_child().set_ellipsize(Pango.EllipsizeMode.END)
        name.connect("clicked", lambda *_: self.win.show_app(app.uid))
        tb.append(name)
        tb.append(label(app.developer, "lib-row-dev", ellipsize=True))
        row.append(tb)
        src = label(_(SOURCES.get(app.source, app.source)) + " · " +
                    (_("Flatpak") if app.packaging == "flatpak" else _("RPM package")), "lib-col", ellipsize=True)
        src.set_size_request(218, -1)
        row.append(src)
        if installed:
            parts = [_("Version %s") % app.version if app.version else "", util.human_size(app.installed_size)]
        else:
            new = app.update_version if app.update_version != "*" else _("new version")
            parts = [f"{app.version}  →  {new}" if app.version else new, util.human_size(app.download_size)]
        info = label("  ·  ".join(p for p in parts if p), "lib-col", ellipsize=True)
        info.set_hexpand(True)
        row.append(info)
        act = ActionArea(self.win, app, show_open=installed, small=True)
        act.add_css_class("lib-action")
        row.append(act)
        more = Gtk.MenuButton()
        more.add_css_class("more-button")
        more.set_icon_name("st-more-symbolic")
        more.set_tooltip_text(_("More options"))
        more.set_valign(Gtk.Align.CENTER)
        pop = Gtk.Popover()
        pop.add_css_class("menu-popover")
        pbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        pbox.append(button(_("Open app page"), "menu-item", lambda: (pop.popdown(), self.win.show_app(app.uid))))
        if app.installed:
            rm = button(_("Uninstall"), "menu-item", lambda: (pop.popdown(), self.win.confirm_remove(app.uid)))
            rm.set_sensitive(not app.busy)
            pbox.append(rm)
        pop.set_child(pbox)
        more.set_popover(pop)
        row.append(more)
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
        end = Gtk.Box(spacing=8)
        if st.checking:
            sp = Gtk.Spinner(spinning=True, valign=Gtk.Align.CENTER)
            sp.add_css_class("fluent-spinner")
            end.append(sp)
        self.update_all_btn = button(_("Update all"), "fluent-button", st.update_all)
        self.update_all_btn.set_sensitive(any(not a.busy for a in ups))
        self.update_all_btn.set_visible(bool(ups))
        end.append(self.update_all_btn)
        check = button(_("Check for updates"), "fluent-button accent", st.check_updates)
        check.set_sensitive(not st.checking)
        end.append(check)
        self._head(_("Updates and downloads"), end=end)
        if ups:
            title = _("1 update available") if len(ups) == 1 else _("%d updates available") % len(ups)
        else:
            title = _("Your apps are up to date")
        self.content.append(label(title, "list-heading"))
        if ups:
            lst = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            lst.add_css_class("row-list")
            for a in ups:
                lst.append(self._row(a, installed=False))
            self.content.append(lst)
        self.checked_lbl = label(self._checked_text(), "page-note")
        self.content.append(self.checked_lbl)
        srcs = sorted({_(SOURCES.get(a.source, a.source)) for a in st.installed()})
        if srcs:
            note = label(_("Updates are checked for apps from: %s.") % ", ".join(srcs), "page-note", wrap=True)
            self.content.append(note)
