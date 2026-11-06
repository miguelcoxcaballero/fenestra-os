"""Pixel helpers for tests/visual/measure_dialogs.py (no scipy: plain numpy + BFS).

Every helper returns plain numbers; the caller wraps them with the screenshot name and the
pixel they were read at (see measure_dialogs.V)."""
import json
import os
from collections import Counter, deque

import numpy as np
from PIL import Image

_cache = {}


class Shot:
    """One reference screenshot (RGB numpy array) plus its .json sidecar."""

    def __init__(self, root, name):
        self.name = name
        self.file = name + '.png'
        path = os.path.join(root, self.file)
        self.a = np.asarray(Image.open(path).convert('RGB')).astype(np.int16)
        side = os.path.join(root, name + '.json')
        try:
            self.meta = json.load(open(side)) if os.path.exists(side) else {}
        except ValueError:
            self.meta = {}
        self.H, self.W = self.a.shape[:2]

    @property
    def pointer(self):
        return self.meta.get('pointer')

    def px(self, x, y):
        return tuple(int(v) for v in self.a[y, x])


def load(root, name):
    k = (root, name)
    if k not in _cache:
        if len(_cache) > 24:          # keep memory small: ~6 MB per shot
            _cache.pop(next(iter(_cache)))
        _cache[k] = Shot(root, name)
    return _cache[k]


def exists(root, name):
    return os.path.exists(os.path.join(root, name + '.png'))


def hexc(c):
    return '#%02x%02x%02x' % tuple(int(v) for v in c[:3])


def lum(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def mode_color(a, mask=None):
    """Most frequent colour of an (h, w, 3) block (optionally only where mask)."""
    px = a.reshape(-1, 3) if mask is None else a[mask]
    if len(px) == 0:
        return None
    c = Counter(map(tuple, px.tolist())).most_common(1)[0][0]
    return tuple(int(v) for v in c)


def components(mask, min_px=1, merge=0):
    """Connected components (8-connected) of a boolean mask -> list of (x0, y0, x1, y1, n), x1/y1
    exclusive, biggest first. merge > 0 dilates by that many pixels before labelling (so text
    glyphs and a control's fill join), but n counts only original pixels."""
    m = mask.copy()
    if merge:
        for _ in range(merge):
            d = m.copy()
            d[1:, :] |= m[:-1, :]
            d[:-1, :] |= m[1:, :]
            d[:, 1:] |= m[:, :-1]
            d[:, :-1] |= m[:, 1:]
            m = d
    H, W = m.shape
    seen = np.zeros_like(m)
    out = []
    ys, xs = np.nonzero(m)
    for y0, x0 in zip(ys.tolist(), xs.tolist()):
        if seen[y0, x0]:
            continue
        q = deque([(y0, x0)])
        seen[y0, x0] = True
        bx0 = bx1 = x0
        by0 = by1 = y0
        while q:
            y, x = q.popleft()
            bx0, bx1, by0, by1 = min(bx0, x), max(bx1, x), min(by0, y), max(by1, y)
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < H and 0 <= xx < W and m[yy, xx] and not seen[yy, xx]:
                        seen[yy, xx] = True
                        q.append((yy, xx))
        n = int(mask[by0:by1 + 1, bx0:bx1 + 1].sum())
        if n >= min_px:
            out.append((bx0, by0, bx1 + 1, by1 + 1, n))
    out.sort(key=lambda b: -(b[2] - b[0]) * (b[3] - b[1]))
    return out


def diff_mask(s1, s2, thr=6, roi=None, ignore_pointer=True):
    """Pixels that differ by more than thr (max channel) between two shots of the same size."""
    d = np.abs(s1.a - s2.a).max(axis=2) > thr
    for s in (s1, s2):
        p = s.pointer
        if ignore_pointer and p:
            x, y = p
            d[max(0, y - 2):y + 34, max(0, x - 2):x + 24] = False
    # the normal shots were taken with the pointer parked at (1900, 20)
    d[0:60, 1880:1920] = False
    # taskbar clock / weather change between shots
    d[1032:, :] = False
    if roi:
        x0, y0, x1, y1 = roi
        m = np.zeros_like(d)
        m[y0:y1, x0:x1] = d[y0:y1, x0:x1]
        d = m
    return d


def flood_box(s, seed, tol=3, limit=None):
    """Bounding box (x0, y0, x1, y1 exclusive) of the 4-connected region around seed whose colour
    is within tol (max channel) of the seed colour. limit = (x0, y0, x1, y1) search window."""
    x, y = seed
    c = s.a[y, x]
    if limit is None:
        limit = (max(0, x - 1200), max(0, y - 900), min(s.W, x + 1200), min(s.H, y + 900))
    lx0, ly0, lx1, ly1 = limit
    sub = s.a[ly0:ly1, lx0:lx1]
    ok = np.abs(sub - c).max(axis=2) <= tol
    seen = np.zeros_like(ok)
    q = deque([(y - ly0, x - lx0)])
    seen[y - ly0, x - lx0] = True
    H, W = ok.shape
    bx0 = bx1 = x - lx0
    by0 = by1 = y - ly0
    while q:
        yy, xx = q.popleft()
        if xx < bx0: bx0 = xx
        if xx > bx1: bx1 = xx
        if yy < by0: by0 = yy
        if yy > by1: by1 = yy
        for ny, nx in ((yy - 1, xx), (yy + 1, xx), (yy, xx - 1), (yy, xx + 1)):
            if 0 <= ny < H and 0 <= nx < W and ok[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                q.append((ny, nx))
    return (bx0 + lx0, by0 + ly0, bx1 + lx0 + 1, by1 + ly0 + 1)


def run_edges(s, y, x0, x1):
    """[(x, '#rrggbb')] where the colour changes along row y."""
    out, prev = [], None
    for x in range(x0, x1):
        p = s.px(x, y)
        if p != prev:
            out.append((x, hexc(p)))
            prev = p
    return out


def corner_radius(s, box, fill, tol=6):
    """Radius of the top-left corner of a filled box: how far along the diagonal the pixels are not
    the fill colour (a square corner gives 0). Returns (radius, at)."""
    x0, y0 = box[0], box[1]
    for i in range(0, 16):
        p = s.a[y0 + i, x0 + i]
        if np.abs(p - np.array(fill)).max() <= tol:
            # diagonal inset i of a circle of radius r: i = r(1 - 1/sqrt2) -> r = i / 0.2929
            return (round(i / 0.2929) if i else 0), [x0 + i, y0 + i]
    return None, [x0, y0]


def ink_box(s, box, bg, thr=40):
    """Bounding box of 'ink' (pixels differing from bg by more than thr) inside box."""
    x0, y0, x1, y1 = box
    sub = s.a[y0:y1, x0:x1]
    m = np.abs(sub - np.array(bg)).max(axis=2) > thr
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return None
    return (x0 + int(xs.min()), y0 + int(ys.min()), x0 + int(xs.max()) + 1, y0 + int(ys.max()) + 1)


def text_color(s, box, bg):
    """The ink colour farthest from bg inside box (antialiased text: the darkest/lightest pixel
    that occurs at least 3 times)."""
    x0, y0, x1, y1 = box
    sub = s.a[y0:y1, x0:x1].reshape(-1, 3)
    d = np.abs(sub - np.array(bg)).max(axis=1)
    cnt = Counter(map(tuple, sub[d > 40].tolist()))
    best = None
    for c, n in cnt.items():
        if n >= 3:
            dist = max(abs(c[i] - bg[i]) for i in range(3))
            if best is None or dist > best[0]:
                best = (dist, c)
    return tuple(best[1]) if best else None
