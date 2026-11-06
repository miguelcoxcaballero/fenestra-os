"""Page base class and registry."""
from __future__ import annotations

from gi.repository import Gtk

from .. import util
from ..backends import session
from ..i18n import _
from ..widgets import Group, SettingRow, label

PAGES: dict[str, type["Page"]] = {}
# Pages that exist in the code but not in this session (backends/session.py); never shown,
# searched or linked to.
HIDDEN_PAGES: dict[str, type["Page"]] = {}

# Top level navigation order.
NAV_ORDER = ["home", "system", "devices", "network", "personalization", "apps", "accounts",
             "time", "gaming", "accessibility", "privacy", "update", "fenestra"]


def register(cls):
    if cls.id in session.hidden_pages() or (cls.parent and cls.parent in HIDDEN_PAGES):
        HIDDEN_PAGES[cls.id] = cls
    else:
        PAGES[cls.id] = cls
    return cls


def visible_ancestor(page_id):
    """page_id itself when it is shown, else its nearest shown parent (None if unknown)."""
    seen = set()
    while page_id and page_id not in PAGES and page_id not in seen:
        seen.add(page_id)
        cls = HIDDEN_PAGES.get(page_id)
        page_id = cls.parent if cls else None
    return page_id if page_id in PAGES else None


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
            self._hide_session_rows()
        return self.widget

    def hidden_keys(self) -> set[str]:
        return session.hidden_rows(self.id)

    def _hide_session_rows(self):
        """Hide rows that do not work in this session (backends/session.py), and groups left
        with nothing to show because of that."""
        hidden = self.hidden_keys()
        groups = []
        stack = [self.widget]
        while stack:
            w = stack.pop()
            if isinstance(w, Group):
                groups.append(w)
            if hidden and getattr(w, "key", None) in hidden:
                w.set_visible(False)
                w.session_hidden = True
                continue
            c = w.get_first_child()
            while c is not None:
                stack.append(c)
                c = c.get_next_sibling()
        for g in groups:
            g.hidden_keys = hidden
            kids, c = [], g.rows.get_first_child()
            while c is not None:
                kids.append(c)
                c = c.get_next_sibling()
            if kids and any(getattr(k, "session_hidden", False) for k in kids) \
                    and not any(k.get_visible() for k in kids):
                g.set_visible(False)

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
        g.hidden_keys = self.hidden_keys()  # rows added later (async loads) are hidden too
        self.box.append(g)
        return g

    @staticmethod
    def _session_hide(r):
        r.set_visible(False)
        r.session_hidden = True
        return r

    def nav_row(self, group, target, title, subtitle=None, icon_name=None, key=None, focus=None):
        """Row that opens another page (and highlights row ``focus`` there). Hidden when that
        page, or that row, does not exist in this session."""
        r = SettingRow(title, subtitle, icon_name, chevron=True,
                       on_click=lambda: self.go(target, focus), key=key or target)
        group.add(r)
        if key or target:
            self._rows[key or target] = r
        if target not in PAGES or (focus and focus in session.hidden_rows(target)):
            self._session_hide(r)
        return r

    def ext_row(self, group, title, subtitle, icon_name, argv, key=None):
        """Row that opens an external tool (GNOME panel / extension prefs). In the Fenestra
        session GNOME panels open their Fenestra counterpart, or the row is hidden."""
        target = session.launch_target(argv)
        if target is None:
            r = SettingRow(title, subtitle, icon_name, key=key)
            group.add(r)
            if key:
                self._rows[key] = r
            return self._session_hide(r)
        if target[0] == "page":
            r = self.nav_row(group, target[1], title, subtitle, icon_name, key=key or f"ext-{target[1]}")
            return r
        argv = target[1]
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
