"""Performance graphs (big 60-second graphs with a moving grid, and the small sidebar ones)."""
from __future__ import annotations

from gi.repository import Gsk, Gtk

from .. import theme
from .table import P, R


class Graph(Gtk.Widget):
    __gtype_name__ = "FenestraTaskGraph"

    def __init__(self, kind="cpu", mini=False, grid=True, rows=10, cols=20, min_h=40):
        super().__init__()
        self.kind = kind
        self.mini = mini
        self.grid = grid and not mini
        self.rows, self.cols = rows, cols
        self.series = []        # list of (values, style) ; style "fill" | "line" | "dash"
        self.maximum = 100.0
        self.scale_line = None  # y value of an auto-scale line (network)
        self.tick = 0
        self.min_h = min_h
        self.set_overflow(Gtk.Overflow.HIDDEN)
        theme.get().listeners.append(self.queue_draw)

    def do_measure(self, orientation, for_size):
        if orientation == Gtk.Orientation.HORIZONTAL:
            return (60, 60, -1, -1) if self.mini else (120, 400, -1, -1)
        return self.min_h, self.min_h, -1, -1

    def set_data(self, series, maximum=100.0, tick=0, scale_line=None, scale_text=None):
        self.scale_text = scale_text
        self.series = series
        self.maximum = maximum or 1.0
        self.tick = tick
        self.scale_line = scale_line
        self.queue_draw()

    def do_snapshot(self, snap):
        th = theme.get()
        w, h = self.get_width(), self.get_height()
        if w < 4 or h < 4:
            return
        line, fill = th.graph.get(self.kind, th.graph["cpu"])
        snap.append_color(th.c["mini-bg"] if self.mini else th.c["panel"], R(0, 0, w, h))
        iw, ih = w - 2, h - 2
        if self.grid:
            dx = iw / self.cols
            off = (self.tick % 3) * dx / 3.0
            x = iw - off
            while x > 0:
                snap.append_color(th.c["grid"], R(1 + x, 1, 1, ih))
                x -= dx
            for r in range(1, self.rows):
                snap.append_color(th.c["grid"], R(1, 1 + round(r * ih / self.rows), iw, 1))
        for values, style in self.series:
            n = len(values)
            if n < 2:
                continue
            step = iw / (n - 1)
            pts = []
            for i, v in enumerate(values):
                if v is None:
                    continue
                y = 1 + ih - max(0.0, min(1.0, v / self.maximum)) * ih
                pts.append((1 + i * step, y))
            if len(pts) < 2:
                continue
            if style == "fill":
                b = Gsk.PathBuilder.new()
                b.move_to(pts[0][0], 1 + ih)
                for x, y in pts:
                    b.line_to(x, y)
                b.line_to(pts[-1][0], 1 + ih)
                b.close()
                snap.append_fill(b.to_path(), Gsk.FillRule.WINDING, fill)
            b = Gsk.PathBuilder.new()
            b.move_to(*pts[0])
            for x, y in pts[1:]:
                b.line_to(x, y)
            stroke = Gsk.Stroke.new(1.0)
            stroke.set_line_join(Gsk.LineJoin.ROUND)
            if style == "dash":
                stroke.set_dash([3.0, 2.0])
            snap.append_stroke(b.to_path(), stroke, line)
        if self.scale_line is not None:
            y = 1 + ih - self.scale_line / self.maximum * ih
            snap.append_color(line, R(1, round(y), iw, 1))
            if getattr(self, "scale_text", None) and not self.mini:
                from .table import font
                lay = self.create_pango_layout(self.scale_text)
                lay.set_font_description(font(10))
                _ink, lg = lay.get_pixel_extents()
                snap.save()
                snap.translate(P(w - lg.width - 3, round(y) - lg.height - 1))
                snap.append_layout(lay, th.c["fg"])
                snap.restore()
        # border
        bc = th.c["graph-border"]
        snap.append_color(bc, R(0, 0, w, 1))
        snap.append_color(bc, R(0, h - 1, w, 1))
        snap.append_color(bc, R(0, 0, 1, h))
        snap.append_color(bc, R(w - 1, 0, 1, h))


class CompositionBar(Gtk.Widget):
    """Memory composition: in use | modified | standby | free."""
    __gtype_name__ = "FenestraTaskComposition"

    def __init__(self):
        super().__init__()
        self.parts = (0.4, 0.01, 0.5, 0.09)
        theme.get().listeners.append(self.queue_draw)

    def do_measure(self, orientation, for_size):
        if orientation == Gtk.Orientation.HORIZONTAL:
            return 120, 400, -1, -1
        return 52, 52, -1, -1

    def set_parts(self, used, modified, standby, free):
        tot = max(1e-9, used + modified + standby + free)
        self.parts = (used / tot, modified / tot, standby / tot, free / tot)
        self.queue_draw()

    def do_snapshot(self, snap):
        th = theme.get()
        w, h = self.get_width(), self.get_height()
        line, fill = th.graph["mem"]
        snap.append_color(th.c["panel"], R(0, 0, w, h))
        used, mod, standby, free = self.parts
        x1 = round(w * used)
        x2 = round(w * (used + mod))
        x3 = round(w * (used + mod + standby))
        snap.append_color(fill, R(0, 0, x1, h))
        mod_fill = fill.copy()
        mod_fill.alpha = 0.7
        snap.append_color(mod_fill, R(x1, 0, max(0, x2 - x1), h))
        for x in (x1, x2, x3):
            if 0 < x < w:
                snap.append_color(line, R(x, 0, 1, h))
        snap.append_color(line, R(0, 0, w, 1))
        snap.append_color(line, R(0, h - 1, w, 1))
        snap.append_color(line, R(0, 0, 1, h))
        snap.append_color(line, R(w - 1, 0, 1, h))
