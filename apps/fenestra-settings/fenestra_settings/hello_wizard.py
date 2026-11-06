"""Fenestra Hello setup wizard (face via Howdy, fingerprint via fprintd).

Rendered as an in-window modal dialog that mimics the reference "Hello setup" window:
dark card, small caption title bar, 20px title at the top-left, body text, a centred
illustration (live camera / fingerprint art), status line, and buttons at the bottom-right.
"""
from __future__ import annotations

import math

from gi.repository import GLib, Gtk

from . import theme, util
from .backends import hello
from .i18n import N_, _
from .widgets import button, icon, label

ANIM_MS = 200


def _rgba(hexstr, alpha=1.0):
    h = hexstr.lstrip("#")
    return int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255, alpha


def _ease(t):
    return 1 - (1 - t) ** 3


class AnimatedValue:
    """Smoothly animates a float toward a target, redrawing a widget each frame."""

    def __init__(self, widget, value=0.0, speed=2.5):
        self.widget, self.value, self.target, self.speed = widget, value, value, speed
        self._tick = 0
        self._last = None

    def set(self, target, instant=False):
        self.target = target
        if instant or not Gtk.Settings.get_default().props.gtk_enable_animations:
            self.value = target
            self.widget.queue_draw()
            return
        if not self._tick:
            self._last = None
            self._tick = self.widget.add_tick_callback(self._step)

    def _step(self, widget, clock):
        now = clock.get_frame_time() / 1e6
        dt = 0.016 if self._last is None else min(0.05, now - self._last)
        self._last = now
        diff = self.target - self.value
        stepv = self.speed * dt
        if abs(diff) <= stepv:
            self.value = self.target
            self._tick = 0
            widget.queue_draw()
            return GLib.SOURCE_REMOVE
        self.value += stepv if diff > 0 else -stepv
        widget.queue_draw()
        return GLib.SOURCE_CONTINUE


def _colors():
    tm = theme.get()
    dark = tm.dark
    return {
        "accent": _rgba(tm.accent_hex()),
        "track": (1, 1, 1, 0.16) if dark else (0, 0, 0, 0.12),
        "ridge": (1, 1, 1, 0.30) if dark else (0, 0, 0, 0.28),
        "fg2": (0.77, 0.77, 0.77, 1) if dark else (0.36, 0.36, 0.36, 1),
        "accent_fg": (0, 0, 0, 1) if dark else (1, 1, 1, 1),
        "danger": _rgba("#ff99a4" if dark else "#c42b1c"),
    }


# --------------------------------------------------------------------------- art
class FingerprintArt(Gtk.DrawingArea):
    """Original vector fingerprint: nested looped ridges that fill with the accent colour."""

    RIDGES = 13

    def __init__(self, size=200):
        super().__init__()
        self.set_content_width(size)
        self.set_content_height(int(size * 1.2))
        self.progress = AnimatedValue(self, 0.0, speed=1.2)
        self.set_draw_func(self._draw)
        # deterministic ridge breaks so it looks like a real print
        self._breaks = [((i * 37) % 100) / 100.0 for i in range(self.RIDGES)]

    def _draw(self, _area, cr, w, h):
        c = _colors()
        sy = 1.22
        cx, cy = w / 2, h * 0.50
        unit = min(w / 2, h / 2 / sy) * 0.94
        cr.set_line_cap(1)  # ROUND
        cr.set_line_width(max(2.0, unit * 0.038))
        n = self.RIDGES
        segs = []
        for i in range(n):
            t = i / (n - 1)
            r = unit * (0.08 + 0.92 * t)
            # inner ridges form the U-shaped core, outer ones are almost closed ovals
            gap = 1.25 - 0.85 * t
            start = math.pi / 2 + gap
            end = math.pi / 2 - gap + 2 * math.pi
            br = self._breaks[i]
            if i % 3 == 1 and i > 1:
                mid = start + (end - start) * (0.2 + br * 0.6)
                segs += [(r, start, mid - 0.14), (r, mid + 0.08, end)]
            elif i % 4 == 2 and i > 3:
                mid = start + (end - start) * (0.55 + br * 0.3)
                segs += [(r, start, mid - 0.1), (r, mid + 0.12, end)]
            else:
                segs.append((r, start, end))

        def ridges(rgba):
            cr.set_source_rgba(*rgba)
            for r, a0, a1 in segs:
                cr.save()
                cr.translate(cx, cy)
                cr.scale(1.0, sy)
                cr.new_path()
                cr.arc(0, 0, r, a0, a1)
                cr.restore()
                cr.stroke()
        ridges(c["ridge"])
        # Like the reference: the print fills with the accent colour from the
        # bottom up as the sensor collects more of the finger.
        p = self.progress.value
        if p > 0:
            top, bottom = cy - unit * sy - 4, cy + unit * sy + 4
            y = bottom - (bottom - top) * min(1.0, p)
            cr.save()
            cr.rectangle(0, y, w, h - y)
            cr.clip()
            ridges(c["accent"])
            cr.restore()


class RingArt(Gtk.DrawingArea):
    """Circular progress ring with an optional face outline or camera picture inside."""

    def __init__(self, size=220, face=True):
        super().__init__()
        self.set_content_width(size)
        self.set_content_height(size)
        self.face = face
        self.progress = AnimatedValue(self, 0.0, speed=0.8)
        self.spin = 0.0
        self._spin_tick = 0
        self.set_draw_func(self._draw)

    def set_scanning(self, on):
        if on and not self._spin_tick:
            self._spin_tick = self.add_tick_callback(self._spin)
        elif not on and self._spin_tick:
            self.remove_tick_callback(self._spin_tick)
            self._spin_tick = 0

    def _spin(self, w, clock):
        self.spin = (clock.get_frame_time() / 1e6) * 1.6
        w.queue_draw()
        return GLib.SOURCE_CONTINUE

    def _draw(self, _a, cr, w, h):
        c = _colors()
        cx, cy = w / 2, h / 2
        r = min(w, h) / 2 - 6
        lw = 4
        cr.set_line_width(lw)
        cr.set_line_cap(1)
        cr.set_source_rgba(*c["track"])
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.stroke()
        p = self.progress.value
        if p > 0:
            cr.set_source_rgba(*c["accent"])
            cr.arc(cx, cy, r, -math.pi / 2, -math.pi / 2 + 2 * math.pi * p)
            cr.stroke()
        if self._spin_tick:
            cr.set_source_rgba(*c["accent"][:3], 0.55)
            a = self.spin
            cr.arc(cx, cy, r, a, a + 0.9)
            cr.stroke()
        if self.face:
            self._face(cr, cx, cy, r * 0.62, c)

    @staticmethod
    def _face(cr, cx, cy, s, c):
        cr.set_source_rgba(*c["fg2"])
        cr.set_line_width(max(2.5, s * 0.045))
        # head
        cr.save()
        cr.translate(cx, cy)
        cr.scale(0.82, 1.0)
        cr.arc(0, 0, s, 0, 2 * math.pi)
        cr.restore()
        cr.stroke()
        # eyes
        for dx in (-0.32, 0.32):
            cr.arc(cx + dx * s, cy - 0.18 * s, s * 0.07, 0, 2 * math.pi)
            cr.fill()
        # nose
        cr.move_to(cx, cy - 0.05 * s)
        cr.line_to(cx - 0.08 * s, cy + 0.18 * s)
        cr.line_to(cx + 0.02 * s, cy + 0.2 * s)
        cr.stroke()
        # smile
        cr.arc(cx, cy + 0.12 * s, s * 0.32, math.pi * 0.2, math.pi * 0.8)
        cr.stroke()
        # corner brackets (scan frame)
        cr.set_source_rgba(*c["accent"])
        L, o = s * 0.25, s * 1.18
        for sx in (-1, 1):
            for sy in (-1, 1):
                x, y = cx + sx * o * 0.9, cy + sy * o
                cr.move_to(x, y - sy * L)
                cr.line_to(x, y)
                cr.line_to(x - sx * L, y)
                cr.stroke()


class StatusArt(Gtk.DrawingArea):
    """Big check mark (done) or exclamation (error) in a circle."""

    def __init__(self, ok=True, size=120):
        super().__init__()
        self.ok = ok
        self.set_content_width(size)
        self.set_content_height(size)
        self.grow = AnimatedValue(self, 0.0, speed=3.0)
        self.set_draw_func(self._draw)
        GLib.idle_add(lambda: (self.grow.set(1.0), False)[1])

    def _draw(self, _a, cr, w, h):
        c = _colors()
        g = _ease(self.grow.value)
        r = (min(w, h) / 2 - 4) * (0.6 + 0.4 * g)
        cx, cy = w / 2, h / 2
        cr.set_source_rgba(*(c["accent"] if self.ok else c["danger"]))
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.fill()
        cr.set_source_rgba(*c["accent_fg"])
        cr.set_line_width(r * 0.13)
        cr.set_line_cap(1)
        cr.set_line_join(1)
        if self.ok:
            cr.move_to(cx - r * 0.42, cy + r * 0.02)
            cr.line_to(cx - r * 0.12, cy + r * 0.32)
            cr.line_to(cx + r * 0.45, cy - r * 0.3)
            cr.stroke()
        else:
            cr.move_to(cx, cy - r * 0.45)
            cr.line_to(cx, cy + r * 0.12)
            cr.stroke()
            cr.arc(cx, cy + r * 0.38, r * 0.08, 0, 2 * math.pi)
            cr.fill()


class CameraView(Gtk.Overlay):
    """Live camera preview cropped to a circle, with a progress ring on top."""

    def __init__(self, device, size=220):
        super().__init__()
        self.set_size_request(size, size)
        self.set_halign(Gtk.Align.CENTER)
        self.pipeline = None
        self.ring = RingArt(size, face=False)
        holder = Gtk.Box()
        holder.add_css_class("hello-camera")
        holder.set_overflow(Gtk.Overflow.HIDDEN)
        holder.set_size_request(size - 24, size - 24)
        holder.set_halign(Gtk.Align.CENTER)
        holder.set_valign(Gtk.Align.CENTER)
        self.picture = Gtk.Picture()
        self.picture.set_content_fit(Gtk.ContentFit.COVER)
        self.picture.set_hexpand(True)
        holder.append(self.picture)
        self.set_child(holder)
        self.add_overlay(self.ring)
        self.ok = self._start(device)

    def _start(self, device):
        if not device or util.READ_ONLY:
            return False
        try:
            import gi
            gi.require_version("Gst", "1.0")
            from gi.repository import Gst
            Gst.init(None)
            pipe = Gst.parse_launch(f'v4l2src device="{device}" ! videoconvert ! videoflip method=horizontal-flip '
                                    "! gtk4paintablesink name=sink")
            sink = pipe.get_by_name("sink")
            self.picture.set_paintable(sink.get_property("paintable"))
            if pipe.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
                pipe.set_state(Gst.State.NULL)
                return False
            self.pipeline = pipe
            self._gst = Gst
            return True
        except Exception as e:  # noqa: BLE001 - any GStreamer problem -> illustration
            util.log("camera preview failed", e)
            return False

    def handover(self, device):
        """Howdy needs the camera now: keep showing the face, live from `device`
        (another camera of the same module) when possible, else the last frame."""
        frame = None
        try:
            paintable = self.picture.get_paintable()
            frame = paintable.get_current_image() if paintable is not None else None
        except Exception:  # noqa: BLE001
            frame = None
        self.stop()
        if device and self._start(device):
            return
        if frame is not None:
            self.picture.set_paintable(frame)

    def stop(self):
        if self.pipeline is not None:
            self.pipeline.set_state(self._gst.State.NULL)
            self.pipeline = None


# --------------------------------------------------------------------------- wizard
class HelloWizard(Gtk.Box):
    """kind: 'face' | 'finger'. on_finish(changed: bool) is called when it closes."""

    def __init__(self, kind, on_finish=None, improve=False, demo_state=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.kind = kind
        self.improve = improve
        self.on_finish = on_finish
        self.changed = False
        self.device = None
        self.camera = None
        self.finger = None
        self.stage = 0
        self.closed = False
        self.add_css_class("hello-dialog")
        self.set_size_request(520, 600)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)

        bar = Gtk.Box()
        bar.add_css_class("hello-titlebar")
        bar.append(icon(util.app_icon_name(), 16))
        bar.append(label(_("Fenestra Hello setup"), "hello-caption"))
        bar.append(Gtk.Box(hexpand=True))
        x = Gtk.Button()
        x.set_child(icon("fs-dismiss-symbolic", 14))
        x.add_css_class("hello-close")
        x.connect("clicked", lambda *_: self.close())
        bar.append(x)
        self.append(bar)

        self.stack = Gtk.Stack()
        self.stack.set_vexpand(True)
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT)
        self.stack.set_transition_duration(ANIM_MS)
        self.stack.set_interpolate_size(False)
        self.append(self.stack)
        self._n = 0

        if demo_state:
            self.stack.set_transition_duration(0)
            self.demo(demo_state)
        else:
            self.page_welcome()

    # ------------------------------------------------------------------ page builder
    def _page(self, title, body=None, art=None, status=None, buttons=()):
        pg = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        pg.add_css_class("hello-page")
        pg.append(label(title, "hello-title", wrap=True))
        self.body = None
        if body:
            b = label(body, "hello-body", wrap=True)
            b.set_max_width_chars(56)
            pg.append(b)
            self.body = b
        mid = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True, valign=Gtk.Align.CENTER, spacing=18)
        if art is not None:
            art.set_halign(Gtk.Align.CENTER)
            mid.append(art)
        self.status = label(status or "", "hello-status", wrap=True, xalign=0.5)
        self.status.set_visible(bool(status))
        mid.append(self.status)
        pg.append(mid)
        foot = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        foot.add_css_class("hello-footer")
        for text, cb, accent in buttons:
            btn = button(text, cb, accent=accent)
            btn.set_size_request(120, -1)
            foot.append(btn)
        pg.append(foot)
        self._n += 1
        name = f"p{self._n}"
        old = self.stack.get_visible_child()
        self.stack.add_named(pg, name)
        self.stack.set_visible_child_name(name)
        if old is not None:
            GLib.timeout_add(ANIM_MS + 50, lambda: (old.get_parent() and self.stack.remove(old), False)[1])
        return pg

    def set_status(self, text):
        self.status.set_label(text)
        self.status.set_visible(bool(text))

    # ------------------------------------------------------------------ common pages
    def page_welcome(self):
        if self.kind == "face":
            body = _("Use your face to unlock your device, sign in to apps and confirm it's you — "
                     "fast and secure. Your face data stays on this device.")
        else:
            body = _("Use your fingerprint to unlock your device, sign in to apps and confirm it's you — "
                     "fast and secure. Your fingerprint data stays on this device.")
        art = RingArt(200, face=True) if self.kind == "face" else FingerprintArt(170)
        self._page(_("Welcome to Fenestra Hello"), body, art, None,
                   [(_("Get started"), self.start, True), (_("Cancel"), self.close, False)])

    def page_done(self):
        if self.kind == "face":
            body = _("You can use your face to unlock your device the next time you sign in.")
            btns = [(_("Close"), self.close, True)]
        else:
            body = _("You can use your fingerprint to unlock your device the next time you sign in.")
            btns = [(_("Add another finger"), self.add_another, False), (_("Close"), self.close, True)]
        self._page(_("All set!"), body, StatusArt(True), None, btns)

    def page_error(self, text):
        self._page(_("Something went wrong"), text, StatusArt(False), None,
                   [(_("Try again"), self.start, True), (_("Cancel"), self.close, False)])

    def start(self):
        if self.kind == "face":
            self.face_preview()
        else:
            self.finger_start()

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.camera is not None:
            self.camera.stop()
        if self.device is not None:
            self.device.enroll_stop()
            self.device.release()
        win = self.get_root()
        if win is not None and hasattr(win, "close_dialog"):
            win.close_dialog(self)
        if self.on_finish:
            self.on_finish(self.changed)

    # ------------------------------------------------------------------ face (Howdy)
    def face_preview(self):
        dev = hello.howdy_device()
        self.camera = CameraView(dev, 230) if dev else None
        art = self.camera if (self.camera and self.camera.ok) else RingArt(230, face=True)
        self._page(_("Make sure you're looking directly at your camera"),
                   _("Position your face in the centre of the frame and keep looking at the camera."),
                   art, _("Getting your camera ready…"),
                   [(_("Cancel"), self.close, False)])
        self.face_art = art
        GLib.timeout_add(1600 if self.camera and self.camera.ok else 400, self._face_capture)

    def _face_capture(self):
        if self.closed:
            return False
        scan_body = _("Keep looking at the camera until the scan is finished. You may be asked for an "
                      "administrator password first.")
        cam = self.camera if (self.camera is not None and self.camera.ok) else None
        if cam is not None:
            # Howdy takes the IR camera from here on. The face stays on screen
            # (same page, same ring), like the reference.
            cam.handover(hello.preview_device(hello.howdy_device()))
            ring = cam.ring
            if self.body is not None:
                self.body.set_label(scan_body)
            self.set_status(_("Scanning your face…"))
        else:
            ring = RingArt(230, face=True)
            self._page(_("Make sure you're looking directly at your camera"), scan_body,
                       ring, _("Scanning your face…"), [(_("Cancel"), self.close, False)])
        ring.set_scanning(True)
        ring.progress.speed = 0.12
        ring.progress.set(0.92)  # creeps forward while Howdy works

        def done(ok, msg):
            ring.set_scanning(False)
            if self.camera is not None:
                self.camera.stop()
            if self.closed:
                return
            if ok:
                self.changed = True
                ring.progress.speed = 2.0
                ring.progress.set(1.0)
                GLib.timeout_add(450, lambda: (self.page_done(), False)[1])
            else:
                self.page_error(hello.howdy_error_text(msg))
        hello.howdy_add(done, label="Fenestra" + (" +" if self.improve else ""))
        return False

    # ------------------------------------------------------------------ fingerprint (fprintd)
    def finger_start(self):
        self._page(_("Touch the fingerprint sensor"), _("Getting your fingerprint sensor ready…"),
                   FingerprintArt(190), None, [(_("Cancel"), self.close, False)])
        hello.fingerprint_device(self._got_device)

    def _got_device(self, dev):
        if self.closed:
            return
        if dev is None:
            self.page_error(_("No fingerprint sensor was found."))
            return
        self.device = dev

        def listed(fingers):
            self.finger = hello.next_finger(fingers)
            if self.finger is None:
                self.page_error(_("All fingers are already enrolled."))
                return
            dev.claim(claimed)

        def claimed(ok, err):
            if not ok:
                self.page_error(_("Couldn't access the fingerprint sensor. It might be in use by another app.")
                                if not util.READ_ONLY else _("This action is disabled in read-only mode"))
                return
            self.stage = 0
            self.finger_page(edges=False, progress=0.0)
            dev.enroll(self.finger, self._enroll_status, started)

        def started(ok, err):
            if not ok:
                dev.release()
                self.page_error(_("We couldn't start fingerprint enrollment."))
        dev.list_fingers(listed)

    def finger_page(self, edges, progress, status=None):
        self.edges = edges
        self.fp_art = FingerprintArt(190)
        self.fp_art.progress.set(progress, instant=True)
        if edges:
            title = _("Now touch the edges of your finger")
            body = _("Touch the sensor with the edges of your finger so we can capture more of it.")
        else:
            title = _("Touch the fingerprint sensor")
            body = _("Lift and rest your finger on the sensor repeatedly until we tell you to stop.")
        self._page(title, body, self.fp_art, status or _("Touch the sensor"), [(_("Cancel"), self.close, False)])

    STATUS = {
        "enroll-stage-passed": N_("Lift your finger and touch the sensor again"),
        "enroll-retry-scan": N_("Try again"),
        "enroll-swipe-too-short": N_("Swipe too short — try again"),
        "enroll-finger-not-centered": N_("Try again — keep your finger centered on the sensor"),
        "enroll-remove-and-retry": N_("Remove your finger and try again"),
        "enroll-duplicate": N_("This finger is already enrolled — try another finger"),
    }

    def _enroll_status(self, result, done):
        if self.closed:
            return
        stages = max(1, self.device.stages if self.device else 5)
        if result == "enroll-stage-passed":
            self.stage += 1
            p = min(1.0, self.stage / stages)
            if not self.edges and p >= 0.6:
                self.finger_page(edges=True, progress=self.fp_art.progress.value,
                                 status=_("Touch the sensor with the edges of your finger"))
            self.fp_art.progress.set(p)
            if self.edges and p >= 0.6:
                self.set_status(_("Touch the sensor with the edges of your finger"))
            else:
                self.set_status(_(self.STATUS[result]))
        elif result == "enroll-completed":
            self.fp_art.progress.set(1.0)
            self.changed = True
            if self.device:
                self.device.release()
                self.device = None
            GLib.timeout_add(500, lambda: (self.page_done(), False)[1])
        elif result in self.STATUS:
            self.set_status(_(self.STATUS[result]))
        elif result == "enroll-data-full":
            self.device.release()
            self.device = None
            self.page_error(_("There's no room left on the fingerprint sensor. Remove a fingerprint and try again."))
        elif done:
            if self.device:
                self.device.release()
                self.device = None
            self.page_error(_("We couldn't capture your fingerprint. Please try again."))

    def add_another(self):
        self.finger_start()

    # ------------------------------------------------------------------ demo states (screenshots)
    def demo(self, state):
        if state == "welcome":
            self.page_welcome()
        elif state == "welcome-finger":
            self.kind = "finger"
            self.page_welcome()
        elif state in ("face-1", "face-2"):
            self.kind = "face"
            ring = RingArt(230, face=True)
            if state == "face-1":
                self._page(_("Make sure you're looking directly at your camera"),
                           _("Position your face in the centre of the frame and keep looking at the camera."),
                           ring, _("Getting your camera ready…"), [(_("Cancel"), self.close, False)])
            else:
                self._page(_("Make sure you're looking directly at your camera"),
                           _("Keep looking at the camera until the scan is finished. You may be asked for an "
                             "administrator password first."),
                           ring, _("Scanning your face…"), [(_("Cancel"), self.close, False)])
                ring.progress.set(0.62, instant=True)
        elif state == "face-done":
            self.kind = "face"
            self.page_done()
        elif state == "finger-1":
            self.kind = "finger"
            self.finger_page(False, 0.0, _("Touch the sensor"))
        elif state == "finger-2":
            self.kind = "finger"
            self.finger_page(False, 0.36, _(self.STATUS["enroll-stage-passed"]))
        elif state == "finger-edges":
            self.kind = "finger"
            self.finger_page(True, 0.73, _("Touch the sensor with the edges of your finger"))
        elif state == "finger-done":
            self.kind = "finger"
            self.page_done()
        else:
            self.page_error(_("We couldn't capture your fingerprint. Please try again."))
