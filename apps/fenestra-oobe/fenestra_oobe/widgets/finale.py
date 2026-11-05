"""Full-screen closing sequence: "Hi" ... "Let's start"."""

from gi.repository import GLib, Gtk

from ..i18n import _
from .background import GradientBackground

FADE = 0.7


def steps():
    # (headline, small line, seconds on screen including fades)
    return [
        (_("Hi"), "", 2.4),
        (_("We're getting everything ready for you"), "", 2.6),
        (_("This might take a few minutes"), _("Don't turn off your PC"), 3.0),
        (_("Let's start"), "", 2.4),
    ]


class FinaleView(Gtk.Overlay):
    __gtype_name__ = "FenestraFinaleView"

    def __init__(self):
        super().__init__(css_classes=["finale"])
        self.set_child(GradientBackground("dark", animate=True, speed=2.5))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                      halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        self.headline = Gtk.Label(css_classes=["finale-headline"], justify=Gtk.Justification.CENTER,
                                  wrap=True)
        self.small = Gtk.Label(css_classes=["finale-small"], justify=Gtk.Justification.CENTER)
        box.append(self.headline)
        box.append(self.small)
        self.text_box = box
        self.add_overlay(box)
        self._steps = []
        self._index = -1
        self._step_start = None
        self._on_done = None
        self._tick_id = 0
        box.set_opacity(0)

    def show_step(self, index: int):
        """Static display of one step (used for screenshots)."""
        st = steps()
        head, small, _dur = st[index]
        self.headline.set_label(head)
        self.small.set_label(small)
        self.small.set_visible(bool(small))
        self.text_box.set_opacity(1)

    def play(self, on_done):
        self._steps = steps()
        self._index = -1
        self._on_done = on_done
        self._next_step()
        self._tick_id = self.add_tick_callback(self._tick)

    def _next_step(self):
        self._index += 1
        self._step_start = None
        if self._index >= len(self._steps):
            return False
        head, small, _dur = self._steps[self._index]
        self.headline.set_label(head)
        self.small.set_label(small)
        self.small.set_visible(bool(small))
        return True

    def _tick(self, _w, clock):
        now = clock.get_frame_time() / 1_000_000
        if self._index >= len(self._steps):
            self.text_box.set_opacity(0)
            cb, self._on_done = self._on_done, None
            if cb:
                GLib.idle_add(lambda: (cb(), False)[1])
            self._tick_id = 0
            return False
        if self._step_start is None:
            self._step_start = now
        dur = self._steps[self._index][2]
        t = now - self._step_start
        if t < FADE:
            op = t / FADE
        elif t > dur - FADE:
            op = max(0.0, (dur - t) / FADE)
        else:
            op = 1.0
        # smoothstep for a softer fade
        self.text_box.set_opacity(op * op * (3 - 2 * op))
        if t >= dur:
            self._next_step()
        return True
