#!/usr/bin/env python3
"""Measure the Windows 11 reference dialogs and merge them into design/reference/measurements.json.

    tests/visual/measure_dialogs.py [SHOTS_DIR] [-o design/reference/measurements.json] [--print]

SHOTS_DIR = reference-shots/dialogs of the visual/screenshots branch (default: ../shots worktree).
Screens: «Guardar como» (30), «Abrir» (31), Imprimir (32), «Más opciones» (33), Recortes (34),
as dark-100-* and light-100-* (see reference-shots/README.md for the state suffixes).

What is measured how:
  * boxes      - flood fill of the control's fill colour from a seed pixel (tolerance 2-3), so a
                 1 px border is reported separately and the box is the border box (fill + border).
  * states     - the same seed pixel read in the -hover-/-pressed-/-focus-NN screenshots; the box of a
                 state that only appears on hover is the connected region of pixels that changed against
                 -normal (the pointer, the clock and the parked cursor at 1900,20 are masked out).
  * text       - the ink box inside a given area; font size = (top of ascenders .. baseline) / 0.727
                 (Segoe UI: ascender of l/d/b = 1490/2048 em); weight from stem width (reliable false).
  * menus      - menu box = changed region against -normal, body = flood of its background; rows from
                 the ink lines; the strings are read from the image by eye and written here.
Every value is {"value", "source" (screenshot file), "at" ([x, y] screen pixel), "reliable"}; x/y are
relative to the window's outer top-left (1 px border included) for the dialogs and to the screen for
Snipping Tool. Nothing from the screenshots is copied into the repo, only these numbers.
"""
import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dlglib as L  # noqa: E402

OWN_KEYS = ('file_dialog_save', 'file_dialog_open', 'file_dialog_menus', 'print_dialog', 'print_dialog_more',
            'print_dialog_menus', 'snip_overlay', 'snip_toolbar', 'snip_after_capture')
ROOT = None
THEMES = ('light', 'dark')


# ----------------------------------------------------------------------------- value helpers
def V(value, src, at, reliable=True, **extra):
    d = {'value': value, 'source': src if src.endswith('.png') else src + '.png', 'at': [int(at[0]), int(at[1])]}
    if not reliable:
        d['reliable'] = False
    d.update(extra)
    return d


def shot(name):
    return L.load(ROOT, name)


def have(name):
    return L.exists(ROOT, name)


def color(s, x, y):
    return V(L.hexc(s.px(x, y)), s.name, (x, y))


def rgba_over(fg_hex_on, bg_hex_under, bg_rgb):
    """Not used for snapping: alpha is fitted in dim_fit()."""
    raise NotImplementedError


def box_values(s, box, org, at):
    x0, y0, x1, y1 = box
    return {'x': V(x0 - org[0], s.name, at), 'y': V(y0 - org[1], s.name, at),
            'width': V(x1 - x0, s.name, at), 'height': V(y1 - y0, s.name, at)}


def border_box(s, inner, fill):
    """Grow a fill box by 1 px on each side whose outside pixel is a line (differs from the fill and
    from the pixel beyond it). Returns (box, {side: (colour, at)})."""
    x0, y0, x1, y1 = inner
    mx, my = (x0 + x1) // 2, (y0 + y1) // 2
    sides = {}
    probes = {'top': ((mx, y0 - 1), (mx, y0 - 2)), 'bottom': ((mx, y1), (mx, y1 + 1)),
              'left': ((x0 - 1, my), (x0 - 2, my)), 'right': ((x1, my), (x1 + 1, my))}
    for side, ((ax, ay), (bx, by)) in probes.items():
        if not (0 <= bx < s.W and 0 <= by < s.H):
            continue
        a, b = s.px(ax, ay), s.px(bx, by)
        if max(abs(a[i] - fill[i]) for i in range(3)) > 4 and max(abs(a[i] - b[i]) for i in range(3)) > 4:
            sides[side] = (L.hexc(a), (ax, ay))
    bx0 = x0 - (1 if 'left' in sides else 0)
    by0 = y0 - (1 if 'top' in sides else 0)
    bx1 = x1 + (1 if 'right' in sides else 0)
    by1 = y1 + (1 if 'bottom' in sides else 0)
    return (bx0, by0, bx1, by1), sides


def radius(s, box, outside):
    """Corner radius of a border box: count, along the top-left diagonal, the pixels that are still the
    colour outside the box (square corner = 0). Ignores the AA pixel."""
    x0, y0 = box[0], box[1]
    out = np.array(outside)
    i = 0
    while i < 12 and np.abs(s.a[y0 + i, x0 + i] - out).max() <= 6:
        i += 1
    return (round(i / 0.2929) if i else 0), (x0 + i, y0 + i)


def element(s, seed, org, tol=2, states=None, limit=None, rad=True, label=None):
    """Measure the control whose fill contains seed. states = {'hover': shot_name, ...}: the seed pixel
    (and the border probes) are read again in each of those screenshots."""
    fill = s.px(*seed)
    inner = L.flood_box(s, seed, tol, limit)
    box, sides = border_box(s, inner, fill)
    d = box_values(s, box, org, seed)
    d['background'] = {'normal': V(L.hexc(fill), s.name, seed)}
    if sides:
        d['border_width'] = V(1, s.name, sides[next(iter(sides))][1])
        d['border'] = {k: V(c, s.name, at) for k, (c, at) in sides.items()}
    if rad:
        outside = s.px(max(0, box[0] - 1), max(0, box[1] - 1))
        r, at = radius(s, box, outside)
        d['radius'] = V(r, s.name, at, reliable=r <= 1 or None)
        if r > 1:
            d['radius'].pop('reliable', None)
    for st, name in (states or {}).items():
        if not name or not have(name):
            continue
        t = shot(name)
        d['background'][st] = V(L.hexc(t.px(*seed)), t.name, seed)
        if sides:
            d.setdefault('border_states', {})[st] = {k: V(L.hexc(t.px(*at)), t.name, at) for k, (c, at) in sides.items()}
    return d


def changed_box(name, base, org, near=None, thr=6, merge=1, roi=None):
    """Box of the changed region (state vs base) that contains / is nearest to `near` (default: the
    pointer of the state shot). Returns (box, n) or (None, 0)."""
    s, b = shot(name), shot(base)
    m = L.diff_mask(s, b, thr=thr, roi=roi)
    comps = L.components(m, min_px=4, merge=merge)
    if not comps:
        return None, 0
    p = near or s.pointer
    if p is None:
        c = comps[0]
        return c[:4], c[4]
    px, py = p

    def dist(c):
        dx = max(c[0] - px, 0, px - c[2] + 1)
        dy = max(c[1] - py, 0, py - c[3] + 1)
        return dx * dx + dy * dy
    c = min(comps, key=lambda c: (dist(c), -c[4]))
    return c[:4], c[4]


def state_fill(name, box, base=None):
    """Dominant colour of a box in a state screenshot (the changed pixels only when base is given)."""
    s = shot(name)
    x0, y0, x1, y1 = box
    sub = s.a[y0:y1, x0:x1]
    mask = None
    if base:
        mask = np.abs(sub - shot(base).a[y0:y1, x0:x1]).max(axis=2) > 6
        p = s.pointer
        if p:
            l, t, r, b = L.POINTER_BOX
            if L.POINTER_BOX == L.CROSS:
                mask[max(0, p[1] - 2 - y0):max(0, p[1] + 3 - y0), max(0, p[0] + l - x0):max(0, p[0] + r - x0)] = False
                mask[max(0, p[1] + t - y0):max(0, p[1] + b - y0), max(0, p[0] - 2 - x0):max(0, p[0] + 3 - x0)] = False
            else:
                mask[max(0, p[1] + t - y0):max(0, p[1] + b - y0), max(0, p[0] + l - x0):max(0, p[0] + r - x0)] = False
    c = L.mode_color(sub, mask)
    if c is None:
        return None
    ys, xs = np.nonzero(np.all(sub == np.array(c), axis=2) & (mask if mask is not None else True))
    at = (x0 + int(xs[len(xs) // 2]), y0 + int(ys[len(ys) // 2]))
    return V(L.hexc(c), s.name, at)


def state_box(name, base, org, near=None, merge=1, roi=None, min_px=60):
    """Box of a control in a hover/pressed screenshot: take the changed pixels around the pointer, their
    dominant colour is the state fill; flood that fill from the changed pixel nearest the pointer and add
    the 1 px border. None when nothing (bigger than the I-beam) changed under the pointer."""
    s, b = shot(name), shot(base)
    p = near or s.pointer
    m = L.diff_mask(s, b, thr=2, roi=roi)
    comps = [c for c in L.components(m, min_px=min_px, merge=merge)
             if c[0] - 3 <= p[0] < c[2] + 3 and c[1] - 3 <= p[1] < c[3] + 3]
    if not comps:
        return None
    x0, y0 = max(0, p[0] - 24), max(0, p[1] - 14)
    x1, y1 = min(s.W, p[0] + 34), min(s.H, p[1] + 14)
    if L.POINTER_BOX == L.CROSS:
        x0, y0, x1, y1 = max(0, p[0] - 30), max(0, p[1] - 22), min(s.W, p[0] + 30), min(s.H, p[1] + 22)
    sub = s.a[y0:y1, x0:x1]
    mask = m[y0:y1, x0:x1].copy()
    c = L.mode_color(sub, mask)
    if c is None:
        return None
    ys, xs = np.nonzero(np.all(sub == np.array(c), axis=2) & mask)
    tx, ty = (p[0] - 12, p[1] - 12) if L.POINTER_BOX == L.CROSS else p   # crosshair: aim at the button corner
    k = int(np.argmin((xs + x0 - tx) ** 2 + (ys + y0 - ty) ** 2))
    at = (x0 + int(xs[k]), y0 + int(ys[k]))
    inner = L.flood_box(s, at, 2, limit=(max(0, at[0] - 700), max(0, at[1] - 120), min(s.W, at[0] + 700), min(s.H, at[1] + 120)))
    box, sides = border_box(s, inner, c)
    d = box_values(s, box, org, at)
    d['background'] = V(L.hexc(c), s.name, at)
    if sides:
        d['border'] = {k2: V(col, s.name, a2) for k2, (col, a2) in sides.items()}
    outside = s.px(max(0, box[0] - 1), max(0, box[1] - 1))
    r, rat = radius(s, box, outside)
    d['radius'] = V(r, s.name, rat)
    return d


# ----------------------------------------------------------------------------- text
ASC = 0.727   # Segoe UI ascender height (l, d, b, h, k) / em


def text(s, area, string, org, bg=None, reliable_size=True, two_lines=False):
    """Ink metrics of the text inside area (absolute screen box)."""
    x0, y0, x1, y1 = area
    if bg is None:
        bg = L.mode_color(s.a[y0:y1, x0:x1])
    ink = L.ink_box(s, area, bg, thr=60)
    if ink is None:
        return {'text': string, 'error': f'no ink in {area} of {s.file}'}
    ix0, iy0, ix1, iy1 = ink
    sub = s.a[iy0:iy1, ix0:ix1]
    dist = np.abs(sub - np.array(bg)).max(axis=2)
    strong = dist > 0.55 * dist.max()
    rows = strong.sum(axis=1)
    # baseline = the row where most glyph columns end (descenders and mnemonic underlines are few)
    cols = [int(np.nonzero(strong[:, j])[0].max()) for j in range(strong.shape[1]) if strong[:, j].any()]
    base = max(set(cols), key=cols.count)
    top = min(i for i, r in enumerate(rows) if r > 0)
    asc = base - top + 1
    d = {'text': V(string, s.name, (ix0, iy0)),
         'ink': box_values(s, ink, org, (ix0, iy0)),
         'color': _color_value(sub, dist, bg, s, (ix0, iy0)),
         'ascender_px': V(asc, s.name, (ix0, iy0 + top))}
    if two_lines:
        d['line_height'] = two_lines
    size = asc / ASC
    d['font_size'] = V(round(size), s.name, (ix0, iy0 + top), reliable=reliable_size,
                       estimate=round(size, 1), method='ascender/0.727 (Segoe UI)')
    # stem width: median horizontal run of strong ink
    runs = []
    for r in strong:
        n = 0
        for v in r:
            if v:
                n += 1
            elif n:
                runs.append(n)
                n = 0
        if n:
            runs.append(n)
    stem = round(float(np.mean(runs)), 2) if runs else 0
    d['font_weight'] = V(600 if stem / max(size, 1) > 0.2 else 400, s.name, (ix0, iy0), reliable=False,
                         stem_px=stem, method='mean horizontal run of strong ink / font size > 0.2 -> 600 (ClearType widens stems)')
    d['baseline_y'] = V(iy0 + base - org[1], s.name, (ix0, iy0 + base))
    return d


def _color_value(sub, dist, bg, s, at):
    c = _ink_color(sub, dist, bg)
    chroma = max(c) - min(c)
    if chroma > 20:
        return V(L.hexc(c), s.name, at, reliable=False,
                 note='mean of the strongest ink pixels: ClearType colour fringes make coloured text approximate')
    return V(L.hexc(c), s.name, at)


def _ink_color(sub, dist, bg):
    """Text colour. ClearType paints colour fringes on grey text, so the most extreme neutral pixel
    (max-min channel <= 20) that occurs at least twice wins; coloured text (links, accents) falls back
    to the most frequent of the strongest pixels."""
    chroma = sub.max(axis=2) - sub.min(axis=2)
    cand = (dist >= 0.5 * dist.max()) & (chroma <= 20)
    strong = dist >= 0.5 * dist.max()
    if cand.sum() >= max(3, 0.1 * strong.sum()):
        from collections import Counter
        cnt = Counter(map(tuple, sub[cand].tolist()))
        best = max((c for c, k in cnt.items() if k >= max(2, 0.05 * strong.sum())),
                   key=lambda c: max(abs(c[i] - bg[i]) for i in range(3)), default=None)
        if best is not None:
            return best
    top = dist >= np.percentile(dist[dist > 0], 90)
    return tuple(int(round(v)) for v in sub[top].mean(axis=0))


def rel(org, pt):
    return (org[0] + pt[0], org[1] + pt[1])


def relbox(org, b):
    return (org[0] + b[0], org[1] + b[1], org[0] + b[2], org[1] + b[3])


# ----------------------------------------------------------------------------- file dialogs
# Window outer top-left (1 px border included), found with tests/visual/dlglib.flood_box on the
# title bar plus the border line (checked in light-100-30-save-normal at x=247/y=234 and
# dark-100-30-save-normal at x=313/y=200); the same in every state screenshot of the series.
FILE_ORG = {'light': (247, 234), 'dark': (313, 200)}

# Static parts: name -> (seed relative to the window origin, flood tolerance[, search limit rel. to window])
FILE_REGIONS = {
    'titlebar': ((150, 6), 1),
    'navigation_row': ((12, 36), 1),
    'address_box': ((450, 58), 1),
    'search_box': ((760, 46), 1),
    'command_bar': ((450, 100), 1),
    'navigation_pane': ((12, 360), 1),
    'navigation_scrollbar': ((143, 300), 1),
    'details_list': ((560, 300), 1),
    'bottom_fields_area': ((60, 445), 1),
    'bottom_buttons_area': ((360, 516), 1),
    'filename_field': ((660, 396), 1),
    'type_combo': ((660, 422), 1),
    'encoding_combo': ((660, 508), 1),
    'primary_button': ((748, 506), 1),
    'cancel_button': ((848, 506), 1),
}
OPEN_REGIONS = dict(FILE_REGIONS)
OPEN_REGIONS.update({
    'navigation_pane': ((12, 440), 1),
    'navigation_scrollbar': ((143, 300), 1, (100, 117, 200, 451)),
    'details_list': ((560, 260), 1),
    'bottom_fields_area': ((60, 456), 1, (0, 451, 946, 533)),
    'filename_field': ((470, 471), 1),
    'type_combo': ((910, 465), 1),
})
OPEN_REGIONS.pop('bottom_buttons_area')


# Hover/pressed controls: key -> (save suffix, open suffix, tooltip es, tooltip en)
FILE_CONTROLS = {
    'close_button': ('close', 'close', None, None),
    'back_button': ('back', 'back', 'Atrás (Alt + Flecha izquierda)', 'Back (Alt + Left Arrow)'),
    'forward_button': ('forward', 'forward', 'Adelante (Alt + Flecha derecha)', 'Forward (Alt + Right Arrow)'),
    'recent_button': ('recent', 'recent', 'Ubicaciones recientes', 'Recent locations'),
    'up_button': ('up', 'up', 'Subir a "Escritorio" (Alt + Flecha arriba)', 'Up to "Desktop" (Alt + Up Arrow)'),
    'address_box': ('address', 'address', None, None),
    'address_dropdown': ('address-dropdown', 'address-dropdown', 'Ubicaciones anteriores', 'Previous Locations'),
    'refresh_button': ('refresh', 'refresh', 'Actualizar "Documentos" (F5)', 'Refresh "Documentos" (F5)'),
    'search_box': ('search', 'search', None, None),
    'organize_button': ('organizar', 'organize', 'Organiza el contenido de esta carpeta.', "Organize this folder's contents."),
    'new_folder_button': ('nueva-carpeta', 'new-folder', 'Crea una nueva carpeta.', 'Create a new folder.'),
    'view_button': ('view', 'view', 'Cambia la vista.', 'Change your view.'),
    'view_dropdown': ('view-dropdown', 'view-dropdown', 'Más opciones', 'More options'),
    'preview_pane_button': (None, 'preview-pane', None, 'Show the preview pane.'),
    'help_button': ('help', 'help', 'Muestra ayuda.', 'Get help.'),
    'nav_item': ('nav-galeria', 'nav-gallery', None, None),
    'nav_expand_chevron': ('nav-expand-onedrive', None, None, None),
    'nav_item_pinned': (None, 'nav-escritorio', None, None),
    'column_header': ('header-nombre', 'header-name', None, None),
    'column_header_2': ('header-fecha', None, None, None),
    'list_row': ('row-informe', 'row-informe', None, None),
    'filename_field': ('nombre-field', 'filename-field', None, None),
    'type_combo': ('tipo-combo', 'filter-combo', None, None),
    'encoding_combo': ('encoding', 'encoding', None, None),
    'primary_button': ('guardar', 'open', None, None),
    'cancel_button': ('cancelar', 'cancel', None, None),
    'hide_folders_button': ('ocultar-carpetas', None, None, None),
}

# Text areas relative to the window (generous boxes: the ink inside is measured). key -> (box, es, en)
FILE_TEXT_SAVE = {
    'title': ((28, 6, 120, 26), 'Save as'),
    'address_crumb': ((180, 48, 300, 68), 'Documentos'),
    'search_placeholder': ((737, 48, 900, 68), 'Buscar en Documentos'),
    'organize': ((15, 91, 75, 111), 'Organizar'),
    'new_folder': ((110, 91, 200, 111), 'Nueva carpeta'),
    'header_name': ((188, 120, 260, 140), 'Nombre'),
    'header_date': ((436, 120, 570, 140), 'Fecha de modificación'),
    'header_type': ((580, 120, 620, 140), 'Tipo'),
    'header_size': ((700, 120, 760, 140), 'Tamaño'),
    'row_name': ((196, 151, 300, 170), 'Informe trimestral'),
    'row_date': ((436, 151, 530, 170), '07/11/2026 2:00'),
    'row_type': ((580, 151, 670, 170), 'Text Document'),
    'row_size': ((740, 151, 775, 170), '1 KB'),
    'nav_home': ((53, 129, 95, 149), 'Inicio'),
    'nav_gallery': ((53, 161, 100, 181), 'Galería'),
    'nav_onedrive': ((53, 193, 110, 213), 'OneDrive'),
    'nav_desktop': ((53, 257, 110, 277), 'Escritorio'),
    'nav_downloads': ((53, 289, 115, 309), 'Descargas'),
    'nav_documents': ((53, 321, 125, 341), 'Documentos'),
    'nav_pictures': ((53, 353, 112, 373), 'Imágenes'),
    'filename_label': ((60, 387, 124, 407), 'Nombre:'),
    'type_label': ((60, 412, 124, 432), 'Tipo:'),
    'filename_value': ((134, 390, 224, 404), 'Informe trimestral'),
    'type_value': ((128, 413, 260, 432), 'Text documents (*.txt)'),
    'hide_folders': ((28, 494, 125, 514), 'Ocultar carpetas'),
    'encoding_label': ((517, 492, 575, 512), 'Encoding:'),
    'encoding_value': ((580, 492, 640, 512), 'UTF-8'),
    'primary_button': ((760, 492, 810, 512), 'Guardar'),
    'cancel_button': ((855, 492, 915, 512), 'Cancelar'),
}
FILE_TEXT_OPEN = {
    'title': ((28, 6, 120, 26), 'Open'),
    'address_crumb': ((180, 48, 300, 68), 'Documentos'),
    'search_placeholder': ((737, 48, 900, 68), 'Search Documentos'),
    'organize': ((15, 91, 75, 111), 'Organize'),
    'new_folder': ((105, 91, 175, 111), 'New folder'),
    'header_name': ((188, 120, 260, 140), 'Name'),
    'header_date': ((436, 120, 570, 140), 'Date modified'),
    'header_type': ((580, 120, 620, 140), 'Type'),
    'header_size': ((700, 120, 760, 140), 'Size'),
    'row_name': ((196, 151, 300, 170), 'Informe trimestral'),
    'row_date': ((436, 151, 530, 170), '07/11/2026 2:00'),
    'row_type': ((580, 151, 670, 170), 'Text Document'),
    'row_size': ((740, 151, 775, 170), '1 KB'),
    'nav_home': ((53, 129, 95, 149), 'Home'),
    'nav_gallery': ((53, 161, 100, 181), 'Gallery'),
    'nav_onedrive': ((53, 193, 110, 213), 'OneDrive'),
    'nav_desktop': ((53, 257, 110, 277), 'Escritorio'),
    'nav_downloads': ((53, 289, 115, 309), 'Descargas'),
    'nav_documents': ((53, 321, 125, 341), 'Documentos'),
    'nav_pictures': ((53, 353, 112, 373), 'Imágenes'),
    'nav_music': ((53, 385, 112, 405), 'Música'),
    'nav_videos': ((53, 417, 112, 437), 'Vídeos'),
    'filename_label': ((120, 461, 188, 481), 'File name:'),
    'type_value': ((742, 461, 870, 481), 'Text documents (*.txt)'),
    'encoding_label': ((517, 492, 575, 512), 'Encoding:'),
    'encoding_value': ((580, 492, 660, 512), 'Auto-Detect'),
    'primary_button': ((760, 492, 810, 512), 'Open'),
    'cancel_button': ((855, 492, 915, 512), 'Cancel'),
}


def file_dialog(kind):
    pre = {'save': '30-save', 'open': '31-open'}[kind]
    regions = FILE_REGIONS if kind == 'save' else OPEN_REGIONS
    texts = FILE_TEXT_SAVE if kind == 'save' else FILE_TEXT_OPEN
    lang = 'es' if kind == 'save' else 'en'
    out = {'_about': ('«Guardar como» (Bloc de notas, Ctrl+Mayús+S): title and caption in English (Notepad is an '
                      'English Store app), labels and buttons in Spanish.' if kind == 'save' else
                      '«Abrir» (Bloc de notas, Ctrl+A): the whole dialog is in English in this VM.'),
           'coordinates': 'x/y relative to the window outer top-left (1 px frame included); at = screen pixel'}
    for th in THEMES:
        p = f'{th}-100-{pre}'
        n = shot(p + '-normal')
        org = FILE_ORG[th]
        o = {}
        tb = L.flood_box(n, rel(org, (150, 6)), 1)
        win = (tb[0] - 1, tb[1] - 1, tb[2] + 1, frame_bottom(n, tb[0] - 1, tb[1] + 200))
        o['window'] = box_values(n, win, org, (win[0], win[1]))
        o['window']['frame'] = color(n, win[0], win[1] + 200)
        o['window']['frame_top'] = color(n, win[0] + 300, win[1])
        o['window']['radius'] = V(0, n.name, (win[0], win[1]), reliable=False,
                                  note='square in the VM (basic display adapter, DWM does not round corners)')
        o['window']['shadow'] = V('present below/right, soft', n.name, (win[0] + 300, win[3] + 2), reliable=False)
        for name, spec in regions.items():
            seed, tol = spec[:2]
            lim = relbox(org, spec[2]) if len(spec) > 2 else None
            o[name] = element(n, rel(org, seed), org, tol, limit=lim, rad=name.endswith(('button', 'combo')))
        # selected (but unfocused) navigation item: OneDrive
        o['nav_item_selected'] = element(n, rel(org, (28, 191)), org, 1, rad=False,
                                         states={'focus': p + '-focus-01'})
        o['nav_divider'] = element(n, rel(org, (53, 235)), org, 1, rad=False)
        # hovered / pressed / tooltips
        ctl = {}
        for key, (ss, os_, tes, ten) in FILE_CONTROLS.items():
            suf = ss if kind == 'save' else os_
            if not suf:
                continue
            h = f'{p}-hover-{suf}'
            if not have(h):
                continue
            c = {}
            hb = state_box(h, p + '-normal', org)
            if hb:
                c['hover'] = hb
            else:
                c['hover'] = V(None, h, shot(h).pointer, note='no visible change under the pointer (disabled or plain field)')
            pr = f'{p}-pressed-{suf}'
            if have(pr):
                pb = state_box(pr, p + '-normal', org)
                if pb:
                    c['pressed'] = pb
            tip = ten if kind == 'open' else tes
            if tip:
                c['tooltip'] = tooltip(h, p + '-normal', org, tip)
            ctl[key] = c
        o['states'] = ctl
        # focus ring order
        o['focus_order'] = focus_steps(p, org, win, FOCUS_LABELS[kind])
        o['text'] = {}
        for key, (b, string) in texts.items():
            o['text'][key] = text(n, relbox(org, b), string, org)
        out[th] = o
    out['lang'] = lang
    return out


def tooltip(h, base, org, string):
    """The tooltip is the changed region below the pointer that does not contain it."""
    s = shot(h)
    m = L.diff_mask(s, shot(base), thr=2)
    px, py = s.pointer
    best = None
    for c in L.components(m, min_px=20, merge=1):
        x0, y0, x1, y1, k = c
        if y0 > py + 8 and x0 - 60 < px < x1 + 200 and (y1 - y0) < 60 and (x1 - x0) > 30:
            if best is None or y0 < best[1]:
                best = c
    if not best:
        return V(None, h, (px, py), note='tooltip not visible in this capture')
    x0, y0, x1, y1, k = best
    c = L.mode_color(s.a[y0:y1, x0:x1], m[y0:y1, x0:x1])
    ys, xs = np.nonzero(np.all(s.a[y0:y1, x0:x1] == np.array(c), axis=2) & m[y0:y1, x0:x1])
    k2 = int(np.argmin((xs - (x1 - x0) / 2) ** 2 + (ys - (y1 - y0) / 2) ** 2 * 4))
    seed = (x0 + int(xs[k2]), y0 + int(ys[k2]))
    d = element(s, seed, org, 1, rad=False)
    if d['width']['value'] < 30 or d['height']['value'] < 12:
        return V(None, h, (px, py), note='tooltip overlaps the previous one (fade) or the control: not separable')
    d['text'] = text(s, (x0 + 2, y0 + 2, x1 - 2, y1 - 2), string, org)
    d['shadow'] = V('1-2 px soft, right and bottom', h, (x1, y1), reliable=False)
    return d


FOCUS_LABELS = {
    'save': ['navigation pane (selected OneDrive item gets a 1 px dark focus border)', 'details list row',
             'column header «Nombre»', '«Nombre» field (caret, text selected)', '«Tipo» combo',
             '«Ocultar carpetas»', '«Encoding» combo', '«Guardar» button'],
    'open': ['navigation pane (OneDrive)', 'details list row', 'column header «Name»', '«File name» field',
             'file type filter combo', '«Encoding» combo', '«Open» button', '«Cancel» button'],
}


def focus_steps(p, org, win, labels):
    """What changes after N Tab presses (only changes inside the dialog window)."""
    base = p + '-normal'
    steps = []
    for i in range(1, 12):
        f = f'{p}-focus-{i:02d}'
        if not have(f):
            break
        s = shot(f)
        m = L.diff_mask(s, shot(base))
        comps = [c for c in L.components(m, min_px=8, merge=1)
                 if c[0] >= win[0] and c[1] >= win[1] and c[2] <= win[2] and c[3] <= win[3]]
        steps.append({'step': i, 'source': s.file, 'focused': labels[i - 1] if i <= len(labels) else None,
                      'changed': [dict(box_values(s, c[:4], org, (c[0], c[1])), background=state_fill(f, c[:4], base))
                                  for c in comps[:3]]})
    return steps


# ----------------------------------------------------------------------------- generic screen
def screen(prefixes, orgs, regions, controls, texts, focus_labels=None, window=None, extra_states=None):
    """prefixes/orgs: {theme: shot prefix / window origin}. regions: {name: (seed_rel, tol[, limit_rel])} measured
    on -normal with their colours re-read in the states listed in extra_states {name: {state: suffix}}.
    controls: {name: (hover suffix, pressed suffix)} measured from the state screenshots.
    texts: {name: (box_rel, string[, shot suffix])}. window: (w, h) measured outer size check."""
    out = {}
    for th, p in prefixes.items():
        if not have(p + '-normal'):
            continue
        n = shot(p + '-normal')
        org = orgs[th]
        o = {}
        if window:
            wx1, wy1 = window
            o['window'] = box_values(n, (org[0], org[1], org[0] + wx1, org[1] + wy1), org, org)
            o['window']['frame'] = color(n, org[0], org[1] + wy1 // 2)
            o['window']['radius'] = V(0, n.name, org, reliable=False,
                                      note='square in the VM (no GPU); Windows 11 rounds top-level windows 8 px')
        for name, spec in regions.items():
            seed, tol = spec[:2]
            lim = relbox(org, spec[2]) if len(spec) > 2 and spec[2] else None
            st = {k: f'{p}-{v}' for k, v in (extra_states or {}).get(name, {}).items()}
            o[name] = element(n, rel(org, seed), org, tol, limit=lim, states=st)
            if name in OUTLINE:
                bg_at = rel(org, OUTLINE[name])
                ob = outline_box(n, rel(org, seed), n.px(*bg_at))
                o[name].update(box_values(n, ob, org, rel(org, seed)))
                o[name]['radius'] = V((ob[3] - ob[1]) // 2 if name == 'toggle' else o[name]['radius']['value'],
                                      n.name, (ob[0], ob[1]),
                                      note='outline box: first pixel that differs from the surrounding background')
                o[name].pop('border', None)
                o[name]['outline'] = color(n, ob[0], (ob[1] + ob[3]) // 2)
        ctl = {}
        for key, (hs, ps) in controls.items():
            c = {}
            for st, suf in (('hover', hs), ('pressed', ps)):
                if not suf or not have(f'{p}-{suf}'):
                    continue
                b = state_box(f'{p}-{suf}', p + '-normal', org)
                c[st] = b if b else V(None, f'{p}-{suf}', shot(f'{p}-{suf}').pointer,
                                      note='no visible change under the pointer in this capture')
            if c:
                ctl[key] = c
        if ctl:
            o['states'] = ctl
        if focus_labels:
            o['focus_order'] = focus_steps(p, org, (org[0], org[1], org[0] + window[0], org[1] + window[1]),
                                           focus_labels)
        o['text'] = {}
        for key, spec in texts.items():
            b, string = spec[:2]
            src = shot(f'{p}-{spec[2]}') if len(spec) > 2 else n
            o['text'][key] = text(src, relbox(org, b), string, org)
        out[th] = o
    return out


# controls measured by their outline against the background read at this point (relative to the window)
OUTLINE = {'toggle': (20, 301), 'checkbox': (20, 693)}


def outline_box(s, seed, bg, tol=0):
    """Walk out from seed along its row and column until the pixel is the background colour again."""
    x, y = seed
    bg = np.array(bg)

    def isbg(xx, yy):
        return np.abs(s.a[yy, xx] - bg).max() <= tol
    l = x
    while not isbg(l - 1, y):
        l -= 1
    r = x
    while not isbg(r + 1, y):
        r += 1
    cx = (l + r) // 2
    t = y
    while not isbg(cx, t - 1):
        t -= 1
    b = y
    while not isbg(cx, b + 1):
        b += 1
    return (l, t, r + 1, b + 1)


# ----------------------------------------------------------------------------- print dialog (32)
PRINT_ORG = (374, 117)     # outer frame top-left, same in both themes (frame at x=374/1225, y=117/850)
PRINT_REGIONS = {
    'body': ((10, 10), 1),
    'footer': ((10, 700), 1),
    'footer_separator': ((10, 652), 1),
    'printer_combo': ((226, 115), 1),
    'orientation_combo': ((226, 213), 1),
    'toggle': ((56, 301), 1),
    'checkbox': ((26, 693), 1),
    'print_button': ((446, 683), 1),
    'cancel_button': ((646, 683), 1),
    'preview_area': ((326, 183), 1),
}
PRINT_REGION_STATES = {
    'printer_combo': {'hover': 'hover-printer', 'pressed': 'pressed-printer', 'unfocused': 'focus-01'},
    'orientation_combo': {'hover': 'hover-orientation', 'focus': 'focus-04'},
    'toggle': {'hover': 'hover-toggle', 'on': 'click-toggle-on', 'off_again': 'click-toggle-off', 'focus': 'focus-05'},
    'checkbox': {'hover': 'hover-checkbox', 'focus': 'focus-07'},
    'print_button': {'hover': 'hover-imprimir', 'pressed': 'pressed-imprimir'},
    'cancel_button': {'hover': 'hover-cancelar', 'pressed': 'pressed-cancelar'},
}
PRINT_CONTROLS = {
    'close_button': ('hover-close', None),
    'fit_button': ('hover-fit', None),
    'prev_page_button': ('hover-prev-page', None),
    'next_page_button': ('hover-next-page', None),
    'add_printer_link': ('hover-add-printer', None),
    'more_options_link': ('hover-more-options', None),
    'toggle': ('hover-toggle', None),
    'checkbox': ('hover-checkbox', None),
}
PRINT_TEXT = {
    'title': ((20, 24, 320, 48), 'Printing from Win32 application - Impresión'),
    'printer_label': ((20, 82, 100, 102), 'Impresora'),
    'printer_value': ((34, 112, 180, 136), 'Microsoft Print to PDF'),
    'add_printer': ((46, 154, 200, 176), 'Agregar una impresora'),
    'orientation_label': ((20, 176, 110, 198), 'Orientation'),
    'orientation_value': ((60, 210, 120, 234), 'Portrait'),
    'print_to_file_label': ((20, 262, 110, 282), 'Print to file'),
    'toggle_off': ((74, 290, 160, 314), 'Desactivado'),
    'toggle_on': ((74, 290, 160, 314), 'Activado', 'click-toggle-on'),
    'print_to_file_hint': ((20, 320, 220, 344), 'Stores printing output to a file'),
    'more_options': ((20, 356, 225, 380), 'Más opciones de configuración'),
    'no_preview': ((400, 344, 745, 368), 'Esta aplicación no admite la vista previa de impresión'),
    'checkbox_line1': ((50, 680, 380, 697), 'Permitir que la aplicación cambie las preferencias de'),
    'checkbox_line2': ((50, 698, 120, 717), 'impresión.'),
    'print_button': ((500, 683, 560, 703), 'Imprimir'),
    'cancel_button': ((700, 683, 762, 703), 'Cancelar'),
}
PRINT_FOCUS = ['fit-to-page button in the preview header (the printer combo had the initial keyboard focus ring)',
               'no visible change (focus on a disabled/invisible element, probably the preview)',
               '«Agregar una impresora» link', 'Orientation combo', 'Print to file toggle',
               '«Más opciones de configuración» link', 'checkbox «Permitir que la aplicación…»']


def print_dialog():
    out = {'_about': 'Modern print dialog (Win32 Notepad, Ctrl+P). Mixed languages in the VM: Spanish title suffix, '
                     'labels «Impresora», «Desactivado/Activado», «Imprimir», «Cancelar»; English «Orientation», '
                     '«Print to file», «Portrait». Only Printer, Orientation and Print to file exist with Microsoft Print '
                     'to PDF and this app (no copies/pages/colour/preview).',
           'coordinates': 'x/y relative to the window outer top-left (1 px frame); at = screen pixel',
           'lang': 'es+en (mixed, as shown)'}
    res = screen({th: f'{th}-100-32-print' for th in THEMES}, {th: PRINT_ORG for th in THEMES}, PRINT_REGIONS,
                 PRINT_CONTROLS, PRINT_TEXT, PRINT_FOCUS, window=(852, 734), extra_states=PRINT_REGION_STATES)
    for th, o in res.items():
        p = f'{th}-100-32-print'
        n = shot(p + '-normal')
        # keyboard focus ring around the printer combo in the initial state (2 px outer + 2 px inner gap)
        x, y = rel(PRINT_ORG, (21, 104))
        o['focus_ring'] = {'outer_width': V(2, n.name, (x, y)), 'outer_color': color(n, x, y),
                           'gap_width': V(2, n.name, (x + 2, y + 2)), 'gap_color': color(n, x + 2, y + 2),
                           'note': 'drawn 4 px outside the control border box (ring 2 px + gap 2 px)'}
        # the selected-item pill on the left of the printer combo (accent)
        o['printer_combo_pill'] = element(n, rel(PRINT_ORG, (27, 124)), PRINT_ORG, 6, rad=False)
        # toggle knob, off and on
        o['toggle_knob'] = {}
        for st, nm in (('off', p + '-normal'), ('on', p + '-click-toggle-on')):
            t = shot(nm)
            ky = rel(PRINT_ORG, (0, 301))[1]
            row = t.a[ky, rel(PRINT_ORG, (25, 0))[0]:rel(PRINT_ORG, (65, 0))[0]]
            xs0 = rel(PRINT_ORG, (25, 0))[0]
            fill = t.px(xs0 + 2, ky)
            knob = [i for i in range(len(row)) if np.abs(row[i] - np.array(fill)).max() > 40]
            if knob:
                a, z = knob[0], knob[-1]
                # skip the outer ring pixels (first/last 2 px of the track)
                inner = [i for i in knob if 2 < i < len(row) - 3]
                a, z = inner[0], inner[-1]
                o['toggle_knob'][st] = {'x': V(xs0 + a - PRINT_ORG[0], t.name, (xs0 + a, ky)),
                                        'diameter': V(z - a + 1, t.name, (xs0 + a, ky)),
                                        'color': V(L.hexc(t.px(xs0 + (a + z) // 2, ky)), t.name, (xs0 + (a + z) // 2, ky))}
        o['toggle_knob']['hover'] = V(None, p + '-hover-toggle', (418, 418),
                                      note='the knob grows on hover (about 14 px) but the pointer covers it: not measured')
        o['preview_nav'] = {'note': 'prev/next page arrows are disabled (single page, no preview); hover shows nothing'}
    out.update(res)
    return out


# ----------------------------------------------------------------------------- «Más opciones» (33)
PREFS_ORG = (398, 134)      # Printing Preferences frame (x 398..930, y 134..605)
ADV_ORG = (441, 189)        # Advanced Options frame (x 441..901, y 189..666)
PREFS_REGIONS = {
    'titlebar': ((202, 16), 1), 'body': ((202, 40), 1), 'tab_page': ((102, 316), 1),
    'orientation_combo': ((25, 106), 1), 'preview_frame': ((252, 346), 1),
    'advanced_button': ((427, 411), 1), 'accept_button': ((374, 446), 1), 'cancel_button': ((455, 446), 1),
}
PREFS_STATES = {'accept_button': {'hover': 'hover-aceptar'}, 'advanced_button': {'hover': 'hover-advanced'}}
PREFS_TEXT = {
    'title': ((7, 8, 117, 24), 'Printing Preferences'), 'tab': ((10, 38, 52, 57), 'Layout'),
    'orientation_label': ((20, 72, 90, 89), 'Orientation:'), 'orientation_value': ((47, 96, 92, 113), 'Portrait'),
    'advanced_button': ((430, 405, 500, 424), 'Advanced...'), 'accept_button': ((385, 444, 430, 462), 'Aceptar'),
    'cancel_button': ((463, 444, 513, 462), 'Cancelar'),
}
ADV_REGIONS = {
    'titlebar': ((259, 6), 1), 'body': ((19, 451), 1), 'tree': ((259, 311), 1), 'paper_size_combo': ((259, 87), 1),
    'ok_button': ((271, 451), 1), 'cancel_button': ((365, 451), 1),
}
ADV_TEXT = {
    'title': ((8, 8, 232, 24), 'Microsoft Print To PDF Advanced Options'),
    'tree_root': ((38, 46, 322, 62), 'Microsoft Print To PDF Advanced Document Settings'),
    'tree_group': ((57, 64, 135, 80), 'Paper/Output'), 'paper_size_label': ((76, 82, 137, 98), 'Paper Size:'),
    'paper_size_value': ((145, 84, 180, 100), 'Letter'), 'copy_count_label': ((76, 100, 145, 116), 'Copy Count:'),
    'copy_count_value': ((147, 100, 188, 117), '1 Copy'), 'ok_button': ((297, 446, 321, 463), 'OK'),
    'cancel_button': ((383, 446, 425, 463), 'Cancel'),
}


def print_more():
    out = {'_about': '«Más opciones de configuración» opens the classic Win32 Printing Preferences of Microsoft Print to '
                     'PDF (English, with Spanish «Aceptar»/«Cancelar»), and «Advanced...» the Advanced Options tree '
                     'dialog. Both are always light (not themed) even in dark mode.',
           'coordinates': 'x/y relative to each window outer top-left', 'lang': 'en (+ es buttons)'}
    for th in THEMES:
        p = f'{th}-100-33-print-more'
        if not have(p + '-normal'):
            continue
        n = shot(p + '-normal')
        o = {'preferences': {}, 'advanced': {}}
        pr = o['preferences']
        pr['window'] = box_values(n, (PREFS_ORG[0], PREFS_ORG[1], 931, 606), PREFS_ORG, PREFS_ORG)
        pr['window']['frame'] = color(n, PREFS_ORG[0], 400)
        for name, (seed, tol) in PREFS_REGIONS.items():
            st = {k: f'{p}-{v}' for k, v in PREFS_STATES.get(name, {}).items()}
            pr[name] = element(n, rel(PREFS_ORG, seed), PREFS_ORG, tol, states=st)
        pr['text'] = {k: text(n, relbox(PREFS_ORG, b), t, PREFS_ORG) for k, (b, t) in PREFS_TEXT.items()}
        a = shot(p + '-advanced')
        ad = o['advanced']
        ad['window'] = box_values(a, (ADV_ORG[0], ADV_ORG[1], 902, 667), ADV_ORG, ADV_ORG)
        ad['window']['frame'] = color(a, ADV_ORG[0], 400)
        ad['parent_title_inactive'] = text(a, relbox(PREFS_ORG, PREFS_TEXT['title'][0]), 'Printing Preferences',
                                           PREFS_ORG)
        for name, (seed, tol) in ADV_REGIONS.items():
            ad[name] = element(a, rel(ADV_ORG, seed), ADV_ORG, tol)
        ad['text'] = {k: text(a, relbox(ADV_ORG, b), t, ADV_ORG) for k, (b, t) in ADV_TEXT.items()}
        out[th] = o
    return out


# ----------------------------------------------------------------------------- Snipping Tool (34)
SCREEN = (0, 0)
SNIP_BUTTONS = {   # hover suffix -> (key, tooltip text as read, tooltip reliable)
    'foto': ('snapshot_segment', 'Snip', True),
    'video': ('video_segment', 'Snip', False),
    'modo': ('mode_button', 'Snipping area', True),
    'anotar': ('quick_markup_button', 'Quick markup (Ctrl + E)', True),
    'lapiz': ('color_picker_button', 'Color picker', True),
    'texto': ('text_extractor_button', 'Text extractor ( \u229e + Shift + T)', True),
    'cerrar': ('close_button', 'Close (Esc)', True),
}


def dim_fit(th):
    """Overlay = undimmed * k + c over the Notepad window area (same pixels with and without the overlay:
    -overlay vs -after-capture). k = 1 - alpha of a black scrim."""
    o, a = shot(f'{th}-100-34-snip-overlay'), shot(f'{th}-100-34-snip-after-capture')
    x0, y0, x1, y1 = 300, 250, 1290, 750
    O = o.a[y0:y1, x0:x1].reshape(-1, 3).astype(float)
    A = a.a[y0:y1, x0:x1].reshape(-1, 3).astype(float)
    res = {}
    k, c = np.polyfit(A.ravel(), O.ravel(), 1)
    resid = float(np.abs(O.ravel() - (k * A.ravel() + c)).mean())
    alpha = 1 - k
    res['scrim_color'] = V('#000000', o.name, (x0, y0), method='linear fit overlay = k * undimmed + c over x 300..1290, y 250..750 '
                           'against ' + a.file + f' (k = {k:.4f}, c = {c:.2f}, mean residual {resid:.2f})')
    res['scrim_opacity'] = V(round(alpha, 3), o.name, (x0, y0))
    res['scrim_rgba'] = V('#000000%02x' % round(alpha * 255), o.name, (x0, y0))
    for px in ((800, 500), (40, 300)):
        res.setdefault('samples', []).append({'undimmed': color(a, *px), 'dimmed': color(o, *px)})
    return res


def snip():
    L.POINTER_BOX = L.CROSS
    try:
        return _snip()
    finally:
        L.POINTER_BOX = L.ARROW


def _snip():
    ov, tb, ac = {}, {}, {}
    for th in THEMES:
        p = f'{th}-100-34-snip'
        n = shot(p + '-overlay')
        # ---- overlay
        o = {'dim': dim_fit(th)}
        o['printscreen_same_as_win_shift_s'] = V(
            bool(np.abs(shot(p + '-printscreen').a[100:1000, 0:780] - n.a[100:1000, 0:780]).max() <= 2),
            p + '-printscreen', (400, 500), note='Impr Pant opens the same overlay (only the teaching tip differs)')
        # rectangle being dragged from (500,300) to (1000,600): undimmed inside, 1 px outline
        r = shot(p + '-rect-dragging')
        rect = {'from': V([500, 300], r.name, (500, 300)), 'to': V([1000, 600], r.name, (1000, 600))}
        inside = r.px(750, 450)
        rect['inside'] = V(L.hexc(inside), r.name, (750, 450), note='same as the undimmed screen: no tint inside')
        # dashed 1 px outline just outside the selection: read the on/off run lengths along the left edge
        col = (r.a[300:600, 499].min(axis=1) > 230).astype(int).tolist()
        runs, cur, k = [], col[0], 0
        for v in col:
            if v == cur:
                k += 1
            else:
                runs.append((cur, k))
                cur, k = v, 1
        on = [k for v, k in runs[1:-1] if v]
        off = [k for v, k in runs[1:-1] if not v]
        rect['outline'] = {'style': V('dashed', r.name, (499, 301)), 'width': V(1, r.name, (499, 301)),
                           'color': color(r, 499, 301),
                           'dash': V(max(set(on), key=on.count) if on else None, r.name, (499, 301)),
                           'gap': V(max(set(off), key=off.count) if off else None, r.name, (499, 305)),
                           'position': V('outside the selection: x-1 / y-1 on the left/top, x2 / y2 on the right/bottom',
                                         r.name, (499, 299))}
        o['rectangle_in_progress'] = rect
        w = shot(p + '-window-mode')
        o['window_mode'] = {'pointer': V(w.pointer, w.name, w.pointer),
                            'highlight_outline': color(w, 304, 400), 'outline_width': V(1, w.name, (304, 400)),
                            'window_inside': color(w, 700, 450),
                            'note': 'the window under the pointer is shown undimmed with a 1 px outline just outside '
                                    'its frame; the rest stays dimmed'}
        # teaching tip shown the first time (Annotate live): only in the first (dark) pass
        if np.abs(n.a[138, 830] - shot(p + '-printscreen').a[138, 830]).max() <= 2:
            ov[th] = o
            o['teaching_tip'] = V(None, n.name, (830, 138), note='not shown in this pass (already dismissed)')
            tip = None
        else:
            tip = element(n, (830, 138), SCREEN, 1, rad=True)
            tip['radius']['reliable'] = False
            tip['radius']['note'] = 'box includes the beak pointing at «Quick markup»; corner estimate is rough'
            tip['text'] = {
                'title': text(n, (820, 75, 1010, 93), 'Annotate live on your screen', SCREEN),
                'body_line1': text(n, (820, 95, 1110, 113), 'Quick markup lets you draw on your screen in', SCREEN),
                'body_line2': text(n, (820, 114, 885, 131), 'real time.', SCREEN),
                'button': text(n, (930, 150, 1000, 168), 'Got it', SCREEN)}
            tip['button'] = element(n, (830, 150), SCREEN, 1)
            o['teaching_tip'] = tip
        ov[th] = o
        # ---- toolbar
        t = {}
        bar = element(n, (800, 40), SCREEN, 1)
        fb = L.flood_box(n, (800, 40), 1)
        bar['fill_box'] = box_values(n, fb, SCREEN, (800, 40))
        bar['fill_box']['note'] = 'fill without the 1 px outline (the outline is only visible on the dark pass)'
        for side, (x, y) in {'top': (960, fb[1] - 1), 'bottom': (960, fb[3]), 'left': (fb[0] - 1, 36),
                             'right': (fb[2], 36)}.items():
            bar.setdefault('outline', {})[side] = color(n, x, y)
        bar['background']['normal']['reliable'] = False
        bar['background']['normal']['note'] = 'acrylic in Windows; flat in the VM'
        bx = (fb[0] + fb[2]) / 2
        bar['center_x'] = V(bx, n.name, (bar['x']['value'], 36), note='screen is 1920 wide: centred = 960')
        bar['top'] = V(bar['y']['value'], n.name, (960, bar['y']['value']))
        bar['shadow'] = V('not visible on the dimmed screen in the VM', n.name, (960, 62), reliable=False)
        t['bar'] = bar
        t['selector_selected_segment'] = element(n, (808, 26), SCREEN, 1, states={'video_mode': p + '-video-mode'})
        t['selector_unselected_segment'] = element(n, (870, 26), SCREEN, 1, states={'video_mode': p + '-video-mode'})
        a1, a2 = t['selector_selected_segment'], t['selector_unselected_segment']
        sx0, sy0 = a1['x']['value'], a1['y']['value']
        sx1 = a2['x']['value'] + a2['width']['value']
        sy1 = max(a1['y']['value'] + a1['height']['value'], a2['y']['value'] + a2['height']['value'])
        t['selector'] = box_values(n, (sx0, sy0, sx1, sy1), SCREEN, (806, 23))
        t['selector']['note'] = 'Snapshot / Video segmented control = union of both segments'
        # accent underline of the selected segment
        acc = None
        for y in range(40, 52):
            for x in range(806, 840):
                c = n.px(x, y)
                if c[2] > 150 and c[2] - c[0] > 60:
                    acc = (x, y)
                    break
            if acc:
                break
        if acc:
            t['selected_indicator'] = element(n, (acc[0] + 3, acc[1] + 1), SCREEN, 30, rad=False)
        # separators: 1 px columns between the groups
        seps = []
        y = 36
        for x in range(bar['x']['value'] + 60, bar['x']['value'] + bar['width']['value'] - 40):
            c, l_, r_ = n.px(x, y), n.px(x - 1, y), n.px(x + 1, y)
            if l_ == r_ and max(abs(c[i] - l_[i]) for i in range(3)) > 10 and all(n.px(x, yy) == c for yy in range(30, 44)):
                top = y
                while n.px(x, top - 1) == c:
                    top -= 1
                bot = y
                while n.px(x, bot + 1) == c:
                    bot += 1
                seps.append({'x': V(x, n.name, (x, y)), 'y': V(top, n.name, (x, top)),
                             'height': V(bot - top + 1, n.name, (x, top)), 'width': V(1, n.name, (x, y)),
                             'color': color(n, x, y)})
        t['separators'] = seps
        btn = {}
        for suf, (key, tip_text, tip_ok) in SNIP_BUTTONS.items():
            h = f'{p}-hover-{suf}'
            if not have(h):
                continue
            d = state_box(h, p + '-overlay', SCREEN)
            e = {'hover': d} if d else {'hover': V(None, h, shot(h).pointer, note='no change')}
            tt = tooltip(h, p + '-overlay', SCREEN, tip_text)
            if isinstance(tt, dict) and not tip_ok:
                tt['reliable'] = False
                tt['note'] = 'captured before the tooltip text updated (shows the previous control\'s «Snip»)'
            e['tooltip'] = tt
            btn[key] = e
        t['buttons'] = btn
        t['quick_markup_disabled_in_video'] = color(shot(p + '-video-mode'), 963, 40)
        # mode menu
        m = menu(p + '-menu-modo', p + '-overlay', SCREEN, (1003, 140), ['Rectangle', 'Window', 'Full screen', 'Freeform'],
                 tol=1, lang='en', text_x=40, limit_diff=True)
        m['selected_entry'] = 'Rectangle (accent pill on the left)'
        m['background']['reliable'] = False
        t['mode_menu'] = m
        tb[th] = t
        # ---- after capture
        a = shot(p + '-after-capture')
        toast = element(a, (1700, 955), SCREEN, 1)
        toast['text'] = {
            'app': text(a, (1575, 875, 1660, 893), 'Snipping Tool', SCREEN),
            'title': text(a, (1552, 912, 1760, 931), 'Screenshot copied to clipboard', SCREEN),
            'body': text(a, (1552, 932, 1830, 950), 'Automatically saved to screenshots folder.', SCREEN),
            'button': text(a, (1660, 978, 1785, 996), 'Markup and share', SCREEN)}
        toast['button'] = element(a, (1565, 980), SCREEN, 1)
        if th == 'light':
            toast['reliable'] = False
            toast['note'] = 'light capture caught the toast while sliding in (top cut by a white block): use dark geometry'
        ac[th] = {'toast': toast,
                  'overlay_closed': V(True, a.name, (800, 500), note='the screen is undimmed right after the snip'),
                  'after_2s': V(have(p + '-after-capture-2s') and bool(np.abs(
                      shot(p + '-after-capture-2s').a[850:1025, 1530:1915] - a.a[850:1025, 1530:1915]).max() <= 2),
                      p + '-after-capture-2s', (1700, 955), note='true = the toast is unchanged 2 s later') if have(
                      p + '-after-capture-2s') else V(None, a.name, (1700, 955), note='no 2 s capture in this theme')}
    about = 'Snipping Tool (Win+Mayús+S or Impr Pant), English UI; x/y are screen pixels (1920x1080, 100 %).'
    return ({'_about': about, **ov}, {'_about': about, **tb}, {'_about': about, **ac})


def print_menus():
    out = {'_about': 'Pop-ups of the modern print dialog: they open over the combo, the selected entry aligned with it, '
                     'with a 3 px accent pill. Acrylic is not rendered in the VM (the pop-up shows a flat colour).',
           'coordinates': 'relative to the print dialog window'}
    for th in THEMES:
        p = f'{th}-100-32-print'
        o = {}
        for key, suf, seed, entries, tx in (('printer', 'menu-printer', (288, 123), ['Microsoft Print to PDF'], None),
                                            ('orientation', 'menu-orientation', (288, 183), ['Landscape', 'Portrait'], 35)):
            m = menu(f'{p}-{suf}', p + '-normal', PRINT_ORG, seed, entries, tol=0, lang='en', limit_diff=True,
                     text_x=tx)
            m['selected_entry'] = entries[-1]
            m['acrylic'] = V('not rendered', f'{p}-{suf}', rel(PRINT_ORG, seed), reliable=False)
            o[key] = m
        q = f'{th}-100-33-print-more'
        if have(q + '-menu-orientation'):
            m = menu(q + '-menu-orientation', q + '-normal', PREFS_ORG, (212, 124), ['Landscape', 'Portrait'],
                     tol=1, lang='en', frame='#0078d7', text_x=22)
            m['selected_entry'] = 'Portrait'
            m['coordinates'] = 'relative to the Printing Preferences window'
            o['preferences_orientation'] = m
        out[th] = o
    return out


# ----------------------------------------------------------------------------- menus
def menu(state, base, org, seed, entries, tol=2, text_x=None, lang=None, frame=None, limit_diff=False):
    """A popup menu or drop-down list: body = flood of its background from seed (relative to org);
    shadow = pixels beyond the border that differ from the base shot; lines of ink -> entries in order.
    entries: list of strings, '-' for a separator (only used to pair strings with ink lines)."""
    s, b = shot(state), shot(base)
    sd = rel(org, seed)
    fill = s.px(*sd)
    if frame:
        inner = frame_scan(s, sd, frame)
    elif limit_diff:
        # the pop-up has the window's own colour: flood only inside the region that changed (minus its
        # 1 px AA/shadow edge), so the fill does not leak into the dialog
        m = L.diff_mask(s, b, thr=2)
        comp = [c for c in L.components(m, min_px=50, merge=2) if c[0] <= sd[0] < c[2] and c[1] <= sd[1] < c[3]]
        lim = comp[0][:4] if comp else None
        inner = L.flood_box(s, sd, tol, limit=lim)
        diffmask = m
    else:
        inner = L.flood_box(s, sd, tol)
    box, sides = border_box(s, inner, fill)
    d = box_values(s, box, org, sd)
    d['background'] = V(L.hexc(fill), s.name, sd)
    if sides:
        d['border_width'] = V(1, s.name, sides[next(iter(sides))][1])
        d['border'] = {k: V(c, s.name, at) for k, (c, at) in sides.items()}
    outside = s.px(box[0] - 1, box[1] - 1)
    r, rat = radius(s, box, outside)
    if limit_diff:
        # same colour inside and outside: count unchanged pixels along the corner diagonal instead
        i = 0
        while i < 12 and not diffmask[box[1] + i, box[0] + i]:
            i += 1
        r, rat = (round(i / 0.2929) if i else 0), (box[0] + i, box[1] + i)
    d['radius'] = V(r, s.name, rat)
    # shadow: how far right of / below the border the screenshot still differs from the base
    my, mx = (box[1] + box[3]) // 2, (box[0] + box[2]) // 2
    sr = 0
    while box[2] + sr < s.W and np.abs(s.a[my, box[2] + sr] - b.a[my, box[2] + sr]).max() > 2 and sr < 40:
        sr += 1
    sb = 0
    while box[3] + sb < s.H and np.abs(s.a[box[3] + sb, mx] - b.a[box[3] + sb, mx]).max() > 2 and sb < 40:
        sb += 1
    d['shadow'] = {'right_px': V(sr, s.name, (box[2], my), reliable=False),
                   'bottom_px': V(sb, s.name, (mx, box[3]), reliable=False),
                   'darkest': V(L.hexc(s.px(box[2], my)), s.name, (box[2], my), reliable=False)}
    # ink lines
    x0, y0, x1, y1 = inner
    tx0 = x0 + (text_x if text_x is not None else 0)
    sub = s.a[y0:y1, tx0:x1]
    rowbg = np.array([L.mode_color(sub[i:i + 1]) for i in range(sub.shape[0])])
    ink = np.abs(sub - rowbg[:, None, :]).max(axis=2) > 60
    rows = ink.sum(axis=1)
    # highlighted rows (hover / selection): row background differs from the menu fill
    hl = [i for i in range(len(rowbg)) if np.abs(rowbg[i] - np.array(fill)).max() > 3
          and np.abs(s.a[y0 + i, x0 + 2] - np.array(fill)).max() <= 6 or (np.abs(rowbg[i] - np.array(fill)).max() > 40)]
    hlrows = set()
    if hl:
        g = [hl[0]]
        for i in hl[1:]:
            if i == g[-1] + 1:
                g.append(i)
            elif len(g) < 8:
                g = [i]
        if len(g) >= 8:
            hlrows = set(g)
            yy = y0 + g[len(g) // 2]
            hc = tuple(int(v) for v in rowbg[g[len(g) // 2]])
            run = np.nonzero(np.abs(s.a[yy, x0:x1] - np.array(hc)).max(axis=1) <= 3)[0]
            d['highlight'] = {'y': V(y0 + g[0] - org[1], s.name, (x0 + int(run[0]), y0 + g[0])),
                              'height': V(len(g), s.name, (x0 + int(run[0]), y0 + g[0])),
                              'x': V(x0 + int(run[0]) - org[0], s.name, (x0 + int(run[0]), yy)),
                              'width': V(int(run[-1] - run[0] + 1), s.name, (x0 + int(run[0]), yy)),
                              'color': V(L.hexc(hc), s.name, (x0 + int(run[0]) + 1, yy))}
    lines, start = [], None
    for i, v in enumerate(list(rows) + [0]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            lines.append((start, i))
            start = None
    # separators: rows whose non-fill run covers most of the width but carry no text
    seps = []
    for i in range(y1 - y0):
        row = s.a[y0 + i, x0:x1]
        diff = np.abs(row - np.array(fill)).max(axis=1) > 6
        if diff.mean() > 0.6 and np.ptp(row[diff], axis=0).max() <= 8 and not ink[i].any() \
                and int(np.ptp(row[diff][0])) <= 10 and i not in hlrows:
            seps.append(y0 + i)
    texts = [e for e in entries if e != '-']
    tl = [ln for ln in lines if ln[1] - ln[0] >= 5]
    items = []
    for k, (a, z) in enumerate(tl[:len(texts)]):
        ya, yz = y0 + a, y0 + z
        area = (tx0, ya - 1, x1, yz + 1)
        t = text(s, area, texts[k], org, bg=tuple(int(v) for v in rowbg[(a + z) // 2]))
        items.append({'text': t['text'], 'y': V(ya - org[1], s.name, (tx0, ya)),
                      'ink_height': V(z - a, s.name, (tx0, ya)), 'color': t.get('color'),
                      'font_size': t.get('font_size')})
    d['entries'] = items
    if len(tl) != len(texts):
        d['entries_note'] = f'{len(tl)} ink lines for {len(texts)} strings: pairing by order may be off'
    cs = [y0 + (a + z) / 2 for a, z in tl]
    if len(cs) > 1:
        gaps = [round(g) for g in np.diff(cs).tolist()]
        pitch = max(set(gaps), key=gaps.count)
        d['row_pitch'] = V(pitch, s.name, (tx0, int(cs[0])),
                           note='most frequent centre-to-centre distance of consecutive entries')
        d['padding_top'] = V(tl[0][0] - 0, s.name, (tx0, y0), note='body top to first ink line')
    if seps:
        groups = []
        for y in seps:
            if groups and y - groups[-1][-1] <= 1:
                groups[-1].append(y)
            else:
                groups.append([y])
        d['separators'] = [{'y': V(g[0] - org[1], s.name, (mx, g[0])), 'height': V(len(g), s.name, (mx, g[0])),
                            'color': V(L.hexc(s.px(mx, g[0])), s.name, (mx, g[0]))} for g in groups]
    if lang:
        d['lang'] = lang
    return d


# key -> (save suffix, open suffix, seed rel, save entries, open entries)
FILE_MENUS = {
    'organize': ('menu-organizar', 'menu-organize', (183, 266),
                 ['Cortar', 'Copiar', 'Pegar', 'Deshacer', 'Rehacer', '-', 'Seleccionar todo', '-', 'Diseño', 'Opciones',
                  '-', 'Eliminar', 'Cambiar nombre', 'Quitar propiedades', 'Propiedades', '-', 'Cerrar'],
                 ['Cut', 'Copy', 'Paste', 'Undo', 'Redo', '-', 'Select all', '-', 'Layout', 'Options', '-', 'Delete',
                  'Rename', 'Remove properties', 'Properties', '-', 'Close']),
    'view': ('menu-view', 'menu-view', None,
             ['Iconos muy grandes', 'Iconos grandes', 'Iconos medianos', 'Iconos pequeños', 'Lista', 'Detalles',
              'Mosaicos', 'Contenido'],
             ['Extra large icons', 'Large icons', 'Medium icons', 'Small icons', 'List', 'Details', 'Tiles', 'Content']),
    'encoding': ('menu-encoding', 'menu-encoding', None,
                 ['ANSI', 'UTF-16 LE', 'UTF-16 BE', 'UTF-8', 'UTF-8 with BOM'],
                 ['Auto-Detect', 'ANSI', 'UTF-16 LE', 'UTF-16 BE', 'UTF-8', 'UTF-8 with BOM']),
    'type': ('menu-tipo', 'menu-filter', None,
             ['Text documents (*.txt)', 'All files'],
             ['Text documents (*.txt)', 'Markdown file (*.md)', 'All files']),
    'filename_history': ('menu-nombre-dropdown', 'menu-filename-dropdown', None, [], []),
    'address_history': ('menu-address-dropdown', 'menu-address-dropdown', (353, 216), [], []),
}
# seeds that differ between Save and Open (relative to the window)
FILE_MENU_SEEDS = {
    ('save', 'view'): (865, -74), ('open', 'view'): (837, -74),
    ('save', 'encoding'): (713, 526), ('open', 'encoding'): (718, 546),
    ('save', 'type'): (853, 464), ('open', 'type'): (923, 516),
    ('save', 'filename_history'): (553, 466), ('open', 'filename_history'): (453, 536),
}
# key -> (x offset of the text column inside the menu body, colour of a list frame to scan to)
MENU_OPTS = {'organize': (40, None), 'view': (65, None), 'encoding': (None, '#0078d7'), 'type': (None, '#0078d7'),
             'filename_history': (None, '#0078d7'), 'address_history': (None, '#0078d7')}
MENU_SELECTED = {'view': 'Detalles / Details (slider thumb)', 'encoding': 'UTF-8 (Guardar como) / Auto-Detect (Abrir)',
                 'type': 'Text documents (*.txt)'}


def frame_scan(s, seed, frame):
    """Inner box of a list whose 1 px frame has colour `frame` (hex): walk left, right and down from seed
    until that colour, up until it or the combo above (a row that is not the list fill)."""
    fc = np.array([int(frame[i:i + 2], 16) for i in (1, 3, 5)])
    x, y = seed

    def hit(xx, yy):
        return np.abs(s.a[yy, xx] - fc).max() <= 12
    l = x
    while l > 0 and not hit(l - 1, y):
        l -= 1
    r = x
    while r < s.W - 1 and not hit(r + 1, y):
        r += 1
    # top and bottom: follow the left frame column while it keeps the frame colour (the selected row's
    # highlight is nearly the same blue, so the inside cannot be used)
    bt = y
    while bt < s.H - 1 and hit(l - 1, bt + 1):
        bt += 1
    tp = y
    while tp > 0 and hit(l - 1, tp - 1):
        tp -= 1
    bt -= 1   # the bottom frame row itself
    return (l, tp, r + 1, bt + 1)


def file_menus():
    out = {'_about': 'Menus and drop-down lists of «Guardar como» (es labels, Win32 classic menus) and «Abrir» (en). '
                     'Disabled entries are the ones whose text colour is the light grey one. The «Ubicaciones recientes» '
                     'chevron only focused the address bar (no menu).',
           'coordinates': 'x/y relative to the dialog window outer top-left'}
    for th in THEMES:
        o = {}
        for kind, pre in (('save', '30-save'), ('open', '31-open')):
            p = f'{th}-100-{pre}'
            org = FILE_ORG[th]
            for key, (ss, os_, seed, es, en) in FILE_MENUS.items():
                suf = ss if kind == 'save' else os_
                name = f'{p}-{suf}'
                if not have(name):
                    continue
                sd = FILE_MENU_SEEDS.get((kind, key), seed)
                tx, fr = MENU_OPTS.get(key, (None, None))
                m = menu(name, p + '-normal', org, sd, es if kind == 'save' else en,
                         lang='es' if kind == 'save' else 'en', text_x=tx, frame=fr)
                if key in MENU_SELECTED:
                    m['selected_entry'] = MENU_SELECTED[key]
                o[f'{kind}_{key}'] = m
        out[th] = o
    return out


def frame_bottom(s, x, y):
    """Follow the 1 px left frame line down from y until its colour jumps: exclusive bottom."""
    prev = s.px(x, y)
    while y + 1 < s.H:
        c = s.px(x, y + 1)
        if max(abs(c[i] - prev[i]) for i in range(3)) > 12:
            return y + 1
        prev, y = c, y + 1
    return y


def _is_frame(s, x, y):
    """Bottom frame line of the dialog: a pixel darker than both neighbours below/above (shadow below)."""
    a, b = s.px(x, y), s.px(x, y + 1)
    return abs(L.lum(a) - L.lum(b)) > 8 and y > 400 and L.lum(s.px(x, y - 1)) - L.lum(a) > 25


def main():
    global ROOT
    ap = argparse.ArgumentParser()
    repo = os.path.abspath(os.path.join(HERE, '..', '..'))
    ap.add_argument('shots', nargs='?', default=os.path.join(repo, '..', 'shots', 'reference-shots', 'dialogs'))
    ap.add_argument('-o', '--out', default=os.path.join(repo, 'design/reference/measurements.json'))
    ap.add_argument('--print', action='store_true', help='print the sections instead of writing')
    ap.add_argument('--only', default='')
    a = ap.parse_args()
    ROOT = os.path.abspath(a.shots)
    doc = {}
    makers = {'file_dialog_save': lambda: file_dialog('save'), 'file_dialog_open': lambda: file_dialog('open'),
              'file_dialog_menus': file_menus, 'print_dialog': print_dialog, 'print_dialog_menus': print_menus,
              'print_dialog_more': print_more}
    snip_cache = {}

    def snip_part(i):
        if 'v' not in snip_cache:
            snip_cache['v'] = snip()
        return snip_cache['v'][i]
    makers.update({'snip_overlay': lambda: snip_part(0), 'snip_toolbar': lambda: snip_part(1),
                   'snip_after_capture': lambda: snip_part(2)})
    only = [k for k in a.only.split(',') if k]
    for k, f in makers.items():
        if not only or k in only:
            doc[k] = f()
    if a.print:
        json.dump(doc, sys.stdout, indent=1, ensure_ascii=False)
        return
    write_merged(a.out, doc)
    print('wrote', ', '.join(doc), 'into', a.out)


def write_merged(path, doc):
    """Read-modify-write: re-read the file right before writing and replace only this script's keys
    (tests/visual/measure.py owns the others). Temporary file + rename so readers never see half a file."""
    try:
        with open(path) as fh:
            old = json.load(fh)
        if not isinstance(old, dict):
            old = {}
    except (OSError, ValueError):
        old = {}
    merged = dict(old)
    for k in OWN_KEYS:
        if k in doc:
            merged[k] = doc[k]
    tmp = f'{path}.tmp{os.getpid()}'
    with open(tmp, 'w') as fh:
        json.dump(merged, fh, indent=1, ensure_ascii=False)
        fh.write('\n')
    os.replace(tmp, path)


if __name__ == '__main__':
    main()
