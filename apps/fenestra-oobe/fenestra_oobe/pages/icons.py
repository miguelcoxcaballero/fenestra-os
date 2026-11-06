""""Personalize your icons": default icons, own Windows partition, icon pack
zip from disk, or an icon pack downloaded through a small in-OOBE browser."""

import os
import re
import tempfile
import urllib.parse

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from .. import iconpack, paths
from ..backends import log, run_async
from ..i18n import _
from ..widgets.illustration import render_svg
from .base import Page

try:
    import gi
    gi.require_version("WebKit", "6.0")
    from gi.repository import WebKit
except (ImportError, ValueError):  # pragma: no cover - depends on the system
    WebKit = None

try:
    import gi
    gi.require_version("Soup", "3.0")
    from gi.repository import Soup
except (ImportError, ValueError):  # pragma: no cover
    Soup = None

RELEASES_URL = "https://github.com/miguelcoxcaballero/fenestra-os/releases"


def help_page_uri() -> str:
    from ..i18n import language
    path = paths.data_file("help", f"icon-packs.{language()}.html")
    if not os.path.exists(path):
        path = paths.data_file("help", "icon-packs.en.html")
    return GLib.filename_to_uri(path, None)


def _option_row(option_id, title, description):
    row = Gtk.ListBoxRow(css_classes=["option-row"])
    row.option_id = option_id
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, valign=Gtk.Align.CENTER)
    box.append(Gtk.Label(label=title, xalign=0, css_classes=["option-title"]))
    desc = Gtk.Label(label=description, xalign=0, wrap=True, css_classes=["option-desc"])
    desc.set_max_width_chars(52)
    box.append(desc)
    row.set_child(box)
    return row


class _BusyMixin:
    def _build_busy(self):
        from ..widgets.controls import RingSpinner
        self.busy_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER,
                                halign=Gtk.Align.CENTER, vexpand=True, visible=False, css_classes=["spinner-box"])
        self.ring = RingSpinner(64, 5)
        self.busy_box.append(self.ring)
        self.busy_label = Gtk.Label(css_classes=["spinner-caption"], wrap=True,
                                    justify=Gtk.Justification.CENTER)
        self.busy_label.set_max_width_chars(36)
        self.busy_box.append(self.busy_label)
        return self.busy_box

    def show_busy(self, text, content):
        self.busy_label.set_label(text)
        content.set_visible(False)
        self.busy_box.set_visible(True)
        self.title_label.set_visible(False)
        self.subtitle_label.set_visible(False)
        if not self.ctx.screenshot_mode:
            self.ring.start()
        self.set_busy(True)

    def hide_busy(self, content):
        self.ring.stop()
        self.busy_box.set_visible(False)
        content.set_visible(True)
        self.title_label.set_visible(True)
        self.subtitle_label.set_visible(bool(self.subtitle_label.get_label()))
        self.set_busy(False)


class IconsPage(_BusyMixin, Page):
    page_id = "icons"
    illustration = "icons"

    def __init__(self, ctx):
        super().__init__(ctx, _("Personalize your icons"),
                         _("Choose how your folders, apps and taskbar icons look. You can change this later "
                           "in Settings > Personalization > Themes."))
        self.primary_label = _("Next")
        self.listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE,
                                   css_classes=["oobe-list", "option-list"])
        self.listbox.connect("row-activated", lambda *_: self.on_primary())
        self.content = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True,
                                          child=self.listbox, css_classes=["oobe-list-frame"])
        self.body.append(self.content)
        self.error = Gtk.Label(xalign=0, wrap=True, css_classes=["error-text"], visible=False)
        self.body.append(self.error)
        self.body.append(self._build_busy())
        self._built_for = object()

    def _rebuild(self):
        root = self.ctx.other_system_root
        if self._built_for == root:
            return
        self._built_for = root
        while (r := self.listbox.get_row_at_index(0)) is not None:
            self.listbox.remove(r)
        rows = [_option_row("default", _("Fenestra default"),
                            _("Open-source icons designed for Fenestra."))]
        if root:
            rows.append(_option_row("windows", _("Import from my Windows partition"),
                                    _("Copy the icons, cursors and fonts from the Windows installation on "
                                      "this PC. Your Windows partition is only read.")))
        rows.append(_option_row("zip", _("Import an icon pack (.zip)"),
                                _("Use a pack made with Fenestra Icon Extractor, or any icon theme zip.")))
        rows.append(_option_row("link", _("Download an icon pack from a link"),
                                _("Paste a link to a pack you uploaded, for example to your cloud drive.")))
        for r in rows:
            self.listbox.append(r)
        self.listbox.select_row(rows[1] if root else rows[0])

    def selected(self):
        row = self.listbox.get_selected_row()
        return row.option_id if row is not None else "default"

    def select(self, option_id):
        i = 0
        while (r := self.listbox.get_row_at_index(i)) is not None:
            if r.option_id == option_id:
                self.listbox.select_row(r)
            i += 1

    def focus_widget(self):
        return self.listbox.get_selected_row()

    def on_enter(self, direction):
        self._rebuild()
        self.error.set_visible(False)

    def on_primary(self):
        if self.busy:
            return
        choice = self.selected()
        self.state.icon_choice = choice
        if choice == "default":
            if self.ctx.mode == "icons":
                self.backends.privacy.reset_icon_theme()
            self.ctx.next()
        elif choice == "windows":
            self.show_busy(_("Importing from your Windows partition…"), self.content)
            run_async(self.backends.privacy.run_import, self.ctx.other_system_root, callback=self._imported)
        elif choice == "zip":
            self._choose_zip()
        elif choice == "link":
            self.ctx.goto("icons-browser")

    def _imported(self, result, error):
        self.hide_busy(self.content)
        if error is not None or result == "missing-helper":
            self.error.set_label(_("Some items couldn't be imported. You can try again later from Settings.")
                                 if error is not None else _("The import tool isn't installed."))
            self.error.set_visible(True)
            return
        self.ctx.next()

    def _choose_zip(self):
        dialog = Gtk.FileDialog(title=_("Choose an icon pack"), modal=True)
        flt = Gtk.FileFilter()
        flt.set_name(_("Icon packs (*.zip)"))
        flt.add_suffix("zip")
        flt.add_mime_type("application/zip")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(flt)
        dialog.set_filters(filters)
        dialog.set_default_filter(flt)
        dl = paths.downloads_dir()
        if os.path.isdir(dl):
            dialog.set_initial_folder(Gio.File.new_for_path(dl))
        dialog.open(self.get_root(), None, self._zip_chosen)

    def _zip_chosen(self, dialog, result):
        try:
            gfile = dialog.open_finish(result)
        except GLib.Error:
            return  # cancelled
        if gfile is not None and gfile.get_path():
            self.ctx.pack_path = gfile.get_path()
            self.ctx.goto("icons-pack")


class PreviewTile(Gtk.Box):
    def __init__(self, label, kind, data, dark):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6, css_classes=["preview-tile"])
        well = Gtk.Box(css_classes=["preview-well"] + (["dark"] if dark else []), halign=Gtk.Align.CENTER)
        tex = None
        try:
            if kind == "svg":
                tex = render_svg("", 96, 96, data=data)
            else:
                tex = Gdk.Texture.new_from_bytes(GLib.Bytes.new(data))
        except GLib.Error as exc:
            log.info("preview %s: %s", label, exc.message)
        pic = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN, can_shrink=True)
        if tex is not None:
            pic.set_paintable(tex)
        pic.set_size_request(48, 48)
        well.append(pic)
        self.append(well)
        self.append(Gtk.Label(label=label, css_classes=["preview-caption"], ellipsize=3, max_width_chars=10))


class IconPackPage(_BusyMixin, Page):
    """Review a pack (name, source, preview grid) and apply it."""

    page_id = "icons-pack"
    illustration = "icons"
    branch = True

    def __init__(self, ctx):
        super().__init__(ctx, _("Review your icon pack"), " ")
        self.primary_label = _("Apply")
        self.secondary_label = _("Choose another")
        self.details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, vexpand=True)
        self.facts = Gtk.Label(xalign=0, wrap=True, css_classes=["pack-facts"], use_markup=True)
        self.details.append(self.facts)
        self.grid = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=6,
                                min_children_per_line=4, column_spacing=6, row_spacing=6,
                                homogeneous=True, css_classes=["preview-grid"], valign=Gtk.Align.START)
        self.details.append(self.grid)
        self.note = Gtk.Label(xalign=0, wrap=True, css_classes=["hint-text"])
        self.details.append(self.note)
        self.body.append(self.details)
        self.error = Gtk.Label(xalign=0, wrap=True, css_classes=["error-text"], visible=False)
        self.body.append(self.error)
        self.body.append(self._build_busy())
        self.info = None

    def on_enter(self, direction):
        self.hide_busy(self.details)
        self.error.set_visible(False)
        while (c := self.grid.get_first_child()) is not None:
            self.grid.remove(c)
        path = self.ctx.pack_path
        try:
            self.info = iconpack.inspect(path)
        except iconpack.PackError as exc:
            self.info = None
            self.title_label.set_label(_("This file isn't an icon pack"))
            self.subtitle_label.set_label(os.path.basename(path or ""))
            self.facts.set_label("")
            self.note.set_label("")
            self.error.set_label(str(exc))
            self.error.set_visible(True)
            self.primary_label = _("Choose another")
            self.secondary_label = None
            self.primary_sensitive = True
            self.ctx.update_footer(self)
            return
        info = self.info
        self.title_label.set_label(info.name)
        self.primary_label = _("Apply")
        self.secondary_label = _("Choose another")
        src = info.source
        if info.kind == "fenestra":
            bits = []
            if src.get("os"):
                bits.append(_("From {os}").format(os=GLib.markup_escape_text(str(src["os"]))))
            if src.get("build"):
                bits.append(_("build {build}").format(build=GLib.markup_escape_text(str(src["build"]))))
            created = str(info.manifest.get("created") or "")
            m = re.match(r"(\d{4})-(\d{2})-(\d{2})", created)
            if m:
                bits.append(_("created {date}").format(date=f"{m.group(3)}/{m.group(2)}/{m.group(1)}"))
            self.subtitle_label.set_label(" · ".join(re.sub("<[^>]+>", "", b) for b in bits)
                                          or _("Fenestra icon pack"))
            labels = {"fonts": _("Fonts"), "cursors": _("Mouse pointers"), "assets": _("Taskbar and folder icons"),
                      "icons": _("App icons"), "glyphs": _("Icon glyphs"), "apps": _("Store app logos"),
                      "raw": _("Battery glyphs")}
            parts = [labels[c] for c in info.contents if c in labels]
            facts = "<b>" + _("Includes:") + "</b> " + GLib.markup_escape_text(", ".join(parts) or "-")
            gen = info.manifest.get("generator")
            if gen:
                facts += "\n<b>" + _("Made with:") + "</b> " + GLib.markup_escape_text(str(gen))
            self.facts.set_label(facts)
            self.note.set_label(str(info.manifest.get("licence_note") or ""))
        else:
            self.subtitle_label.set_label(_("Icon theme"))
            self.facts.set_label("<b>" + _("Includes:") + "</b> " + GLib.markup_escape_text(_("App icons")))
            self.note.set_label("")
        self.subtitle_label.set_visible(True)
        for label, kind, data, dark in iconpack.previews(info):
            self.grid.append(PreviewTile(_(label), kind, data, dark))
        self.primary_sensitive = True
        self.ctx.update_footer(self)

    def on_primary(self):
        if self.info is None:
            self.ctx.back()
            return
        if self.busy:
            return
        self.show_busy(_("Installing your icon pack…"), self.details)
        if self.ctx.screenshot_mode:
            return
        run_async(self.backends.privacy.run_pack_import, self.info.path, callback=self._applied)

    def _applied(self, result, error):
        self.hide_busy(self.details)
        if error is not None or result == "missing-helper":
            msg = str(error) if error is not None else _("The import tool isn't installed.")
            self.error.set_label(_("The icon pack couldn't be installed.") + "\n" + msg)
            self.error.set_visible(True)
            return
        self.state.icon_pack = self.info.name
        self.ctx.next()

    def on_secondary(self):
        self.ctx.back()

    def screenshot_state(self, name):
        if name == "applying":
            self.show_busy(_("Installing your icon pack…"), self.details)


class IconBrowserPage(Page):
    """Mini browser to download a pack; direct .zip links skip the web view."""

    page_id = "icons-browser"
    illustration = "icons"
    branch = True
    wide = True

    def __init__(self, ctx):
        super().__init__(ctx, _("Download an icon pack"))
        self.add_css_class("browser-page")
        self.primary_label = _("Next")
        self.primary_sensitive = False
        self.downloaded = None
        self._soup = None
        self._cancel = None

        bar = Gtk.Box(spacing=4, css_classes=["browser-bar", "own-enter"])
        self.back_btn = self._tool("go-previous-symbolic", _("Back"), lambda *_: self.view and self.view.go_back())
        self.fwd_btn = self._tool("go-next-symbolic", _("Forward"), lambda *_: self.view and self.view.go_forward())
        self.reload_btn = self._tool("view-refresh-symbolic", _("Refresh"), lambda *_: self.view and self.view.reload())
        for b in (self.back_btn, self.fwd_btn, self.reload_btn):
            bar.append(b)
        self.address = Gtk.Entry(hexpand=True, css_classes=["oobe-entry", "address-entry"],
                                 placeholder_text=_("Paste a link to your icon pack"))
        self.address.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "edit-paste-symbolic")
        self.address.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, _("Paste"))
        self.address.connect("icon-press", lambda *_: self._paste())
        self.address.connect("activate", lambda *_: self.navigate(self.address.get_text()))
        bar.append(self.address)
        go = Gtk.Button(label=_("Go"), css_classes=["oobe-button", "secondary", "go-button"])
        go.connect("clicked", lambda *_: self.navigate(self.address.get_text()))
        bar.append(go)
        self.body.append(bar)

        frame = Gtk.Box(css_classes=["browser-view", "own-enter"], vexpand=True, overflow=Gtk.Overflow.HIDDEN)
        self.view = None
        if WebKit is not None and not os.environ.get("FENESTRA_OOBE_NO_WEBKIT"):
            try:
                session = WebKit.NetworkSession.new_ephemeral()
                self.view = WebKit.WebView(network_session=session, hexpand=True, vexpand=True)
                session.connect("download-started", self._on_download_started)
                self.view.connect("decide-policy", self._on_decide_policy)
                self.view.connect("notify::uri", self._sync_nav)
                self.view.connect("load-changed", self._sync_nav)
                settings = self.view.get_settings()
                settings.set_enable_developer_extras(False)
                frame.append(self.view)
            except Exception as exc:  # noqa: BLE001 - fall back to the plain UI
                log.warning("WebKit unavailable: %s", exc)
                self.view = None
        if self.view is None:
            fallback = Gtk.Label(wrap=True, xalign=0, yalign=0, css_classes=["browser-fallback"], use_markup=True)
            fallback.set_markup(
                "<b>" + GLib.markup_escape_text(_("Bring your own icons")) + "</b>\n\n" + GLib.markup_escape_text(
                    _("Use Fenestra Icon Extractor on your Windows PC to export your own icons, upload the zip "
                      "anywhere you like (e.g. your cloud drive) and paste the link here.")) +
                "\n\n" + f'<a href="{RELEASES_URL}">{GLib.markup_escape_text(RELEASES_URL)}</a>')
            fallback.set_hexpand(True)
            frame.append(fallback)
            for b in (self.back_btn, self.fwd_btn, self.reload_btn):
                b.set_sensitive(False)
        self.body.append(frame)

        status = Gtk.Box(spacing=12, css_classes=["download-row"], visible=False)
        self.progress = Gtk.ProgressBar(hexpand=True, valign=Gtk.Align.CENTER, css_classes=["oobe-progress"])
        self.status = Gtk.Label(xalign=0, ellipsize=3, css_classes=["download-status"])
        self.status.set_max_width_chars(48)
        status.append(self.status)
        status.append(self.progress)
        self.status_row = status
        self.body.append(status)
        self._home_loaded = False

    @staticmethod
    def _tool(icon, tooltip, cb):
        b = Gtk.Button(icon_name=icon, tooltip_text=tooltip, css_classes=["browser-tool"],
                       valign=Gtk.Align.CENTER)
        b.update_property([Gtk.AccessibleProperty.LABEL], [tooltip])
        b.connect("clicked", cb)
        return b

    def focus_widget(self):
        return self.address

    def on_enter(self, direction):
        if self.view is not None and not self._home_loaded:
            self._home_loaded = True
            self.view.load_uri(help_page_uri())

    def _sync_nav(self, *_args):
        if self.view is None:
            return
        self.back_btn.set_sensitive(self.view.can_go_back())
        self.fwd_btn.set_sensitive(self.view.can_go_forward())
        uri = self.view.get_uri() or ""
        if uri.startswith(("file:", "about:")):
            return  # local help page: keep whatever the user typed
        if not self.address.has_focus():
            self.address.set_text(uri)

    def _paste(self):
        clip = self.get_display().get_clipboard()

        def done(cb, res):
            try:
                text = cb.read_text_finish(res)
            except GLib.Error:
                return
            if text:
                self.address.set_text(text.strip())
                self.navigate(text.strip())
        clip.read_text_async(None, done)

    # -- navigation & downloads ------------------------------------------
    @staticmethod
    def normalize(text: str) -> str | None:
        text = (text or "").strip()
        if not text:
            return None
        scheme = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*):(?!\d)", text)
        if scheme and scheme.group(1).lower() not in ("http", "https"):
            return None
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", text):
            text = "https://" + text
        parts = urllib.parse.urlsplit(text)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            return None
        return text

    @staticmethod
    def is_direct_zip(url: str) -> bool:
        return urllib.parse.urlsplit(url).path.lower().endswith(".zip")

    def navigate(self, text):
        url = self.normalize(text)
        if url is None:
            self._set_status(_("That doesn't look like a web address."), None)
            return
        self.address.set_text(url)
        if self.is_direct_zip(url) or self.view is None:
            self.download_direct(url)
        else:
            self.view.load_uri(url)

    def _download_dir(self):
        if self.ctx.mode == "demo" or self.backends.demo:
            d = os.path.join(GLib.get_tmp_dir(), "fenestra-oobe-downloads")
        else:
            d = paths.downloads_dir()
        os.makedirs(d, exist_ok=True)
        return d

    def _unique(self, filename):
        filename = os.path.basename(filename or "") or "icon-pack.zip"
        filename = re.sub(r"[\x00-\x1f/\\\\]", "_", filename)
        base, ext = os.path.splitext(filename)
        d = self._download_dir()
        cand, n = os.path.join(d, filename), 1
        while os.path.exists(cand):
            cand = os.path.join(d, f"{base} ({n}){ext}")
            n += 1
        return cand

    def _set_status(self, text, fraction):
        self.status_row.set_visible(True)
        self.status.set_label(text)
        if fraction is None:
            self.progress.set_visible(False)
        else:
            self.progress.set_visible(True)
            if fraction < 0:
                self.progress.pulse()
            else:
                self.progress.set_fraction(max(0.0, min(1.0, fraction)))

    # WebKit downloads
    def _on_decide_policy(self, view, decision, decision_type):
        if decision_type == WebKit.PolicyDecisionType.RESPONSE:
            supported = decision.is_mime_type_supported() if hasattr(decision, "is_mime_type_supported") else True
            resp = decision.get_response()
            mime = resp.get_mime_type() if resp is not None else ""
            if not supported or mime in ("application/zip", "application/x-zip-compressed",
                                         "application/octet-stream"):
                decision.download()
                return True
        return False

    def _on_download_started(self, _session, download):
        self.primary_sensitive = False
        self.ctx.update_footer(self)
        download.connect("decide-destination", self._on_decide_destination)
        download.connect("received-data", lambda d, _n: self._set_status(
            _("Downloading {name}…").format(name=os.path.basename(d.get_destination() or "")),
            d.get_estimated_progress()))
        download.connect("finished", lambda d: self._finished(GLib.filename_from_uri(d.get_destination())[0]
                                                              if (d.get_destination() or "").startswith("file:")
                                                              else d.get_destination()))
        download.connect("failed", lambda d, err: self._failed(err.message if err else ""))
        self._set_status(_("Starting download…"), -1)

    def _on_decide_destination(self, download, suggested):
        dest = self._unique(suggested)
        download.set_destination(dest)
        return True

    # Direct download through libsoup (no web view needed)
    def download_direct(self, url):
        if Soup is None:
            run_async(self._urllib_download, url, callback=lambda p, e: self._failed(str(e)) if e else self._finished(p))
            return
        try:
            msg = Soup.Message.new("GET", url)
        except (TypeError, GLib.Error):
            msg = None
        if msg is None:
            self._set_status(_("That doesn't look like a web address."), None)
            return
        self._soup = Soup.Session()
        self._cancel = Gio.Cancellable()
        name = urllib.parse.unquote(os.path.basename(urllib.parse.urlsplit(url).path)) or "icon-pack.zip"
        self._set_status(_("Downloading {name}…").format(name=name), -1)
        self._soup.send_async(msg, GLib.PRIORITY_DEFAULT, self._cancel, self._on_sent, (msg, name))

    def _on_sent(self, session, result, data):
        msg, name = data
        try:
            stream = session.send_finish(result)
        except GLib.Error as exc:
            self._failed(exc.message)
            return
        if msg.get_status() >= 400:
            self._failed(f"HTTP {msg.get_status()}")
            return
        headers = msg.get_response_headers()
        ok, _disp, params = headers.get_content_disposition()
        if ok and params and params.get("filename"):
            name = params["filename"]
        total = headers.get_content_length()
        dest = self._unique(name if name.lower().endswith(".zip") else name + ".zip")
        out = Gio.File.new_for_path(dest).replace(None, False, Gio.FileCreateFlags.NONE, None)
        self._read_chunk(stream, out, dest, total, 0)

    def _read_chunk(self, stream, out, dest, total, received):
        def done(s, res):
            try:
                chunk = s.read_bytes_finish(res)
            except GLib.Error as exc:
                out.close(None)
                self._failed(exc.message)
                return
            if chunk.get_size() == 0:
                out.close(None)
                stream.close(None)
                self._finished(dest)
                return
            out.write_bytes(chunk, None)
            got = received + chunk.get_size()
            if got > 1 << 30:
                out.close(None)
                self._failed(_("The file is too large."))
                return
            self._set_status(_("Downloading {name}…").format(name=os.path.basename(dest)),
                             got / total if total > 0 else -1)
            self._read_chunk(stream, out, dest, total, got)
        stream.read_bytes_async(1 << 16, GLib.PRIORITY_DEFAULT, self._cancel, done)

    def _urllib_download(self, url):
        import urllib.request
        name = os.path.basename(urllib.parse.urlsplit(url).path) or "icon-pack.zip"
        dest = self._unique(name)
        with urllib.request.urlopen(url, timeout=60) as resp, open(dest, "wb") as fh:  # noqa: S310 - user URL
            while chunk := resp.read(1 << 16):
                fh.write(chunk)
        return dest

    def _failed(self, message):
        self._set_status(_("The download failed.") + (f" {message}" if message else ""), None)

    def _finished(self, dest):
        self.downloaded = dest
        name = os.path.basename(dest or "")
        if not dest or not iconpack.looks_like_zip(dest):
            self._set_status(_("Downloaded {name}, but it isn't a zip file.").format(name=name), None)
            return
        try:
            info = iconpack.inspect(dest)
        except iconpack.PackError as exc:
            self._set_status(_("Downloaded {name}, but it isn't an icon pack: {why}").format(name=name, why=exc),
                             None)
            return
        self.ctx.pack_path = dest
        self._set_status(_("Ready: {name}").format(name=info.name), 1.0)
        self.primary_sensitive = True
        self.ctx.update_footer(self)

    def on_primary(self):
        if self.ctx.pack_path and self.downloaded:
            self.ctx.goto("icons-pack")

    def screenshot_state(self, name):
        if name == "download":
            self.address.set_text("https://example.com/files/my-icons.zip")
            self._set_status(_("Downloading {name}…").format(name="my-icons.zip"), 0.45)
