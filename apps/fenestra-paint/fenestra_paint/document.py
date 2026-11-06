"""Image document: layers, background, cached composite and undo history.

Rendering model
* every layer is a full-size ARGB32 cairo surface; the background is a plain colour
  (white) that can be hidden for a transparent canvas, like Paint's background layer;
* ``composite`` caches the flattened image and is only recomputed in damaged rectangles;
* while a tool is working (stroke, floating selection, shape preview) the layers below
  and above the active layer are flattened once into ``_below``/``_above`` so every
  motion event composites three surfaces whatever the layer count;
* tools never touch a layer until they commit: they draw into their own surfaces and
  register *preview* callables that paint over the active layer in its group.

Undo: paint operations store zlib-packed before/after patches of the touched rectangle;
structural operations (resize, rotate, layer changes) store packed snapshots.  The
history is bounded by memory (``HISTORY_BYTES``) and entry count."""
from __future__ import annotations

import zlib

import cairo

from . import raster
from .i18n import _

HISTORY_BYTES = 192 * 1024 * 1024
HISTORY_COUNT = 100


class Layer:
    _next = 1

    def __init__(self, w, h, name=None, surface=None, lid=None):
        if lid is None:
            lid = Layer._next
            Layer._next += 1
        else:
            Layer._next = max(Layer._next, lid + 1)
        self.id = lid
        self.surface = surface if surface is not None else raster.new_surface(w, h)
        self.name = name or (_("Layer %d") % lid)
        self.visible = True
        self.opacity = 1.0


class PatchEntry:
    def __init__(self, label, layer_id, rect, before, after):
        self.label, self.layer_id, self.rect = label, layer_id, rect
        self.before, self.after = before, after
        self.size = len(before) + len(after) + 200

    def undo(self, doc):
        layer = doc.layer_by_id(self.layer_id)
        if layer is not None:
            raster.unpack(layer.surface, self.rect, self.before)
            doc.damage(self.rect)

    def redo(self, doc):
        layer = doc.layer_by_id(self.layer_id)
        if layer is not None:
            raster.unpack(layer.surface, self.rect, self.after)
            doc.damage(self.rect)


class StateEntry:
    def __init__(self, label, before, after):
        self.label, self.before, self.after = label, before, after
        self.size = _state_size(before) + _state_size(after) + 200

    def undo(self, doc):
        doc.restore_state(self.before)

    def redo(self, doc):
        doc.restore_state(self.after)


def _state_size(st):
    return sum(len(layer[5]) for layer in st["layers"]) + 200


class History:
    def __init__(self, doc):
        self.doc = doc
        self.undo_stack: list = []
        self.redo_stack: list = []
        self.serial = 0          # increases with every change; used for "modified"
        self._counter = 0
        self.bytes = 0

    def push(self, entry):
        self._counter += 1
        entry.serial = self._counter
        self.undo_stack.append(entry)
        self.bytes += entry.size
        self.redo_stack.clear()
        self._trim()
        self.serial = entry.serial
        self.doc.notify("history")

    def _trim(self):
        self.bytes = sum(e.size for e in self.undo_stack)
        while len(self.undo_stack) > 1 and (self.bytes > HISTORY_BYTES or len(self.undo_stack) > HISTORY_COUNT):
            e = self.undo_stack.pop(0)
            self.bytes -= e.size

    def can_undo(self):
        return bool(self.undo_stack)

    def can_redo(self):
        return bool(self.redo_stack)

    def undo(self):
        if not self.undo_stack:
            return False
        e = self.undo_stack.pop()
        e.undo(self.doc)
        self.redo_stack.append(e)
        self.serial = self.undo_stack[-1].serial if self.undo_stack else 0
        self.doc.notify("history")
        return True

    def redo(self):
        if not self.redo_stack:
            return False
        e = self.redo_stack.pop()
        e.redo(self.doc)
        self.undo_stack.append(e)
        self.serial = e.serial
        self.doc.notify("history")
        return True

    def clear(self):
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.serial = 0
        self.bytes = 0
        self.doc.notify("history")


class Document:
    def __init__(self, w=1152, h=648):
        self.width, self.height = int(w), int(h)
        self.bg_color = (1.0, 1.0, 1.0)
        self.bg_visible = True
        self.layers = [Layer(self.width, self.height)]
        self.active = 0
        self.composite = raster.new_surface(self.width, self.height)
        self.preview = []            # callables(cr) drawn over the active layer
        self.listeners = []          # cb(kind, rect)
        self.history = History(self)
        self.saved_serial = 0
        self._below = self._above = None
        self.render()

    # ------------------------------------------------------------------ events
    def connect(self, cb):
        self.listeners.append(cb)

    def notify(self, kind, rect=None):
        for cb in list(self.listeners):
            cb(kind, rect)

    @property
    def modified(self):
        return self.history.serial != self.saved_serial

    def mark_saved(self):
        self.saved_serial = self.history.serial
        self.notify("history")

    # ------------------------------------------------------------------ layers
    @property
    def layer(self) -> Layer:
        return self.layers[self.active]

    def layer_by_id(self, lid):
        for layer in self.layers:
            if layer.id == lid:
                return layer
        return None

    def visible_layers(self):
        return [layer for layer in self.layers if layer.visible]

    # ------------------------------------------------------------------ rendering
    def begin_cache(self):
        """Flatten the layers below/above the active one (called when a tool starts)."""
        w, h = self.width, self.height
        below = raster.new_surface(w, h)
        cr = cairo.Context(below)
        if self.bg_visible:
            cr.set_source_rgb(*self.bg_color)
            cr.paint()
        for layer in self.layers[:self.active]:
            if layer.visible:
                cr.set_source_surface(layer.surface, 0, 0)
                cr.paint_with_alpha(layer.opacity)
        above = None
        ups = [layer for layer in self.layers[self.active + 1:] if layer.visible]
        if ups:
            above = raster.new_surface(w, h)
            cr = cairo.Context(above)
            for layer in ups:
                cr.set_source_surface(layer.surface, 0, 0)
                cr.paint_with_alpha(layer.opacity)
        self._below, self._above = below, above

    def end_cache(self):
        self._below = self._above = None

    def _paint_active(self, cr, layer):
        if not layer.visible:
            return
        if not self.preview and layer.opacity >= 1:
            cr.set_source_surface(layer.surface, 0, 0)
            cr.paint()
            return
        cr.push_group()
        cr.set_source_surface(layer.surface, 0, 0)
        cr.paint()
        for fn in self.preview:
            cr.save()
            fn(cr)
            cr.restore()
        cr.pop_group_to_source()
        cr.paint_with_alpha(layer.opacity)

    def render(self, rect=None):
        r = raster.clip_rect(rect or (0, 0, self.width, self.height), self.width, self.height)
        if r is None:
            return None
        cr = cairo.Context(self.composite)
        cr.rectangle(*r)
        cr.clip()
        cr.set_operator(cairo.OPERATOR_SOURCE)
        if self._below is not None:
            cr.set_source_surface(self._below, 0, 0)
            cr.paint()
            cr.set_operator(cairo.OPERATOR_OVER)
            self._paint_active(cr, self.layer)
            if self._above is not None:
                cr.set_source_surface(self._above, 0, 0)
                cr.paint()
        else:
            if self.bg_visible:
                cr.set_source_rgb(*self.bg_color)
            else:
                cr.set_source_rgba(0, 0, 0, 0)
            cr.paint()
            cr.set_operator(cairo.OPERATOR_OVER)
            for i, layer in enumerate(self.layers):
                if i == self.active:
                    self._paint_active(cr, layer)
                elif layer.visible:
                    cr.set_source_surface(layer.surface, 0, 0)
                    cr.paint_with_alpha(layer.opacity)
        self.composite.flush()
        return r

    def damage(self, rect=None):
        r = self.render(rect)
        if r is not None:
            self.notify("damage", r)

    def flatten(self, include_bg=True):
        """New surface with all visible layers (and the background when visible)."""
        s = raster.new_surface(self.width, self.height)
        cr = cairo.Context(s)
        if include_bg and self.bg_visible:
            cr.set_source_rgb(*self.bg_color)
            cr.paint()
        for layer in self.layers:
            if layer.visible:
                cr.set_source_surface(layer.surface, 0, 0)
                cr.paint_with_alpha(layer.opacity)
        s.flush()
        return s

    # ------------------------------------------------------------------ undoable edits
    def modify_layer(self, rect, fn, label="", layer=None):
        """Run fn(cr) on the (active) layer clipped to rect, recording an undo patch."""
        layer = layer or self.layer
        r = raster.clip_rect(rect, self.width, self.height)
        if r is None:
            return False
        before = raster.pack(layer.surface, r)
        cr = cairo.Context(layer.surface)
        cr.rectangle(*r)
        cr.clip()
        fn(cr)
        layer.surface.flush()
        after = raster.pack(layer.surface, r)
        if before != after:
            self.history.push(PatchEntry(label, layer.id, r, before, after))
        self.damage(r)
        return True

    def capture_state(self):
        return {
            "w": self.width, "h": self.height, "bg": self.bg_color, "bgv": self.bg_visible,
            "active": self.active,
            "layers": [(layer.id, layer.name, layer.visible, layer.opacity,
                        (layer.surface.get_width(), layer.surface.get_height()),
                        zlib.compress(raster.surface_bytes(layer.surface), 1))
                       for layer in self.layers],
        }

    def restore_state(self, st):
        self.width, self.height = st["w"], st["h"]
        self.bg_color, self.bg_visible = st["bg"], st["bgv"]
        layers = []
        for lid, name, vis, op, (w, h), blob in st["layers"]:
            s = raster.new_surface(w, h)
            data = zlib.decompress(blob)
            s.get_data()[:len(data)] = data
            s.mark_dirty()
            layer = Layer(w, h, name, s, lid)
            layer.visible, layer.opacity = vis, op
            layers.append(layer)
        self.layers = layers
        self.active = min(st["active"], len(layers) - 1)
        self._resized()

    def _resized(self):
        if (self.composite.get_width(), self.composite.get_height()) != (self.width, self.height):
            self.composite = raster.new_surface(self.width, self.height)
        self.end_cache()
        self.render()
        self.notify("structure")
        self.notify("damage", (0, 0, self.width, self.height))

    def structural(self, fn, label=""):
        """Run fn() (which may replace layers / size) recording a full snapshot."""
        before = self.capture_state()
        fn()
        self._resized()
        self.history.push(StateEntry(label, before, self.capture_state()))

    # ------------------------------------------------------------------ whole-image ops
    def replace_all(self, surface, name=None):
        """Load: the image becomes the single layer, history cleared."""
        self.width, self.height = surface.get_width(), surface.get_height()
        Layer._next = 1
        self.layers = [Layer(self.width, self.height, name, surface)]
        self.active = 0
        self.bg_visible = True
        self.history.clear()
        self.saved_serial = 0
        self._resized()

    def map_layers(self, fn, label=""):
        """Replace every layer surface by fn(surface); size follows the first layer."""
        def run():
            for layer in self.layers:
                layer.surface = fn(layer.surface)
            self.width = self.layers[0].surface.get_width()
            self.height = self.layers[0].surface.get_height()
        self.structural(run, label)

    def resize_canvas(self, w, h, dx=0, dy=0, label=""):
        """Change the canvas size keeping pixels (offset by dx, dy)."""
        w, h = max(1, int(w)), max(1, int(h))

        def fn(s):
            out = raster.new_surface(w, h)
            cr = cairo.Context(out)
            cr.set_source_surface(s, dx, dy)
            cr.paint()
            out.flush()
            return out
        self.map_layers(fn, label or _("Resize canvas"))

    # ------------------------------------------------------------------ layer ops
    def add_layer(self, surface=None, name=None):
        def fn():
            layer = Layer(self.width, self.height, name, surface)
            self.layers.insert(self.active + 1, layer)
            self.active += 1
        self.structural(fn, _("Add layer"))

    def delete_layer(self, idx=None):
        idx = self.active if idx is None else idx
        if len(self.layers) <= 1:
            # Paint keeps one layer: deleting it clears it instead.
            def clear():
                self.layers[0] = Layer(self.width, self.height, self.layers[0].name, None, self.layers[0].id)
            self.structural(clear, _("Delete layer"))
            return

        def fn():
            del self.layers[idx]
            self.active = max(0, min(self.active if self.active < idx else self.active - 1, len(self.layers) - 1))
        self.structural(fn, _("Delete layer"))

    def duplicate_layer(self, idx=None):
        idx = self.active if idx is None else idx
        src = self.layers[idx]

        def fn():
            layer = Layer(self.width, self.height, _("%s copy") % src.name, raster.copy_surface(src.surface))
            layer.opacity, layer.visible = src.opacity, src.visible
            self.layers.insert(idx + 1, layer)
            self.active = idx + 1
        self.structural(fn, _("Duplicate layer"))

    def move_layer(self, idx, delta):
        j = idx + delta
        if not (0 <= idx < len(self.layers) and 0 <= j < len(self.layers)):
            return

        def fn():
            act = self.layers[self.active]
            self.layers[idx], self.layers[j] = self.layers[j], self.layers[idx]
            self.active = self.layers.index(act)
        self.structural(fn, _("Move layer"))

    def merge_down(self, idx=None):
        idx = self.active if idx is None else idx
        if idx <= 0:
            return

        def fn():
            top, bottom = self.layers[idx], self.layers[idx - 1]
            out = raster.new_surface(self.width, self.height)
            cr = cairo.Context(out)
            if bottom.visible:
                cr.set_source_surface(bottom.surface, 0, 0)
                cr.paint_with_alpha(bottom.opacity)
            if top.visible:
                cr.set_source_surface(top.surface, 0, 0)
                cr.paint_with_alpha(top.opacity)
            out.flush()
            bottom.surface, bottom.opacity, bottom.visible = out, 1.0, True
            del self.layers[idx]
            self.active = idx - 1
        self.structural(fn, _("Merge down"))

    def set_layer_visible(self, idx, vis):
        def fn():
            self.layers[idx].visible = vis
        self.structural(fn, _("Hide layer") if not vis else _("Show layer"))

    def set_layer_opacity(self, idx, op, record=True):
        if record:
            def fn():
                self.layers[idx].opacity = op
            self.structural(fn, _("Layer opacity"))
        else:
            self.layers[idx].opacity = op
            self.damage()

    def set_bg_visible(self, vis):
        def fn():
            self.bg_visible = vis
        self.structural(fn, _("Background"))

    def set_active(self, idx):
        if 0 <= idx < len(self.layers) and idx != self.active:
            self.active = idx
            self.end_cache()
            self.notify("structure")
