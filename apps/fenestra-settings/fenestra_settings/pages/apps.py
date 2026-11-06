"""Apps: installed apps, default apps, startup apps."""
from __future__ import annotations

from gi.repository import GLib, Gtk

from .. import util
from ..backends import apps as appsb
from ..backends import session
from ..i18n import N_, _
from ..widgets import (ContentDialog, Dropdown, SettingRow, ToggleSwitch, clear, icon, label,
                       show_dialog, toast)
from .base import Page, register


def app_icon(gicon, size=24):
    img = Gtk.Image.new_from_gicon(gicon) if gicon else icon("fs-app-generic-symbolic")
    img.set_pixel_size(size)
    return img


@register
class AppsPage(Page):
    id = "apps"
    title = "Apps"
    keywords = "applications programs software uninstall default startup"
    ROWS = [
        ("installed", N_("Installed apps"), N_("Uninstall and manage apps on your PC"), "fs-apps-list-symbolic"),
        ("defaultapps", N_("Default apps"), N_("Defaults for file and link types, other defaults"),
         "fs-app-generic-symbolic"),
        ("startup", N_("Startup"), N_("Apps that start automatically when you sign in"), "fs-rocket-symbolic"),
    ]

    def build(self, box):
        g = self.group()
        for pid, t, s, ic in self.ROWS:
            self.nav_row(g, pid, _(t), _(s), ic)
        self.ext_row(g, _("Advanced app settings"), _("Permissions, storage and default handlers per app"),
                     "fs-options-symbolic", ["gnome-control-center", "applications"], key="advanced-apps")
        if util.have("gnome-software"):
            self.ext_row(g, _("Get more apps"), _("Browse and install apps from the Software center"),
                         "fs-arrow-download-symbolic", ["gnome-software"])


@register
class InstalledAppsPage(Page):
    id = "installed"
    parent = "apps"
    title = "Installed apps"
    keywords = "uninstall remove programs list software size"
    index = [("search-apps", "Search apps", "find program")]

    SORTS = [("name", N_("Name (A to Z)")), ("name-desc", N_("Name (Z to A)")),
             ("size", N_("Size (large to small)")), ("date", N_("Install date (newest)"))]
    FILTERS = [("all", N_("All apps")), ("rpm", N_("System packages")), ("flatpak", N_("Flatpak")),
               ("user", N_("User apps"))]

    def build(self, box):
        bar = Gtk.Box(spacing=12)
        bar.add_css_class("apps-toolbar")
        self.search = Gtk.Entry()
        self.search.add_css_class("fluent-entry")
        self.search.set_placeholder_text(_("Search apps"))
        self.search.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "fs-search-symbolic")
        self.search.set_size_request(280, -1)
        self.search.connect("changed", lambda *_: self._schedule())
        self.search.key = "search-apps"
        self._rows["search-apps"] = self.search
        bar.append(self.search)
        sp = Gtk.Box(hexpand=True)
        bar.append(sp)
        box.append(bar)
        bar2 = Gtk.Box(spacing=8)
        bar2.set_margin_top(12)
        bar2.append(label(_("Sort by:"), "caption"))
        self.sort = Dropdown([(k, _(v)) for k, v in self.SORTS], "name", lambda _v: self._fill())
        self.sort.add_css_class("flat")
        self.sort.ui_only = "sorts the list (not a setting)"
        bar2.append(self.sort)
        bar2.append(label(_("Filter by:"), "caption"))
        self.filt = Dropdown([(k, _(v)) for k, v in self.FILTERS], "all", lambda _v: self._fill())
        self.filt.ui_only = "filters the list (not a setting)"
        bar2.append(self.filt)
        box.append(bar2)
        self.count = label("", "caption")
        self.count.set_margin_top(12)
        self.count.set_margin_bottom(8)
        box.append(self.count)
        self.list = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.append(self.list)
        self.apps = appsb.installed()
        self._timer = 0
        self._fill()
        appsb.enrich(self.apps, self._fill)

    def _schedule(self):
        if self._timer:
            GLib.source_remove(self._timer)
        self._timer = GLib.timeout_add(150, self._fill_timer)

    def _fill_timer(self):
        self._timer = 0
        self._fill()
        return False

    def _fill(self):
        q = self.search.get_text().lower().strip()
        f = self.filt.selected_id()
        items = [a for a in self.apps if (not q or q in a.name.lower() or q in a.id.lower())
                 and (f == "all" or a.source == f)]
        s = self.sort.selected_id()
        if s == "name-desc":
            items.sort(key=lambda a: a.name.lower(), reverse=True)
        elif s == "size":
            items.sort(key=lambda a: -(a.size or 0))
        elif s == "date":
            items.sort(key=lambda a: -(a.date or 0))
        else:
            items.sort(key=lambda a: a.name.lower())
        self.count.set_label(_("{0} apps found").format(len(items)))
        clear(self.list)
        for a in items:
            self.list.append(self._row(a))

    def _row(self, a):
        parts = []
        if a.publisher:
            parts.append(a.publisher)
        if a.date:
            parts.append(GLib.DateTime.new_from_unix_local(a.date).format("%x"))
        if not parts:
            parts.append({"flatpak": "Flatpak", "user": _("User app"), "rpm": _("System package")}[a.source])
        ctrl = Gtk.Box(spacing=12)
        if a.size:
            ctrl.append(label(util.human_size(a.size), "row-value"))
        mb = Gtk.MenuButton()
        mb.set_icon_name("fs-more-horizontal-symbolic")
        mb.add_css_class("more-button")
        mb.set_valign(Gtk.Align.CENTER)
        pop = Gtk.Popover()
        pop.add_css_class("fluent-popover")
        pop.set_has_arrow(False)
        pb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        items = [(_("Open"), lambda: appsb.launch_app(a), True)]
        if session.panel_available("applications"):
            items.append((_("Advanced options"), lambda: session.open_panel("applications", self.window), True))
        items.append((_("Uninstall"), lambda: self._uninstall(a), a.source != "user"))
        for text, cb, sensitive in items:
            b = Gtk.Button(label=text)
            b.add_css_class("menu-item")
            b.set_sensitive(sensitive)
            b.connect("clicked", lambda _b, cb=cb: (pop.popdown(), cb()))
            pb.append(b)
        pop.set_child(pb)
        mb.set_popover(pop)
        ctrl.append(mb)
        return SettingRow(a.name, " | ".join(parts), image=app_icon(a.icon, 24), control=ctrl)

    def _uninstall(self, a):
        def go(resp):
            if resp != "primary":
                return
            if util.READ_ONLY:
                toast(self.box, _("This action is disabled in read-only mode"))
                return
            toast(self.box, _("Uninstalling {0}…").format(a.name), ms=8000)

            def done(ok, msg):
                if ok:
                    toast(self.box, _("{0} was uninstalled").format(a.name))
                    self.apps = [x for x in self.apps if x is not a]
                    self._fill()
                else:
                    toast(self.box, _("Couldn't uninstall {0}").format(a.name))
            appsb.uninstall(a, done)
        body = _("This app and its related info will be uninstalled.")
        if a.source == "rpm" and a.package:
            body += "\n" + _("Package: {0}").format(a.package)
        dlg = ContentDialog(_("Uninstall {0}?").format(a.name), body, primary=_("Uninstall"),
                            close=_("Cancel"), on_response=go)
        show_dialog(self.box, dlg)


@register
class DefaultAppsPage(Page):
    id = "defaultapps"
    parent = "apps"
    title = "Default apps"
    keywords = "browser email music video photo pdf default handler open with"
    index = [("default-web", "Web browser", "default browser"), ("default-mail", "Email", "mail client")]

    def build(self, box):
        g = self.group(_("Set defaults for applications"))
        labels = {"web": N_("Web browser"), "mail": N_("Email"), "music": N_("Music player"),
                  "video": N_("Video player"), "photos": N_("Photo viewer"), "pdf": N_("PDF viewer"),
                  "text": N_("Text editor"), "files": N_("File manager"), "calendar": N_("Calendar")}
        icons = {"web": "fs-globe-symbolic", "mail": "fs-mail-symbolic", "music": "fs-music-note-2-symbolic",
                 "video": "fs-video-symbolic", "photos": "fs-image-symbolic", "pdf": "fs-document-symbolic",
                 "text": "fs-edit-symbolic", "files": "fs-folder-symbolic", "calendar": "fs-calendar-symbolic"}
        for key, _title, mime, extra in appsb.DEFAULT_TYPES:
            cands = appsb.candidates_for(mime)
            if util.DEMO:
                cands = [c for c in cands if (getattr(c, "get_filename", lambda: "")() or "").startswith("/usr/share/applications/")]
            cur = appsb.default_for(mime)
            if util.DEMO and cur is not None and cur.get_id() not in [c.get_id() for c in cands]:
                cur = cands[0] if cands else None
            if not cands:
                r = SettingRow(_(labels[key]), _("No apps installed for this type"), icons[key])
                g.add(r)
                continue
            opts = [(c.get_id(), c.get_display_name()) for c in cands]
            cur_id = cur.get_id() if cur else None
            if cur_id is None:
                opts.insert(0, ("", _("Choose a default")))
                cur_id = ""
            by_id = {c.get_id(): c for c in cands}

            def changed(v, mime=mime, extra=extra, by_id=by_id):
                if v in by_id and not appsb.set_default(by_id[v], [mime] + extra):
                    toast(self.box, _("This action is disabled in read-only mode") if util.READ_ONLY
                          else _("Couldn't change the default app"))
            dd = Dropdown(opts, cur_id, changed, width=220)
            img = app_icon(cur.get_icon() if cur else None, 24) if cur else icon(icons[key], 20, "row-icon")
            r = SettingRow(_(labels[key]), cur.get_display_name() if cur else None, image=img, control=dd,
                           key=f"default-{key}")
            if key in ("web", "mail"):
                self.remember(f"default-{key}", r)
            g.add(r)
        g2 = self.group(_("Related settings"))
        self.ext_row(g2, _("Choose defaults by file type"), None, "fs-document-symbolic",
                     ["gnome-control-center", "applications"])


@register
class StartupPage(Page):
    id = "startup"
    parent = "apps"
    title = "Startup"
    keywords = "autostart login boot apps"

    def build(self, box):
        box.append(label(_("Apps can be configured to start when you log in. In most cases, they'll start "
                           "minimized or might only start a background task."), "page-intro", wrap=True))
        g = self.group()
        g.set_margin_top(12)
        entries = appsb.startup_entries()
        if not entries:
            g.add(SettingRow(_("No startup apps"), None, "fs-rocket-symbolic"))
        for e in entries:
            if e.nodisplay and not e.comment:
                continue
            t = ToggleSwitch(e.enabled, lambda v, e=e: self._set(e, v))
            img = Gtk.Image.new_from_icon_name(e.icon or "fs-app-generic-symbolic")
            img.set_pixel_size(24)
            g.add(SettingRow(e.name, e.comment or None, image=img, control=t))
        g2 = self.group(_("Related settings"))
        if util.have("gnome-tweaks"):
            self.ext_row(g2, _("Add startup apps"), _("Tweaks › Startup Applications"), "fs-options-symbolic",
                         ["gnome-tweaks"])

    def _set(self, e, v):
        if not appsb.set_startup_enabled(e, v):
            toast(self.box, _("This action is disabled in read-only mode") if util.READ_ONLY
                  else _("Couldn't change this startup app"))

