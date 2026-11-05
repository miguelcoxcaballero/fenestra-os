"""Custom containers: responsive centered card and animated page host."""

from gi.repository import Graphene, Gsk, Gtk


def _ease_out_cubic(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


class CardFrame(Gtk.Widget):
    """Centers a single child and sizes it like the reference OOBE card
    (about 1040x660 on a 1920x1080 screen, scaled for other sizes)."""

    __gtype_name__ = "FenestraCardFrame"

    def __init__(self, child: Gtk.Widget, corner: Gtk.Widget | None = None):
        super().__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.child = child
        child.set_parent(self)
        # Small widget placed under the card's bottom-right corner
        # (the accessibility button in the reference layout).
        self.corner = corner
        if corner is not None:
            corner.set_parent(self)

    def do_dispose(self):
        for w in (self.child, self.corner):
            if w is not None:
                w.unparent()
        self.child = self.corner = None

    def do_measure(self, orientation, for_size):
        mn, nat, _, _ = self.child.measure(orientation, -1)
        return (min(mn, 300), nat, -1, -1)

    def do_snapshot(self, snapshot):
        self.snapshot_child(self.child, snapshot)
        if self.corner is not None:
            self.snapshot_child(self.corner, snapshot)

    CARD_W, CARD_H = 1200, 760   # reference size at 1920x1080 (100 % scale)

    @classmethod
    def card_size(cls, width: int, height: int) -> tuple[int, int]:
        """Fixed 1200x760 like the reference; shrinks only on small screens."""
        cw = min(cls.CARD_W, width - 48)
        ch = min(cls.CARD_H, height - 96)
        return int(max(cw, 320)), int(max(ch, 320))

    def do_size_allocate(self, width, height, baseline):
        cw, ch = self.card_size(width, height)
        min_w, _, _, _ = self.child.measure(Gtk.Orientation.HORIZONTAL, -1)
        cw = max(cw, min(min_w, width))
        min_h, _, _, _ = self.child.measure(Gtk.Orientation.VERTICAL, cw)
        ch = max(ch, min(min_h, height))
        x = int((width - cw) / 2)
        y = int((height - ch) / 2)
        t = Gsk.Transform.new().translate(Graphene.Point().init(x, y))
        self.child.allocate(cw, ch, -1, t)
        if self.corner is not None:
            _, nw, _, _ = self.corner.measure(Gtk.Orientation.HORIZONTAL, -1)
            _, nh, _, _ = self.corner.measure(Gtk.Orientation.VERTICAL, nw)
            # Reference: icon centre ~21 px left of the card's right edge and
            # ~28 px below its bottom edge.
            cx = x + cw - 21 - nw / 2
            cy = min(y + ch + 28 - nh / 2, height - nh)
            self.corner.allocate(nw, nh, -1,
                                 Gsk.Transform.new().translate(Graphene.Point().init(int(cx), int(cy))))


class PageHost(Gtk.Widget):
    """Shows one page; switching slides the new page in from the side while
    fading it in, and fades the old page out (~250 ms, ease-out)."""

    __gtype_name__ = "FenestraPageHost"

    DURATION = 0.26
    OFFSET = 48

    def __init__(self):
        super().__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_overflow(Gtk.Overflow.HIDDEN)
        self.current = None
        self.old = None
        self.progress = 1.0
        self.direction = 1
        self._start = None
        self._tick_id = 0

    def do_dispose(self):
        for w in (self.old, self.current):
            if w is not None and w.get_parent() is self:
                w.unparent()
        self.old = self.current = None

    def set_page(self, page: Gtk.Widget, direction: int = 1, animate: bool = True):
        if page is self.current:
            return
        if self.old is not None and self.old.get_parent() is self:
            self.old.unparent()
        if page.get_parent() is not None:
            page.unparent()
        self.old = self.current
        self.current = page
        page.set_parent(self)
        self.direction = direction
        if animate and self.old is not None and self.get_mapped():
            self.progress = 0.0
            self._start = None
            if not self._tick_id:
                self._tick_id = self.add_tick_callback(self._tick)
        else:
            self._finish()
        self.queue_allocate()

    def _finish(self):
        self.progress = 1.0
        if self.old is not None and self.old.get_parent() is self:
            self.old.unparent()
        self.old = None
        if self.current is not None:
            self.current.set_opacity(1.0)

    def _tick(self, _w, clock):
        now = clock.get_frame_time() / 1_000_000
        if self._start is None:
            self._start = now
        self.progress = min(1.0, (now - self._start) / self.DURATION)
        if self.progress >= 1.0:
            self._finish()
            self._tick_id = 0
            self.queue_allocate()
            return False
        self.queue_allocate()
        return True

    def do_measure(self, orientation, for_size):
        mn = nat = 0
        for w in (self.current, self.old):
            if w is not None:
                a, b, _, _ = w.measure(orientation, for_size)
                mn, nat = max(mn, a), max(nat, b)
        return (mn, nat, -1, -1)

    def do_size_allocate(self, width, height, baseline):
        e = _ease_out_cubic(self.progress)
        if self.current is not None:
            dx = (1 - e) * self.OFFSET * self.direction
            self.current.set_opacity(min(1.0, e * 1.15) if self.old is not None else 1.0)
            self.current.allocate(width, height, -1,
                                  Gsk.Transform.new().translate(Graphene.Point().init(dx, 0)))
        if self.old is not None:
            fade = _ease_out_cubic(min(1.0, self.progress * 2.2))
            self.old.set_opacity(1 - fade)
            dx = -fade * self.OFFSET * 0.5 * self.direction
            self.old.allocate(width, height, -1,
                              Gsk.Transform.new().translate(Graphene.Point().init(dx, 0)))

    def do_snapshot(self, snapshot):
        if self.old is not None:
            self.snapshot_child(self.old, snapshot)
        if self.current is not None:
            self.snapshot_child(self.current, snapshot)
