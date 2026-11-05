"""Page base class and registry."""
from __future__ import annotations

from gi.repository import Gtk

from .. import util
from ..i18n import _
from ..widgets import Group, SettingRow, label

PAGES: dict[str, type["Page"]] = {}

# Top level navigation order.
NAV_ORDER = ["home", "system", "devices", "network", "personalization", "apps", "accounts",
             "time", "gaming", "accessibility", "privacy", "update", "fenestra"]


def register(cls):
    PAGES[cls.id] = cls
    return cls


class Page:
    id = ""
    title = ""            # English source string, translated via _()
    parent: str | None = None
    icon = None
    keywords = ""         # extra search terms (English and translated both indexed)
    # Searchable rows: list of (row key, title, keywords)
    index: list[tuple[str, str, str]] = []

    def __init__(self, window):
        self.window = window
        self.widget: Gtk.Widget | None = None
        self._rows: dict[str, Gtk.Widget] = {}

    # -- helpers ---------------------------------------------------------------
    def tr_title(self):
        return _(self.title)

    def nav_root(self) -> str:
        p = self
        while p.parent:
            p = PAGES[p.parent]
        return p.id

    def get_widget(self) -> Gtk.Widget:
        if self.widget is None:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            box.add_css_class("page-body")
            self.box = box
            self.build(box)
            self.widget = box
        return self.widget

    def build(self, box: Gtk.Box):
        raise NotImplementedError

    def on_show(self):
        pass

    def go(self, page_id, key=None):
        self.window.navigate(page_id, key)

    def remember(self, key, widget):
        widget.key = key
        self._rows[key] = widget
        return widget

    def find_row(self, key):
        if key in self._rows:
            return self._rows[key]
        # Fallback: walk the tree for a widget with .key
        stack = [self.widget]
        while stack:
            w = stack.pop()
            if w is None:
                continue
            if getattr(w, "key", None) == key:
                return w
            c = w.get_first_child()
            while c is not None:
                stack.append(c)
                c = c.get_next_sibling()
        return None

    def group(self, title=None, css=None):
        g = Group(title, css)
        self.box.append(g)
        return g

    def nav_row(self, group, target, title, subtitle=None, icon_name=None, key=None):
        r = SettingRow(title, subtitle, icon_name, chevron=True,
                       on_click=lambda: self.go(target), key=key or target)
        group.add(r)
        if key or target:
            self._rows[key or target] = r
        return r

    def ext_row(self, group, title, subtitle, icon_name, argv, key=None):
        """Row that opens an external tool (GNOME panel / extension prefs)."""
        available = util.have(argv[0])

        def run():
            if not util.launch(argv):
                from ..widgets import toast
                toast(group, _("This action is disabled in read-only mode") if util.READ_ONLY
                      else _("Could not open {0}").format(argv[0]))
        r = SettingRow(title, subtitle if available else _("Not available"), icon_name,
                       external=available, on_click=run if available else None, key=key)
        if not available:
            r.add_css_class("dim")
        group.add(r)
        if key:
            self._rows[key] = r
        return r

    def related(self, items):
        """'Related settings' section: items = list of (title, subtitle, icon, callable)."""
        g = self.group(_("Related settings"))
        for t, s, ic, cb in items:
            g.add(SettingRow(t, s, ic, on_click=cb, chevron=True))
        return g

    def note(self, text):
        lb = label(text, "page-note", wrap=True)
        self.box.append(lb)
        return lb
