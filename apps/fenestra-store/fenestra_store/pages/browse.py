"""Apps, Games and single-category pages, and live search results."""
from __future__ import annotations

from gi.repository import GLib, Gtk

from .. import util
from ..i18n import N_, _
from ..model import CATEGORIES, CATEGORY_TITLES
from ..widgets import clear, label
from .base import Page

SORTS = [("popular", N_("Most popular")), ("name", N_("Name")), ("recent", N_("Recently updated"))]
SORTS_NO_STATS = [("popular", N_("Recommended")), ("name", N_("Name")), ("recent", N_("Recently updated"))]


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
        sorts = SORTS if self.store.has_popularity else SORTS_NO_STATS
        model = Gtk.StringList.new([_(t) for _k, t in sorts])
        dd = Gtk.DropDown(model=model)
        dd.add_css_class("fluent-dropdown")
        dd.set_tooltip_text(_("Sort by"))
        dd.set_selected([k for k, _t in SORTS].index(self.sort))
        dd.connect("notify::selected", lambda d, *_: self._set_sort(SORTS[d.get_selected()][0]))
        self.page_title(self.tr_title(), end=dd)
        if self.kind == "apps":
            opts = [("all", _("All"))] + [(k, _(t)) for k, t, _i in CATEGORIES
                                          if k != "games" and self.store.by_category(k)]
            self.box.append(self.chips(opts, self.filter, self._set_filter))
        self.count = label("", "caption count-line")
        self.count.set_visible(False)
        self.results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.results_box.add_css_class("results")
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
        self.page_title("“%s”" % self.query)
        opts = [("all", _("All departments")), ("apps", _("Apps")), ("games", _("Games"))]
        self.box.append(self.chips(opts, self.kind, self._set_kind))
        self.count = label("", "caption count-line")
        self.count.set_visible(False)
        self.results_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.results_box.add_css_class("results")
        self.box.append(self.results_box)
        self._fill()

    def _fill(self):
        clear(self.results_box)
        self.results = self.store.search(self.query, None if self.kind == "all" else self.kind)
        n = len(self.results)
        self.count.set_label(_("%d results") % n if n != 1 else _("1 result"))
        self.packages = []
        self._gen = getattr(self, "_gen", 0) + 1
        everything = self.kind == "all" and not util.DEMO
        if self.results:
            self.paged_grid(self.results_box, self.results)
        # Everything else that can be installed: the package managers' own search (every RPM of
        # the repositories, every snap), under the apps. Asked once the text has settled.
        self.more_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.results_box.append(self.more_box)
        if everything:
            self.more_box.append(label(_("Searching every package…"), "caption count-line"))
            GLib.timeout_add(350, self._search_packages, self._gen, self.query)
        elif not self.results:
            self._empty()

    def _empty(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, halign=Gtk.Align.CENTER)
        box.add_css_class("empty-state")
        box.append(label(_("No apps match “%s”") % self.query, "empty-title", xalign=0.5, wrap=True))
        box.append(label(_("Check the spelling or try a shorter word."), "empty-text", xalign=0.5, wrap=True))
        self.more_box.append(box)

    def _search_packages(self, gen, query):
        if gen == self._gen:
            self.store.search_packages(query, lambda _text, apps: self._packages(gen, apps))
        return False

    def _packages(self, gen, apps):
        if gen != self._gen:
            return   # the text changed meanwhile
        clear(self.more_box)
        shown = {a.uid for a in self.results}
        self.packages = [a for a in apps if a.uid not in shown]
        # The package called exactly what was typed is the answer, wherever the apps rank.
        q = util.fold(self.query).strip()
        exact = [a for a in self.packages if q in (util.fold(a.name), util.fold(a.pkgname))]
        # ...unless the catalogue already has an app by that name (its listing is the better card).
        if exact and self.results and not any(util.fold(a.name) == q for a in self.results):
            self.packages = [a for a in self.packages if a not in exact]
            top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            self.paged_grid(top, exact)
            self.results_box.prepend(top)
        n = len(self.results) + len(apps)
        self.count.set_label(_("%d results") % n if n != 1 else _("1 result"))
        if self.packages:
            self.more_box.append(label(_("Packages and tools (%d)") % len(self.packages), "section-title", xalign=0))
            self.paged_grid(self.more_box, self.packages)
        elif not self.results:
            self._empty()

    def _set_kind(self, k):
        self.kind = k
        self._fill()
