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
            mask[max(0, p[1] - 2 - y0):max(0, p[1] + 34 - y0), max(0, p[0] - 2 - x0):max(0, p[0] + 24 - x0)] = False
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
    m = L.diff_mask(s, b, roi=roi)
    comps = [c for c in L.components(m, min_px=min_px, merge=merge)
             if c[0] - 3 <= p[0] < c[2] + 3 and c[1] - 3 <= p[1] < c[3] + 3]
    if not comps:
        return None
    x0, y0 = max(0, p[0] - 24), max(0, p[1] - 14)
    x1, y1 = min(s.W, p[0] + 34), min(s.H, p[1] + 14)
    sub = s.a[y0:y1, x0:x1]
    mask = m[y0:y1, x0:x1].copy()
    c = L.mode_color(sub, mask)
    if c is None:
        return None
    ys, xs = np.nonzero(np.all(sub == np.array(c), axis=2) & mask)
    k = int(np.argmin((xs + x0 - p[0]) ** 2 + (ys + y0 - p[1]) ** 2))
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


# ----------------------------------------------------------------------------- menus
def menu(state, base, org, seed, entries, tol=2, text_x=None, lang=None, frame=None):
    """A popup menu or drop-down list: body = flood of its background from seed (relative to org);
    shadow = pixels beyond the border that differ from the base shot; lines of ink -> entries in order.
    entries: list of strings, '-' for a separator (only used to pair strings with ink lines)."""
    s, b = shot(state), shot(base)
    sd = rel(org, seed)
    fill = s.px(*sd)
    if frame:
        inner = frame_scan(s, sd, frame)
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
    hl = [i for i in range(len(rowbg)) if np.abs(rowbg[i] - np.array(fill)).max() > 6
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
    doc['file_dialog_save'] = file_dialog('save')
    doc['file_dialog_open'] = file_dialog('open')
    doc['file_dialog_menus'] = file_menus()
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
