"""System landing page."""
from __future__ import annotations

from ..i18n import N_, _
from .base import Page, register
from .common import device_hero


@register
class SystemPage(Page):
    id = "system"
    title = "System"
    keywords = "computer device pc"

    ROWS = [
        ("display", N_("Display"), N_("Monitors, brightness, night light, display profile"), "fs-desktop-symbolic"),
        ("sound", N_("Sound"), N_("Volume levels, output, input, sound devices"), "fs-speaker-2-symbolic"),
        ("notifications", N_("Notifications"), N_("Alerts from apps and system, do not disturb"), "fs-alert-symbolic"),
        ("focus", N_("Focus"), N_("Reduce distractions"), "fs-timer-symbolic"),
        ("power", N_("Power & battery"), N_("Sleep, battery usage, battery saver"), "fs-battery-charge-symbolic"),
        ("storage", N_("Storage"), N_("Storage space, drives, configuration rules"), "fs-hard-drive-symbolic"),
        ("nearby", N_("Nearby sharing"), N_("Discoverability, received files location"), "fs-share-symbolic"),
        ("multitasking", N_("Multitasking"), N_("Snap windows, desktops, task switching"), "fs-window-multiple-symbolic"),
        ("troubleshoot", N_("Troubleshoot"), N_("Recommended troubleshooters, preferences, history"), "fs-wrench-symbolic"),
        ("recovery", N_("Recovery"), N_("Reset, advanced startup, go back"), "fs-arrow-counterclockwise-symbolic"),
        ("projecting", N_("Projecting to this PC"), N_("Permissions, pairing PIN, discoverability"), "fs-phone-desktop-symbolic"),
        ("clipboard", N_("Clipboard"), N_("Cut and copy history, sync, clear"), "fs-clipboard-symbolic"),
        ("about", N_("About"), N_("Device specifications, rename PC, Fenestra specifications"), "fs-info-symbolic"),
    ]

    def build(self, box):
        box.append(device_hero(self))
        g = self.group()
        for pid, t, sub, ic in self.ROWS:
            self.nav_row(g, pid, _(t), _(sub), ic)
