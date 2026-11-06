"""Page setup and printing (Gtk.PrintOperation + GtkSource.PrintCompositor)."""
from __future__ import annotations

import os

import gi

gi.require_version("GtkSource", "5")
from gi.repository import Gtk, GtkSource, Pango  # noqa: E402

from . import util  # noqa: E402

_page_setup = None
_print_settings = None


def page_setup(parent, done=None):
    global _page_setup, _print_settings

    def finished(ps, *_):
        global _page_setup
        if ps is not None:
            _page_setup = ps
        if done:
            done()
    if _print_settings is None:
        _print_settings = Gtk.PrintSettings()
    Gtk.print_run_page_setup_dialog_async(parent, _page_setup, _print_settings, finished, None)


def print_document(parent, doc, on_error=None, export_to=None):
    """Print through the print dialog, or straight to a PDF file with export_to (tests)."""
    s = util.settings()
    comp = GtkSource.PrintCompositor.new(doc.buffer)
    family = s["font_family"] or util.DEFAULT_FONT
    style = s["font_style"]
    fd = Pango.FontDescription.from_string(family)
    fd.set_size(int(s["font_size"] * Pango.SCALE))
    if "bold" in style:
        fd.set_weight(Pango.Weight.BOLD)
    if "italic" in style:
        fd.set_style(Pango.Style.ITALIC)
    comp.set_body_font_name(fd.to_string())
    comp.set_wrap_mode(Pango.WrapMode.WORD_CHAR if s["word_wrap"] else Pango.WrapMode.CHAR)
    comp.set_highlight_syntax(doc.markdown and doc.formatting)
    comp.set_print_header(True)
    comp.set_header_format(True, os.path.basename(doc.path) if doc.path else doc.title, None, None)
    comp.set_print_footer(True)
    comp.set_footer_format(True, None, "%N", None)
    for side in (Gtk.Unit.MM,):
        comp.set_left_margin(20, side)
        comp.set_right_margin(20, side)
        comp.set_top_margin(25, side)
        comp.set_bottom_margin(25, side)

    op = Gtk.PrintOperation()
    op.set_job_name(doc.title)
    if _print_settings is not None:
        op.set_print_settings(_print_settings)
    if _page_setup is not None:
        op.set_default_page_setup(_page_setup)

    def paginate(_op, ctx):
        if comp.paginate(ctx):
            op.set_n_pages(comp.get_n_pages())
            return True
        return False

    def draw(_op, ctx, n):
        comp.draw_page(ctx, n)

    def done(_op, res):
        global _print_settings
        if res == Gtk.PrintOperationResult.APPLY:
            _print_settings = op.get_print_settings()
        elif res == Gtk.PrintOperationResult.ERROR and on_error:
            try:
                op.get_error()
            except Exception as e:  # noqa: BLE001  (GLib.Error)
                on_error(str(e))

    op.connect("paginate", paginate)
    op.connect("draw-page", draw)
    op.connect("done", done)
    op.set_allow_async(export_to is None)
    if export_to:
        op.set_export_filename(export_to)
    try:
        op.run(Gtk.PrintOperationAction.EXPORT if export_to else Gtk.PrintOperationAction.PRINT_DIALOG, parent)
    except Exception as e:  # noqa: BLE001  (GLib.Error)
        if on_error:
            on_error(str(e))
