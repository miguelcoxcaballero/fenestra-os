"""Page base class."""
from __future__ import annotations

from gi.repository import Gtk


class Page(Gtk.Box):
    pid = ""
    title = ""
    searchable = True
    has_toolbar = True

    def __init__(self, win):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.win = win
        self.filter = ""
        self.add_css_class("page")
        self.add_css_class(f"page-{self.pid}")

    def tools(self):
        return []

    def update(self, snap):
        pass

    def set_filter(self, text):
        self.filter = text.strip().lower()

    def shown(self):
        pass

    def more_menu(self, menu):
        pass


def scrolled(child, hpolicy=Gtk.PolicyType.AUTOMATIC):
    sw = Gtk.ScrolledWindow()
    sw.set_policy(hpolicy, Gtk.PolicyType.AUTOMATIC)
    sw.set_overlay_scrolling(True)
    sw.set_child(child)
    sw.set_vexpand(True)
    sw.set_hexpand(True)
    return sw
