"""Title-bar tab strip (Windows 11 Notepad tabs: rounded active tab joined to the menu bar)."""
from __future__ import annotations

import math

from gi.repository import Gdk, GLib, Graphene, Gtk, Pango

from . import theme
from .i18n import _
from .widgets import icon

TAB_MAX = 240
TAB_MIN = 96
FOOT = 8          # radius of the curves joining the active tab to the menu bar
RADIUS = 8


class Tab(Gtk.Box):
    __gtype_name__ = "FenestraNotepadTab"

    def __init__(self, strip, doc):
        super().__init__()
        self.strip = strip
        self.doc = doc
        self.add_css_class("tab")
        self.set_valign(Gtk.Align.END)
        self.set_hexpand(False)
        self.title = Gtk.Inscription()
        self.title.add_css_class("tab-title")
        self.title.set_text_overflow(Gtk.InscriptionOverflow.CLIP)
        self.title.set_hexpand(True)
        self.title.set_min_chars(1)
        self.title.set_nat_chars(10)
        self.title.set_yalign(0.5)
        self.title.set_min_lines(1)
        self.title.set_nat_lines(1)
        if hasattr(Pango.WrapMode, "NONE"):
            self.title.set_wrap_mode(Pango.WrapMode.NONE)
        self.append(self.title)
        self.close = Gtk.Button()
        self.close.add_css_class("tab-close")
        self.close.set_focus_on_click(False)
        self.close.set_valign(Gtk.Align.CENTER)
        self.close_stack = Gtk.Stack()
        self.close_stack.add_named(icon("np-dismiss-symbolic", 12), "x")
        dot = Gtk.Box(css_classes=["tab-dot"], halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        self.close_stack.add_named(dot, "dot")
        self.close.set_child(self.close_stack)
        self.close.set_tooltip_text(_("Close tab"))
        self.close.connect("clicked", lambda *_: strip.on_close(self.doc))
        self.append(self.close)
        click = Gtk.GestureClick(button=0)
        click.connect("pressed", self._pressed)
        self.add_controller(click)
        motion = Gtk.EventControllerMotion()
        motion.connect("enter", lambda *_: self._hover(True))
        motion.connect("leave", lambda *_: self._hover(False))
        self.add_controller(motion)
        self.hovered = False
        self.refresh()

    def _pressed(self, g, n, x, y):
        b = g.get_current_button()
        if b == 2:
            g.set_state(Gtk.EventSequenceState.CLAIMED)
            self.strip.on_close(self.doc)
        elif b == 1:
            self.strip.on_select(self.doc)

    def _hover(self, on):
        self.hovered = on
        self.refresh_close()
        if on:
            self.add_css_class("hover")
        else:
            self.remove_css_class("hover")
        self.strip.queue_draw_tabs()

    def refresh_close(self):
        dirty = self.doc.modified or (self.doc.path is None and not self.doc.is_empty() and False)
        self.close_stack.set_visible_child_name("dot" if dirty and not self.hovered else "x")
        self.close.set_opacity(1.0)

    def refresh(self):
        t = self.doc.title
        self.title.set_text(t)
        self.set_tooltip_text(self.doc.path or t)
        layout = self.title.create_pango_layout(t)
        w = layout.get_pixel_size()[0]
        self.set_size_request(int(max(TAB_MIN, min(TAB_MAX, w + 9 + 40))), -1)
        self.refresh_close()

    def set_active(self, on):
        if on:
            self.add_css_class("active")
        else:
            self.remove_css_class("active")

    def do_snapshot(self, snap):
        th = theme.get()
        w, h = self.get_width(), self.get_height()
        active = self.has_css_class("active")
        if active:
            c = th.c["layer"]
            b = th.c["tab-border"]
            r, f = RADIUS, FOOT
            cr = snap.append_cairo(Graphene.Rect().init(-f, 0, w + 2 * f, h + 1))
            # fill with feet
            cr.move_to(-f, h)
            cr.arc_negative(-f, h - f, f, math.pi / 2, 0)
            cr.line_to(0, r)
            cr.arc(r, r, r, math.pi, 1.5 * math.pi)
            cr.line_to(w - r, 0)
            cr.arc(w - r, r, r, 1.5 * math.pi, 2 * math.pi)
            cr.line_to(w, h - f)
            cr.arc_negative(w + f, h - f, f, math.pi, math.pi / 2)
            cr.close_path()
            Gdk.cairo_set_source_rgba(cr, c)
            cr.fill()
            # outline (not along the bottom)
            cr.set_line_width(1.0)
            cr.move_to(-f, h - 0.5)
            cr.arc_negative(-f, h - f, f - 0.5, math.pi / 2, 0)
            cr.line_to(0.5, r)
            cr.arc(r, r, r - 0.5, math.pi, 1.5 * math.pi)
            cr.line_to(w - r, 0.5)
            cr.arc(w - r, r, r - 0.5, 1.5 * math.pi, 2 * math.pi)
            cr.line_to(w - 0.5, h - f)
            cr.arc_negative(w + f, h - f, f - 0.5, math.pi, math.pi / 2)
            Gdk.cairo_set_source_rgba(cr, b)
            cr.stroke()
        elif self.hovered:
            c = th.c["tab-hover"]
            rr = Gsk_rounded(0, 3, w, h - 6, 6)
            snap.push_rounded_clip(rr)
            snap.append_color(c, Graphene.Rect().init(0, 3, w, h - 6))
            snap.pop()
        else:
            # separator after an inactive tab (unless the next one is active/hovered)
            if self.strip.separator_after(self):
                snap.append_color(th.c["tab-sep"], Graphene.Rect().init(w - 1, 8, 1, h - 16))
        Gtk.Box.do_snapshot(self, snap)


def Gsk_rounded(x, y, w, h, r):
    from gi.repository import Gsk
    rr = Gsk.RoundedRect()
    rect = Graphene.Rect().init(x, y, w, h)
    size = Graphene.Size().init(r, r)
    rr.init(rect, size, size, size, size)
    return rr


class TabStrip(Gtk.Box):
    """[tabs (scrollable)] [+] ; the window places it between the app icon and the caption buttons."""
    __gtype_name__ = "FenestraNotepadTabStrip"

    def __init__(self, on_select, on_close, on_new):
        super().__init__()
        self.add_css_class("tab-strip")
        self.on_select = on_select
        self.on_close = on_close
        self.tabs = []
        self.active = None
        self.scroller = Gtk.ScrolledWindow()
        self.scroller.add_css_class("tab-scroller")
        self.scroller.set_policy(Gtk.PolicyType.EXTERNAL, Gtk.PolicyType.NEVER)
        self.scroller.set_propagate_natural_width(True)
        self.scroller.set_overflow(Gtk.Overflow.VISIBLE)
        self.box = Gtk.Box()
        self.box.add_css_class("tabs")
        self.scroller.set_child(self.box)
        self.append(self.scroller)
        sc = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.BOTH_AXES)
        sc.connect("scroll", self._scroll)
        self.scroller.add_controller(sc)
        self.plus = Gtk.Button()
        self.plus.add_css_class("tab-new")
        self.plus.set_child(icon("np-add-symbolic", 16))
        self.plus.set_tooltip_text(_("Add new tab"))
        self.plus.set_valign(Gtk.Align.END)
        self.plus.set_focus_on_click(False)
        self.plus.connect("clicked", lambda *_: on_new())
        self.append(self.plus)

    def _scroll(self, _c, dx, dy):
        adj = self.scroller.get_hadjustment()
        adj.set_value(adj.get_value() + (dx + dy) * 40)
        return True

    def add(self, doc, position=None):
        t = Tab(self, doc)
        if position is None or position >= len(self.tabs):
            self.tabs.append(t)
            self.box.append(t)
        else:
            sib = self.tabs[position - 1] if position > 0 else None
            self.tabs.insert(position, t)
            self.box.insert_child_after(t, sib)
        return t

    def remove(self, doc):
        t = self.tab_for(doc)
        if t is not None:
            self.tabs.remove(t)
            self.box.remove(t)
            if self.active is t:
                self.active = None
        self.queue_draw_tabs()

    def tab_for(self, doc):
        return next((t for t in self.tabs if t.doc is doc), None)

    def set_active(self, doc):
        for t in self.tabs:
            t.set_active(t.doc is doc)
        self.active = self.tab_for(doc)
        self.queue_draw_tabs()
        if self.active is not None:
            GLib.idle_add(self._reveal, self.active, priority=GLib.PRIORITY_DEFAULT)

    def _reveal(self, t):
        if t.get_parent() is None:
            return False
        ok, pt = t.compute_point(self.box, Graphene.Point().init(0, 0))
        if not ok:
            return False
        adj = self.scroller.get_hadjustment()
        x, w = pt.x, t.get_width()
        if x < adj.get_value():
            adj.set_value(x - 8)
        elif x + w > adj.get_value() + adj.get_page_size():
            adj.set_value(x + w + 8 - adj.get_page_size())
        return False

    def separator_after(self, tab):
        i = self.tabs.index(tab) if tab in self.tabs else -1
        if i < 0 or i == len(self.tabs) - 1:
            return False
        nxt = self.tabs[i + 1]
        return not (nxt.has_css_class("active") or nxt.hovered or tab.hovered)

    def queue_draw_tabs(self):
        for t in self.tabs:
            t.queue_draw()

    def refresh(self, doc):
        t = self.tab_for(doc)
        if t is not None:
            t.refresh()


__all__ = ["TabStrip", "Pango"]
