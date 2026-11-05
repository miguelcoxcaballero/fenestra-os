"""A fast, fully custom-drawn tree table (header + rows) used by every list page.

Drawing goes straight to Gtk.Snapshot (no per-cell widgets), only the visible
rows are rendered, and updates replace the flat row list without touching
selection, expansion or scroll position.  Implements Gtk.Scrollable so it can
live inside a Gtk.ScrolledWindow (overlay scrollbars, kinetic scrolling).
"""
from __future__ import annotations

import bisect

from gi.repository import Gdk, Gio, GObject, Graphene, Gsk, Gtk, Pango

from .. import theme

FONT_FAMILY = "Segoe UI Variable Text, Segoe UI, Selawik, Inter, sans-serif"


def font(px, weight=Pango.Weight.NORMAL):
    d = Pango.FontDescription.from_string(FONT_FAMILY)
    d.set_absolute_size(px * Pango.SCALE)
    d.set_weight(weight)
    return d


def R(x, y, w, h):
    return Graphene.Rect().init(x, y, w, h)


def P(x, y):
    p = Graphene.Point()
    p.x, p.y = x, y
    return p


class Column:
    def __init__(self, key, title, width, align="left", heat=False, stretch=False, sortable=True,
                 desc_first=False, min_width=28):
        self.key, self.title, self.width = key, title, width
        self.align, self.heat, self.stretch, self.sortable = align, heat, stretch, sortable
        self.desc_first, self.min_width = desc_first, min_width
        self.value = None          # header top line (e.g. "8%")
        self.value_heat = None     # heat index for the header (high system load)
        self.x = 0
        self.w = width


class Row:
    __slots__ = ("key", "kind", "level", "cells", "heat", "icon", "expandable", "status", "data", "dim")

    def __init__(self, key, kind="item", level=0, cells=None, heat=None, icon=None, expandable=False,
                 status=None, data=None, dim=False):
        self.key, self.kind, self.level = key, kind, level
        self.cells = cells or {}
        self.heat = heat or {}
        self.icon, self.expandable, self.status, self.data, self.dim = icon, expandable, status, data, dim


class Table(Gtk.Widget, Gtk.Scrollable):
    __gtype_name__ = "FenestraTaskTable"
    __gsignals__ = {
        "selection-changed": (GObject.SignalFlags.RUN_LAST, None, ()),
        "sort-changed": (GObject.SignalFlags.RUN_LAST, None, ()),
        "expand-toggled": (GObject.SignalFlags.RUN_LAST, None, (str,)),
        "context-menu": (GObject.SignalFlags.RUN_LAST, None, (float, float)),
        "row-activated": (GObject.SignalFlags.RUN_LAST, None, ()),
        "delete-pressed": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    hscroll_policy = GObject.Property(type=Gtk.ScrollablePolicy, default=Gtk.ScrollablePolicy.MINIMUM)
    vscroll_policy = GObject.Property(type=Gtk.ScrollablePolicy, default=Gtk.ScrollablePolicy.MINIMUM)

    def __init__(self, columns, header_h=48, row_h=28, group_h=38, two_line=True, name_pad=16,
                 icon_col=True, font_px=12, group_px=16, chev_w=21, right_pad=0):
        super().__init__()
        self.columns = columns
        self.header_h, self.row_h, self.group_h = header_h, row_h, group_h
        self.two_line, self.name_pad, self.icon_col = two_line, name_pad, icon_col
        self.chev_w, self.right_pad = chev_w, right_pad
        self.f_text = font(font_px)
        self.f_group = font(group_px)
        self.f_value = font(16)
        self.f_head = font(12)
        self.rows: list[Row] = []
        self._ys: list[int] = [0]
        self._index: dict[str, int] = {}
        self.expanded: set[str] = set()
        self.selected: str | None = None
        self.hover = -1
        self.sort_key = columns[0].key
        self.sort_desc = False
        self.header_focus = False
        self._hadj = None
        self._vadj = None
        self._layouts: dict = {}
        self._icons: dict = {}
        self._resize = None
        self.set_focusable(True)
        self.set_overflow(Gtk.Overflow.HIDDEN)
        self.add_css_class("task-table")

        click = Gtk.GestureClick(button=0)
        click.connect("pressed", self._on_press)
        self.add_controller(click)
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._drag_begin)
        drag.connect("drag-update", self._drag_update)
        drag.connect("drag-end", lambda *a: setattr(self, "_resize", None))
        self.add_controller(drag)
        motion = Gtk.EventControllerMotion()
        motion.connect("motion", self._on_motion)
        motion.connect("leave", self._on_leave)
        self.add_controller(motion)
        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self._on_key)
        self.add_controller(key)
        theme.get().listeners.append(self._theme_changed)

    def _theme_changed(self):
        self._icons.clear()
        self.queue_draw()

    # ------------------------------------------------------------ scrollable
    @GObject.Property(type=Gtk.Adjustment)
    def hadjustment(self):
        return self._hadj

    @hadjustment.setter
    def hadjustment(self, adj):
        self._hadj = adj
        if adj is not None:
            adj.connect("value-changed", lambda *_: self.queue_draw())
        self._configure()

    @GObject.Property(type=Gtk.Adjustment)
    def vadjustment(self):
        return self._vadj

    @vadjustment.setter
    def vadjustment(self, adj):
        self._vadj = adj
        if adj is not None:
            adj.connect("value-changed", lambda *_: self._on_scroll())
        self._configure()

    def do_get_border(self):
        b = Gtk.Border()
        b.top = self.header_h
        return True, b

    def _on_scroll(self):
        self.hover = -1
        self.queue_draw()

    def _content_w(self):
        return sum(c.width for c in self.columns)

    def _configure(self):
        w, h = self.get_width(), self.get_height()
        if self._hadj is not None:
            cw = max(self._content_w(), w)
            v = min(self._hadj.get_value(), max(0, cw - w))
            self._hadj.configure(v, 0, cw, 20, w * 0.9, w)
        if self._vadj is not None:
            ch = self._ys[-1]
            page = max(1, h - self.header_h)
            v = min(self._vadj.get_value(), max(0, ch - page))
            self._vadj.configure(v, 0, max(ch, page), self.row_h, page * 0.9, page)

    def do_measure(self, orientation, for_size):
        if orientation == Gtk.Orientation.HORIZONTAL:
            return 100, self._content_w(), -1, -1
        mn = self.header_h + self.row_h
        return mn, max(mn, self.header_h + self._ys[-1]), -1, -1

    def do_size_allocate(self, w, h, baseline):
        self._layout_columns(w)
        self._configure()

    def _layout_columns(self, w=None):
        w = self.get_width() if w is None else w
        total = self._content_w()
        extra = max(0, w - total - self.right_pad)
        x = 0
        for c in self.columns:
            c.w = c.width + (extra if c.stretch else 0)
            c.x = x
            x += c.w

    # ------------------------------------------------------------ data
    def set_rows(self, rows):
        self.rows = rows
        ys = [0]
        y = 0
        for r in rows:
            y += self.group_h if r.kind == "group" else self.row_h
            ys.append(y)
        self._ys = ys
        self._index = {r.key: i for i, r in enumerate(rows)}
        if self.selected is not None and self.selected not in self._index:
            self.selected = None
            self.emit("selection-changed")
        if len(self._layouts) > 6000:
            self._layouts.clear()
        self._configure()
        self.queue_draw()
        self.queue_resize() if self.get_height() < 2 else None

    def selected_row(self):
        i = self._index.get(self.selected) if self.selected else None
        return self.rows[i] if i is not None else None

    def select(self, key):
        if key != self.selected:
            self.selected = key
            self.emit("selection-changed")
            self.queue_draw()

    def set_sort(self, key, desc):
        self.sort_key, self.sort_desc = key, desc
        self.queue_draw()

    def toggle(self, key):
        if key in self.expanded:
            self.expanded.discard(key)
        else:
            self.expanded.add(key)
        self.emit("expand-toggled", key)

    def refresh_header(self):
        self.queue_draw()

    # ------------------------------------------------------------ geometry
    def _scroll_x(self):
        return self._hadj.get_value() if self._hadj else 0.0

    def _scroll_y(self):
        return self._vadj.get_value() if self._vadj else 0.0

    def row_at(self, y):
        if y < self.header_h:
            return -1
        cy = y - self.header_h + self._scroll_y()
        i = bisect.bisect_right(self._ys, cy) - 1
        return i if 0 <= i < len(self.rows) else -1

    def col_at(self, x):
        cx = x + self._scroll_x()
        for c in self.columns:
            if c.x <= cx < c.x + c.w:
                return c
        return None

    def ensure_visible(self, i):
        if self._vadj is None or not (0 <= i < len(self.rows)):
            return
        top, bot = self._ys[i], self._ys[i + 1]
        v = self._vadj.get_value()
        page = self._vadj.get_page_size()
        if top < v:
            self._vadj.set_value(top)
        elif bot > v + page:
            self._vadj.set_value(bot - page)

    # ------------------------------------------------------------ events
    def _on_motion(self, _c, x, y):
        i = self.row_at(y)
        if i != self.hover:
            self.hover = i
            self.queue_draw()
        edge = self._edge_at(x, y)
        self.set_cursor_from_name("col-resize" if edge is not None else None)

    def _on_leave(self, *_):
        if self.hover != -1:
            self.hover = -1
            self.queue_draw()

    def _edge_at(self, x, y):
        if y >= self.header_h:
            return None
        cx = x + self._scroll_x()
        for c in self.columns:
            if abs(c.x + c.w - cx) <= 4 and not c.stretch:
                return c
        return None

    def _drag_begin(self, g, x, y):
        c = self._edge_at(x, y)
        self._resize = (c, c.width) if c else None

    def _drag_update(self, g, dx, dy):
        if not self._resize:
            return
        c, w0 = self._resize
        c.width = max(c.min_width, int(w0 + dx))
        self._layout_columns()
        self._configure()
        self.queue_draw()

    def _on_press(self, gesture, n, x, y):
        self.grab_focus()
        button = gesture.get_current_button()
        if y < self.header_h:
            if button != 1 or self._edge_at(x, y) is not None:
                return
            c = self.col_at(x)
            if c and c.sortable:
                if c.key == self.sort_key:
                    self.sort_desc = not self.sort_desc
                else:
                    self.sort_key, self.sort_desc = c.key, c.desc_first
                self.header_focus = False
                self.emit("sort-changed")
                self.queue_draw()
            return
        i = self.row_at(y)
        if i < 0:
            if button == 1:
                self.select(None)
            return
        row = self.rows[i]
        self.header_focus = False
        if button == 3:
            if row.kind != "group":
                self.select(row.key)
                self.emit("context-menu", x, y)
            return
        if row.kind == "group":
            return
        first = self.columns[0]
        cx = x + self._scroll_x() - first.x
        chev_x = self.name_pad + 4 + row.level * 22
        if row.expandable and chev_x - 8 <= cx <= chev_x + 12 and n == 1:
            self.select(row.key)
            self.toggle(row.key)
            return
        self.select(row.key)
        if n == 2:
            if row.expandable:
                self.toggle(row.key)
            else:
                self.emit("row-activated")

    def _on_key(self, _c, keyval, keycode, state):
        name = Gdk.keyval_name(keyval) or ""
        sel = self._index.get(self.selected, -1) if self.selected else -1
        items = [i for i, r in enumerate(self.rows) if r.kind != "group"]
        if not items:
            return False
        if name in ("Down", "Up", "Home", "End", "Page_Down", "Page_Up"):
            pos = bisect.bisect_left(items, sel) if sel >= 0 else -1
            step = max(1, int((self.get_height() - self.header_h) / self.row_h) - 1)
            if name == "Down":
                pos = 0 if pos < 0 else min(len(items) - 1, pos + 1)
            elif name == "Up":
                pos = 0 if pos < 0 else max(0, pos - 1)
            elif name == "Home":
                pos = 0
            elif name == "End":
                pos = len(items) - 1
            elif name == "Page_Down":
                pos = min(len(items) - 1, max(0, pos) + step)
            else:
                pos = max(0, pos - step)
            self.select(self.rows[items[pos]].key)
            self.ensure_visible(items[pos])
            return True
        row = self.selected_row()
        if row is None:
            return False
        if name in ("Right", "plus", "KP_Add") and row.expandable and row.key not in self.expanded:
            self.toggle(row.key)
            return True
        if name in ("Left", "minus", "KP_Subtract") and row.expandable and row.key in self.expanded:
            self.toggle(row.key)
            return True
        if name in ("Return", "KP_Enter"):
            if row.expandable:
                self.toggle(row.key)
            else:
                self.emit("row-activated")
            return True
        if name == "Delete":
            self.emit("delete-pressed")
            return True
        if name == "Menu" or (name == "F10" and state & Gdk.ModifierType.SHIFT_MASK):
            i = self._index[row.key]
            y = self.header_h + self._ys[i] - self._scroll_y() + self.row_h / 2
            self.emit("context-menu", 120.0, float(y))
            return True
        return False

    # ------------------------------------------------------------ drawing helpers
    def _layout(self, text, desc, width=None):
        key = (text, id(desc), width)
        lay = self._layouts.get(key)
        if lay is None:
            lay = Pango.Layout.new(self.get_pango_context())
            lay.set_font_description(desc)
            lay.set_text(text, -1)
            if width is not None:
                lay.set_width(max(1, int(width)) * Pango.SCALE)
                lay.set_ellipsize(Pango.EllipsizeMode.END)
            self._layouts[key] = lay
        return lay

    def _text(self, snap, text, desc, x, y_center, color, width=None, align="left"):
        lay = self._layout(text, desc, width)
        _ink, logical = lay.get_pixel_extents()
        tw = logical.width
        if align == "right":
            x = x - tw
        elif align == "center":
            x = x - tw / 2
        snap.save()
        snap.translate(P(round(x), round(y_center - logical.height / 2)))
        snap.append_layout(lay, color)
        snap.restore()
        return tw

    def _paintable(self, spec, size=16):
        key = (spec, size, self.get_scale_factor())
        if key in self._icons:
            return self._icons[key]
        p = None
        it = Gtk.IconTheme.get_for_display(self.get_display())
        try:
            if isinstance(spec, Gio.Icon):
                gicon = spec
            elif spec and (spec.startswith("/") or spec.startswith(". ")):
                gicon = Gio.Icon.new_for_string(spec)
            else:
                gicon = None
            if gicon is not None:
                p = it.lookup_by_gicon(gicon, size, self.get_scale_factor(), Gtk.TextDirection.NONE, 0)
            elif spec:
                if it.has_icon(spec) or spec.startswith("tm-"):
                    p = it.lookup_icon(spec, None, size, self.get_scale_factor(), Gtk.TextDirection.NONE, 0)
        except Exception:  # noqa: BLE001
            p = None
        self._icons[key] = p
        return p

    def _icon(self, snap, spec, x, y, size=16, color=None):
        p = self._paintable(spec, size)
        if p is None:
            p = self._paintable("tm-process", size)
            if p is None:
                return
        snap.save()
        snap.translate(P(x, y))
        if color is not None and isinstance(p, Gtk.SymbolicPaintable):
            p.snapshot_symbolic(snap, size, size, [color])
        else:
            p.snapshot(snap, size, size)
        snap.restore()

    @staticmethod
    def _chevron(snap, cx, cy, direction, color, s=3.5):
        b = Gsk.PathBuilder.new()
        if direction == "right":
            b.move_to(cx - s / 2, cy - s)
            b.line_to(cx + s / 2, cy)
            b.line_to(cx - s / 2, cy + s)
        elif direction == "down":
            b.move_to(cx - s, cy - s / 2)
            b.line_to(cx, cy + s / 2)
            b.line_to(cx + s, cy - s / 2)
        else:  # up
            b.move_to(cx - s, cy + s / 2)
            b.line_to(cx, cy - s / 2)
            b.line_to(cx + s, cy + s / 2)
        stroke = Gsk.Stroke.new(1.0)
        stroke.set_line_cap(Gsk.LineCap.ROUND)
        stroke.set_line_join(Gsk.LineJoin.ROUND)
        snap.append_stroke(b.to_path(), stroke, color)

    # ------------------------------------------------------------ snapshot
    def do_snapshot(self, snap):
        th = theme.get()
        c = th.c
        w, h = self.get_width(), self.get_height()
        sx, sy = self._scroll_x(), self._scroll_y()
        hh = self.header_h
        cols = self.columns
        last_x = cols[-1].x + cols[-1].w
        has_focus = self.has_focus()

        # ---------------- body
        snap.push_clip(R(0, hh, w, max(0, h - hh)))
        first = max(0, bisect.bisect_right(self._ys, sy) - 1)
        i = first
        sel_bg = c["select"]
        hover_bg = c["hover"]
        while i < len(self.rows):
            y = hh + self._ys[i] - sy
            if y > h:
                break
            row = self.rows[i]
            rh = self._ys[i + 1] - self._ys[i]
            if row.kind == "group":
                gtxt = row.cells.get(cols[0].key, "")
                self._text(snap, gtxt, self.f_group, cols[0].x - sx + self.name_pad, y + rh / 2 + 3,
                           c["fg"], width=last_x)
            else:
                for col in cols:
                    if col.heat and col.key in row.heat and row.heat[col.key] is not None:
                        hc = th.heat[min(row.heat[col.key], len(th.heat) - 1)]
                        snap.append_color(hc, R(col.x - sx, y, col.w, rh))
                if row.key == self.selected:
                    snap.append_color(sel_bg if True else hover_bg, R(-sx, y, max(w + sx, last_x), rh))
                    if any(col.heat for col in cols):
                        for col in cols:
                            if col.heat and col.key in row.heat:
                                hc = th.heat[min((row.heat[col.key] or 0) + 1, len(th.heat) - 2)]
                                snap.append_color(hc, R(col.x - sx, y, col.w, rh))
                elif i == self.hover:
                    snap.append_color(hover_bg, R(-sx, y, max(w + sx, last_x), rh))
                fg = c["fg2"] if row.dim else c["fg"]
                for ci, col in enumerate(cols):
                    x = col.x - sx
                    if x > w or x + col.w < 0:
                        continue
                    txt = row.cells.get(col.key, "")
                    if ci == 0:
                        base = x + self.name_pad + row.level * 22
                        tx = base
                        if self.icon_col:
                            if row.expandable:
                                d = "down" if row.key in self.expanded else "right"
                                self._chevron(snap, base + 5, y + rh / 2, d, c["fg2"])
                            ix = base + self.chev_w
                            if row.icon is not None:
                                self._icon(snap, row.icon, ix, y + (rh - 16) / 2)
                            tx = ix + 22
                        self._text(snap, txt, self.f_text, tx, y + rh / 2, fg, width=x + col.w - tx - 6)
                    elif col.key == "status" and row.status:
                        st = row.status
                        if st in ("eff", "susp"):
                            icon = "tm-leaf-filled-symbolic" if st == "eff" else "tm-pause-symbolic"
                            color = c["leaf"] if st == "eff" else c["warn"]
                            self._icon(snap, icon, x + col.w - 27, y + (rh - 16) / 2, 16, color)
                        if txt:
                            self._text(snap, txt, self.f_text, x + 6, y + rh / 2, fg, width=col.w - 36)
                    elif txt:
                        if col.align == "right":
                            self._text(snap, txt, self.f_text, x + col.w - 7, y + rh / 2, fg,
                                       width=None, align="right")
                        else:
                            self._text(snap, txt, self.f_text, x + 6, y + rh / 2, fg, width=col.w - 12)
            i += 1
        # column separators through the body
        for col in cols:
            x = col.x + col.w - 1 - sx
            if 0 <= x < w:
                snap.append_color(th.heat_line if col.heat else c["line"], R(x, hh, 1, h - hh))
        snap.pop()

        # ---------------- header
        snap.push_clip(R(0, 0, w, hh))
        snap.append_color(c["panel"], R(0, 0, w, hh))
        for ci, col in enumerate(cols):
            x = col.x - sx
            if x > w or x + col.w < 0:
                continue
            sorted_col = col.key == self.sort_key
            if sorted_col and self.header_focus:
                snap.append_color(c["header-sel"], R(x, 0, col.w, hh - 1))
                b = Gsk.RoundedRect()
                b.init_from_rect(R(x, 0, col.w, hh - 1), 0)
                fgc = c["fg"]
                snap.append_border(b, [1, 1, 1, 1], [fgc, fgc, fgc, fgc])
            pad = self.name_pad if ci == 0 else 6
            label_y = hh - 12 if self.two_line else hh / 2
            if col.align == "right":
                tl = self._layout(col.title, self.f_head, col.w - 10)
                tw = min(tl.get_pixel_extents()[1].width, col.w - 10)
                self._text(snap, col.title, self.f_head, x + col.w - 7 - tw, label_y, c["fg2"],
                           width=col.w - 10)
                if self.two_line and col.value:
                    self._text(snap, col.value, self.f_value, x + col.w - 7, 16, c["fg"], align="right")
            else:
                self._text(snap, col.title, self.f_head, x + pad, label_y, c["fg2"], width=col.w - pad - 4)
            if sorted_col and col.sortable:
                self._chevron(snap, x + col.w / 2, 9 if self.two_line else 4,
                              "down" if self.sort_desc else "up", c["fg2"], s=3.2)
            if ci > 0 or not self.header_focus:
                lx = x + col.w - 1
                if not (sorted_col and self.header_focus):
                    snap.append_color(c["line"], R(lx, 0, 1, hh))
        snap.append_color(c["line"], R(0, hh - 1, w, 1))
        snap.pop()
        if has_focus and self.selected is None and not self.header_focus:
            pass
