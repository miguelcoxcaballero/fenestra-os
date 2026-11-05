"""Base class for the pages shown on the right side of the OOBE card."""

from gi.repository import Gtk


class Page(Gtk.Box):
    page_id = ""
    illustration = "region"
    #: branch pages are only reached through ``ctx.goto()``, never by "next"
    branch = False
    can_go_back = True
    #: transient pages are not recorded in the back history
    transient = False

    def __init__(self, ctx, title: str, subtitle: str = ""):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, css_classes=["page"])
        self.ctx = ctx
        self.state = ctx.state
        self.backends = ctx.backends
        self.title_label = Gtk.Label(label=title, xalign=0, wrap=True, css_classes=["page-title"])
        self.append(self.title_label)
        self.subtitle_label = Gtk.Label(label=subtitle, xalign=0, wrap=True, css_classes=["page-subtitle"])
        self.subtitle_label.set_visible(bool(subtitle))
        if subtitle:
            self.add_css_class("has-subtitle")
        self.append(self.subtitle_label)
        self.body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, vexpand=True, css_classes=["page-body"])
        self.append(self.body)
        # Footer configuration (read by the window).
        self.primary_label = None
        self.secondary_label = None
        self.link_label = None
        self.primary_sensitive = True
        self.busy = False

    def make_spinner_layout(self, text: str):
        """Reference "progress" layout: no title, a 64 px ring centred in the
        right half with a 20 px caption under it."""
        from ..widgets.controls import RingSpinner
        self.add_css_class("spinner-page")
        self.title_label.set_visible(False)
        self.subtitle_label.set_visible(False)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER,
                      halign=Gtk.Align.CENTER, vexpand=True, css_classes=["spinner-box"])
        self.spinner = RingSpinner(64, 5)
        box.append(self.spinner)
        self.spinner_label = Gtk.Label(label=text, css_classes=["spinner-caption"],
                                       justify=Gtk.Justification.CENTER, wrap=True)
        box.append(self.spinner_label)
        self.body.append(box)
        return box

    # -- hooks -----------------------------------------------------------
    def should_skip(self) -> bool:
        return False

    def on_enter(self, direction: int):
        pass

    def on_leave(self):
        pass

    def on_primary(self):
        self.ctx.next()

    def on_secondary(self):
        self.ctx.next()

    def on_link(self):
        pass

    def focus_widget(self):
        return None

    # -- helpers ---------------------------------------------------------
    def set_primary_sensitive(self, sensitive: bool):
        self.primary_sensitive = sensitive
        self.ctx.update_footer(self)

    def set_busy(self, busy: bool):
        self.busy = busy
        self.ctx.update_footer(self)
