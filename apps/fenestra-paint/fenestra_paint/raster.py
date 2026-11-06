"""Pixel-level helpers on cairo ARGB32 surfaces (premultiplied, native-endian BGRA).

No numpy: everything heavy is done with C-speed bytes operations (slicing with a step,
bytes.translate, big-int AND, bytes.find) so a full-HD flood fill takes milliseconds."""
from __future__ import annotations

import math
import zlib

import cairo
import gi

gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib  # noqa: E402

FMT = cairo.FORMAT_ARGB32
TEX_FMT = Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED


def new_surface(w, h):
    return cairo.ImageSurface(FMT, max(1, int(w)), max(1, int(h)))


def copy_surface(src, x=0, y=0, w=None, h=None):
    w = src.get_width() - x if w is None else w
    h = src.get_height() - y if h is None else h
    s = new_surface(w, h)
    cr = cairo.Context(s)
    cr.set_operator(cairo.OPERATOR_SOURCE)
    cr.set_source_surface(src, -x, -y)
    cr.paint()
    s.flush()
    return s


def clip_rect(rect, w, h):
    """Intersect (x, y, w, h) with the image; None if empty."""
    x0, y0 = max(0, int(math.floor(rect[0]))), max(0, int(math.floor(rect[1])))
    x1 = min(w, int(math.ceil(rect[0] + rect[2])))
    y1 = min(h, int(math.ceil(rect[1] + rect[3])))
    if x1 <= x0 or y1 <= y0:
        return None
    return (x0, y0, x1 - x0, y1 - y0)


def union(a, b):
    if a is None:
        return b
    if b is None:
        return a
    x0, y0 = min(a[0], b[0]), min(a[1], b[1])
    x1, y1 = max(a[0] + a[2], b[0] + b[2]), max(a[1] + a[3], b[1] + b[3])
    return (x0, y0, x1 - x0, y1 - y0)


def grow(r, d):
    return (r[0] - d, r[1] - d, r[2] + 2 * d, r[3] + 2 * d)


# --------------------------------------------------------------------------- raw bytes

def read_rect(surf, rect):
    """Raw BGRA bytes of rect (x, y, w, h) (rows packed)."""
    surf.flush()
    x, y, w, h = rect
    stride = surf.get_stride()
    mv = surf.get_data()
    a = x * 4
    return b"".join(mv[(y + r) * stride + a:(y + r) * stride + a + w * 4] for r in range(h))


def write_rect(surf, rect, data):
    surf.flush()
    x, y, w, h = rect
    stride = surf.get_stride()
    mv = surf.get_data()
    row = w * 4
    a = x * 4
    for r in range(h):
        o = (y + r) * stride + a
        mv[o:o + row] = data[r * row:(r + 1) * row]
    surf.mark_dirty()


def pack(surf, rect):
    return zlib.compress(read_rect(surf, rect), 1)


def unpack(surf, rect, blob):
    write_rect(surf, rect, zlib.decompress(blob))


def surface_bytes(surf):
    surf.flush()
    return bytes(surf.get_data())


def texture_from_surface(surf, rect=None):
    if rect is None:
        rect = (0, 0, surf.get_width(), surf.get_height())
    data = read_rect(surf, rect)
    return Gdk.MemoryTexture.new(rect[2], rect[3], TEX_FMT, GLib.Bytes.new(data), rect[2] * 4)


def surface_from_texture(tex):
    w, h = tex.get_width(), tex.get_height()
    dl = Gdk.TextureDownloader.new(tex)
    dl.set_format(TEX_FMT)
    gbytes, stride = dl.download_bytes()
    s = new_surface(w, h)
    data = gbytes.get_data()
    sst = s.get_stride()
    mv = s.get_data()
    row = w * 4
    if stride == sst:
        mv[:len(data)] = data
    else:
        for r in range(h):
            mv[r * sst:r * sst + row] = data[r * stride:r * stride + row]
    s.mark_dirty()
    return s


def pixbuf_from_surface(surf, alpha=True):
    tex = texture_from_surface(surf)
    dl = Gdk.TextureDownloader.new(tex)
    dl.set_format(Gdk.MemoryFormat.R8G8B8A8 if alpha else Gdk.MemoryFormat.R8G8B8)
    gbytes, stride = dl.download_bytes()
    return GdkPixbuf.Pixbuf.new_from_bytes(gbytes, GdkPixbuf.Colorspace.RGB, alpha, 8,
                                           surf.get_width(), surf.get_height(), stride)


def surface_from_pixbuf(pb):
    return surface_from_texture(Gdk.Texture.new_for_pixbuf(pb))


def flatten(surf, bg=(1, 1, 1)):
    s = new_surface(surf.get_width(), surf.get_height())
    cr = cairo.Context(s)
    cr.set_source_rgb(*bg)
    cr.paint()
    cr.set_source_surface(surf, 0, 0)
    cr.paint()
    s.flush()
    return s


# --------------------------------------------------------------------------- pixels

def get_pixel(surf, x, y):
    """(r, g, b, a) floats, un-premultiplied."""
    w, h = surf.get_width(), surf.get_height()
    if not (0 <= x < w and 0 <= y < h):
        return None
    surf.flush()
    o = int(y) * surf.get_stride() + int(x) * 4
    b, g, r, a = surf.get_data()[o:o + 4]
    if a == 0:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(1, r / a), min(1, g / a), min(1, b / a), a / 255)


def premul_bytes(rgba):
    r, g, b, a = rgba
    a8 = int(round(a * 255))
    return bytes((int(round(b * a8)), int(round(g * a8)), int(round(r * a8)), a8))


def _range_table(v, tol):
    lo, hi = max(0, v - tol), min(255, v + tol)
    return bytes(1 if lo <= i <= hi else 0 for i in range(256))


def match_mask(surf, target, tol=0):
    """bytearray (w*h), 1 where the pixel is within tol of target (4 BGRA bytes)."""
    surf.flush()
    w, h = surf.get_width(), surf.get_height()
    stride = surf.get_stride()
    data = bytes(surf.get_data())
    if stride != w * 4:
        data = b"".join(data[r * stride:r * stride + w * 4] for r in range(h))
    acc = None
    for c in range(4):
        ch = data[c::4].translate(_range_table(target[c], tol))
        v = int.from_bytes(ch, "little")
        acc = v if acc is None else acc & v
    return bytearray(acc.to_bytes(w * h, "little"))


def flood_mask(surf, sx, sy, tol=0):
    """Scanline flood fill from (sx, sy) on pixels similar to the seed.
    Returns (mask_bytes (w*h, 255 inside), bbox) or (None, None)."""
    w, h = surf.get_width(), surf.get_height()
    sx, sy = int(sx), int(sy)
    if not (0 <= sx < w and 0 <= sy < h):
        return None, None
    surf.flush()
    o = sy * surf.get_stride() + sx * 4
    target = bytes(surf.get_data()[o:o + 4])
    m = match_mask(surf, target, tol)
    find, rfind = m.find, m.rfind
    one, zero, two = b"\x01", b"\x00", b"\x02"
    minx, miny, maxx, maxy = sx, sy, sx, sy
    stack = [(sx, sy)]
    while stack:
        x, y = stack.pop()
        base = y * w
        if m[base + x] != 1:
            continue
        # extend left / right
        l0 = max(rfind(zero, base, base + x), rfind(two, base, base + x))
        left = (l0 + 1 - base) if l0 >= 0 else 0
        r0 = find(zero, base + x, base + w)
        r1 = find(two, base + x, base + w)
        r0 = min(v for v in (r0, r1, base + w) if v >= 0)
        right = r0 - base  # exclusive
        m[base + left:base + right] = two * (right - left)
        if left < minx:
            minx = left
        if right - 1 > maxx:
            maxx = right - 1
        if y < miny:
            miny = y
        if y > maxy:
            maxy = y
        for ny in (y - 1, y + 1):
            if 0 <= ny < h:
                nb = ny * w
                p = nb + left
                end = nb + right
                while p < end:
                    p = find(one, p, end)
                    if p < 0:
                        break
                    stack.append((p - nb, ny))
                    q0 = find(zero, p, end)
                    q1 = find(two, p, end)
                    q = min(v for v in (q0, q1, end) if v >= 0)
                    p = q
    out = bytes(m).translate(bytes(255 if i == 2 else 0 for i in range(256)))
    return out, (minx, miny, maxx - minx + 1, maxy - miny + 1)


def mask_surface_from_bytes(mask, w, h):
    """A8 cairo surface from w*h bytes."""
    stride = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_A8, w)
    if stride == w:
        buf = bytearray(mask)
    else:
        pad = bytes(stride - w)
        buf = bytearray(b"".join(mask[r * w:(r + 1) * w] + pad for r in range(h)))
    return cairo.ImageSurface.create_for_data(buf, cairo.FORMAT_A8, w, h, stride)


def key_out(surf, rgba, tol=12):
    """Copy of surf with pixels close to rgba made transparent (transparent selection)."""
    target = premul_bytes(rgba)
    w, h = surf.get_width(), surf.get_height()
    m = match_mask(surf, target, tol)
    mask = bytes(m).translate(bytes(0 if i == 1 else 255 for i in range(256)))
    ms = mask_surface_from_bytes(mask, w, h)
    out = new_surface(w, h)
    cr = cairo.Context(out)
    cr.set_source_surface(surf, 0, 0)
    cr.mask_surface(ms, 0, 0)
    out.flush()
    return out


def invert_colors(surf, rect=None):
    """Invert RGB in place (keeps alpha): premultiplied c' = a - c."""
    w, h = surf.get_width(), surf.get_height()
    x, y, rw, rh = rect or (0, 0, w, h)
    cr = cairo.Context(surf)
    cr.rectangle(x, y, rw, rh)
    cr.clip()
    # DIFFERENCE with white inverts colours; then restore the original alpha.
    tmp = copy_surface(surf)
    cr.set_operator(cairo.OPERATOR_SOURCE)
    cr.set_source_rgb(1, 1, 1)
    cr.paint()
    cr.set_operator(cairo.OPERATOR_DIFFERENCE)
    cr.set_source_surface(tmp, 0, 0)
    cr.paint()
    cr.set_operator(cairo.OPERATOR_DEST_IN)
    cr.set_source_surface(tmp, 0, 0)
    cr.paint()
    surf.flush()


# --------------------------------------------------------------------------- geometry ops

def transformed(src, op):
    """New surface: op in rot90 (clockwise), rot270, rot180, flip_h, flip_v."""
    w, h = src.get_width(), src.get_height()
    if op in ("rot90", "rot270"):
        out = new_surface(h, w)
    else:
        out = new_surface(w, h)
    cr = cairo.Context(out)
    if op == "rot90":
        cr.translate(h, 0)
        cr.rotate(math.pi / 2)
    elif op == "rot270":
        cr.translate(0, w)
        cr.rotate(-math.pi / 2)
    elif op == "rot180":
        cr.translate(w, h)
        cr.rotate(math.pi)
    elif op == "flip_h":
        cr.translate(w, 0)
        cr.scale(-1, 1)
    elif op == "flip_v":
        cr.translate(0, h)
        cr.scale(1, -1)
    cr.set_source_surface(src, 0, 0)
    cr.get_source().set_filter(cairo.FILTER_NEAREST)
    cr.paint()
    out.flush()
    return out


def scaled(src, nw, nh, smooth=True):
    nw, nh = max(1, int(round(nw))), max(1, int(round(nh)))
    w, h = src.get_width(), src.get_height()
    out = new_surface(nw, nh)
    cr = cairo.Context(out)
    cr.scale(nw / w, nh / h)
    cr.set_source_surface(src, 0, 0)
    p = cr.get_source()
    p.set_filter(cairo.FILTER_GOOD if smooth else cairo.FILTER_NEAREST)
    p.set_extend(cairo.EXTEND_PAD)
    cr.rectangle(0, 0, w, h)
    cr.fill()
    out.flush()
    return out


def skewed(src, ax_deg, ay_deg):
    """Skew by horizontal/vertical angles (degrees, -89..89); canvas grows to fit."""
    w, h = src.get_width(), src.get_height()
    kx = math.tan(math.radians(ax_deg))
    ky = math.tan(math.radians(ay_deg))
    m = cairo.Matrix(1, ky, kx, 1, 0, 0)
    pts = [m.transform_point(x, y) for x, y in ((0, 0), (w, 0), (0, h), (w, h))]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    nw, nh = int(math.ceil(max(xs) - min(xs))), int(math.ceil(max(ys) - min(ys)))
    out = new_surface(nw, nh)
    cr = cairo.Context(out)
    cr.translate(-min(xs), -min(ys))
    cr.transform(m)
    cr.set_source_surface(src, 0, 0)
    cr.get_source().set_filter(cairo.FILTER_GOOD)
    cr.paint()
    out.flush()
    return out


def rotated(src, deg):
    """Rotate by an arbitrary angle (clockwise degrees); canvas grows to fit."""
    a = math.radians(deg)
    w, h = src.get_width(), src.get_height()
    c, s = abs(math.cos(a)), abs(math.sin(a))
    nw, nh = int(math.ceil(w * c + h * s - 1e-6)), int(math.ceil(w * s + h * c - 1e-6))
    out = new_surface(nw, nh)
    cr = cairo.Context(out)
    cr.translate(nw / 2, nh / 2)
    cr.rotate(a)
    cr.translate(-w / 2, -h / 2)
    cr.set_source_surface(src, 0, 0)
    cr.get_source().set_filter(cairo.FILTER_GOOD)
    cr.paint()
    out.flush()
    return out


def bbox_of_alpha(surf):
    """Tight bounding box of non-transparent pixels, or None."""
    surf.flush()
    w, h = surf.get_width(), surf.get_height()
    stride = surf.get_stride()
    data = bytes(surf.get_data())
    alpha = data[3::4] if stride == w * 4 else b"".join(
        data[r * stride + 3:r * stride + w * 4:4] for r in range(h))
    nz = alpha.translate(bytes([0] + [1] * 255))
    first = nz.find(b"\x01")
    if first < 0:
        return None
    last = nz.rfind(b"\x01")
    y0, y1 = first // w, last // w
    x0, x1 = w, -1
    for y in range(y0, y1 + 1):
        row = nz[y * w:(y + 1) * w]
        a = row.find(b"\x01")
        if a >= 0:
            x0 = min(x0, a)
            x1 = max(x1, row.rfind(b"\x01"))
    return (x0, y0, x1 - x0 + 1, y1 - y0 + 1)


# --------------------------------------------------------------------------- textures

_noise_cache = {}


def noise_surface(size=128, seed=7, density=0.55, soft=False):
    """Repeating A8 paper-grain texture (crayon / natural pencil)."""
    key = (size, seed, density, soft)
    if key in _noise_cache:
        return _noise_cache[key]
    import random
    rnd = random.Random(seed)
    s = cairo.ImageSurface(cairo.FORMAT_A8, size, size)
    stride = s.get_stride()
    buf = bytearray(stride * size)
    for y in range(size):
        for x in range(size):
            v = rnd.random()
            if soft:
                a = int(120 + 135 * v)
            else:
                a = 255 if v < density else int(60 * v)
            buf[y * stride + x] = a
    s.get_data()[:] = buf
    s.mark_dirty()
    _noise_cache[key] = s
    return s


def checker_surface(cell=8, light=(1, 1, 1), dark=(0.8, 0.8, 0.8)):
    s = new_surface(cell * 2, cell * 2)
    cr = cairo.Context(s)
    cr.set_source_rgb(*light)
    cr.paint()
    cr.set_source_rgb(*dark)
    cr.rectangle(0, 0, cell, cell)
    cr.rectangle(cell, cell, cell, cell)
    cr.fill()
    s.flush()
    return s


def to_black_white(surf):
    """New surface: threshold to pure black / white (alpha kept), like Paint's
    Image properties > Colors > Black and white."""
    w, h = surf.get_width(), surf.get_height()
    flat = flatten(surf)
    data = bytes(flat.get_data())
    n = w * h
    b, g, r = data[0::4], data[1::4], data[2::4]
    # luminance with weights 29/150/77 (sum 256): per-channel tables, summed with big ints
    lum = (int.from_bytes(r.translate(bytes(v * 77 // 256 for v in range(256))), "little")
           + int.from_bytes(g.translate(bytes(v * 150 // 256 for v in range(256))), "little")
           + int.from_bytes(b.translate(bytes(v * 29 // 256 for v in range(256))), "little")).to_bytes(n, "little")
    v = lum.translate(bytes(255 if i >= 128 else 0 for i in range(256)))
    out = bytearray(n * 4)
    out[0::4] = v
    out[1::4] = v
    out[2::4] = v
    out[3::4] = b"\xff" * n
    s = new_surface(w, h)
    s.get_data()[:] = bytes(out)
    s.mark_dirty()
    # keep the original transparency
    cr = cairo.Context(s)
    cr.set_operator(cairo.OPERATOR_DEST_IN)
    cr.set_source_surface(surf, 0, 0)
    cr.paint()
    s.flush()
    return s
