"""Soft, blurred-looking abstract gradient backgrounds drawn with GSK.

No bitmap is involved: a base linear gradient plus a few large radial
"blobs" that drift very slowly, which reads like a heavily blurred photo.
"""

import math

from gi.repository import Gdk, Graphene, Gsk, Gtk


def _rgba(spec: str, alpha: float | None = None) -> Gdk.RGBA:
    c = Gdk.RGBA()
    c.parse(spec)
    if alpha is not None:
        c.alpha = alpha
    return c


def _stop(offset: float, color: Gdk.RGBA) -> Gsk.ColorStop:
    s = Gsk.ColorStop()
    s.offset = offset
    s.color = color
    return s


# (base top-left, base bottom-right, blobs[(x, y, radius, color, drift)])
THEMES = {
    # Very pale blue-grey with large soft blue / periwinkle blobs.
    # Very pale blue-grey with large soft blue / periwinkle blobs.
    "light": (
        "#d3e1ec", "#dee8f1",
        [
            (0.60, 0.13, 0.12, "#a6d1ff", 0.02),
            (0.43, 0.99, 0.27, "#98b5e8", 0.02),
            (0.19, 0.85, 0.14, "#a8cbfc", 0.03),
            (0.87, 0.62, 0.14, "#a2acdc", 0.03),
            (0.70, 0.97, 0.13, "#9fb4de", 0.02),
        ],
    ),
    "dark": (
        "#0b1a33", "#1b0f2e",
        [
            (0.20, 0.25, 0.60, "#1f4f8a", 0.08),
            (0.80, 0.30, 0.55, "#3c2a7a", 0.09),
            (0.65, 0.85, 0.65, "#0f5d73", 0.07),
            (0.15, 0.85, 0.45, "#22306b", 0.10),
        ],
    ),
}


class GradientBackground(Gtk.Widget):
    __gtype_name__ = "FenestraGradientBackground"

    def __init__(self, theme: str = "light", animate: bool = True, speed: float = 1.0):
        super().__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)
        self._theme = THEMES[theme]
        self._phase = 0.0
        self._speed = speed
        self._start = None
        if animate:
            self.add_tick_callback(self._tick)

    def _tick(self, _widget, clock):
        t = clock.get_frame_time() / 1_000_000
        if self._start is None:
            self._start = t
        self._phase = (t - self._start) * 0.12 * self._speed
        self.queue_draw()
        return True

    def do_snapshot(self, snapshot):
        w, h = self.get_width(), self.get_height()
        if w <= 0 or h <= 0:
            return
        top, bottom, blobs = self._theme
        rect = Graphene.Rect().init(0, 0, w, h)
        snapshot.append_linear_gradient(
            rect, Graphene.Point().init(0, 0), Graphene.Point().init(w, h),
            [_stop(0.0, _rgba(top)), _stop(1.0, _rgba(bottom))],
        )
        diag = math.hypot(w, h)
        for i, (x, y, r, color, drift) in enumerate(blobs):
            ph = self._phase + i * 1.7
            cx = (x + drift * math.sin(ph)) * w
            cy = (y + drift * math.cos(ph * 0.8)) * h
            rad = r * diag * (1.0 + 0.06 * math.sin(ph * 0.6))
            clear = _rgba(color, 0.0)
            snapshot.append_radial_gradient(
                rect, Graphene.Point().init(cx, cy), rad, rad, 0.0, 1.0,
                [_stop(0.0, _rgba(color, 0.85)), _stop(0.45, _rgba(color, 0.45)), _stop(1.0, clear)],
            )
