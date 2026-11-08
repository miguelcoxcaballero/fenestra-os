"""Images for banners and icons, loaded off the UI thread.

* `request_banner(app, width, cb)`: the app's first screenshot (the large AppStream image when
  there is one), downloaded once into ~/.cache/fenestra-store/media, scaled down to `width`
  pixels once and kept as ~/.cache/fenestra-store/banners/<hash>-<width>.(jpg|png), so the
  next start only decodes a small file. cb(Gdk.Texture or None) runs on the UI thread.
* `request_icon(app, cb)`: the app's icon file (cached, remote or a web app's site icon) as a
  texture, plus its dominant colour for banners of apps without branding colours.

Two worker threads (newest request first, so what is on screen loads first), an in-memory
cache of the last textures, and one request per image however many widgets ask for it.
Demo mode never touches the network: banners are the generated screenshots from art.py.
"""
from __future__ import annotations

import colorsys
import hashlib
import os
import queue
import threading

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib  # noqa: E402

from . import util  # noqa: E402

WORKERS = 2
KEEP = 64


class Loader:
    def __init__(self, workers=WORKERS, keep=KEEP):
        self._q: queue.LifoQueue = queue.LifoQueue()
        self._lock = threading.Lock()
        self._pending: dict = {}
        self._done: dict = {}
        self._order: list = []
        self._keep = keep
        self._n = workers
        self._threads: list = []
        self.requests = 0          # tests: how many images were actually produced by a worker

    def cached(self, key):
        with self._lock:
            return self._done.get(key)

    def get(self, key, fn, cb):
        """cb(result) on the UI thread; right away when the result is cached. fn runs in a worker."""
        with self._lock:
            hit = key in self._done
            res = self._done.get(key)
        if hit:   # synchronous: a page that is rebuilt (or a hero that rotates) never flashes the skeleton
            _call(cb, res)
            return
        with self._lock:
            if key in self._pending:
                self._pending[key].append(cb)
                return
            self._pending[key] = [cb]
            self._threads = [t for t in self._threads if t.is_alive()]
            if len(self._threads) < self._n:
                t = threading.Thread(target=self._work, name="fenestra-store-media", daemon=True)
                self._threads.append(t)
                t.start()
        self._q.put((key, fn))

    def _work(self):
        while True:
            try:
                key, fn = self._q.get(timeout=5.0)
            except queue.Empty:
                return
            try:
                res = fn()
            except Exception as e:  # noqa: BLE001 - a broken image only shows the fallback
                util.log("media failed", key, e)
                res = None
            with self._lock:
                self.requests += 1
                self._done[key] = res
                self._order.append(key)
                while len(self._order) > self._keep:
                    self._done.pop(self._order.pop(0), None)
                cbs = self._pending.pop(key, [])
            for cb in cbs:
                GLib.idle_add(_call, cb, res)


def _call(cb, res):
    try:
        cb(res)
    except Exception as e:  # noqa: BLE001 - a widget that went away must not break the loader
        util.log("media callback failed", e)
    return False


loader = Loader()


# --------------------------------------------------------------------------- workers

def scaled_file(src: str, width: int, key: str) -> str | None:
    """A copy of image src at most `width` px wide in the banner cache (made once)."""
    base = os.path.join(util.cache_dir("banners"), hashlib.sha1(key.encode()).hexdigest() + f"-{width}")
    for ext in (".jpg", ".png"):
        if os.path.isfile(base + ext):
            return base + ext
    fmt, w, _h = GdkPixbuf.Pixbuf.get_file_info(src)
    if fmt is None:
        return None
    pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(src, width, -1, True) if w > width else \
        GdkPixbuf.Pixbuf.new_from_file(src)
    ext, kind, keys, vals = (".png", "png", [], []) if pb.get_has_alpha() else (".jpg", "jpeg", ["quality"], ["88"])
    try:
        pb.savev(base + ext + ".part", kind, keys, vals)
        os.replace(base + ext + ".part", base + ext)
        return base + ext
    except GLib.Error as e:
        util.log("cannot cache banner", e)
        return None


def banner_texture(url: str, width: int):
    """Worker: the screenshot at url as a texture at most `width` px wide (None if unavailable)."""
    src = util.fetch_cached(url)
    if not src:
        return None
    path = scaled_file(src, width, url)
    try:
        return Gdk.Texture.new_from_filename(path or src)
    except GLib.Error:
        return None


def dominant_color(path: str) -> str:
    """'#rrggbb' of the most colourful pixels of an icon ('' when it is grey or unreadable)."""
    try:
        pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 24, 24, True)
    except GLib.Error:
        return ""
    n, rs, w, h = pb.get_n_channels(), pb.get_rowstride(), pb.get_width(), pb.get_height()
    data = pb.get_pixels()
    acc = [0.0, 0.0, 0.0]
    total = 0.0
    for y in range(h):
        for x in range(w):
            i = y * rs + x * n
            r, g, b = data[i], data[i + 1], data[i + 2]
            a = data[i + 3] / 255.0 if n == 4 else 1.0
            _hh, ll, ss = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
            wgt = a * (ss + 0.05) * (1.0 - abs(ll - 0.5))
            acc[0] += r * wgt
            acc[1] += g * wgt
            acc[2] += b * wgt
            total += wgt
    if total <= 0:
        return ""
    r, g, b = (v / total / 255.0 for v in acc)
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    if ss < 0.12:
        return ""
    return "#%02x%02x%02x" % tuple(int(v * 255) for v in colorsys.hls_to_rgb(hh, ll, min(1.0, ss * 1.15)))


def icon_file(app) -> str | None:
    """Worker: a local icon file for app (cached AppStream icon, remote icon or the site's icon)."""
    if app.icon_path and os.path.isfile(app.icon_path):
        return app.icon_path
    if app.packaging == "web":
        from .backends import webapps
        return webapps.fetch_icon(app)
    if app.icon_url:
        return util.fetch_cached(app.icon_url)
    return None


def _icon_job(app):
    path = icon_file(app)
    if not path:
        return None, ""
    app.icon_path = path      # later widgets load the file directly
    try:
        tex = Gdk.Texture.new_from_filename(path)
    except GLib.Error:
        return None, ""
    return tex, ("" if (app.brand_dark or app.brand_light) else dominant_color(path))


# --------------------------------------------------------------------------- API (UI thread)

def request_banner(app, width: int, cb):
    """cb(texture or None) with the app's banner image (its first screenshot)."""
    shot = app.hero_shot
    if shot is None:
        _call(cb, None)
        return
    if util.DEMO or not (shot.large or shot.url):
        from . import art, theme
        _call(cb, art.screenshot_texture(app, shot.art, 960, 600, theme.get().dark))
        return
    url = shot.large or shot.url
    loader.get(("banner", url, width), lambda: banner_texture(url, width), cb)


def request_icon(app, cb):
    """cb((texture or None, dominant colour '' or '#rrggbb'))."""
    if util.DEMO:
        from . import art
        _call(cb, (art.icon_texture(app, 128), ""))
        return
    loader.get(("icon", app.uid), lambda: _icon_job(app), cb)


def rgba(hexcolor: str, alpha: float = 1.0) -> Gdk.RGBA:
    c = Gdk.RGBA()
    if not hexcolor or not c.parse(hexcolor):
        c.parse("#2b2b2b")
    c.alpha = alpha
    return c


def banner_colour(app, dark: bool, fallback: str = "") -> str:
    """The colour behind an app's banner: its branding colour for the scheme, else the icon's
    dominant colour darkened (dark) or lightened (light), else a neutral grey."""
    c = app.brand(dark)
    if c:
        return c
    if fallback:
        r, g, b = (int(fallback[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
        h, _l, s = colorsys.rgb_to_hls(r, g, b)
        return "#%02x%02x%02x" % tuple(int(v * 255) for v in colorsys.hls_to_rgb(h, 0.24 if dark else 0.86,
                                                                                    min(s, 0.55)))
    return "#2b2b2b" if dark else "#e6e6e6"
