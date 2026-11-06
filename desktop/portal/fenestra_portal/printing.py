# SPDX-License-Identifier: GPL-3.0-or-later
"""Print model: the user's choices, their mapping to GtkPrintSettings/GtkPageSetup,
printer discovery (GTK's own CUPS backend) and sending the document.

How the work is split with the app (see gtk/print/gtkprintoperation-portal.c):
* After PreparePrint the app renders the document itself, applying page ranges,
  odd/even, reverse and scale. For a real printer it leaves copies and pages per sheet
  to the printer; for print-to-file (an output-uri is set) it also makes the copies
  and the pages-per-sheet layout. Print() then gets that PDF.
* Print() without a token gets the app's untouched document, so page selection and
  pages per sheet are applied here: by CUPS options for a printer, by composing a new
  PDF (poppler + cairo) for Save as PDF.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass, field

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

from . import metrics  # noqa: E402

PDF_PRINTER = "Print to File"   # GTK's own name for its file printer; returned in settings["printer"]


# ------------------------------------------------------------------ page ranges

def parse_ranges(text: str, n_pages: int | None = None) -> list[tuple[int, int]]:
    """'1-3, 5, 8-' (1-based, as typed) -> [(0, 2), (4, 4), (7, n-1)] (0-based, inclusive).

    Raises ValueError on anything that is not a valid list."""
    out = []
    parts = [p.strip() for p in text.replace(";", ",").split(",")]
    if not any(parts):
        raise ValueError("empty")
    for p in parts:
        if not p:
            continue
        if "-" in p:
            a, _, b = p.partition("-")
            a, b = a.strip(), b.strip()
            start = int(a) if a else 1
            if b:
                end = int(b)
            elif n_pages:
                end = n_pages
            else:
                raise ValueError(p)
        else:
            start = end = int(p)
        if start < 1 or end < start:
            raise ValueError(p)
        if n_pages is not None and start > n_pages:
            raise ValueError(p)
        if n_pages is not None:
            end = min(end, n_pages)
        out.append((start - 1, end - 1))
    return out


def ranges_to_setting(ranges: list[tuple[int, int]]) -> str:
    """0-based ranges -> GtkPrintSettings 'page-ranges' value ('0-2,4')."""
    return ",".join(f"{a}" if a == b else f"{a}-{b}" for a, b in ranges)


def setting_to_text(value: str) -> str:
    """GtkPrintSettings 'page-ranges' (0-based) -> what the user types (1-based)."""
    out = []
    for p in (value or "").split(","):
        p = p.strip()
        if not p:
            continue
        try:
            if "-" in p:
                a, b = p.split("-", 1)
                out.append(f"{int(a) + 1}-{int(b) + 1}" if b else f"{int(a) + 1}-")
            else:
                out.append(str(int(p) + 1))
        except ValueError:
            continue
    return ", ".join(out)


# ------------------------------------------------------------------ choices

@dataclass
class Choice:
    printer: str = PDF_PRINTER
    copies: int = 1
    collate: bool = True
    orientation: str = "portrait"     # portrait | landscape
    pages: str = "all"                # all | odd | even | ranges | current | selection
    ranges_text: str = ""             # as typed, 1-based
    color: bool = True
    paper: str = "iso_a4"
    number_up: int = 1
    margins: str = "normal"           # see metrics.MARGIN_PRESETS
    duplex: str = "simplex"           # simplex | long | short
    output_uri: str = ""              # Save as PDF target
    extra: dict = field(default_factory=dict)   # app-provided settings we do not show, passed through

    @property
    def is_pdf(self) -> bool:
        return self.printer == PDF_PRINTER

    def page_size(self) -> Gtk.PaperSize:
        try:
            return Gtk.PaperSize.new(self.paper)
        except Exception:  # noqa: BLE001 - unknown name from an app
            return Gtk.PaperSize.new(Gtk.PaperSize.get_default())

    def sheet_mm(self) -> tuple[float, float]:
        """Paper size in mm as the sheet lies (width, height), orientation applied."""
        ps = self.page_size()
        w, h = ps.get_width(Gtk.Unit.MM), ps.get_height(Gtk.Unit.MM)
        return (h, w) if self.orientation == "landscape" else (w, h)

    def margins_mm(self) -> tuple[float, float, float, float]:
        """top, bottom, left, right in mm."""
        if self.margins == "none":
            return (0.0, 0.0, 0.0, 0.0)
        if self.margins == "narrow":
            m = metrics.NARROW_MARGIN_MM
            return (m, m, m, m)
        ps = self.page_size()
        return (ps.get_default_top_margin(Gtk.Unit.MM), ps.get_default_bottom_margin(Gtk.Unit.MM),
                ps.get_default_left_margin(Gtk.Unit.MM), ps.get_default_right_margin(Gtk.Unit.MM))

    def selected_pages(self, n_pages: int) -> list[int]:
        """0-based page indices this choice prints, for a document of n_pages."""
        if self.pages == "ranges":
            try:
                rs = parse_ranges(self.ranges_text, n_pages)
            except ValueError:
                rs = [(0, n_pages - 1)]
            idx = [i for a, b in rs for i in range(a, b + 1)]
        else:
            idx = list(range(n_pages))
        if self.pages == "odd":
            idx = [i for i in idx if i % 2 == 0]   # pages 1, 3, 5... as the user counts them
        elif self.pages == "even":
            idx = [i for i in idx if i % 2 == 1]
        return idx


def choice_from_gtk(settings: Gtk.PrintSettings, page_setup: Gtk.PageSetup | None) -> Choice:
    c = Choice()
    c.extra = {}
    settings.foreach(lambda k, v, *_: c.extra.__setitem__(k, v))
    c.printer = settings.get_printer() or ""
    c.copies = max(1, settings.get_n_copies())
    c.collate = settings.get_collate() if settings.has_key("collate") else True
    orient = page_setup.get_orientation() if page_setup else settings.get_orientation()
    if settings.has_key("orientation") and not page_setup:
        orient = settings.get_orientation()
    c.orientation = "landscape" if orient in (Gtk.PageOrientation.LANDSCAPE,
                                               Gtk.PageOrientation.REVERSE_LANDSCAPE) else "portrait"
    c.color = settings.get_use_color() if settings.has_key("use-color") else True
    pages = settings.get_print_pages()
    page_set = settings.get_page_set()
    if pages == Gtk.PrintPages.RANGES:
        c.pages = "ranges"
        c.ranges_text = setting_to_text(settings.get("page-ranges") or "")
        if not c.ranges_text:
            c.pages = "all"
    elif pages == Gtk.PrintPages.CURRENT:
        c.pages = "current"
    elif pages == Gtk.PrintPages.SELECTION:
        c.pages = "selection"
    elif page_set == Gtk.PageSet.ODD:
        c.pages = "odd"
    elif page_set == Gtk.PageSet.EVEN:
        c.pages = "even"
    ps = page_setup.get_paper_size() if page_setup else settings.get_paper_size()
    c.paper = ps.get_name() if ps else Gtk.PaperSize.get_default()
    n_up = settings.get_number_up() if settings.has_key("number-up") else 1
    c.number_up = n_up if n_up in metrics.PAGES_PER_SHEET else 1
    d = settings.get_duplex() if settings.has_key("duplex") else Gtk.PrintDuplex.SIMPLEX
    c.duplex = {Gtk.PrintDuplex.HORIZONTAL: "long", Gtk.PrintDuplex.VERTICAL: "short"}.get(d, "simplex")
    c.output_uri = settings.get("output-uri") or ""
    return c


# Settings this dialog owns; everything else the app sent is passed back untouched.
_OWNED = {"printer", "n-copies", "collate", "orientation", "use-color", "print-pages", "page-ranges",
          "page-set", "paper-format", "paper-width", "paper-height", "number-up", "duplex",
          "output-uri", "output-file-format", "output-basename"}


def choice_to_gtk(c: Choice) -> tuple[Gtk.PrintSettings, Gtk.PageSetup]:
    s = Gtk.PrintSettings.new()
    for k, v in c.extra.items():
        if k not in _OWNED and v is not None:
            s.set(k, v)
    s.set_printer(c.printer)
    s.set_n_copies(c.copies)
    s.set_collate(c.collate)
    orient = Gtk.PageOrientation.LANDSCAPE if c.orientation == "landscape" else Gtk.PageOrientation.PORTRAIT
    s.set_orientation(orient)
    s.set_use_color(c.color)
    s.set_page_set(Gtk.PageSet.ALL)
    if c.pages == "ranges":
        s.set_print_pages(Gtk.PrintPages.RANGES)
        try:
            s.set("page-ranges", ranges_to_setting(parse_ranges(c.ranges_text)))
        except ValueError:
            s.set_print_pages(Gtk.PrintPages.ALL)
    elif c.pages == "current":
        s.set_print_pages(Gtk.PrintPages.CURRENT)
    elif c.pages == "selection":
        s.set_print_pages(Gtk.PrintPages.SELECTION)
    else:
        s.set_print_pages(Gtk.PrintPages.ALL)
        if c.pages == "odd":
            s.set_page_set(Gtk.PageSet.ODD)
        elif c.pages == "even":
            s.set_page_set(Gtk.PageSet.EVEN)
    ps = c.page_size()
    s.set_paper_size(ps)
    s.set_number_up(c.number_up)
    s.set_duplex({"long": Gtk.PrintDuplex.HORIZONTAL, "short": Gtk.PrintDuplex.VERTICAL}
                 .get(c.duplex, Gtk.PrintDuplex.SIMPLEX))
    if c.is_pdf:
        s.set("output-file-format", "pdf")
        if c.output_uri:
            s.set("output-uri", c.output_uri)

    setup = Gtk.PageSetup.new()
    setup.set_paper_size(ps)
    setup.set_orientation(orient)
    top, bottom, left, right = c.margins_mm()
    setup.set_top_margin(top, Gtk.Unit.MM)
    setup.set_bottom_margin(bottom, Gtk.Unit.MM)
    setup.set_left_margin(left, Gtk.Unit.MM)
    setup.set_right_margin(right, Gtk.Unit.MM)
    return s, setup


# ------------------------------------------------------------------ printers

@dataclass
class PrinterInfo:
    name: str
    label: str
    location: str = ""
    state: str = ""
    is_default: bool = False
    is_pdf: bool = False
    accepts_pdf: bool = True
    gtk: object = None           # Gtk.Printer, None for the PDF entry and demo printers


DEMO_PRINTERS = (
    ("Office-Laser", "Office laser", "2nd floor", True),
    ("Color-Inkjet", "Color inkjet", "Studio", False),
    ("Label-Printer", "Label printer", "Front desk", False),
)


class PrinterWatcher:
    """Enumerates printers through GTK's print backends (CUPS); calls on_added(PrinterInfo)
    for each one as it appears, then on_done() once every backend has finished listing."""

    def __init__(self, on_added, on_done=None, demo=False):
        self.on_added = on_added
        self.on_done = on_done
        self.found: dict[str, PrinterInfo] = {}
        self._done = False
        if demo:
            from .i18n import _
            for name, label, loc, default in DEMO_PRINTERS:
                self._add(PrinterInfo(name=name, label=_(label), location=_(loc), is_default=default))
            GLib.idle_add(self._finish)
            return
        # Gtk.enumerate_printers(wait=False) reports printers from the main loop as backends
        # find them; GTK does not tell us when it is done, so "done" is a short quiet period.
        self._quiet = GLib.timeout_add(1500, self._finish)
        Gtk.enumerate_printers(self._on_printer, False)

    def _on_printer(self, printer, *_):
        if self._done:
            return True
        if printer.is_virtual():          # GTK's own "Print to File"; we offer Save as PDF instead
            return False
        info = PrinterInfo(name=printer.get_name(), label=printer.get_description() or printer.get_name(),
                           location=printer.get_location() or "", state=printer.get_state_message() or "",
                           is_default=printer.is_default(), accepts_pdf=printer.accepts_pdf(), gtk=printer)
        self._add(info)
        if self._quiet:
            GLib.source_remove(self._quiet)
        self._quiet = GLib.timeout_add(800, self._finish)
        return False

    def _add(self, info):
        if info.name in self.found:
            return
        self.found[info.name] = info
        self.on_added(info)

    def _finish(self):
        self._quiet = 0
        if not self._done:
            self._done = True
            if self.on_done:
                self.on_done()
        return False

    def stop(self):
        self._done = True
        if getattr(self, "_quiet", 0):
            GLib.source_remove(self._quiet)
            self._quiet = 0


def find_printer(name: str, callback, timeout_ms=10000):
    """Look a printer up by name; callback(Gtk.Printer | None)."""
    state = {"done": False}

    def finish(p):
        if not state["done"]:
            state["done"] = True
            callback(p)

    def on_added(info):
        if info.name == name and info.gtk is not None:
            watcher.stop()
            finish(info.gtk)

    watcher = PrinterWatcher(on_added, on_done=lambda: finish(None))
    GLib.timeout_add(timeout_ms, lambda: (finish(None), False)[1])


# ------------------------------------------------------------------ sending

def job_settings(c: Choice, app_already_applied: bool) -> tuple[Gtk.PrintSettings, Gtk.PageSetup]:
    """Settings for the CUPS job. CUPS options are passed as 'cups-<ipp name>' keys."""
    s, setup = choice_to_gtk(c)
    s.set("cups-print-color-mode", "color" if c.color else "monochrome")
    s.set("cups-sides", {"long": "two-sided-long-edge", "short": "two-sided-short-edge"}
          .get(c.duplex, "one-sided"))
    if c.number_up > 1:
        s.set("cups-number-up", str(c.number_up))
    if app_already_applied:
        # The app already left out unselected pages and applied reverse/scale.
        s.set_print_pages(Gtk.PrintPages.ALL)
        s.unset("page-ranges")
        s.set_page_set(Gtk.PageSet.ALL)
        s.set_reverse(False)
        s.set_scale(100.0)
    elif c.pages == "ranges":
        try:
            rs = parse_ranges(c.ranges_text)
            s.set("cups-page-ranges", ",".join(f"{a + 1}" if a == b else f"{a + 1}-{b + 1}" for a, b in rs))
        except ValueError:
            pass
    # page-set (odd/even) becomes cups-page-set in GTK's CUPS backend itself.
    return s, setup


def send_to_printer(printer: Gtk.Printer, title: str, path: str, c: Choice, app_already_applied: bool, done):
    """Queue the file on a CUPS printer; done(error_message | None)."""
    s, setup = job_settings(c, app_already_applied)
    try:
        job = Gtk.PrintJob.new(title or "Document", printer, s, setup)
        job.set_source_file(path)
    except GLib.Error as e:
        done(e.message)
        return

    def complete(_job, *rest):
        err = rest[-1] if rest and isinstance(rest[-1], GLib.Error) else None
        done(err.message if err else None)
    job.send(complete)


def save_pdf(src_path: str, c: Choice, doc=None) -> str:
    """Write the Save as PDF result; returns the path written.

    With doc (a Poppler.Document of the app's untouched output) the page selection,
    paper size, orientation and pages per sheet are applied by composing a new PDF."""
    dest = file_path_from_uri(c.output_uri) if c.output_uri else default_pdf_path("document")
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if doc is None:
        tmp = dest + ".part"
        shutil.copyfile(src_path, tmp)
        os.replace(tmp, dest)
        return dest
    from . import render
    tmp = dest + ".part"
    render.compose_pdf(doc, c, tmp)
    os.replace(tmp, dest)
    return dest


def file_path_from_uri(uri: str) -> str:
    from gi.repository import Gio
    return Gio.File.new_for_uri(uri).get_path() if "://" in uri else uri


def documents_dir() -> str:
    d = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOCUMENTS)
    return d or os.path.join(GLib.get_home_dir(), "Documents")


def safe_basename(title: str) -> str:
    name = "".join(ch for ch in (title or "") if ch not in '/\\:*?"<>|\n\r\t').strip(" .")
    return (name or "document")[:120]


def default_pdf_path(title: str) -> str:
    base = os.path.join(documents_dir(), safe_basename(title))
    path = base + ".pdf"
    i = 2
    while os.path.exists(path):
        path = f"{base} ({i}).pdf"
        i += 1
    return path


def spool_fd(fd: int) -> str:
    """Copy the document from the caller's fd to a private temporary file; returns its path."""
    rt = GLib.get_user_runtime_dir() or tempfile.gettempdir()
    out_fd, path = tempfile.mkstemp(prefix="fenestra-print-", suffix=".pdf", dir=rt)
    try:
        with os.fdopen(out_fd, "wb") as out, os.fdopen(fd, "rb", closefd=True) as src:
            shutil.copyfileobj(src, out, 1 << 20)
    except Exception:
        os.unlink(path)
        raise
    return path
