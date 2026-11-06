"""Apps, Games and single-category pages, and live search results."""
from __future__ import annotations

from gi.repository import Gtk

from .. import util
from ..i18n import N_, _
from ..model import CATEGORIES, CATEGORY_TITLES
from ..widgets import clear, label
from .base import Page

SORTS = [("popular", N_("Most popular")), ("name", N_("Name")), ("recent", N_("Recently updated"))]


def sort_apps(apps, how):
    if how == "name":
        return sorted(apps, key=lambda a: util.fold(a.name))
    if how == "recent":
        return sorted(apps, key=lambda a: (a.released, a.popularity), reverse=True)
    return sorted(apps, key=lambda a: (-a.popularity, util.fold(a.name)))


class BrowsePage(Page):
    """kind: 'apps' (category chips), 'games', or 'category' (arg = category key)."""
    sort = "popular"
    filter = "all"

    def __init__(self, win, kind):
        super().__init__(win)
        self.kind = kind
        self.id = kind
        self.nav = {"apps": "apps", "games": "games"}.get(kind, "apps")
        self.title = {"apps": N_("Apps"), "games": N_("Games")}.get(kind, "")

    def tr_title(self):
        if self.kind == "category":
            return _(CATEGORY_TITLES.get(self.arg, ""))
        return _(self.title)

    def build(self, arg):
        self.page_title(self.tr_title())
        bar = Gtk.Box(spacing=12)
        bar.add_css_class("browse-bar")
        if self.kind == "apps":
            opts = [("all", _("All"))] + [(k, _(t)) for k, t, _i in CATEGORIES
                                          if k != "games" and self.store.by_category(k)]
            chips = self.chips(opts, self.filter, self._set_filter)
            chips.set_hexpand(True)
            bar.append(chips)
        else:
            bar.append(Gtk.Box(hexpand=True))
        bar.append(label(_("Sort by"), "caption"))
        model = Gtk.StringList.new([_(t) for _k, t in SORTS])
        dd = Gtk.DropDown(model=model)
        dd.add_css_class("fluent-dropdown")
        dd.set_valign(Gtk.Align.CENTER)
        dd.set_selected([k for k, _t in SORTS].index(self.sort))
        dd.connect("notify::selected", lambda d, *_: self._set_sort(SORTS[d.get_selected()][0]))
        bar.append(dd)
        self.box.append(bar)
        self.count = label("", "caption count-line")
        self.box.append(self.count)
        self.results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.box.append(self.results_box)
        self._fill()

    def _apps(self):
        st = self.store
        if self.kind == "games":
            return st.popular(games=True)
        if self.kind == "category":
            return st.by_category(self.arg)
        if self.filter != "all":
            return [a for a in st.by_category(self.filter) if not a.is_game]
        return st.popular(games=False)

    def _fill(self):
        clear(self.results_box)
        apps = sort_apps(self._apps(), self.sort)
        self.count.set_label(_("%d apps") % len(apps) if len(apps) != 1 else _("1 app"))
        self.paged_grid(self.results_box, apps)

    def _set_filter(self, f):
        self.filter = f
        self._fill()

    def _set_sort(self, s):
        if s != self.sort:
            self.sort = s
            self._fill()


class SearchPage(Page):
    id = "search"
    nav = None
    title = N_("Search")

    def __init__(self, win):
        super().__init__(win)
        self.kind = "all"
        self.results = []

    def build(self, arg):
        self.query = arg or ""
        self.page_title(_("Results for “%s”") % self.query)
        opts = [("all", _("All")), ("apps", _("Apps")), ("games", _("Games"))]
        self.box.append(self.chips(opts, self.kind, self._set_kind))
        self.count = label("", "caption count-line")
        self.box.append(self.count)
        self.results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.box.append(self.results_box)
        self._fill()

    def _fill(self):
        clear(self.results_box)
        self.results = self.store.search(self.query, None if self.kind == "all" else self.kind)
        n = len(self.results)
        self.count.set_label(_("%d results") % n if n != 1 else _("1 result"))
        if not self.results:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, halign=Gtk.Align.CENTER)
            box.add_css_class("empty-state")
            box.append(label(_("No apps match “%s”") % self.query, "empty-title", xalign=0.5, wrap=True))
            box.append(label(_("Check the spelling or try a shorter word."), "empty-text", xalign=0.5, wrap=True))
            self.results_box.append(box)
            return
        self.paged_grid(self.results_box, self.results)

    def _set_kind(self, k):
        self.kind = k
        self._fill()
