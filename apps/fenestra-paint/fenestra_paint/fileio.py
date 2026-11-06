"""Loading and saving images (GdkPixbuf / GdkTexture), GIF encoding, desktop background."""
from __future__ import annotations

import os
import struct
import time

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gio, GLib  # noqa: E402

from . import raster, util  # noqa: E402
from .i18n import N_  # noqa: E402

OPEN_MIME = ["image/png", "image/jpeg", "image/bmp", "image/gif", "image/webp", "image/tiff",
             "image/x-bmp", "image/x-icon", "image/avif"]
OPEN_EXT = ["png", "jpg", "jpeg", "jpe", "jfif", "bmp", "dib", "gif", "webp", "tif", "tiff", "ico", "avif"]

# (id, label, extensions, pixbuf type, keeps alpha)
FORMATS = [
    ("png", N_("PNG picture"), ["png"], "png", True),
    ("jpeg", N_("JPEG picture"), ["jpg", "jpeg", "jpe", "jfif"], "jpeg", False),
    ("bmp", N_("BMP picture"), ["bmp", "dib"], "bmp", False),
    ("gif", N_("GIF picture"), ["gif"], None, True),
    ("tiff", N_("TIFF picture"), ["tif", "tiff"], "tiff", True),
    ("webp", N_("WEBP picture"), ["webp"], "webp", True),
]


def writable_types():
    out = set()
    for f in GdkPixbuf.Pixbuf.get_formats():
        if f.is_writable():
            out.add(f.get_name())
    return out


def save_formats():
    w = writable_types()
    return [f for f in FORMATS if f[3] is None or f[3] in w]


def format_for_path(path):
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    for f in save_formats():
        if ext in f[2]:
            return f
    return None


def load(path):
    """Cairo surface of the image at path (first frame of animations)."""
    tex = None
    try:
        tex = Gdk.Texture.new_from_filename(path)
    except GLib.Error:
        tex = None
    if tex is None:
        pb = GdkPixbuf.Pixbuf.new_from_file(path)
        pb = pb.apply_embedded_orientation() or pb
        return raster.surface_from_pixbuf(pb)
    surf = raster.surface_from_texture(tex)
    # Gdk textures ignore EXIF orientation; pixbuf knows it (JPEG photos)
    if path.lower().endswith((".jpg", ".jpeg", ".jpe", ".jfif")):
        try:
            pb = GdkPixbuf.Pixbuf.new_from_file(path)
            if pb.get_option("orientation") not in (None, "1"):
                return raster.surface_from_pixbuf(pb.apply_embedded_orientation())
        except GLib.Error:
            pass
    return surf


def load_bytes(data):
    tex = Gdk.Texture.new_from_bytes(GLib.Bytes.new(data))
    return raster.surface_from_texture(tex)


def save(surface, path, fmt=None):
    """Write surface (already flattened, ARGB32) to path. Raises GLib.Error / OSError."""
    f = fmt or format_for_path(path) or FORMATS[0]
    fid = f[0]
    tmp = path + ".part~"
    if fid == "gif":
        with open(tmp, "wb") as fh:
            fh.write(encode_gif(surface))
    else:
        alpha = f[4]
        src = surface if alpha else raster.flatten(surface)
        pb = raster.pixbuf_from_surface(src, alpha)
        keys, vals = [], []
        if fid == "jpeg":
            keys, vals = ["quality"], ["92"]
        elif fid == "png":
            keys, vals = ["compression"], ["6"]
        elif fid == "webp":
            keys, vals = ["quality"], ["92"]
        pb.savev(tmp, f[3], keys, vals)
    os.replace(tmp, path)


# --------------------------------------------------------------------------- GIF

def _quantize(surface):
    """(palette bytes (768), index bytes, transparent index or None)."""
    surface.flush()
    w, h = surface.get_width(), surface.get_height()
    data = bytes(surface.get_data())
    stride = surface.get_stride()
    if stride != w * 4:
        data = b"".join(data[r * stride:r * stride + w * 4] for r in range(h))
    b, g, r, a = data[0::4], data[1::4], data[2::4], data[3::4]
    n = w * h
    has_alpha = min(a) < 128
    from collections import Counter
    counts = Counter(zip(r, g, b)) if n <= 4_000_000 else Counter()
    pal = bytearray(768)
    if counts and len(counts) <= (255 if has_alpha else 256):
        cols = {c: i for i, c in enumerate(sorted(counts))}
        for (cr_, cg, cb), i in cols.items():
            pal[i * 3:i * 3 + 3] = bytes((cr_, cg, cb))
        idx = bytes(map(cols.__getitem__, zip(r, g, b)))
    else:
        # 5x5x5 colour cube (125 entries) for the long tail plus the 125 most frequent
        # colours kept exact (flat fills and strokes, which dominate drawings)
        tr = bytes(min(4, (v * 5) // 256) * 25 for v in range(256))
        tg = bytes(min(4, (v * 5) // 256) * 5 for v in range(256))
        tb = bytes(min(4, (v * 5) // 256) for v in range(256))
        sm = (int.from_bytes(r.translate(tr), "little") + int.from_bytes(g.translate(tg), "little")
              + int.from_bytes(b.translate(tb), "little"))
        cube = sm.to_bytes(n, "little")
        for R in range(5):
            for G in range(5):
                for B in range(5):
                    i = R * 25 + G * 5 + B
                    pal[i * 3:i * 3 + 3] = bytes((R * 255 // 4, G * 255 // 4, B * 255 // 4))
        common = {}
        for k, (c, _n) in enumerate(counts.most_common(125 if has_alpha else 126)):
            common[c] = 125 + k
            pal[(125 + k) * 3:(125 + k) * 3 + 3] = bytes(c)
        get = common.get
        idx = bytes(get(c, ci) for c, ci in zip(zip(r, g, b), cube))
    trans = None
    if has_alpha:
        trans = 255
        m = a.translate(bytes(255 if v < 128 else 0 for v in range(256)))
        idx = (int.from_bytes(idx, "little") | int.from_bytes(m, "little")).to_bytes(n, "little")
    return bytes(pal), idx, trans


def _lzw(idx, min_code=8):
    clear = 1 << min_code
    eoi = clear + 1
    out = bytearray()
    bitbuf = 0
    nbits = 0
    size = min_code + 1
    table = {}
    nxt = eoi + 1
    limit = 1 << size

    bitbuf |= clear << nbits
    nbits += size
    it = iter(idx)
    try:
        w = next(it)
    except StopIteration:
        w = None
    get = table.get
    for k in it:
        key = (w << 8) | k
        c = get(key)
        if c is not None:
            w = c
            continue
        bitbuf |= w << nbits
        nbits += size
        while nbits >= 8:
            out.append(bitbuf & 0xFF)
            bitbuf >>= 8
            nbits -= 8
        if nxt < 4096:
            table[key] = nxt
            nxt += 1
            if nxt > limit and size < 12:
                size += 1
                limit = 1 << size
        else:
            bitbuf |= clear << nbits
            nbits += size
            table.clear()
            get = table.get
            nxt = eoi + 1
            size = min_code + 1
            limit = 1 << size
        w = k
    if w is not None:
        bitbuf |= w << nbits
        nbits += size
    bitbuf |= eoi << nbits
    nbits += size
    while nbits > 0:
        out.append(bitbuf & 0xFF)
        bitbuf >>= 8
        nbits -= 8
    return bytes(out)


def encode_gif(surface):
    w, h = surface.get_width(), surface.get_height()
    pal, idx, trans = _quantize(surface)
    out = bytearray(b"GIF89a")
    out += struct.pack("<HHBBB", w, h, 0xF7, 0, 0)
    out += pal
    if trans is not None:
        out += b"\x21\xF9\x04\x01\x00\x00" + bytes([trans]) + b"\x00"
    out += b"\x2C" + struct.pack("<HHHHB", 0, 0, w, h, 0)
    out += b"\x08"
    data = _lzw(idx, 8)
    for i in range(0, len(data), 255):
        chunk = data[i:i + 255]
        out += bytes([len(chunk)]) + chunk
    out += b"\x00\x3B"
    return bytes(out)


# --------------------------------------------------------------------------- desktop

def wallpaper_dir():
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "backgrounds")


def set_wallpaper(path, option="zoom"):
    """Point both light and dark GNOME backgrounds at path."""
    uri = Gio.File.new_for_path(path).get_uri()
    ok = util.gset("org.gnome.desktop.background", "picture-uri", uri)
    util.gset("org.gnome.desktop.background", "picture-uri-dark", uri)
    util.gset("org.gnome.desktop.background", "picture-options", option)
    return ok


def wallpaper_copy(surface):
    d = wallpaper_dir()
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "paint-%s.png" % time.strftime("%Y%m%d-%H%M%S"))
    save(surface, path, FORMATS[0])
    return path

