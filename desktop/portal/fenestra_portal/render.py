# SPDX-License-Identifier: GPL-3.0-or-later
"""Drawing sheets: the preview (cairo on screen) and Save as PDF composition use the same code,
so what the preview shows is what gets written."""
from __future__ import annotations

import cairo

from . import metrics

MM_TO_PT = 72.0 / 25.4


def grid_for(n: int, landscape_sheet: bool) -> tuple[int, int]:
    """(columns, rows) for n pages per sheet."""
    table = {1: (1, 1), 2: (1, 2), 4: (2, 2), 6: (2, 3), 9: (3, 3), 16: (4, 4)}
    cols, rows = table.get(n, (1, 1))
    return (rows, cols) if landscape_sheet else (cols, rows)


def sheets_for(choice, n_pages: int) -> list[list[int]]:
    """Group the selected 0-based pages into sheets of choice.number_up."""
    idx = choice.selected_pages(n_pages)
    n = max(1, choice.number_up)
    return [idx[i:i + n] for i in range(0, len(idx), n)] or [[]]


def _cells(choice, w: float, h: float):
    cols, rows = grid_for(choice.number_up, w > h)
    gap = min(w, h) * metrics.PREVIEW_NUP_GAP if choice.number_up > 1 else 0.0
    cw, ch = (w - gap * (cols + 1)) / cols, (h - gap * (rows + 1)) / rows
    for i in range(cols * rows):
        r, col = divmod(i, cols)
        yield (gap + col * (cw + gap), gap + r * (ch + gap), cw, ch)


def draw_sheet(cr, choice, w: float, h: float, pages, colors=None, printing=False):
    """Draw one sheet of size w x h (user units) at the origin.

    pages: list of Poppler.Page, or None for a blank sheet (PreparePrint: the document does
    not exist yet), drawn as page outlines with faint text-line hints."""
    colors = colors or metrics.PREVIEW_LIGHT
    if not printing:
        cr.set_source_rgb(*colors["sheet"])
        cr.rectangle(0, 0, w, h)
        cr.fill()
    if not choice.color:
        cr.push_group()
    sheet_w_mm, sheet_h_mm = choice.sheet_mm()
    scale_mm = w / sheet_w_mm
    cells = list(_cells(choice, w, h))
    slots = pages if pages is not None else [None] * len(cells)
    for (cx, cy, cw, ch), page in zip(cells, slots):
        if page is None:
            _blank_page(cr, choice, cx, cy, cw, ch, scale_mm, colors)
        else:
            pw, ph = page.get_size()
            s = min(cw / pw, ch / ph)
            ox, oy = cx + (cw - pw * s) / 2, cy + (ch - ph * s) / 2
            cr.save()
            cr.translate(ox, oy)
            cr.scale(s, s)
            cr.rectangle(0, 0, pw, ph)
            cr.clip()
            if printing:
                page.render_for_printing(cr)
            else:
                page.render(cr)
            cr.restore()
            if choice.number_up > 1 and not printing:
                cr.set_source_rgba(*colors["outline"])
                cr.set_line_width(1)
                cr.rectangle(ox + 0.5, oy + 0.5, pw * s - 1, ph * s - 1)
                cr.stroke()
    if not choice.color:
        cr.pop_group_to_source()
        cr.paint()
        cr.set_operator(cairo.OPERATOR_HSL_SATURATION)
        cr.set_source_rgb(0.5, 0.5, 0.5)
        cr.rectangle(0, 0, w, h)
        cr.fill()
        cr.set_operator(cairo.OPERATOR_OVER)


def _blank_page(cr, choice, cx, cy, cw, ch, scale_mm, colors):
    """A page of the paper's shape inside the cell, with faint lines where text would go."""
    pw_mm, ph_mm = choice.sheet_mm()
    s = min(cw / pw_mm, ch / ph_mm)
    pw, ph = pw_mm * s, ph_mm * s
    ox, oy = cx + (cw - pw) / 2, cy + (ch - ph) / 2
    if choice.number_up > 1:
        cr.set_source_rgba(*colors["outline"])
        cr.set_line_width(1)
        cr.rectangle(ox + 0.5, oy + 0.5, pw - 1, ph - 1)
        cr.stroke()
    if not metrics.PREVIEW_PLACEHOLDER_LINES:
        return
    top, bottom, left, right = (m * s for m in choice.margins_mm())
    # A minimum inset so text hints never touch the edge, even with "no margins".
    inset = min(pw, ph) * 0.04
    x0, y0 = ox + max(left, inset), oy + max(top, inset)
    x1, y1 = ox + pw - max(right, inset), oy + ph - max(bottom, inset)
    line_h = max(1.0, ph * 0.012)
    step = line_h * 2.6
    cr.set_source_rgba(*colors["hint"])
    # title line
    cr.rectangle(x0, y0, (x1 - x0) * 0.45, line_h * 1.6)
    cr.fill()
    y = y0 + step * 1.8
    i = 0
    while y + line_h <= y1:
        frac = 0.62 if i % 7 == 6 else (0.94 if i % 3 else 1.0)
        if i % 7 != 0 or i == 0:
            cr.rectangle(x0, y, (x1 - x0) * frac, line_h)
            cr.fill()
        y += step
        i += 1


def compose_pdf(doc, choice, path: str):
    """Write the selected pages of doc to path, on the chosen paper and orientation, with
    pages per sheet applied (Save as PDF when the app called Print() without a token)."""
    w_mm, h_mm = choice.sheet_mm()
    w, h = w_mm * MM_TO_PT, h_mm * MM_TO_PT
    surface = cairo.PDFSurface(path, w, h)
    cr = cairo.Context(surface)
    for sheet in sheets_for(choice, doc.get_n_pages()):
        pages = [doc.get_page(i) for i in sheet]
        draw_sheet(cr, choice, w, h, pages, printing=True)
        cr.show_page()
    surface.finish()
