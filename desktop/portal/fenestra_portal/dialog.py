# SPDX-License-Identifier: GPL-3.0-or-later
"""The print dialog window.

Reference layout: a settings column on the left (heading, printer, copies, orientation,
pages, colour mode, a "more settings" link to a second page), the preview on the right
on a slightly darker neutral background with a sheet counter under it, and the accent
Print button plus Cancel at the bottom right. Sizes and colours live in metrics.py.
"""
from __future__ import annotations

import dataclasses
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


def icon(name: str, size: int) -> Gtk.Image:
    img = Gtk.Image.new_from_icon_name(name)
    img.set_pixel_size(size)
    return img


def item_factory(icons: dict | None, ellipsize: bool) -> Gtk.SignalListItemFactory:
    """Combo rows: an optional icon (orientation) and the label."""
    f = Gtk.SignalListItemFactory()

    def setup(_f, item):
        box = Gtk.Box()
        if icons:
            img = Gtk.Image(valign=Gtk.Align.CENTER)
            img.set_pixel_size(16)
            img.add_css_class("print-item-icon")
            box.append(img)
        lbl = Gtk.Label(xalign=0, valign=Gtk.Align.CENTER, hexpand=True)
        lbl.add_css_class("print-item-label")
        if ellipsize:
            lbl.set_ellipsize(3)   # Pango.EllipsizeMode.END
            lbl.set_width_chars(1)
        box.append(lbl)
        item.set_child(box)

    def bind(_f, item):
        text = item.get_item().get_string()
        box = item.get_child()
        lbl = box.get_last_child()
        lbl.set_label(text)
        if icons:
            box.get_first_child().set_from_icon_name(icons.get(text, ""))
    f.connect("setup", setup)
    f.connect("bind", bind)
    return f


def dropdown_popover(dd: Gtk.DropDown):
    child = dd.get_first_child()
    while child is not None:
        if isinstance(child, Gtk.Popover):
            return child
        child = child.get_next_sibling()
    return None


def menu_over_combo(dd: Gtk.DropDown, row_height: int, icon_menu=False):
    """The reference opens a combo's list over the combo, the selected row on top of it."""
    pop = dropdown_popover(dd)
    if pop is None:
        return
    pop.add_css_class("print-menu")
    if icon_menu:
        pop.add_css_class("print-icon-menu")
    pop.set_has_arrow(False)
    pop.set_position(Gtk.PositionType.BOTTOM)

    def place(*_a):
        h = dd.get_height() or metrics.CONTROL_HEIGHT
        sel = dd.get_selected()
        model = dd.get_model()
        if model is None or sel >= model.get_n_items():
            sel = 0
        pitch = row_height + 2 * metrics.MENU_ROW_MARGIN
        inset = 1 + metrics.MENU_PAD[0] + metrics.MENU_ROW_MARGIN
        shift = metrics.MENU_ICON_ROW_SHIFT if icon_menu else metrics.MENU_ROW_SHIFT
        top = shift - inset - sel * pitch
        pop.set_offset(0, top - h - metrics.MENU_POPUP_GAP)
    pop.connect("show", place)
    dd.connect("notify::selected", place)
    place()


class Choices(Gtk.DropDown):
    """A combo of (id, label) pairs; icons: {id: icon name} for an icon combo."""

    def __init__(self, items, selected=None, icons=None):
        self.ids = [i for i, _l in items]
        labels = [lbl for _i, lbl in items]
        super().__init__(model=Gtk.StringList.new(labels))
        self.add_css_class("print-dropdown")
        by_label = {lbl: icons[i] for i, lbl in items if i in icons} if icons else None
        if icons:
            self.add_css_class("print-icon-combo")
        # Ellipsize in the button so a long choice cannot widen the settings column.
        self.set_factory(item_factory(by_label, ellipsize=True))
        self.set_list_factory(item_factory(by_label, ellipsize=False))
        self.set_size_request(metrics.CONTROL_WIDTH, -1)
        self.set_halign(Gtk.Align.START)
        if selected in self.ids:
            self.set_selected(self.ids.index(selected))
        menu_over_combo(self, metrics.MENU_ICON_ROW_HEIGHT if icons else metrics.MENU_ROW_HEIGHT, bool(icons))

    @property
    def value(self):
        i = self.get_selected()
        return self.ids[i] if 0 <= i < len(self.ids) else None

    def set_value(self, v):
        if v in self.ids:
            self.set_selected(self.ids.index(v))


class Preview(Gtk.Stack):
    """The preview box: the sheets of the document, or a note when there is none
    (PreparePrint: through the portal the app hands the document over only after the
    dialog, so there is nothing to preview yet)."""

    def __init__(self, dialog):
        super().__init__()
        self.dialog = dialog
        self.add_css_class("print-preview-box")
        x, y, w, h = metrics.PREVIEW_BOX
        self.set_size_request(w, h)
        self.set_halign(Gtk.Align.START)
        self.set_valign(Gtk.Align.START)
        self.set_overflow(Gtk.Overflow.HIDDEN)
        self.index = 0
        self.fit_width = False
        note = Gtk.Label(label=_("This app doesn't support print preview"), wrap=True,
                         justify=Gtk.Justification.CENTER, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        note.add_css_class("print-preview-note")
        note.set_margin_top(2 * metrics.TEXT_NUDGE)
        self.add_named(note, "none")
        self.area = Gtk.DrawingArea(hexpand=True, vexpand=True)
        self.area.set_draw_func(self._draw)
        self.scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.scroller.set_child(self.area)
        self.add_named(self.scroller, "sheets")
        self.set_visible_child_name("sheets" if dialog.doc is not None else "none")

    def sheets(self):
        doc = self.dialog.doc
        if doc is None:
            return [None]
        return render.sheets_for(self.dialog.choice, doc.get_n_pages())

    def refresh(self):
        n = len(self.sheets())
        self.index = max(0, min(self.index, n - 1))
        d = self.dialog
        has_doc = d.doc is not None
        d.counter.set_label(f"{self.index + 1} / {n}" if has_doc else "")
        d.prev_btn.set_sensitive(has_doc and self.index > 0)
        d.next_btn.set_sensitive(has_doc and self.index < n - 1)
        if self.fit_width and has_doc:
            sw, sh = d.choice.sheet_mm()
            w = metrics.PREVIEW_BOX[2] - 2
            self.area.set_content_height(round((w - 2 * metrics.PREVIEW_MARGIN) * sh / sw + 2 * metrics.PREVIEW_MARGIN))
        else:
            self.area.set_content_height(0)
        self.area.queue_draw()

    def go(self, delta):
        self.index += delta
        self.refresh()

    def set_fit_width(self, on):
        self.fit_width = on
        self.refresh()

    def _draw(self, _area, cr, width, height):
        dark = theme.get().dark if theme.get() else False
        colors = metrics.PREVIEW_DARK if dark else metrics.PREVIEW_LIGHT
        c = self.dialog.choice
        sw, sh = c.sheet_mm()
        m = metrics.PREVIEW_MARGIN
        avail_w, avail_h = max(1, width - 2 * m), max(1, height - 2 * m)
        s = avail_w / sw if self.fit_width else min(avail_w / sw, avail_h / sh)
        w, h = sw * s, sh * s
        x, y = round((width - w) / 2), round((height - h) / 2) if not self.fit_width else m
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
        self.app_choice = dataclasses.replace(choice)     # what the app asked for
        self.doc = doc
        self.on_done = on_done
        self._finished = False
        self._loading = False
        self._user_picked_printer = False
        self.printers: dict[str, printing.PrinterInfo] = {}
        self.add_css_class("fenestra-print")
        self.set_title(app_title or _("Print"))
        self.set_default_size(metrics.CONTENT_WIDTH, metrics.CONTENT_HEIGHT)
        self.set_size_request(metrics.CONTENT_WIDTH, metrics.CONTENT_HEIGHT)
        self.set_resizable(False)
        self.set_modal(opts.modal)
        # The title row is part of the body (no title bar): an empty titlebar widget keeps
        # GTK from adding its own header bar.
        self.set_titlebar(Gtk.Box(visible=False))

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(outer)
        outer.append(self._header(app_title))

        body = Gtk.Box(vexpand=True)
        outer.append(body)
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        left.add_css_class("print-pane")
        left.set_size_request(metrics.LEFT_COLUMN_WIDTH, -1)
        left.set_hexpand(False)
        body.append(left)
        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT, vexpand=True)
        left.append(self.stack)
        self.stack.add_named(self._scroll(self._main_page()), "main")
        self.stack.add_named(self._scroll(self._more_page()), "more")

        self.preview = Preview(self)
        px, py, pw, ph = metrics.PREVIEW_BOX
        self.preview.set_margin_start(px - metrics.LEFT_COLUMN_WIDTH)
        self.preview.set_margin_top(py - metrics.HEADER_HEIGHT)
        body.append(self.preview)

        outer.append(self._footer())
        self.set_default_widget(self.print_button)
        self.print_button.connect("clicked", self._on_print)
        self.cancel_button.connect("clicked", lambda *_: self.finish(1))
        self.connect("close-request", self._on_close_request)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.add_controller(keys)
        if opts.parent_window:
            self.connect("realize", self._attach_parent)

        if not self.allow_app.get_active():
            self._apply_remembered()
        self._sync_from_choice()
        self.watcher = printing.PrinterWatcher(self._printer_added, self._printers_done, demo=opts.demo)
        theme.get().connect(self.preview.area.queue_draw)
        # The reference opens with the keyboard focus (ring and pill) on the printer combo.
        self.connect("map", lambda *_: (self.printer_dd.grab_focus(), self.set_focus_visible(True)))
        if os.environ.get("FENESTRA_PORTAL_TEST_ACCEPT"):
            GLib.timeout_add(int(os.environ["FENESTRA_PORTAL_TEST_ACCEPT"]), self._test_accept)

    # ------------------------------------------------------------------ building
    def _header(self, app_title):
        handle = Gtk.WindowHandle()
        fixed = Gtk.Fixed()
        fixed.set_size_request(metrics.CONTENT_WIDTH, metrics.HEADER_HEIGHT)
        handle.set_child(fixed)
        title = (_("{title} - Printing").format(title=app_title) if app_title else _("Printing"))
        tl = Gtk.Label(label=title, xalign=0, ellipsize=3)
        tl.add_css_class("print-title")
        tl.set_size_request(metrics.PREV_GLYPH[0] - metrics.HEADER_BUTTON - metrics.TITLE_X, -1)
        fixed.put(tl, metrics.TITLE_X, metrics.TITLE_Y + metrics.TEXT_NUDGE)
        self.summary = Gtk.Label(xalign=0, visible=False)
        self.summary.add_css_class("print-hint")
        fixed.put(self.summary, metrics.TITLE_X, metrics.TITLE_Y + metrics.LINE_HEIGHT + 2)

        hb = metrics.HEADER_BUTTON

        def put_button(btn, glyph):
            gx, gy, gw, gh = glyph
            fixed.put(btn, gx + gw // 2 - hb // 2, gy + gh // 2 - hb // 2)

        self.prev_btn = Gtk.Button(child=icon("fx-caret-left-symbolic", 8))
        self.prev_btn.set_tooltip_text(_("Previous page"))
        self.next_btn = Gtk.Button(child=icon("fx-caret-right-symbolic", 8))
        self.next_btn.set_tooltip_text(_("Next page"))
        self.fit_btn = Gtk.ToggleButton(child=icon("fx-fit-page-symbolic", 16))
        self.fit_btn.set_tooltip_text(_("Fit to width"))
        for b, g in ((self.prev_btn, metrics.PREV_GLYPH), (self.next_btn, metrics.NEXT_GLYPH),
                     (self.fit_btn, metrics.FIT_GLYPH)):
            b.add_css_class("print-nav")
            put_button(b, g)
        self.counter = Gtk.Label(xalign=0.5)
        self.counter.add_css_class("print-counter")
        cx0 = metrics.PREV_GLYPH[0] + metrics.PREV_GLYPH[2] // 2 + hb // 2
        cx1 = metrics.NEXT_GLYPH[0] + metrics.NEXT_GLYPH[2] // 2 - hb // 2
        self.counter.set_size_request(cx1 - cx0, hb)
        fixed.put(self.counter, cx0, metrics.PREV_GLYPH[1] + metrics.PREV_GLYPH[3] // 2 - hb // 2)
        self.prev_btn.connect("clicked", lambda *_: self.preview.go(-1))
        self.next_btn.connect("clicked", lambda *_: self.preview.go(+1))
        self.fit_btn.connect("toggled", lambda b: self.preview.set_fit_width(b.get_active()))

        close = Gtk.Button(child=icon("fx-close-symbolic", metrics.CLOSE_GLYPH))
        close.add_css_class("print-close")
        close.set_tooltip_text(_("Close"))
        close.set_focusable(False)
        close.set_size_request(metrics.CLOSE_BOX[2], metrics.CLOSE_BOX[3])
        close.connect("clicked", lambda *_: self.finish(1))
        fixed.put(close, metrics.CLOSE_BOX[0], metrics.CLOSE_BOX[1])
        return handle

    def _footer(self):
        footer = Gtk.Box()
        footer.add_css_class("print-footer")
        pad = metrics.FOOTER_PADDING
        lbl = Gtk.Label(label=_("Allow the app to change print preferences."), xalign=0, wrap=True)
        lbl.set_wrap_mode(2)   # Pango.WrapMode.WORD_CHAR
        lbl.set_max_width_chars(10)       # natural width = the request below, never wider
        lbl.set_lines(2)                  # and never taller than the footer
        lbl.set_ellipsize(3)
        lbl.set_size_request(metrics.BUTTON_X - 2 * pad - metrics.CHECK_SIZE - metrics.CHECK_TEXT_GAP, -1)
        self.allow_app = Gtk.CheckButton(child=lbl, valign=Gtk.Align.START, hexpand=True)
        self.allow_app.add_css_class("print-check")
        self.allow_app.set_active(config_get("allow_app", "1") != "0")
        self.allow_app.set_margin_start(pad)
        self.allow_app.set_margin_end(pad)
        self.allow_app.set_margin_top(pad + 1)
        self.allow_app.connect("toggled", self._on_allow_app)
        footer.append(self.allow_app)
        self.print_button = Gtk.Button(label=self.opts.accept_label or _("Print"), use_underline=True)
        self.cancel_button = Gtk.Button(label=_("Cancel"))
        for b, w in zip((self.print_button, self.cancel_button), metrics.BUTTON_WIDTHS):
            b.add_css_class("fluent-button")
            b.add_css_class("print-button")
            b.set_size_request(w, metrics.CONTROL_HEIGHT)
            b.set_valign(Gtk.Align.START)
            b.set_margin_top(pad)
            footer.append(b)
        self.print_button.set_margin_end(metrics.BUTTON_GAP)
        self.cancel_button.set_margin_end(pad)
        return footer

    @staticmethod
    def _scroll(child):
        sw = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        sw.set_child(child)
        return sw

    @staticmethod
    def _label(text, top=0, css="print-label"):
        lbl = Gtk.Label(label=text, xalign=0)
        lbl.add_css_class(css)
        lbl.set_margin_top(top + metrics.TEXT_NUDGE)
        return lbl

    def _field(self, box, label, widget, top=None):
        """A label over its control; returns the label. top: gap above the label."""
        lbl = self._label(label, metrics.FIELD_GAP if top is None else top)
        lbl.set_margin_bottom(metrics.LABEL_GAP - metrics.TEXT_NUDGE)
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

    def _link(self, text, icon_name=None):
        btn = Gtk.Button(halign=Gtk.Align.START)
        btn.add_css_class("print-link")
        lbl = Gtk.Label(label=text, valign=Gtk.Align.START)
        lbl.set_margin_top(metrics.TEXT_NUDGE)
        if icon_name:
            btn.add_css_class("print-icon-link")
            box = Gtk.Box()
            img = icon(icon_name, metrics.LINK_ICON)
            img.set_valign(Gtk.Align.CENTER)
            box.append(img)
            box.append(lbl)
            btn.set_child(box)
        else:
            btn.set_child(lbl)
        return btn

    def _main_page(self):
        box = self._column()

        # Printer: a combo of names; the list shows the location under each name.
        self.printer_ids: list[str] = []
        self.printer_model = Gtk.StringList()
        self.printer_dd = Gtk.DropDown(model=self.printer_model)
        self.printer_dd.add_css_class("print-dropdown")
        self.printer_dd.set_size_request(metrics.CONTROL_WIDTH, -1)
        self.printer_dd.set_halign(Gtk.Align.START)
        self.printer_dd.set_factory(self._printer_factory(False))
        self.printer_dd.set_list_factory(self._printer_factory(True))
        menu_over_combo(self.printer_dd, metrics.MENU_ROW_HEIGHT)
        self._field(box, _("Printer"), self.printer_dd, top=0)
        # Only a printer that needs attention gets a status line (offline, out of paper...).
        self.printer_status = Gtk.Label(xalign=0, wrap=True, max_width_chars=30, visible=False)
        self.printer_status.add_css_class("print-caption")
        self.printer_status.set_margin_top(4)
        box.append(self.printer_status)
        self._add_printer(printing.PrinterInfo(name=printing.PDF_PRINTER, label=_("Save as PDF"), is_pdf=True))
        self.printer_dd.connect("notify::selected", self._on_printer_changed)

        self.add_printer = self._link(_("Add a printer"), "fx-add-symbolic")
        self.add_printer.set_margin_top(metrics.LINK_GAP_ABOVE)
        self.add_printer.connect("clicked", self._on_add_printer)
        self.add_printer.set_visible(self.opts.demo or printing.printer_settings_command() is not None)
        box.append(self.add_printer)

        adj = Gtk.Adjustment(lower=1, upper=999, step_increment=1, page_increment=10, value=1)
        self.copies = Gtk.SpinButton(adjustment=adj, numeric=True)
        self.copies.set_size_request(metrics.CONTROL_WIDTH, -1)
        self.copies.set_halign(Gtk.Align.START)
        self.copies.add_css_class("print-spin")
        self.copies_label = self._field(box, _("Copies"), self.copies, top=metrics.LINK_GAP_BELOW)
        self.collate = Gtk.CheckButton(label=_("Collate"))
        self.collate.add_css_class("print-check")
        self.collate.set_margin_top(8)
        box.append(self.collate)

        self.orientation = Choices([("landscape", _("Landscape")), ("portrait", _("Portrait"))],
                                   icons={"portrait": "fx-page-portrait-symbolic",
                                          "landscape": "fx-page-landscape-symbolic"})
        self.orientation_label = self._field(box, _("Orientation"), self.orientation)

        # Pages: on this page for a printer; for Save as PDF it moves to the "more" page so
        # the main page keeps the reference layout (printer, orientation, print to file).
        self.pages_slot_main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(self.pages_slot_main)
        self.pages_field = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        pages = [("all", _("All pages")), ("odd", _("Odd pages only")), ("even", _("Even pages only"))]
        if self.opts.has_current:
            pages.append(("current", _("Current page")))
        if self.opts.has_selection:
            pages.append(("selection", _("Selection")))
        pages.append(("ranges", _("Custom range")))
        self.pages = Choices(pages)
        self.pages_label = self._field(self.pages_field, _("Pages"), self.pages)
        self.ranges = Gtk.Entry(placeholder_text=_("e.g. 1-5, 8, 11-13"))
        self.ranges.set_size_request(metrics.CONTROL_WIDTH, -1)
        self.ranges.set_halign(Gtk.Align.START)
        self.ranges.add_css_class("print-entry")
        self.ranges.set_margin_top(8)
        self.pages_field.append(self.ranges)
        self.pages_slot_main.append(self.pages_field)

        self.color = Choices([("color", _("Color")), ("mono", _("Black and white"))])
        self.color_label = self._field(box, _("Color mode"), self.color)

        self.to_file = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.to_file.add_css_class("print-switch")
        lbl = self._field(box, _("Print to file"), Gtk.Box())
        lbl.set_margin_bottom(0)
        row = Gtk.Box(spacing=metrics.TOGGLE_TEXT_GAP)
        row.set_margin_top(metrics.TOGGLE_LABEL_GAP - metrics.TEXT_NUDGE)
        row.append(self.to_file)
        self.to_file_state = Gtk.Label(xalign=0, valign=Gtk.Align.CENTER)
        self.to_file_state.set_margin_top(2 * metrics.TEXT_NUDGE)
        row.append(self.to_file_state)
        lbl.set_mnemonic_widget(self.to_file)
        box.append(row)
        hint = self._label(_("Stores printing output to a file"), metrics.HINT_GAP, "print-hint")
        hint.set_margin_bottom(-0)
        hint.set_wrap(True)
        hint.set_max_width_chars(10)      # natural width = the request below, never wider
        hint.set_size_request(metrics.CONTROL_WIDTH, -1)
        box.append(hint)

        more = self._link(_("More settings"))
        more.set_margin_top(metrics.MORE_GAP - metrics.TEXT_NUDGE)
        more.connect("clicked", lambda *_: self.stack.set_visible_child_name("more"))
        box.append(more)

        for w, sig in ((self.copies, "value-changed"), (self.collate, "toggled"),
                       (self.orientation, "notify::selected"), (self.pages, "notify::selected"),
                       (self.ranges, "changed"), (self.color, "notify::selected"),
                       (self.to_file, "notify::active")):
            w.connect(sig, self._on_changed)
        return box

    def _more_page(self):
        box = self._column()
        top = Gtk.Box(spacing=8)
        back = Gtk.Button(child=icon("fx-back-symbolic", 16), valign=Gtk.Align.CENTER)
        back.add_css_class("print-nav")
        back.set_tooltip_text(_("Back"))
        back.set_margin_start(-8)
        back.connect("clicked", lambda *_: self.stack.set_visible_child_name("main"))
        top.append(back)
        head = Gtk.Label(label=_("More settings"), xalign=0)
        head.add_css_class("print-title")
        top.append(head)
        top.set_margin_top(-8)
        box.append(top)
        self.pages_slot_more = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(self.pages_slot_more)

        papers = list(metrics.PAPER_SIZES)
        if self.choice.paper not in papers:
            papers.append(self.choice.paper)
        self.paper = Choices([(p, self._paper_label(p)) for p in papers])
        self._field(box, _("Paper size"), self.paper, top=metrics.FIELD_GAP - 8)
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
        """One line per printer, as the reference list (fixed row height keeps the open
        list aligned on the combo); the location goes to the row's tooltip."""
        f = Gtk.SignalListItemFactory()

        def setup(_f, item):
            name = Gtk.Label(xalign=0, ellipsize=3, valign=Gtk.Align.CENTER)
            name.add_css_class("print-item-label")
            if not in_list:
                name.set_width_chars(1)
            item.set_child(name)

        def bind(_f, item):
            info = self.printers.get(item.get_item().get_string())
            name = item.get_child()
            name.set_label(info.label if info else "")
            if in_list:
                name.set_tooltip_text(info.location if info and info.location else None)
        f.connect("setup", setup)
        f.connect("bind", bind)
        return f

    def _on_add_printer(self, *_args):
        cmd = printing.printer_settings_command()
        if cmd is None:
            return
        try:
            Gio.Subprocess.new(cmd, Gio.SubprocessFlags.NONE)
        except GLib.Error as e:
            print(f"fenestra-portal: cannot open printer settings: {e.message}", file=sys.stderr)

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
        """A status line only for a printer that needs attention; ready printers and
        Save as PDF keep the reference layout (the "Add a printer" link right under)."""
        info = self.printers.get(self._current_printer())
        text = ""
        if info is not None and not info.is_pdf and info.state and info.state_problem:
            text = info.state
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
        self.to_file.set_active(False)
        self._loading = False
        self._select_printer(self.preferred_printer)
        self._on_changed()

    def _read_choice(self):
        c = self.choice
        # Print to file: the job goes to a PDF file with this printer's settings.
        c.printer = printing.PDF_PRINTER if self.to_file.get_active() else self._current_printer()
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
        info = self.printers.get(self._current_printer())
        printer_is_pdf = info is None or info.is_pdf
        # Copies and colour mean nothing for a PDF file; the reference shows the PDF
        # printer with printer, orientation and print to file only.
        for w in (self.copies_label, self.copies, self.color_label, self.color):
            w.set_visible(not printer_is_pdf)
        self.collate.set_visible(not printer_is_pdf and c.copies > 1)
        self.orientation_label.set_margin_top(
            (metrics.LINK_GAP_BELOW if printer_is_pdf else metrics.FIELD_GAP) + metrics.TEXT_NUDGE)
        slot = self.pages_slot_more if printer_is_pdf else self.pages_slot_main
        if self.pages_field.get_parent() is not slot:
            self.pages_field.get_parent().remove(self.pages_field)
            slot.append(self.pages_field)
        self.pages_label.set_margin_top(
            (metrics.FIELD_GAP - 8 if printer_is_pdf else metrics.FIELD_GAP) + metrics.TEXT_NUDGE)
        self.to_file_state.set_label(_("On") if self.to_file.get_active() else _("Off"))
        self.ranges.set_visible(c.pages == "ranges")
        ok = self._ranges_valid()
        if ok:
            self.ranges.remove_css_class("error")
        else:
            self.ranges.add_css_class("error")
        self.print_button.set_sensitive(ok)
        self.duplex.set_visible(not c.is_pdf)
        self.duplex_label.set_visible(not c.is_pdf)
        self._update_status()
        self._update_summary()
        self.preview.refresh()

    # "Allow the app to change print preferences": off = the last settings used here win
    # over what the app asks for.
    _REMEMBERED = ("orientation", "color", "paper", "number_up", "margins", "duplex")

    def _remembered(self):
        out = {}
        for k in self._REMEMBERED:
            v = config_get(k, "")
            if v == "":
                continue
            if k == "color":
                out[k] = v == "1"
            elif k == "number_up":
                try:
                    out[k] = int(v)
                except ValueError:
                    continue
            else:
                out[k] = v
        return out

    def _apply_remembered(self):
        for k, v in self._remembered().items():
            setattr(self.choice, k, v)

    def _on_allow_app(self, btn):
        if self._loading:
            return
        if btn.get_active():
            for k in self._REMEMBERED:
                setattr(self.choice, k, getattr(self.app_choice, k))
        else:
            self._read_choice()
            self._apply_remembered()
        printer, self.choice.printer = self._current_printer(), self._current_printer()
        self._sync_from_choice()
        self._select_printer(printer)

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
            c = self.choice
            config_set(printer=self._current_printer(), allow_app="1" if self.allow_app.get_active() else "0",
                       orientation=c.orientation, color="1" if c.color else "0", paper=c.paper,
                       number_up=c.number_up, margins=c.margins, duplex=c.duplex)
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
            if k == "cancel":
                self.finish(1)
                return False
            if k == "printer":
                self._select_printer(v)
            elif k == "copies":
                self.copies.set_value(int(v))
            elif k == "ranges":
                self.ranges.set_text(v.replace(";", ","))
            elif k == "to_file":
                self.to_file.set_active(v in ("1", "on", "true"))
            elif k == "allow_app":
                self.allow_app.set_active(v in ("1", "on", "true"))
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
        """The window content plus any open combo list (pop-ups are separate surfaces)."""
        w, h = self.get_width(), self.get_height()
        snap = Gtk.Snapshot()
        Gtk.WidgetPaintable.new(self).snapshot(snap, w, h)
        wx, wy = self.get_surface_transform()
        for dd in (self.printer_dd, self.orientation, self.pages, self.color,
                   self.paper, self.number_up, self.margins, self.duplex):
            pop = dropdown_popover(dd)
            if pop is None or not pop.get_mapped():
                continue
            surf = pop.get_surface()
            px, py = pop.get_surface_transform()
            ox = surf.get_position_x() + px - wx
            oy = surf.get_position_y() + py - wy
            snap.save()
            snap.translate(Graphene.Point().init(ox, oy))
            Gtk.WidgetPaintable.new(pop).snapshot(snap, pop.get_width(), pop.get_height())
            snap.restore()
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
