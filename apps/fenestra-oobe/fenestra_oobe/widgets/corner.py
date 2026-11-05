"""Accessibility button shown under the card's bottom-right corner."""

from gi.repository import Gtk

from ..i18n import _
from .controls import ToggleSwitch
from .illustration import SvgIcon


class CornerControls(Gtk.Box):
    __gtype_name__ = "FenestraCornerControls"

    def __init__(self, window, system_backend):
        super().__init__(css_classes=["corner-controls"])
        self.window = window
        self.system = system_backend
        self.a11y_button = Gtk.MenuButton(css_classes=["corner-button"], direction=Gtk.ArrowType.UP,
                                          tooltip_text=_("Accessibility"))
        self.a11y_button.set_child(SvgIcon("accessibility", 20))
        self.a11y_button.update_property([Gtk.AccessibleProperty.LABEL], [_("Accessibility")])
        self.a11y_button.set_popover(self._build_a11y_popover())
        self.append(self.a11y_button)

    def _build_a11y_popover(self):
        pop = Gtk.Popover(css_classes=["oobe-popover"], has_arrow=False)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.append(Gtk.Label(label=_("Accessibility"), xalign=0, css_classes=["popover-title"]))
        for key, label in (
            ("large-text", _("Text size")),
            ("high-contrast", _("Contrast themes")),
            ("screen-reader", _("Narrator")),
            ("screen-keyboard", _("On-screen keyboard")),
        ):
            row = Gtk.Box(spacing=24, css_classes=["popover-row"])
            row.append(Gtk.Label(label=label, xalign=0, hexpand=True))
            sw = ToggleSwitch(active=self.system.get_a11y(key), valign=Gtk.Align.CENTER)
            sw.update_property([Gtk.AccessibleProperty.LABEL], [label])
            sw.connect("notify::active", self._on_a11y, key)
            row.append(sw)
            box.append(row)
        # Volume lives here too (the reference has no separate volume button).
        vol_row = Gtk.Box(spacing=12, css_classes=["popover-row"])
        vol_row.append(Gtk.Label(label=_("Volume"), xalign=0))
        vol = self.system.get_volume()
        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        scale.set_hexpand(True)
        scale.set_size_request(160, -1)
        scale.set_value(round((vol if vol is not None else 0.5) * 100))
        scale.set_sensitive(vol is not None)
        scale.update_property([Gtk.AccessibleProperty.LABEL], [_("Volume")])
        scale.connect("value-changed", lambda s: self.system.set_volume(s.get_value() / 100))
        vol_row.append(scale)
        box.append(vol_row)
        pop.set_child(box)
        return pop

    def _on_a11y(self, sw, _pspec, key):
        value = sw.get_active()
        self.system.set_a11y(key, value)
        # Apply inside the OOBE immediately (also in demo mode).
        if key == "large-text":
            settings = Gtk.Settings.get_default()
            settings.reset_property("gtk-xft-dpi")
            if value:
                base = settings.props.gtk_xft_dpi
                base = base if base > 0 else 96 * 1024
                settings.props.gtk_xft_dpi = int(base * 1.25)
        elif key == "high-contrast":
            if value:
                self.window.add_css_class("high-contrast")
            else:
                self.window.remove_css_class("high-contrast")
