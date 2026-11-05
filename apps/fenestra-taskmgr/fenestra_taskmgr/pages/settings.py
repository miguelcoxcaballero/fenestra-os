"""Settings page (Windows 11 Task Manager settings, the parts that make sense here)."""
from __future__ import annotations

from gi.repository import Gdk, Gtk

from .. import theme, util
from ..i18n import _
from ..widgets.common import Menu, icon, label
from .base import Page


class Clamp(Gtk.Widget):
    __gtype_name__ = "FenestraTaskClamp"

    def __init__(self, child, maximum=1250, margin=24):
        super().__init__()
        self.child, self.maximum, self.margin = child, maximum, margin
        child.set_parent(self)

    def do_measure(self, orientation, for_size):
        if orientation == Gtk.Orientation.HORIZONTAL:
            mn, nat, _a, _b = self.child.measure(orientation, -1)
            return mn + 2 * self.margin, nat + 2 * self.margin, -1, -1
        fs = min(self.maximum, for_size - 2 * self.margin) if for_size > 0 else -1
        mn, nat, _a, _b = self.child.measure(orientation, fs)
        return mn, nat, -1, -1

    def do_size_allocate(self, w, h, b):
        cw = max(0, min(self.maximum, w - 2 * self.margin))
        alloc = Gdk.Rectangle()
        alloc.x, alloc.y, alloc.width, alloc.height = int((w - cw) / 2), 0, int(cw), h
        self.child.size_allocate(alloc, -1)


SPEED_NAMES = [("high", "High"), ("normal", "Normal"), ("low", "Low"), ("paused", "Paused")]
THEME_NAMES = [("system", "Use system setting"), ("light", "Light"), ("dark", "Dark")]
START_PAGES = [("processes", "Processes"), ("performance", "Performance"), ("apphistory", "App history"),
               ("startup", "Startup apps"), ("users", "Users"), ("details", "Details"), ("services", "Services")]


class SettingsPage(Page):
    pid = "settings"
    title = _("Settings")
    searchable = False
    has_toolbar = False

    def __init__(self, win):
        super().__init__(win)
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_vexpand(True)
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        col.add_css_class("settings-column")
        col.append(label(_("Settings"), "settings-title"))
        col.append(label(_("Appearance"), "settings-section"))
        col.append(self._combo_card("tm-palette-symbolic", _("App theme"), _("Select which app theme to display"),
                                    THEME_NAMES, "theme", self._theme))
        col.append(label(_("General"), "settings-section"))
        col.append(self._combo_card("tm-start-page-symbolic", _("Default start page"),
                                    _("Specify which page is visible when launching Task Manager"),
                                    START_PAGES, "start_page"))
        col.append(self._combo_card("tm-speed-symbolic", _("Real time update speed"),
                                    _("Choose how often to update the system resource usage report"),
                                    SPEED_NAMES, "speed", lambda v: win.app.set_speed(v)))
        col.append(self._expander("tm-windows-symbolic", _("Window management"),
                                  _("Specify default Task Manager window behavior"), "wm_open",
                                  [("always_on_top", _("Always on top")), ("minimize_on_use", _("Minimize on use")),
                                   ("hide_when_minimized", _("Hide when minimized"))]))
        col.append(self._expander("tm-options-symbolic", _("Other options"),
                                  _("Show full account name, show history for all processes, confirmation "
                                    "dialog settings"), "other_open",
                                  [("full_account_name", _("Show full account name")),
                                   ("history_all", _("Show history for all processes")),
                                   ("ask_efficiency", _("Ask me before applying Efficiency mode"))]))
        clamp = Clamp(col, 1250, 24)
        clamp.add_css_class("settings-page")
        sw.set_child(clamp)
        self.append(sw)

    def _card(self, icon_name, title, sub):
        card = Gtk.Box()
        card.add_css_class("card")
        card.append(icon(icon_name, 20, "card-icon"))
        t = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        t.set_valign(Gtk.Align.CENTER)
        t.append(label(title, "card-title"))
        t.append(label(sub, "card-sub", ellipsize=True))
        t.set_hexpand(True)
        card.append(t)
        return card

    def _combo_card(self, icon_name, title, sub, choices, key, on_change=None):
        card = self._card(icon_name, title, sub)
        btn = Gtk.Button()
        btn.add_css_class("combo")
        btn.set_valign(Gtk.Align.CENTER)
        btn.set_hexpand(False)
        btn.set_halign(Gtk.Align.END)
        bx = Gtk.Box(spacing=16)
        cur = dict(choices).get(util.opts()[key], choices[0][1])
        lb = label(_(cur))
        bx.append(lb)
        bx.append(icon("tm-chevron-down-symbolic", 12))
        btn.set_child(bx)

        def pick(val, text):
            util.opts().set(key, val)
            lb.set_text(_(text))
            if on_change:
                on_change(val)

        def open_menu(*_a):
            m = Menu(btn)
            for val, text in choices:
                m.add(_(text), lambda v=val, t=text: pick(v, t), check=util.opts()[key] == val)
            m.set_position(Gtk.PositionType.BOTTOM)
            m.popup()
        btn.connect("clicked", open_menu)
        card.append(btn)
        return card

    def _expander(self, icon_name, title, sub, key, options):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        head = self._card(icon_name, title, sub)
        head.add_css_class("expander-head")
        arrow = Gtk.Button()
        arrow.add_css_class("flat-icon")
        arrow.set_valign(Gtk.Align.CENTER)
        img = icon("tm-chevron-up-symbolic", 12)
        arrow.set_child(img)
        head.append(arrow)
        box.append(head)
        subs = []
        for i, (opt, text) in enumerate(options):
            row = Gtk.Box()
            row.add_css_class("card")
            row.add_css_class("sub")
            if i == len(options) - 1:
                row.add_css_class("last")
            cb = Gtk.CheckButton(label=text)
            cb.add_css_class("fluent-check")
            cb.set_active(util.opts()[opt])
            cb.connect("toggled", lambda b, o=opt: self._toggle(o, b.get_active()))
            row.append(cb)
            box.append(row)
            subs.append(row)

        def apply(open_):
            for r in subs:
                r.set_visible(open_)
            img.set_from_icon_name("tm-chevron-up-symbolic" if open_ else "tm-chevron-down-symbolic")
            if open_:
                head.remove_css_class("collapsed")
            else:
                head.add_css_class("collapsed")

        def flip(*_a):
            util.opts().set(key, not util.opts()[key])
            apply(util.opts()[key])
        arrow.connect("clicked", flip)
        click = Gtk.GestureClick()
        click.connect("released", flip)
        head.add_controller(click)
        apply(util.opts()[key])
        return box

    def _toggle(self, opt, val):
        util.opts().set(opt, val)
        if opt in ("full_account_name",) and self.win.pages.get("users") and self.win.snap:
            self.win.pages["users"].update(self.win.snap)

    def _theme(self, val):
        theme.get().apply()
