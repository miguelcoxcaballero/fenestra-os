"""Home, Apps and Games showcases: the hero (one large rotating banner and three tiles), a row
of category chips on Apps, and pairs of panels that list apps three at a time."""
from __future__ import annotations

from gi.repository import Gtk

from .. import util
from ..i18n import N_, _
from ..model import CATEGORIES, CATEGORY_TITLES
from ..widgets import Hero, Panel, icon, label, panel_pair
from .base import Page


def hero_apps(st, games=None, n=7):
    """Featured apps first, then the most popular ones, without repeats."""
    out = []
    for a in [x for x in st.featured() if games is None or x.is_game == games] + st.popular(games=games):
        if a not in out:
            out.append(a)
    return out[:n]


class ShowcasePage(Page):
    """kind: 'home', 'apps' or 'games'."""

    def __init__(self, win, kind="home"):
        super().__init__(win)
        self.kind = kind
        self.id = kind
        self.nav = kind
        self.title = {"home": N_("Home"), "apps": N_("Apps"), "games": N_("Games")}[kind]
        self.box.add_css_class("showcase")
        self.banner = None

    def build(self, arg):
        st = self.store
        self.banner = None
        if not st.backends:
            self.page_title(_(self.title))
            self.empty_state("st-warning-symbolic", _("No software sources are available"),
                             _("Install flatpak-libs or PackageKit to browse and install apps."))
            return
        games = {"home": None, "apps": False, "games": True}[self.kind]
        if not st.popular(games=games):
            self.page_title(_(self.title))
            self.empty_state("st-apps-symbolic", _("The catalogue is empty"),
                             _("Turn on a source in Sources, or check your internet connection."))
            return
        apps = hero_apps(st, games)
        if apps:
            rotate = not getattr(self.win.get_application(), "screenshot", None)
            self.banner = Hero(self.win, apps, rotate=rotate)
            self.box.append(self.banner)
        if self.kind == "apps":
            self.box.append(self._category_chips())
        pop = st.has_popularity
        pairs = []
        if self.kind == "home":
            pairs.append(((_("Popular apps") if pop else _("Recommended apps"), st.popular(games=False),
                           lambda: self.win.navigate("apps")),
                          (_("Popular games") if pop else _("Recommended games"), st.popular(games=True),
                           lambda: self.win.navigate("games"))))
            pairs.append(((_("New and updated"), st.new_and_updated(games=False), None),
                          (_("New games"), st.new_and_updated(games=True), None)))
        elif self.kind == "apps":
            pairs.append(((_("Popular apps") if pop else _("Recommended apps"), st.popular(games=False), None),
                          (_("New and updated"), st.new_and_updated(games=False), None)))
        else:
            pairs.append(((_("Popular games") if pop else _("Recommended games"), st.popular(games=True), None),
                          (_("New games"), st.new_and_updated(games=True), None)))
        if self.kind != "games":
            cats = [(k, t) for k, t, _i in CATEGORIES if k != "games" and len(st.by_category(k)) >= 2]
            for i in range(0, len(cats), 2):
                pair = []
                for k, t in cats[i:i + 2]:
                    pair.append((_(t), st.by_category(k), lambda k=k: self.win.navigate("category", k)))
                pairs.append(tuple(pair))
        for pair in pairs:
            panels = [Panel(self.win, t, a, cb) for t, a, cb in pair if a]
            if not panels:
                continue
            self.box.append(panel_pair(self.win, panels[0], panels[1] if len(panels) > 1 else None))
        util.log(f"{self.kind} built")

    def _category_chips(self):
        row = Gtk.Box(spacing=12)
        row.add_css_class("category-chips")
        for key, title, icon_name in CATEGORIES:
            if key == "games" or not self.store.by_category(key):
                continue
            b = Gtk.Button()
            b.add_css_class("category-chip")
            inner = Gtk.Box(spacing=8)
            inner.append(icon(icon_name, 16, "category-chip-icon"))
            inner.append(label(_(title)))
            b.set_child(inner)
            b.connect("clicked", lambda _b, k=key: self.win.navigate("category", k))
            row.append(b)
        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.EXTERNAL, Gtk.PolicyType.NEVER)
        sc.set_propagate_natural_height(True)
        sc.set_child(row)
        sc.add_css_class("chip-scroll")
        return sc

    def set_narrow(self, narrow):
        if self.banner is not None:
            self.banner.set_narrow(narrow)


class HomePage(ShowcasePage):
    id = "home"

    def __init__(self, win):
        super().__init__(win, "home")


__all__ = ["HomePage", "ShowcasePage", "CATEGORY_TITLES"]
