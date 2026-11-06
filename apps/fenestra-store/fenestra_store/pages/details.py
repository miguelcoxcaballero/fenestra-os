"""App page: header with actions and progress, screenshots, description, details, permissions,
other apps by the same developer. No ratings: Fenestra Store has no review source yet."""
from __future__ import annotations

from gi.repository import Gtk

from .. import util
from ..i18n import N_, _
from ..model import CATEGORY_TITLES, PERMISSIONS, SOURCES
from ..widgets import ActionArea, Carousel, app_icon, button, chip, clear, icon, label, section_header, source_badge
from .base import Page


class DetailsPage(Page):
    id = "details"
    nav = None
    title = N_("App")

    def tr_title(self):
        app = self.store.get(self.arg)
        return app.name if app else ""

    def show(self, arg=None):
        # always rebuild: state, sizes and permissions may have changed since last time
        self.dirty = True
        super().show(arg)

    def build(self, uid):
        app = self.store.get(uid)
        self.action = None
        self.remove_btn = None
        if app is None:
            self.empty_state("st-warning-symbolic", _("This app is no longer available"))
            return
        self.app = app
        self.store.load_details(uid)
        self.win.watch(uid, self)

        # ------------------------------------------------------------ header card
        head = Gtk.Box(spacing=24)
        head.add_css_class("app-head")
        self.head_icon = app_icon(app, 96)
        self.head_icon.set_halign(Gtk.Align.START)
        self.head_icon.set_valign(Gtk.Align.START)
        head.append(self.head_icon)
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True, valign=Gtk.Align.CENTER)
        info.append(label(app.name, "app-title", wrap=True))
        if app.developer:
            dev = Gtk.Button(label=app.developer)
            dev.add_css_class("hyperlink")
            dev.set_halign(Gtk.Align.START)
            dev.set_tooltip_text(_("Search for apps by this developer"))
            dev.connect("clicked", lambda *_: self.win.search_for(app.developer))
            info.append(dev)
        info.append(label(app.summary, "app-summary", wrap=True))
        chips = Gtk.Box(spacing=6, margin_top=6)
        chips.append(source_badge(app))
        chips.append(chip(_("Flatpak") if app.packaging == "flatpak" else _("RPM package")))
        for c in app.categories[:2]:
            chips.append(chip(_(CATEGORY_TITLES.get(c, c))))
        info.append(chips)
        head.append(info)
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, valign=Gtk.Align.CENTER)
        side.add_css_class("app-head-side")
        self.action = ActionArea(self.win, app)
        self.action.set_halign(Gtk.Align.END)
        side.append(self.action)
        self.remove_btn = button(_("Uninstall"), "fluent-button", lambda: self.win.confirm_remove(app.uid),
                                 "st-trash-symbolic")
        self.remove_btn.set_halign(Gtk.Align.END)
        side.append(self.remove_btn)
        self.state_line = label("", "caption", xalign=1.0)
        side.append(self.state_line)
        head.append(side)
        self.head = head
        self.head_side = side
        self.box.append(head)

        alts = self.store.alternatives(app)
        if alts:
            row = Gtk.Box(spacing=8)
            row.add_css_class("alt-row")
            row.append(label(_("Also available from"), "caption"))
            for alt in alts:
                b = Gtk.Button()
                b.add_css_class("hyperlink")
                b.set_label(_(SOURCES.get(alt.source, alt.source)) +
                            (" · " + (_("Flatpak") if alt.packaging == "flatpak" else _("RPM package"))))
                b.connect("clicked", lambda _b, u=alt.uid: self.win.show_app(u, record=False))
                row.append(b)
            self.box.append(row)

        # ------------------------------------------------------------ screenshots
        if app.screenshots:
            self.carousel = Carousel(app)
            self.box.append(self.carousel)

        # ------------------------------------------------------------ description + side cards
        self.columns = Gtk.Box(spacing=24)
        self.columns.add_css_class("detail-columns")
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, hexpand=True)
        left.append(label(_("About this app"), "section-title"))
        for para in app.description or [app.summary]:
            lb = label(para, "desc-bullet" if para.startswith("• ") else "desc-text", wrap=True)
            lb.set_selectable(True)
            left.append(lb)
        self.columns.append(left)
        self.right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.right.set_size_request(320, -1)
        self.columns.append(self.right)
        self.box.append(self.columns)
        self._fill_side(app)

        # ------------------------------------------------------------ same developer
        others = self.store.by_developer(app)
        if others:
            self.box.append(section_header(_("Other apps by %s") % app.developer))
            self.box.append(self.grid_of(others, 4, 8))
        self.sync(app)
        self.set_narrow(self.win.narrow)

    def _fill_side(self, app):
        clear(self.right)
        self.right.append(label(_("Details"), "section-title"))
        card = Gtk.Grid(column_spacing=16, row_spacing=10)
        card.add_css_class("info-card")
        rows = [
            (_("Version"), app.version + (f"  →  {app.update_version}" if app.has_update and
                                          app.update_version != "*" else "")),
            (_("Updated"), app.released),
            (_("Download size"), util.human_size(app.download_size) if not app.installed else ""),
            (_("Installed size"), util.human_size(app.installed_size)),
            (_("License"), app.license or _("Unknown")),
            (_("Source"), _(SOURCES.get(app.source, app.source)) + (f" ({app.origin})" if app.origin and
                                                                    app.origin.lower() != app.source else "")),
            (_("Format"), _("Flatpak") if app.packaging == "flatpak" else _("RPM package")),
            (_("Developer"), app.developer),
        ]
        r = 0
        for k, v in rows:
            if not v:
                continue
            card.attach(label(k, "info-key"), 0, r, 1, 1)
            val = label(v, "info-value", wrap=True)
            val.set_selectable(True)
            card.attach(val, 1, r, 1, 1)
            r += 1
        if app.homepage:
            link = Gtk.LinkButton(uri=app.homepage, label=_("Website"))
            link.add_css_class("hyperlink")
            link.set_halign(Gtk.Align.START)
            if util.DEMO or util.READ_ONLY:
                link.set_sensitive(False)
            card.attach(label(_("Website"), "info-key"), 0, r, 1, 1)
            card.attach(link, 1, r, 1, 1)
        self.right.append(card)

        self.right.append(label(_("Permissions"), "section-title"))
        perm = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        perm.add_css_class("info-card")
        if app.packaging != "flatpak":
            perm.append(self._perm_row("st-perm-shield-symbolic",
                                       _("Not sandboxed"),
                                       _("System packages can use everything your account can."), True))
        elif app.permissions is None:
            perm.append(label(_("Loading…"), "caption"))
        else:
            for key in app.permissions:
                text, icon_name, sensitive = PERMISSIONS.get(key, (key, "st-perm-shield-symbolic", False))
                perm.append(self._perm_row(icon_name, _(text), None, sensitive))
        self.right.append(perm)

    @staticmethod
    def _perm_row(icon_name, title, sub, warn):
        row = Gtk.Box(spacing=12)
        row.add_css_class("perm-row")
        row.append(icon(icon_name, 16, "perm-icon warn" if warn else "perm-icon"))
        tb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        tb.append(label(title, "perm-title", wrap=True))
        if sub:
            tb.append(label(sub, "caption", wrap=True))
        row.append(tb)
        return row

    # window watcher protocol
    def sync(self, app):
        if getattr(self, "app", None) is not app or self.remove_btn is None:
            return
        self.remove_btn.set_visible(app.installed and not app.busy)
        if app.busy:
            self.state_line.set_label("")
        elif app.installed:
            size = util.human_size(app.installed_size)
            self.state_line.set_label(_("Installed") + (f" · {size}" if size else ""))
        else:
            size = util.human_size(app.download_size)
            self.state_line.set_label(_("Download: %s") % size if size else "")
        self._fill_side(app)

    def progress(self, frac, text):
        pass

    def set_narrow(self, narrow):
        cols = getattr(self, "columns", None)
        if cols is None:
            return
        cols.set_orientation(Gtk.Orientation.VERTICAL if narrow else Gtk.Orientation.HORIZONTAL)
        self.right.set_size_request(-1 if narrow else 320, -1)
        self.head.set_orientation(Gtk.Orientation.VERTICAL if narrow else Gtk.Orientation.HORIZONTAL)
        self.head_side.set_halign(Gtk.Align.START if narrow else Gtk.Align.FILL)
        for w in (self.action, self.remove_btn):
            w.set_halign(Gtk.Align.START if narrow else Gtk.Align.END)
        self.state_line.set_xalign(0.0 if narrow else 1.0)
