"""Sources: Flathub on/off (Flatpak remotes) and Fedora repositories (PackageKit)."""
from __future__ import annotations

from gi.repository import Gtk

from .. import util
from ..i18n import N_, _
from ..widgets import ToggleSwitch, button, icon, label
from .base import Page


class SourcesPage(Page):
    id = "sources"
    nav = "sources"
    title = N_("Sources")

    def build(self, arg):
        st = self.store
        self.page_title(_("Sources"), _("Where Fenestra Store finds apps. Changes ask for your password."))
        if util.DEMO:
            self.box.append(self._info(_("Demo mode: sample apps only, nothing on this computer is changed.")))
        srcs = st.sources()
        flathub = [s for s in srcs if s.kind == "flathub"]
        fedora = [s for s in srcs if s.kind == "fedora"]

        self.box.append(label(_("Flatpak apps"), "section-title"))
        group = self._group()
        if "flatpak" not in st.backends and not util.DEMO:
            group.append(self._row("st-perm-shield-symbolic", _("Flatpak is not available"),
                                   _("Install the flatpak-libs package to use Flathub."), None))
        elif not flathub:
            add = button(_("Add Flathub"), "fluent-button accent", self._add_flathub)
            group.append(self._row("st-download-symbolic", "Flathub",
                                   _("Thousands of apps from their developers, run in a sandbox."), add))
        for s in flathub:
            group.append(self._source_row(s, _("Apps from their developers, run in a sandbox.")))
        self.box.append(group)

        self.box.append(label(_("Fedora repositories"), "section-title"))
        group = self._group()
        if "packagekit" not in st.backends and not util.DEMO:
            group.append(self._row("st-perm-shield-symbolic", _("PackageKit is not available"),
                                   _("Install PackageKit to manage apps from the Fedora repositories."), None))
        for s in fedora:
            group.append(self._source_row(s, s.description if s.description and s.description != s.id else ""))
        self.box.append(group)

        self.box.append(label(_("How apps are installed"), "section-title"))
        self.box.append(self._info(_("Flatpak apps come from Flathub and run in a sandbox with the permissions "
                                     "shown on their page. RPM packages come from the Fedora repositories and "
                                     "are installed through PackageKit. Both ask for your permission through the "
                                     "system; Fenestra Store itself never runs as administrator.")))
        names = ", ".join(b.label for b in st.backends.values()) or _("none")
        self.box.append(label(_("Active backends: %s") % names, "page-note"))

    def _group(self):
        g = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        g.add_css_class("row-list")
        return g

    def _info(self, text):
        box = Gtk.Box(spacing=12)
        box.add_css_class("infobar")
        box.append(icon("st-info-symbolic", 16, "infobar-icon"))
        lb = label(text, None, wrap=True)
        lb.set_hexpand(True)
        box.append(lb)
        return box

    def _row(self, icon_name, title, sub, suffix):
        row = Gtk.Box(spacing=16)
        row.add_css_class("setting-row")
        row.append(icon(icon_name, 20, "row-icon"))
        tb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, hexpand=True)
        tb.append(label(title, "row-title", wrap=True))
        if sub:
            tb.append(label(sub, "row-subtitle", wrap=True))
        row.append(tb)
        if suffix is not None:
            suffix.set_valign(Gtk.Align.CENTER)
            row.append(suffix)
        return row

    def _source_row(self, src, sub):
        def toggled(on, src=src):
            sw.set_sensitive(False)

            def done(ok, msg):
                sw.set_sensitive(src.can_toggle)
                sw.set_active(src.enabled)
                if not ok:
                    self.win.toast(_("Could not change %s: %s") % (src.title, self.win.explain(msg)))
                else:
                    self.win.catalogue_changed()
            self.store.set_source_enabled(src, on, done)
        sw = ToggleSwitch(src.enabled, toggled)
        sw.set_sensitive(src.can_toggle)
        name = "st-download-symbolic" if src.kind == "flathub" else "st-library-symbolic"
        return self._row(name, src.title, sub, sw)

    def _add_flathub(self):
        be = self.store.backends.get("flatpak")
        if be is None or util.READ_ONLY:
            self.win.toast(self.win.explain("read-only"))
            return
        self.win.toast(_("Adding Flathub…"))

        def done(_r):
            self.win.toast(_("Flathub was added. Loading its apps…"))
            self.store.loaded = False
            self.store.load()

        util.in_thread(be.add_flathub, on_done=done,
                       on_error=lambda e: self.win.toast(_("Could not add Flathub: %s") % e))
