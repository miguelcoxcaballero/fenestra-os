"""Home: featured banner, category tiles, Popular, New and updated and one row per category."""
from __future__ import annotations

from gi.repository import Gtk

from .. import util
from ..i18n import N_, _
from ..model import CATEGORIES
from ..widgets import Banner, icon, label, section_header
from .base import Page


class HomePage(Page):
    id = "home"
    nav = "home"
    title = N_("Home")

    def build(self, arg):
        st = self.store
        self.banner = None
        if not st.backends:
            self.page_title(_("Home"))
            self.empty_state("st-warning-symbolic", _("No software sources are available"),
                             _("Install flatpak-libs or PackageKit to browse and install apps."))
            return
        if not st.catalogue():
            self.page_title(_("Home"))
            self.empty_state("st-apps-symbolic", _("The catalogue is empty"),
                             _("Turn on a source in Sources, or check your internet connection."))
            return
        featured = st.featured()
        if featured:
            self.banner = Banner(self.win, featured, rotate=not getattr(self.win.get_application(), "screenshot", None))
            self.box.append(self.banner)

        self.box.append(section_header(_("Browse by category")))
        tiles = Gtk.FlowBox()
        tiles.set_selection_mode(Gtk.SelectionMode.NONE)
        tiles.set_homogeneous(True)
        tiles.set_max_children_per_line(4)
        tiles.set_min_children_per_line(2)
        tiles.set_column_spacing(8)
        tiles.set_row_spacing(8)
        tiles.add_css_class("category-tiles")
        for key, title, icon_name in CATEGORIES:
            n = len(st.by_category(key))
            if not n:
                continue
            b = Gtk.Button()
            b.add_css_class("category-tile")
            inner = Gtk.Box(spacing=12)
            ic = icon(icon_name, 18, "category-icon")
            ic.set_valign(Gtk.Align.CENTER)
            inner.append(ic)
            texts = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
            texts.append(label(_(title), "category-name", ellipsize=True))
            texts.append(label(_("%d apps") % n if n != 1 else _("1 app"), "caption"))
            inner.append(texts)
            b.set_child(inner)
            target = ("games", None) if key == "games" else ("category", key)
            b.connect("clicked", lambda _b, t=target: self.win.navigate(*t))
            tiles.append(b)
        self.box.append(tiles)

        self._row(_("Popular apps"), st.popular(games=False), 8, lambda: self.win.navigate("apps"))
        self._row(_("New and updated"), st.new_and_updated(), 8, None)
        self._row(_("Popular games"), st.popular(games=True), 4, lambda: self.win.navigate("games"))
        for key, title, _i in CATEGORIES:
            if key == "games":
                continue
            apps = st.by_category(key)
            if len(apps) >= 2:
                self._row(_(title), apps, 4, lambda k=key: self.win.navigate("category", k))
        util.log("home built")

    def _row(self, title, apps, limit, see_all):
        if not apps:
            return
        self.box.append(section_header(title, see_all if len(apps) > limit else None))
        self.box.append(self.grid_of(apps, 4, limit))

    def set_narrow(self, narrow):
        if getattr(self, "banner", None) is not None:
            self.banner.set_narrow(narrow)
