"""Page base class. A page owns a vertical box inside the window's scroller and rebuilds it
when the catalogue changed (`dirty`) or it is shown for another argument."""
from __future__ import annotations

from gi.repository import Gtk

from ..i18n import _
from ..widgets import AppCard, button, card_grid, clear, icon, label

PAGE_STEP = 60  # cards added per "Show more"


class Page:
    id = ""
    nav = None          # navigation item highlighted while this page is shown
    title = ""

    def __init__(self, win):
        self.win = win
        self.store = win.store
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.box.add_css_class("page-body")
        self.box.set_valign(Gtk.Align.START)  # never stretch rows when the page is shorter than the window
        self.dirty = True
        self.arg = None
        self.scroller = None

    def tr_title(self):
        return _(self.title)

    def show(self, arg=None):
        if self.dirty or arg != self.arg:
            self.arg = arg
            self.dirty = False
            clear(self.box)
            self.build(arg)

    def build(self, arg):
        raise NotImplementedError

    def on_updates_changed(self):
        """Library/update state changed (installs, removals, update checks)."""

    def set_narrow(self, narrow):
        pass

    # helpers ----------------------------------------------------------
    def page_title(self, text, subtitle=None):
        head = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        head.add_css_class("page-head")
        head.append(label(text, "page-title", ellipsize=True))
        if subtitle:
            head.append(label(subtitle, "page-subtitle", wrap=True))
        self.box.append(head)
        return head

    def grid_of(self, apps, max_per_line=4, limit=None):
        grid = card_grid()
        grid.set_max_children_per_line(max_per_line)
        for a in (apps[:limit] if limit else apps):
            card = AppCard(self.win, a)
            card.set_size_request(200, 172)
            grid.append(card)
        return grid

    def paged_grid(self, parent, apps, max_per_line=6):
        """Grid that shows PAGE_STEP cards and a 'Show more' button for the rest."""
        grid = card_grid()
        grid.set_max_children_per_line(max_per_line)
        parent.append(grid)
        more = button("", "fluent-button show-more")
        more.set_halign(Gtk.Align.CENTER)
        state = {"n": 0}

        def add():
            n = state["n"]
            for a in apps[n:n + PAGE_STEP]:
                card = AppCard(self.win, a)
                card.set_size_request(200, 172)
                grid.append(card)
            state["n"] = min(len(apps), n + PAGE_STEP)
            left = len(apps) - state["n"]
            more.set_label(_("Show %d more") % min(left, PAGE_STEP))
            more.set_visible(left > 0)
        more.connect("clicked", lambda *_: add())
        parent.append(more)
        add()
        return grid

    def empty_state(self, icon_name, title, text=None):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, halign=Gtk.Align.CENTER)
        box.add_css_class("empty-state")
        box.append(icon(icon_name, 48, "empty-icon"))
        box.append(label(title, "empty-title", xalign=0.5, wrap=True))
        if text:
            lb = label(text, "empty-text", xalign=0.5, wrap=True)
            lb.set_justify(Gtk.Justification.CENTER)
            box.append(lb)
        self.box.append(box)
        return box

    def chips(self, options, selected, on_select):
        """Single row of filter chips (scrolls sideways when narrow): options = [(id, label)]."""
        row = Gtk.Box(spacing=8)
        row.add_css_class("chip-row")
        group = None
        for oid, text in options:
            b = Gtk.ToggleButton(label=text)
            b.add_css_class("filter-chip")
            if group is None:
                group = b
            else:
                b.set_group(group)
            b.set_active(oid == selected)
            b.connect("toggled", lambda btn, oid=oid: btn.get_active() and on_select(oid))
            row.append(b)
        sc = Gtk.ScrolledWindow()
        sc.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        sc.set_propagate_natural_height(True)
        sc.set_child(row)
        sc.add_css_class("chip-scroll")
        return sc
