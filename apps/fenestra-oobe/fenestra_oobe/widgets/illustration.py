"""Crisp SVG illustrations rendered at the exact on-screen pixel size."""

import logging

from gi.repository import GLib, Gdk, Graphene, Gtk

from .. import paths

log = logging.getLogger("fenestra-oobe")

try:
    import cairo
    import gi
    gi.require_version("Rsvg", "2.0")
    from gi.repository import Rsvg
except (ImportError, ValueError):  # pragma: no cover - fallback path
    Rsvg = None
    cairo = None


def render_svg(path: str, width: int, height: int, data: bytes | None = None):
    """Return a Gdk.Texture for the SVG (file or ``data``) scaled to fit width x height."""
    if Rsvg is not None and cairo is not None:
        try:
            handle = Rsvg.Handle.new_from_data(data) if data is not None else Rsvg.Handle.new_from_file(path)
            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
            cr = cairo.Context(surface)
            vp = Rsvg.Rectangle()
            vp.x, vp.y, vp.width, vp.height = 0, 0, width, height
            handle.render_document(cr, vp)
            surface.flush()
            data = GLib.Bytes.new(bytes(surface.get_data()))
            return Gdk.MemoryTexture.new(width, height, Gdk.MemoryFormat.B8G8R8A8_PREMULTIPLIED,
                                         data, surface.get_stride())
        except Exception as exc:  # noqa: BLE001
            log.warning("rsvg failed for %s: %s", path, exc)
    try:
        if data is not None:
            return Gdk.Texture.new_from_bytes(GLib.Bytes.new(data))
        return Gdk.Texture.new_from_filename(path)
    except GLib.Error as exc:
        log.warning("could not load %s: %s", path, exc.message)
        return None


class Illustration(Gtk.Widget):
    __gtype_name__ = "FenestraIllustration"

    def __init__(self, name: str, fraction: float = 0.667, aspect: float = 1.0):
        super().__init__()
        self.path = paths.illustration(name)
        self.fraction = fraction
        self.aspect = aspect  # width / height of the artwork
        self._texture = None
        self._tex_size = (0, 0)
        self.set_hexpand(True)
        self.set_vexpand(True)

    def do_measure(self, orientation, for_size):
        return (0, 200, -1, -1)

    def do_snapshot(self, snapshot):
        w, h = self.get_width(), self.get_height()
        if w <= 0 or h <= 0:
            return
        box = min(w, h / self.aspect) * self.fraction
        dw, dh = box, box / self.aspect
        scale = self.get_scale_factor()
        px = (max(1, int(dw * scale)), max(1, int(dh * scale)))
        if self._texture is None or self._tex_size != px:
            self._texture = render_svg(self.path, *px)
            self._tex_size = px
        if self._texture is None:
            return
        x, y = (w - dw) / 2, (h - dh) / 2
        snapshot.append_texture(self._texture, Graphene.Rect().init(x, y, dw, dh))


class SvgIcon(Gtk.Widget):
    """Fixed-size icon drawn from data/icons/<name>.svg at device resolution."""

    __gtype_name__ = "FenestraSvgIcon"

    def __init__(self, name: str, size: int = 16):
        super().__init__()
        self.path = paths.data_file("icons", f"{name}.svg")
        self.size = size
        self._texture = None
        self._scale = 0
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)

    def do_measure(self, orientation, for_size):
        return (self.size, self.size, -1, -1)

    def do_snapshot(self, snapshot):
        scale = self.get_scale_factor()
        if self._texture is None or self._scale != scale:
            self._texture = render_svg(self.path, self.size * scale, self.size * scale)
            self._scale = scale
        if self._texture is not None:
            snapshot.append_texture(self._texture, Graphene.Rect().init(0, 0, self.size, self.size))
