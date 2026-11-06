# SPDX-License-Identifier: GPL-3.0-or-later
"""The print dialog window.

Reference layout: a settings column on the left (heading, printer, copies, orientation,
pages, colour mode, a "more settings" link to a second page), the preview on the right
on a slightly darker neutral background with a sheet counter under it, and the accent
Print button plus Cancel at the bottom right. Sizes and colours live in metrics.py.
"""
from __future__ import annotations

import math
import os
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Graphene", "1.0")
from gi.repository import Gio, GLib, Gsk, Gtk, Graphene  # noqa: E402

from . import metrics, printing, render, theme  # noqa: E402
from .i18n import _  # noqa: E402

CONFIG = os.path.join(GLib.get_user_config_dir(), "fenestra", "print-portal.ini")

PAPER_LABELS = {
    "iso_a4": "A4 (210 × 297 mm)", "na_letter": "Letter (8.5 × 11 in)", "na_legal": "Legal (8.5 × 14 in)",
    "iso_a3": "A3 (297 × 420 mm)", "iso_a5": "A5 (148 × 210 mm)", "iso_b5": "B5 (176 × 250 mm)",
    "na_executive": "Executive (7.25 × 10.5 in)",
}


def load_config() -> GLib.KeyFile:
    kf = GLib.KeyFile()
    try:
        kf.load_from_file(CONFIG, GLib.KeyFileFlags.NONE)
    except GLib.Error:
        pass
    return kf


def config_get(key, default=""):
    try:
        return load_config().get_string("print", key)
    except GLib.Error:
        return default


def config_set(**values):
    kf = load_config()
    for k, v in values.items():
        kf.set_string("print", k, str(v))
    try:
        os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
        kf.save_to_file(CONFIG)
    except (GLib.Error, OSError):
        pass


class Options:
    """What the caller passes about the request (PreparePrint/Print options)."""

    def __init__(self, title="", accept_label="", modal=True, has_current=False, has_selection=False,
                 parent_window="", demo=False, no_save_dialog=False):
        self.title = title
        self.accept_label = accept_label
        self.modal = modal
        self.has_current = has_current
        self.has_selection = has_selection
        self.parent_window = parent_window
        self.demo = demo
        self.no_save_dialog = no_save_dialog


def label_factory(ellipsize: bool) -> Gtk.SignalListItemFactory:
    f = Gtk.SignalListItemFactory()

    def setup(_f, item):
        lbl = Gtk.Label(xalign=0)
        if ellipsize:
            lbl.set_ellipsize(3)   # Pango.EllipsizeMode.END
            lbl.set_width_chars(1)
        item.set_child(lbl)
    f.connect("setup", setup)
    f.connect("bind", lambda _f, item: item.get_child().set_label(item.get_item().get_string()))
    return f


class Choices(Gtk.DropDown):
    """A dropdown of (id, label) pairs."""

    def __init__(self, items, selected=None):
        self.ids = [i for i, _l in items]
        super().__init__(model=Gtk.StringList.new([lbl for _i, lbl in items]))
        self.add_css_class("print-dropdown")
        # Ellipsize in the button so a long choice cannot widen the settings column.
        self.set_factory(label_factory(ellipsize=True))
        self.set_list_factory(label_factory(ellipsize=False))
        self.set_hexpand(True)
        if selected in self.ids:
            self.set_selected(self.ids.index(selected))

    @property
    def value(self):
        i = self.get_selected()
        return self.ids[i] if 0 <= i < len(self.ids) else None

    def set_value(self, v):
        if v in self.ids:
            self.set_selected(self.ids.index(v))


class Preview(Gtk.Box):
    """The sheet preview with its 'n / N' pager."""

    def __init__(self, dialog):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.dialog = dialog
        self.add_css_class("print-preview")
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.index = 0
        self.area = Gtk.DrawingArea()
        self.area.set_vexpand(True)
        self.area.set_hexpand(True)
        self.area.set_draw_func(self._draw)
        self.append(self.area)

        pager = Gtk.Box(spacing=4, halign=Gtk.Align.CENTER)
        pager.add_css_class("print-pager")
        pager.set_size_request(-1, metrics.PAGER_HEIGHT)
        self.prev = Gtk.Button(icon_name="pan-start-symbolic", valign=Gtk.Align.CENTER)
        self.prev.set_tooltip_text(_("Previous page"))
        self.next = Gtk.Button(icon_name="pan-end-symbolic", valign=Gtk.Align.CENTER)
        self.next.set_tooltip_text(_("Next page"))
        for b in (self.prev, self.next):
            b.add_css_class("flat-icon")
        self.counter = Gtk.Label(valign=Gtk.Align.CENTER)
        self.counter.add_css_class("print-counter")
        self.counter.set_width_chars(7)
        pager.append(self.prev)
        pager.append(self.counter)
        pager.append(self.next)
        self.append(pager)
        self.prev.connect("clicked", lambda *_: self.go(-1))
        self.next.connect("clicked", lambda *_: self.go(+1))

    def sheets(self):
        doc = self.dialog.doc
        if doc is None:
            return [None]
        return render.sheets_for(self.dialog.choice, doc.get_n_pages())

    def refresh(self):
        n = len(self.sheets())
        self.index = max(0, min(self.index, n - 1))
        self.counter.set_label(f"{self.index + 1} / {n}")
        self.prev.set_sensitive(self.index > 0)
        self.next.set_sensitive(self.index < n - 1)
        self.area.queue_draw()

    def go(self, delta):
        self.index += delta
        self.refresh()

    def _draw(self, _area, cr, width, height):
        dark = theme.get().dark if theme.get() else False
        colors = metrics.PREVIEW_DARK if dark else metrics.PREVIEW_LIGHT
        c = self.dialog.choice
        sw, sh = c.sheet_mm()
        m = metrics.PREVIEW_MARGIN
        avail_w, avail_h = max(1, width - 2 * m), max(1, height - 2 * m)
        s = min(avail_w / sw, avail_h / sh)
        w, h = sw * s, sh * s
        x, y = round((width - w) / 2), round((height - h) / 2)
        # soft shadow: a few widening translucent rectangles
        r, g, b, a = colors["shadow"]
        for i in range(metrics.PREVIEW_SHADOW, 0, -1):
            cr.set_source_rgba(r, g, b, a / metrics.PREVIEW_SHADOW)
            cr.rectangle(x - i / 2, y - i / 4, w + i, h + i)
            cr.fill()
        sheets = self.sheets()
        sheet = sheets[min(self.index, len(sheets) - 1)]
        pages = None if sheet is None else [self.dialog.doc.get_page(i) for i in sheet]
        cr.save()
        cr.translate(x, y)
        cr.rectangle(0, 0, w, h)
        cr.clip()
        render.draw_sheet(cr, c, w, h, pages, colors)
        cr.restore()


class PrintDialog(Gtk.Window):
    """on_done(response, choice): response 0 = print, 1 = cancelled."""

    def __init__(self, app_title: str, choice: printing.Choice, opts: Options, on_done, doc=None):
        super().__init__()
        self.opts = opts
        self.choice = choice
        self.doc = doc
        self.on_done = on_done
        self._finished = False
        self._user_picked_printer = False
        self.printers: dict[str, printing.PrinterInfo] = {}
        self.add_css_class("fenestra-print")
        self.set_title(app_title or _("Print"))
        self.set_default_size(metrics.WINDOW_WIDTH, metrics.WINDOW_HEIGHT)
        self.set_size_request(metrics.MIN_WIDTH, metrics.MIN_HEIGHT)
        self.set_modal(opts.modal)

        header = Gtk.HeaderBar()
        header.add_css_class("print-titlebar")
        tl = Gtk.Label(label=app_title or _("Print"), ellipsize=3)
        tl.add_css_class("print-window-title")
        header.set_title_widget(tl)
        self.set_titlebar(header)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(outer)
        body = Gtk.Box()
        body.set_vexpand(True)
        outer.append(body)

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        left.add_css_class("print-pane")
        left.set_size_request(metrics.LEFT_COLUMN_WIDTH, -1)
        left.set_hexpand(False)   # explicit: stops the controls' hexpand from widening the column
        body.append(left)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT, vexpand=True)
        left.append(self.stack)
        self.stack.add_named(self._scroll(self._main_page()), "main")
        self.stack.add_named(self._scroll(self._more_page()), "more")

        self.preview = Preview(self)
        body.append(self.preview)

        footer = Gtk.Box(spacing=metrics.BUTTON_GAP, halign=Gtk.Align.FILL)
        footer.add_css_class("print-footer")
        spacer = Gtk.Box(hexpand=True)
        footer.append(spacer)
        self.print_button = Gtk.Button(label=opts.accept_label or _("Print"), use_underline=True)
        self.print_button.add_css_class("fluent-button")
        self.print_button.add_css_class("print-button")
        self.print_button.add_css_class("accent")
        self.cancel_button = Gtk.Button(label=_("Cancel"))
        self.cancel_button.add_css_class("fluent-button")
        self.cancel_button.add_css_class("print-button")
        for b in (self.print_button, self.cancel_button):
            b.set_valign(Gtk.Align.CENTER)
            footer.append(b)
        spacer.set_size_request(metrics.FOOTER_PADDING, -1)
        end_pad = Gtk.Box()
        end_pad.set_size_request(metrics.FOOTER_PADDING - metrics.BUTTON_GAP, -1)
        footer.append(end_pad)
        outer.append(footer)
        self.set_default_widget(self.print_button)
        self.print_button.connect("clicked", self._on_print)
        self.cancel_button.connect("clicked", lambda *_: self.finish(1))
        self.connect("close-request", self._on_close_request)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)
        if opts.parent_window:
            self.connect("realize", self._attach_parent)

        self._sync_from_choice()
        self.watcher = printing.PrinterWatcher(self._printer_added, self._printers_done, demo=opts.demo)
        theme.get().connect(self.preview.area.queue_draw)
        if os.environ.get("FENESTRA_PORTAL_TEST_ACCEPT"):
            GLib.timeout_add(int(os.environ["FENESTRA_PORTAL_TEST_ACCEPT"]), self._test_accept)

    # ------------------------------------------------------------------ building
    @staticmethod
    def _scroll(child):
        sw = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        sw.set_child(child)
        return sw

    @staticmethod
    def _field(box, label, widget, first=False):
        lbl = Gtk.Label(label=label, xalign=0)
        lbl.add_css_class("print-label")
        lbl.set_margin_top(0 if first else metrics.FIELD_GAP)
        lbl.set_margin_bottom(metrics.LABEL_GAP)
        lbl.set_mnemonic_widget(widget)
        box.append(lbl)
        box.append(widget)
        return lbl

    def _column(self):
        t, r, b, l = metrics.LEFT_PADDING
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.set_margin_top(t)
        box.set_margin_end(r)
        box.set_margin_bottom(b)
        box.set_margin_start(l)
        return box

    def _main_page(self):
        box = self._column()
        head = Gtk.Label(label=_("Print"), xalign=0)
        head.add_css_class("print-heading")
        box.append(head)
        self.summary = Gtk.Label(xalign=0)
        self.summary.add_css_class("print-summary")
        box.append(self.summary)
        spacer = Gtk.Box()
        spacer.set_size_request(-1, metrics.FIELD_GAP)
        box.append(spacer)

        # Printer: a dropdown of names with the location under each in the list.
        self.printer_ids: list[str] = []
        self.printer_model = Gtk.StringList()
        self.printer_dd = Gtk.DropDown(model=self.printer_model)
        self.printer_dd.add_css_class("print-dropdown")
        self.printer_dd.set_hexpand(True)
        self.printer_dd.set_factory(self._printer_factory(False))
        self.printer_dd.set_list_factory(self._printer_factory(True))
        self._field(box, _("Printer"), self.printer_dd, first=True)
        self.printer_status = Gtk.Label(xalign=0, wrap=True, max_width_chars=30)
        self.printer_status.add_css_class("print-caption")
        box.append(self.printer_status)
        self._add_printer(printing.PrinterInfo(name=printing.PDF_PRINTER, label=_("Save as PDF"), is_pdf=True))
        self.printer_dd.connect("notify::selected", self._on_printer_changed)

        adj = Gtk.Adjustment(lower=1, upper=999, step_increment=1, page_increment=10, value=1)
        self.copies = Gtk.SpinButton(adjustment=adj, numeric=True, hexpand=True)
        self.copies.add_css_class("print-spin")
        self._field(box, _("Copies"), self.copies)
        self.collate = Gtk.CheckButton(label=_("Collate"))
        self.collate.add_css_class("print-check")
        self.collate.set_margin_top(6)
        box.append(self.collate)

        self.orientation = Choices([("portrait", _("Portrait")), ("landscape", _("Landscape"))])
        self._field(box, _("Orientation"), self.orientation)

        pages = [("all", _("All pages")), ("odd", _("Odd pages only")), ("even", _("Even pages only"))]
        if self.opts.has_current:
            pages.append(("current", _("Current page")))
        if self.opts.has_selection:
            pages.append(("selection", _("Selection")))
        pages.append(("ranges", _("Custom range")))
        self.pages = Choices(pages)
        self._field(box, _("Pages"), self.pages)
        self.ranges = Gtk.Entry(placeholder_text=_("e.g. 1-5, 8, 11-13"), hexpand=True)
        self.ranges.add_css_class("print-entry")
        self.ranges.set_margin_top(8)
        box.append(self.ranges)

        self.color = Choices([("color", _("Color")), ("mono", _("Black and white"))])
        self._field(box, _("Color mode"), self.color)

        more = Gtk.Button(label=_("More settings"), halign=Gtk.Align.START)
        more.add_css_class("hyperlink")
        more.set_margin_top(metrics.FIELD_GAP + 2)
        more.connect("clicked", lambda *_: self.stack.set_visible_child_name("more"))
        box.append(more)

        for w, sig in ((self.copies, "value-changed"), (self.collate, "toggled"),
                       (self.orientation, "notify::selected"), (self.pages, "notify::selected"),
                       (self.ranges, "changed"), (self.color, "notify::selected")):
            w.connect(sig, self._on_changed)
        return box

    def _more_page(self):
        box = self._column()
        top = Gtk.Box(spacing=8)
        back = Gtk.Button(icon_name="go-previous-symbolic", valign=Gtk.Align.CENTER)
        back.add_css_class("flat-icon")
        back.set_tooltip_text(_("Back"))
        back.connect("clicked", lambda *_: self.stack.set_visible_child_name("main"))
        top.append(back)
        head = Gtk.Label(label=_("More settings"), xalign=0)
        head.add_css_class("print-subheading")
        top.append(head)
        box.append(top)
        spacer = Gtk.Box()
        spacer.set_size_request(-1, metrics.FIELD_GAP)
        box.append(spacer)

        papers = list(metrics.PAPER_SIZES)
        if self.choice.paper not in papers:
            papers.append(self.choice.paper)
        self.paper = Choices([(p, self._paper_label(p)) for p in papers])
        self._field(box, _("Paper size"), self.paper, first=True)
        self.number_up = Choices([(str(n), str(n)) for n in metrics.PAGES_PER_SHEET])
        self._field(box, _("Pages per sheet"), self.number_up)
        self.margins = Choices([("normal", _("Normal")), ("narrow", _("Narrow")), ("none", _("None"))])
        self._field(box, _("Margins"), self.margins)
        self.duplex = Choices([("simplex", _("Print on one side")),
                               ("long", _("Print on both sides, flip on long edge")),
                               ("short", _("Print on both sides, flip on short edge"))])
        self.duplex_label = self._field(box, _("Two-sided printing"), self.duplex)
        for w in (self.paper, self.number_up, self.margins, self.duplex):
            w.connect("notify::selected", self._on_changed)
        return box

    @staticmethod
    def _paper_label(name):
        if name in PAPER_LABELS:
            return _(PAPER_LABELS[name])
        try:
            return Gtk.PaperSize.new(name).get_display_name()
        except Exception:  # noqa: BLE001
            return name

    def _printer_factory(self, in_list):
        f = Gtk.SignalListItemFactory()

        def setup(_f, item):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            name = Gtk.Label(xalign=0, ellipsize=3)
            if not in_list:
                name.set_width_chars(1)
            box.append(name)
            if in_list:
                sub = Gtk.Label(xalign=0, ellipsize=3)
                sub.add_css_class("print-caption")
                box.append(sub)
            item.set_child(box)

        def bind(_f, item):
            info = self.printers.get(item.get_item().get_string())
            box = item.get_child()
            name = box.get_first_child()
            name.set_label(info.label if info else "")
            if in_list:
                sub = name.get_next_sibling()
                sub.set_label(info.location if info else "")
                sub.set_visible(bool(info and info.location))
        f.connect("setup", setup)
        f.connect("bind", bind)
        return f

    # ------------------------------------------------------------------ printers
    def _add_printer(self, info: printing.PrinterInfo):
        self.printers[info.name] = info
        # Save as PDF stays last; real printers are inserted before it.
        pos = len(self.printer_ids) - 1 if self.printer_ids and not info.is_pdf else len(self.printer_ids)
        self.printer_ids.insert(pos, info.name)
        self._loading = True
        cur = self.printer_dd.get_selected()
        self.printer_model.splice(pos, 0, [info.name])
        if 0 <= cur < len(self.printer_ids) and pos <= cur:
            self.printer_dd.set_selected(cur + 1)
        self._loading = False

    def _printer_added(self, info):
        self._add_printer(info)
        want = self.preferred_printer
        if info.name == want or (info.is_default and not self._user_picked_printer
                                 and self._current_printer() != want):
            self._select_printer(info.name)

    def _printers_done(self):
        self._update_status()

    def _current_printer(self):
        i = self.printer_dd.get_selected()
        return self.printer_ids[i] if 0 <= i < len(self.printer_ids) else printing.PDF_PRINTER

    def _select_printer(self, name):
        if name in self.printer_ids:
            self._loading = True
            self.printer_dd.set_selected(self.printer_ids.index(name))
            self._loading = False
            self._on_changed()

    def _on_printer_changed(self, *_args):
        if not getattr(self, "_loading", False):
            self._user_picked_printer = True
        self._on_changed()

    def _update_status(self):
        info = self.printers.get(self._current_printer())
        if info is None:
            text = ""
        elif info.is_pdf:
            text = _("Saves the document as a PDF file")
        else:
            text = info.state or _("Ready")
        self.printer_status.set_label(text)
        self.printer_status.set_visible(bool(text))

    # ------------------------------------------------------------------ state
    def _sync_from_choice(self):
        c = self.choice
        self._loading = True
        self.preferred_printer = c.printer or config_get("printer", "")
        self.copies.set_value(c.copies)
        self.collate.set_active(c.collate)
        self.orientation.set_value(c.orientation)
        self.pages.set_value(c.pages if c.pages in self.pages.ids else "all")
        self.ranges.set_text(c.ranges_text)
        self.color.set_value("color" if c.color else "mono")
        self.paper.set_value(c.paper)
        self.number_up.set_value(str(c.number_up))
        self.margins.set_value(c.margins)
        self.duplex.set_value(c.duplex)
        self._loading = False
        self._select_printer(self.preferred_printer)
        self._on_changed()

    def _read_choice(self):
        c = self.choice
        c.printer = self._current_printer()
        c.copies = int(self.copies.get_value())
        c.collate = self.collate.get_active()
        c.orientation = self.orientation.value
        c.pages = self.pages.value
        c.ranges_text = self.ranges.get_text().strip()
        c.color = self.color.value == "color"
        c.paper = self.paper.value
        c.number_up = int(self.number_up.value)
        c.margins = self.margins.value
        c.duplex = self.duplex.value

    def _ranges_valid(self):
        if self.choice.pages != "ranges":
            return True
        try:
            printing.parse_ranges(self.choice.ranges_text, self.doc.get_n_pages() if self.doc else None)
            return True
        except ValueError:
            return False

    def _on_changed(self, *_args):
        if getattr(self, "_loading", False) or not hasattr(self, "duplex"):
            return
        self._read_choice()
        c = self.choice
        self.collate.set_visible(c.copies > 1)
        self.ranges.set_visible(c.pages == "ranges")
        ok = self._ranges_valid()
        if ok:
            self.ranges.remove_css_class("error")
        else:
            self.ranges.add_css_class("error")
        self.print_button.set_sensitive(ok)
        self.print_button.set_label(self.opts.accept_label or (_("Save") if c.is_pdf else _("Print")))
        self.duplex.set_visible(not c.is_pdf)
        self.duplex_label.set_visible(not c.is_pdf)
        self._update_status()
        self._update_summary()
        self.preview.refresh()

    def _update_summary(self):
        if self.doc is None:
            self.summary.set_visible(False)
            return
        c = self.choice
        sheets = len([s for s in render.sheets_for(c, self.doc.get_n_pages()) if s])
        if c.duplex != "simplex" and not c.is_pdf:
            sheets = math.ceil(sheets / 2)
        total = sheets * c.copies
        if c.is_pdf:
            text = (_("Total: 1 page") if total == 1 else _("Total: {n} pages")).format(n=total)
        else:
            text = (_("Total: 1 sheet of paper") if total == 1 else _("Total: {n} sheets of paper")).format(n=total)
        self.summary.set_label(text)
        self.summary.set_visible(True)

    # ------------------------------------------------------------------ finishing
    def _on_key(self, _ctl, keyval, _code, _state):
        from gi.repository import Gdk
        if keyval == Gdk.KEY_Escape:
            self.finish(1)
            return True
        return False

    def _on_close_request(self, *_args):
        if not self._finished:
            self.finish(1)
        return False

    def _on_print(self, *_args):
        self._read_choice()
        if not self._ranges_valid():
            return
        c = self.choice
        if c.is_pdf and not c.output_uri:
            if self.opts.no_save_dialog:
                c.output_uri = Gio.File.new_for_path(printing.default_pdf_path(self.opts.title)).get_uri()
            else:
                self._ask_pdf_path()
                return
        self.finish(0)

    def _ask_pdf_path(self):
        fd = Gtk.FileDialog(title=_("Save as PDF"), modal=True,
                            accept_label=_("Save"))
        fd.set_initial_folder(Gio.File.new_for_path(printing.documents_dir()))
        fd.set_initial_name(printing.safe_basename(self.opts.title) + ".pdf")
        flt = Gtk.FileFilter(name=_("PDF documents"))
        flt.add_mime_type("application/pdf")
        flt.add_suffix("pdf")
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(flt)
        fd.set_filters(store)

        def done(dialog, res):
            try:
                f = dialog.save_finish(res)
            except GLib.Error:
                return          # cancelled: stay in the print dialog
            uri = f.get_uri()
            if not uri.lower().endswith(".pdf"):
                uri += ".pdf"
            self.choice.output_uri = uri
            self.finish(0)
        fd.save(self, None, done)

    def finish(self, response):
        if self._finished:
            return
        self._finished = True
        self.watcher.stop()
        if response == 0:
            config_set(printer=self.choice.printer)
        cb, self.on_done = self.on_done, None
        self.set_visible(False)
        if cb:
            cb(response, self.choice)
        self.destroy()

    # ------------------------------------------------------------------ parent window
    def _attach_parent(self, *_args):
        handle = self.opts.parent_window
        if not handle.startswith("wayland:"):
            return      # x11: GTK 4 has no API to parent to a foreign X window
        try:
            gi.require_version("GdkWayland", "4.0")
            from gi.repository import GdkWayland
            surface = self.get_surface()
            if isinstance(surface, GdkWayland.WaylandToplevel):
                surface.set_transient_for_exported(handle[len("wayland:"):])
        except (ValueError, ImportError, AttributeError) as e:
            print(f"fenestra-portal: cannot parent dialog: {e}", file=sys.stderr)

    # ------------------------------------------------------------------ test hooks
    def _test_accept(self):
        """Automated tests (no input devices in the lab): FENESTRA_PORTAL_TEST_ACCEPT=<ms> accepts
        the dialog after that delay, after applying FENESTRA_PORTAL_TEST_SET="printer=X,pages=odd,..."
        and saving a screenshot into FENESTRA_PORTAL_TEST_SHOT (a directory) if set."""
        for kv in filter(None, os.environ.get("FENESTRA_PORTAL_TEST_SET", "").split(",")):
            k, _sep, v = kv.partition("=")
            if k == "printer":
                self._select_printer(v)
            elif k == "copies":
                self.copies.set_value(int(v))
            elif k == "ranges":
                self.ranges.set_text(v.replace(";", ","))
            elif isinstance(getattr(self, k, None), Choices):
                getattr(self, k).set_value(v)
        shot_dir = os.environ.get("FENESTRA_PORTAL_TEST_SHOT")
        if shot_dir:
            def shoot():
                self.save_screenshot(os.path.join(shot_dir, f"dialog-{os.getpid()}-{int(GLib.get_monotonic_time())}.png"))
                self._on_print()
                return False
            GLib.timeout_add(300, shoot)
        else:
            self._on_print()
        return False

    # ------------------------------------------------------------------ screenshot (tests)
    def save_screenshot(self, path) -> bool:
        w, h = self.get_width(), self.get_height()
        paintable = Gtk.WidgetPaintable.new(self)
        snap = Gtk.Snapshot()
        paintable.snapshot(snap, w, h)
        node = snap.to_node()
        if node is None:
            return False
        rect = Graphene.Rect().init(0, 0, w, h)
        tex = None
        for make in (Gsk.GLRenderer.new, Gsk.CairoRenderer.new):
            try:
                r = make()
                r.realize_for_display(self.get_display())
                tex = r.render_texture(node, rect)
                r.unrealize()
                break
            except GLib.Error:
                continue
        if tex is None:
            tex = self.get_renderer().render_texture(node, rect)
        tex.save_to_png(path)
        print(f"saved {path} ({w}x{h})")
        return True
