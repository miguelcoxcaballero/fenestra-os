"""App page: header with actions and progress, screenshots, description, details, permissions,
other apps by the same developer. No ratings: Fenestra Store has no review source yet."""
from __future__ import annotations

from gi.repository import Gtk

from .. import util
from ..i18n import N_, _
from ..model import CATEGORY_TITLES, PERMISSIONS, SOURCES
from ..widgets import ActionArea, Carousel, app_icon, button, clear, icon, label, status_text
from .base import Page


class DetailsPage(Page):
    id = "details"
    nav = None
    title = N_("App")
    max_width = 100000

    def __init__(self, win):
        super().__init__(win)
        self.box.add_css_class("details")

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

        # ------------------------------------------------------------ header (over a gradient of the app's colour)
        head = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        head.add_css_class("app-head")
        self._tint(head, app)
        top = Gtk.Box(spacing=0)
        self.head_icon = app_icon(app, 84)
        self.head_icon.set_valign(Gtk.Align.START)
        self.head_icon.add_css_class("app-head-icon")
        top.append(self.head_icon)
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0, hexpand=True)
        info.add_css_class("app-head-info")
        info.append(label(app.name, "app-title", wrap=True))
        if app.developer:
            dev = Gtk.Button(label=app.developer)
            dev.add_css_class("dev-link")
            dev.set_halign(Gtk.Align.START)
            dev.set_tooltip_text(_("Search for apps by this developer"))
            dev.connect("clicked", lambda *_: self.win.search_for(app.developer))
            info.append(dev)
        meta = Gtk.Box(spacing=0)
        meta.add_css_class("app-meta")
        meta.append(label(_(SOURCES.get(app.source, app.source)), "app-meta-text"))
        sep = Gtk.Box()
        sep.add_css_class("meta-sep")
        meta.append(sep)
        meta.append(label(_("Flatpak") if app.packaging == "flatpak" else _("RPM package"), "app-meta-text"))
        for c in app.categories[:1]:
            sep = Gtk.Box()
            sep.add_css_class("meta-sep")
            meta.append(sep)
            cb = Gtk.Button(label=_(CATEGORY_TITLES.get(c, c)))
            cb.add_css_class("meta-link")
            if c == "games":
                cb.connect("clicked", lambda *_: self.win.navigate("games"))
            else:
                cb.connect("clicked", lambda _b, c=c: self.win.navigate("category", c))
            meta.append(cb)
        info.append(meta)
        top.append(info)
        head.append(top)
        summ = label(app.summary, "app-summary", wrap=True)
        summ.set_max_width_chars(62)
        head.append(summ)
        actions = Gtk.Box(spacing=0)
        actions.add_css_class("app-actions")
        self.action = ActionArea(self.win, app, big=True)
        actions.append(self.action)
        self.remove_btn = button("", "icon-action", lambda: self.win.confirm_remove(app.uid), "st-trash-symbolic",
                                 _("Uninstall"))
        self.remove_btn.set_valign(Gtk.Align.CENTER)
        actions.append(self.remove_btn)
        head.append(actions)
        src = Gtk.Box(spacing=0)
        src.add_css_class("source-block")
        mark = Gtk.Box()
        mark.add_css_class("source-mark")
        mark.add_css_class(f"badge-{app.source}")
        mark.append(icon("st-perm-shield-symbolic" if app.packaging != "flatpak" else "st-sources-symbolic", 20))
        mark.set_valign(Gtk.Align.CENTER)
        src.append(mark)
        st = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        st.append(label(_("From %s") % _(SOURCES.get(app.source, app.source)), "source-block-title"))
        self.state_line = label("", "source-block-text")
        st.append(self.state_line)
        st.append(label(app.license or _("Unknown licence"), "source-block-text"))
        src.append(st)
        head.append(src)
        self.head = head
        self.box.append(head)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        body.add_css_class("app-body")
        self.box.append(body)

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
            body.append(row)

        # ------------------------------------------------------------ screenshots
        if app.screenshots:
            self.carousel = Carousel(app)
            body.append(self._section(_("Screenshots"), self.carousel, chevron=True))

        # ------------------------------------------------------------ description, details, permissions
        desc = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        for para in app.description or [app.summary]:
            lb = label(para, "desc-bullet" if para.startswith("• ") else "desc-text", wrap=True)
            lb.set_selectable(True)
            desc.append(lb)
        body.append(self._section(_("Description"), desc))
        self.details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        body.append(self._section(_("Details"), self.details_box))
        self.perm_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        body.append(self._section(_("Permissions"), self.perm_box))
        self.right = self.details_box
        self._fill_side(app)

        # ------------------------------------------------------------ same developer
        others = self.store.by_developer(app)
        if others:
            body.append(self._section(_("Other apps by %s") % app.developer, self.grid_of(others, 3, 6)))
        self.sync(app)
        self.set_narrow(self.win.narrow)

    def _section(self, title, child, chevron=False):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.add_css_class("section-card")
        head = Gtk.Box()
        head.add_css_class("section-card-head")
        head.append(label(title, "section-card-title", ellipsize=True, xalign=0.0))
        head.get_first_child().set_hexpand(True)
        if chevron:
            ch = icon("st-chevron-right-symbolic", 16, "section-card-chevron")
            ch.set_valign(Gtk.Align.CENTER)
            head.append(ch)
        card.append(head)
        div = Gtk.Box()
        div.add_css_class("section-card-divider")
        card.append(div)
        child.add_css_class("section-card-body")
        card.append(child)
        return card

    _tint_providers: dict = {}

    def _tint(self, widget, app):
        """Gradient from the app's colour (top) to the page background, as a per-page provider."""
        from .. import art, theme
        hue, _g = art.art_for(app)
        dark = theme.get().dark
        r, g, b = (int(v * 255) for v in art.rgb(hue, 0.30 if dark else 0.86, 0.45 if dark else 0.9))
        name = "app-tint-%d" % (round(hue * 360) % 360) + ("-d" if dark else "-l")
        widget.add_css_class(name)
        if name not in self._tint_providers:
            prov = Gtk.CssProvider()
            prov.load_from_string(f".app-head.{name} {{ background-image: linear-gradient(to bottom, "
                                  f"rgb({r},{g},{b}) 0px, rgba({r},{g},{b},0.55) 250px, "
                                  f"rgba({r},{g},{b},0) 420px); }}")
            from gi.repository import Gdk
            Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), prov,
                                                      Gtk.STYLE_PROVIDER_PRIORITY_USER + 3)
            self._tint_providers[name] = prov

    def _fill_side(self, app):
        clear(self.details_box)
        clear(self.perm_box)
        card = Gtk.Grid(column_spacing=24, row_spacing=10)
        card.add_css_class("info-grid")
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
        cells = []
        for k, v in rows:
            if v:
                val = label(v, "info-value", wrap=True)
                val.set_selectable(True)
                cells.append((k, val))
        if app.homepage:
            link = Gtk.LinkButton(uri=app.homepage, label=_("Website"))
            link.add_css_class("hyperlink")
            link.set_halign(Gtk.Align.START)
            if util.DEMO or util.READ_ONLY:
                link.set_sensitive(False)
            cells.append((_("Website"), link))
        cols = 1 if getattr(self.win, "narrow", False) else 3
        for i, (k, w) in enumerate(cells):
            col, row = i % cols, i // cols
            cell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
            cell.append(label(k, "info-key"))
            cell.append(w)
            card.attach(cell, col, row, 1, 1)
        self.details_box.append(card)

        if app.packaging != "flatpak":
            self.perm_box.append(self._perm_row("st-perm-shield-symbolic",
                                                _("Not sandboxed"),
                                                _("System packages can use everything your account can."), True))
        elif app.permissions is None:
            self.perm_box.append(label(_("Loading…"), "caption"))
        else:
            for key in app.permissions:
                text, icon_name, sensitive = PERMISSIONS.get(key, (key, "st-perm-shield-symbolic", False))
                self.perm_box.append(self._perm_row(icon_name, _(text), None, sensitive))

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
            self.state_line.set_label(status_text(app))
        elif app.installed:
            size = util.human_size(app.installed_size)
            self.state_line.set_label(_("Installed") + (f" · {size}" if size else ""))
        else:
            size = util.human_size(app.download_size)
            self.state_line.set_label(_("Download: %s") % size if size else _("Free"))
        self._fill_side(app)

    def progress(self, frac, text):
        pass

    def set_narrow(self, narrow):
        super().set_narrow(narrow)
        head = getattr(self, "head", None)
        if head is None:
            return
        (head.add_css_class if narrow else head.remove_css_class)("narrow")
        body = head.get_next_sibling()
        if body is not None:
            (body.add_css_class if narrow else body.remove_css_class)("narrow")
