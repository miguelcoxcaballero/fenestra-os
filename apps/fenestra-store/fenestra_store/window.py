"""Main window: title bar with the search box, navigation rail, page stack, dialogs, toasts."""
from __future__ import annotations

import weakref

from gi.repository import Gdk, GLib, Gtk

from . import util
from .i18n import _
from .pages.base import Page
from .pages.browse import BrowsePage, SearchPage
from .pages.details import DetailsPage
from .pages.home import HomePage
from .pages.library import LibraryPage
from .pages.sources import SourcesPage
from .widgets import Clamp, button, icon, label

NAV = [("home", "st-home-symbolic", "Home"), ("apps", "st-apps-symbolic", "Apps"),
       ("games", "st-games-symbolic", "Games"), ("library", "st-library-symbolic", "Library")]
NAV_BOTTOM = [("sources", "st-sources-symbolic", "Sources")]
COMPACT_WIDTH = 900
NARROW_CONTENT = 760

OK_TEXT = {"install": "%s is installed", "remove": "%s was uninstalled", "update": "%s is up to date"}
FAIL_TEXT = {"install": "Could not install %s", "remove": "Could not uninstall %s", "update": "Could not update %s"}


class StoreWindow(Gtk.ApplicationWindow):
    def __init__(self, app, store, start_page="home", start_arg=None):
        super().__init__(application=app)
        self.store = store
        self.set_title(_("Fenestra Store"))
        self.set_icon_name("org.fenestra.Store")
        self.set_default_size(1180, 760)
        self.set_size_request(560, 480)
        self.add_css_class("fenestra-store")
        self.pages: dict[str, Page] = {}
        self.history: list[tuple[str, object]] = []
        self.current = None
        self.current_arg = None
        self.dialog = None
        self.narrow = False
        self._compact = None
        self._watchers: dict[str, list] = {}
        self._search_timer = 0
        self._search_return = None
        self._start = (start_page, start_arg)

        # ------------------------------------------------------------- title bar
        handle = Gtk.WindowHandle()
        tbox = Gtk.Box(spacing=0)
        tbox.add_css_class("titlebar-box")
        self.back_btn = button("", "back-button", self.go_back, "st-back-symbolic", _("Back"))
        self.back_btn.set_sensitive(False)
        tbox.append(self.back_btn)
        app_icon = icon("org.fenestra.Store", 16, "title-icon")
        tbox.append(app_icon)
        tbox.append(label(_("Fenestra Store"), "title-label"))
        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text(_("Search apps and games"))
        self.search.add_css_class("store-search")
        self.search.set_valign(Gtk.Align.CENTER)
        self.search.set_hexpand(False)
        self.search.set_size_request(380, -1)
        self.search.connect("changed", self._on_search_changed)
        self.search.connect("activate", lambda *_: self._run_search())
        self.search.connect("stop-search", lambda *_: self.search.set_text(""))
        tbox.append(self.search)
        tbox.append(Gtk.Box(hexpand=True))
        if util.DEMO:
            pill = label(_("Demo"), "demo-pill")
            pill.set_valign(Gtk.Align.CENTER)
            pill.set_tooltip_text(_("Sample catalogue: nothing on this computer is changed"))
            tbox.append(pill)
        controls = Gtk.WindowControls(side=Gtk.PackType.END)
        controls.add_css_class("window-controls")
        tbox.append(controls)
        handle.set_child(tbox)
        self.set_titlebar(handle)

        # ------------------------------------------------------------- body
        self.overlay = Gtk.Overlay()
        self.set_child(self.overlay)
        body = Gtk.Box()
        body.add_css_class("window-body")
        self.overlay.set_child(body)

        self.nav = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.nav.add_css_class("nav-pane")
        self.nav_rows = {}
        top = Gtk.ListBox()
        top.add_css_class("nav-list")
        bottom = Gtk.ListBox()
        bottom.add_css_class("nav-list")
        for lst, items in ((top, NAV), (bottom, NAV_BOTTOM)):
            for pid, icon_name, title in items:
                lst.append(self._nav_row(pid, icon_name, _(title)))
            lst.connect("row-activated", lambda _l, row: self.navigate(row.page_id))
        self.nav_lists = (top, bottom)
        self.nav.append(top)
        self.nav.append(Gtk.Box(vexpand=True))
        self.nav.append(bottom)
        body.append(self.nav)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        content.add_css_class("content-area")
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=140)
        self.stack.set_vexpand(True)
        self.stack.set_hhomogeneous(False)
        self.stack.set_vhomogeneous(False)
        content.append(self.stack)
        body.append(content)

        loading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, valign=Gtk.Align.CENTER,
                          halign=Gtk.Align.CENTER)
        sp = Gtk.Spinner(spinning=True)
        sp.set_size_request(32, 32)
        sp.add_css_class("fluent-spinner")
        loading.append(sp)
        loading.append(label(_("Loading the catalogue…"), "caption", xalign=0.5))
        self.stack.add_named(loading, "loading")

        self.smoke = Gtk.Box()
        self.smoke.add_css_class("smoke")
        self.smoke.set_visible(False)
        self.overlay.add_overlay(self.smoke)
        self.toast_box = Gtk.Revealer(transition_type=Gtk.RevealerTransitionType.CROSSFADE)
        self.toast_box.set_halign(Gtk.Align.CENTER)
        self.toast_box.set_valign(Gtk.Align.END)
        self.toast_lbl = label("", "toast", wrap=True)
        self.toast_box.set_child(self.toast_lbl)
        self.toast_box.set_can_target(False)
        self.overlay.add_overlay(self.toast_box)
        self._toast_timer = 0

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)

        store.connect("loaded", self._on_loaded)
        store.connect("app-changed", self._on_app_changed)
        store.connect("progress", self._on_progress)
        store.connect("job-done", self._on_job_done)
        store.connect("updates-changed", self._on_updates_changed)
        if store.loaded:
            self._on_loaded(store)

    # ----------------------------------------------------------------- navigation rail
    def _nav_row(self, pid, icon_name, title):
        row = Gtk.ListBoxRow()
        row.page_id = pid
        row.add_css_class("nav-item")
        row.set_tooltip_text(title)
        ov = Gtk.Overlay()
        box = Gtk.Box(spacing=14)
        box.add_css_class("nav-item-box")
        box.append(icon(icon_name, 18, "nav-icon"))
        lb = label(title, "nav-label", ellipsize=True)
        lb.set_hexpand(True)
        box.append(lb)
        badge = label("", "nav-badge", xalign=0.5)
        badge.set_valign(Gtk.Align.CENTER)
        badge.set_visible(False)
        box.append(badge)
        row.nav_label = lb
        row.badge = badge
        ov.set_child(box)
        pill = Gtk.Box()
        pill.add_css_class("nav-pill")
        pill.set_halign(Gtk.Align.START)
        pill.set_valign(Gtk.Align.CENTER)
        pill.set_size_request(3, 16)
        ov.add_overlay(pill)
        row.set_child(ov)
        self.nav_rows[pid] = row
        return row

    def _select_nav(self, nav_id):
        for lst in self.nav_lists:
            lst.unselect_all()
        row = self.nav_rows.get(nav_id)
        if row is not None:
            row.get_parent().select_row(row)

    def set_compact(self, compact):
        if compact == self._compact:
            return
        self._compact = compact
        (self.nav.add_css_class if compact else self.nav.remove_css_class)("compact")
        for row in self.nav_rows.values():
            row.nav_label.set_visible(not compact)
        self._update_badge()

    # ----------------------------------------------------------------- layout
    def do_size_allocate(self, w, h, b):
        Gtk.ApplicationWindow.do_size_allocate(self, w, h, b)
        compact = w < COMPACT_WIDTH
        narrow = w - (64 if compact else 232) < NARROW_CONTENT
        if compact != self._compact or narrow != self.narrow:
            GLib.idle_add(self._apply_layout, compact, narrow)

    def _apply_layout(self, compact, narrow):
        self.set_compact(compact)
        self.search.set_size_request(220 if compact else 380, -1)
        if narrow != self.narrow:
            self.narrow = narrow
            for p in self.pages.values():
                p.set_narrow(narrow)
        return False

    # ----------------------------------------------------------------- pages
    def _make_page(self, pid) -> Page | None:
        if pid == "home":
            return HomePage(self)
        if pid in ("apps", "games", "category"):
            return BrowsePage(self, pid)
        if pid == "search":
            return SearchPage(self)
        if pid == "details":
            return DetailsPage(self)
        if pid == "library":
            return LibraryPage(self)
        if pid == "sources":
            return SourcesPage(self)
        return None

    def get_page(self, pid) -> Page | None:
        if pid not in self.pages:
            page = self._make_page(pid)
            if page is None:
                return None
            scroller = Gtk.ScrolledWindow()
            scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scroller.add_css_class("page-scroll")
            scroller.set_child(Clamp(page.box, 1240))
            page.scroller = scroller
            self.pages[pid] = page
            self.stack.add_named(scroller, pid)
            page.set_narrow(self.narrow)
        return self.pages[pid]

    def navigate(self, pid, arg=None, record=True):
        if pid == "updates":
            pid, arg = "library", "updates"
        if not self.store.loaded:
            self._start = (pid, arg)
            return
        page = self.get_page(pid)
        if page is None:
            util.log("unknown page", pid)
            return
        if self.current == pid and arg == self.current_arg and not page.dirty and pid != "details":
            return
        if record and self.current is not None and self.current != "search":
            self.history.append((self.current, self.current_arg))
            del self.history[:-50]
        if pid != "search" and self.search.get_text():
            self._search_return = None
            self.search.set_text("")
            self._cancel_search_timer()
        self.current, self.current_arg = pid, arg
        self.back_btn.set_sensitive(bool(self.history))
        page.show(arg)
        self._select_nav(page.nav)
        page.scroller.get_vadjustment().set_value(0)
        self.stack.set_visible_child_name(pid)

    def show_app(self, uid, record=True):
        self.navigate("details", uid, record)

    def go_back(self):
        if not self.history:
            return
        pid, arg = self.history.pop()
        self.navigate(pid, arg, record=False)
        self.back_btn.set_sensitive(bool(self.history))

    def catalogue_changed(self):
        """Sources changed: rebuild every page next time it is shown, refresh the current one."""
        for p in self.pages.values():
            p.dirty = True
        if self.current:
            cur, arg = self.current, self.current_arg
            self.current = None
            self.navigate(cur, arg, record=False)

    # ----------------------------------------------------------------- search
    def _on_search_changed(self, entry):
        self._cancel_search_timer()
        self._search_timer = GLib.timeout_add(150, self._run_search)

    def _cancel_search_timer(self):
        if self._search_timer:
            GLib.source_remove(self._search_timer)
            self._search_timer = 0

    def _run_search(self):
        self._search_timer = 0
        text = self.search.get_text().strip()
        if not self.store.loaded:
            return False
        if text:
            if self.current != "search":
                self._search_return = (self.current, self.current_arg)
            page = self.get_page("search")
            page.dirty = True
            self.navigate("search", text, record=False)
        elif self.current == "search":
            pid, arg = self._search_return or ("home", None)
            self._search_return = None
            self.navigate(pid, arg, record=False)
        return False

    def search_for(self, text):
        self.search.set_text(text)
        self._cancel_search_timer()
        self._run_search()

    def _on_key(self, _c, keyval, _code, state):
        ctrl = state & Gdk.ModifierType.CONTROL_MASK
        alt = state & Gdk.ModifierType.ALT_MASK
        if ctrl and keyval in (Gdk.KEY_f, Gdk.KEY_k):
            self.search.grab_focus()
            return True
        if alt and keyval == Gdk.KEY_Left:
            self.go_back()
            return True
        if keyval == Gdk.KEY_Escape and self.dialog is not None:
            self.close_dialog()
            return True
        return False

    # ----------------------------------------------------------------- store events
    def watch(self, uid, widget):
        """widget.sync(app) on state changes, widget.progress(frac, text) while an operation runs."""
        lst = self._watchers.setdefault(uid, [])
        lst[:] = [r for r in lst if r() is not None]
        lst.append(weakref.ref(widget))

    def _live(self, uid):
        out = []
        for r in self._watchers.get(uid, []):
            w = r()
            if w is not None:
                out.append(w)
        return out

    def open_target(self, pid, arg, record=True):
        """Open a page from the command line: page id + argument, or ("app", id/package/name)."""
        if not self.store.loaded:
            self._start = (pid, arg)
            return
        if pid == "app":
            st = self.store
            app = st.get(arg) or next((a for a in st.catalogue() if arg in (a.app_id, a.pkgname, a.name)), None)
            if app is not None:
                self.navigate("details", app.uid, record)
                return
            self.toast(_("No app called “%s” was found") % arg)
            pid, arg = "home", None
        self.navigate(pid or "home", arg, record)

    def _on_loaded(self, store):
        for p in self.pages.values():
            p.dirty = True
        self._update_badge()
        pid, arg = self._start
        self._start = ("home", None)
        self.current = None
        self.open_target(pid, arg, record=False)
        if self.search.get_text():
            self._run_search()

    def _on_app_changed(self, store, uid):
        app = store.get(uid)
        for w in self._live(uid):
            w.sync(app)

    def _on_progress(self, store, uid, frac, text):
        for w in self._live(uid):
            w.progress(frac, text)

    def _on_updates_changed(self, store):
        self._update_badge()
        lib = self.pages.get("library")
        if lib is not None:
            if self.current == "library":
                lib.on_updates_changed()
            else:
                lib.dirty = True

    def _update_badge(self):
        row = self.nav_rows.get("library")
        if row is None:
            return
        n = len(self.store.updates()) if self.store.loaded else 0
        row.badge.set_label(str(n))
        row.badge.set_visible(n > 0 and not self._compact)
        row.set_tooltip_text(_("Library") + (f" ({_('%d updates') % n})" if n else ""))

    def _on_job_done(self, store, uid, op, ok, msg):
        app = store.get(uid)
        name = app.name if app else uid
        if ok:
            self.toast(_(OK_TEXT[op]) % name)
        else:
            self.toast((_(FAIL_TEXT[op]) % name) + (": " + self.explain(msg) if msg else ""), 6000)

    def explain(self, msg):
        if msg == "read-only":
            return _("read-only mode, nothing was changed")
        if msg == "source-disabled":
            return _("its source is turned off")
        return msg

    # ----------------------------------------------------------------- actions
    def launch(self, uid):
        app = self.store.get(uid)
        if app is None:
            return
        if util.DEMO:
            self.toast(_("%s would open now (demo mode)") % app.name)
            return
        if not self.store.launch(uid):
            self.toast(_("Could not open %s") % app.name)

    def confirm_remove(self, uid):
        app = self.store.get(uid)
        if app is None:
            return
        extra = _("Your files and settings for it are kept in your home folder.")
        self.show_dialog(_("Uninstall %s?") % app.name, extra, _("Uninstall"), lambda: self.store.remove(uid))

    # ----------------------------------------------------------------- dialogs / toasts
    def show_dialog(self, title, text, ok_label, on_ok):
        self.close_dialog()
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.add_css_class("content-dialog")
        card.set_halign(Gtk.Align.CENTER)
        card.set_valign(Gtk.Align.CENTER)
        card.set_size_request(420, -1)
        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        body.add_css_class("dialog-body")
        body.append(label(title, "dialog-title", wrap=True))
        body.append(label(text, "dialog-text", wrap=True))
        card.append(body)
        foot = Gtk.Box(spacing=8, homogeneous=True)
        foot.add_css_class("dialog-footer")

        def ok():
            self.close_dialog()
            on_ok()
        okb = button(ok_label, "fluent-button accent", ok)
        foot.append(okb)
        foot.append(button(_("Cancel"), "fluent-button", self.close_dialog))
        card.append(foot)
        card.confirm = ok
        self.smoke.set_visible(True)
        self.overlay.add_overlay(card)
        self.dialog = card
        okb.grab_focus()

    def close_dialog(self):
        if self.dialog is not None:
            self.overlay.remove_overlay(self.dialog)
            self.dialog = None
            self.smoke.set_visible(False)

    def toast(self, text, ms=3500):
        self.toast_lbl.set_label(text)
        self.toast_box.set_reveal_child(True)
        if self._toast_timer:
            GLib.source_remove(self._toast_timer)

        def hide():
            self._toast_timer = 0
            self.toast_box.set_reveal_child(False)
            return False
        self._toast_timer = GLib.timeout_add(ms, hide)
