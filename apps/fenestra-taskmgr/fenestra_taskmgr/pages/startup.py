"""Startup apps: XDG autostart entries (~/.config/autostart + /etc/xdg/autostart)."""
from __future__ import annotations

import os
import threading

from gi.repository import Gio, GLib, Gtk

from .. import util
from ..i18n import _
from ..widgets.common import Menu, ToolButton, label, separator
from ..widgets.table import Column, Row, Table
from .base import Page, scrolled
from .processes import run_task_dialog


def user_autostart():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "autostart")


def system_autostart_dirs():
    dirs = (os.environ.get("XDG_CONFIG_DIRS") or "/etc/xdg").split(":")
    return [os.path.join(d, "autostart") for d in dirs if d]


def read_entries():
    """file name -> dict(name, publisher, enabled, icon, path, user_path)."""
    out = {}
    for d in reversed(system_autostart_dirs()):
        _scan(d, out, False)
    _scan(user_autostart(), out, True)
    return out


def _scan(d, out, is_user):
    try:
        names = os.listdir(d)
    except OSError:
        return
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "GNOME").split(":")
    for n in names:
        if not n.endswith(".desktop"):
            continue
        kf = GLib.KeyFile()
        path = os.path.join(d, n)
        try:
            kf.load_from_file(path, GLib.KeyFileFlags.NONE)
        except GLib.Error:
            continue

        def get(key, default=""):
            try:
                return kf.get_locale_string("Desktop Entry", key, None)
            except GLib.Error:
                return default

        def getb(key):
            try:
                return kf.get_boolean("Desktop Entry", key)
            except GLib.Error:
                return False
        only = [x for x in get("OnlyShowIn").split(";") if x]
        notin = [x for x in get("NotShowIn").split(";") if x]
        if only and not set(only) & set(desktop):
            out.pop(n, None)
            continue
        if notin and set(notin) & set(desktop):
            out.pop(n, None)
            continue
        if getb("NoDisplay") and not is_user and n not in out:
            # system helpers that are not meant to be listed (keep Windows-like short list)
            pass
        enabled = not getb("Hidden") and getb_default(kf, "X-GNOME-Autostart-enabled", True)
        out[n] = {"file": n, "name": get("Name") or n[:-8], "publisher": get("X-Publisher")
                  or get("X-GNOME-Bugzilla-Product") and "The GNOME Project" or "",
                  "enabled": enabled, "icon": get("Icon") or "tm-process", "path": path,
                  "user": is_user, "comment": get("Comment"), "exec": get("Exec")}


def getb_default(kf, key, default):
    try:
        return kf.get_boolean("Desktop Entry", key)
    except GLib.Error:
        return default


def set_enabled(entry, on):
    """Write a user copy with Hidden=true/false (the XDG way to disable an autostart entry)."""
    if util.DEMO or util.READ_ONLY:
        return
    if os.environ.get("FENESTRA_TASKMGR_TEST_ALLOW_PIDS") is not None:
        print("TEST-SANDBOX startup", entry["file"], on, flush=True)
        return
    dst = os.path.join(user_autostart(), entry["file"])
    kf = GLib.KeyFile()
    try:
        kf.load_from_file(entry["path"], GLib.KeyFileFlags.KEEP_COMMENTS | GLib.KeyFileFlags.KEEP_TRANSLATIONS)
    except GLib.Error:
        return
    kf.set_boolean("Desktop Entry", "Hidden", not on)
    if on:
        try:
            kf.set_boolean("Desktop Entry", "X-GNOME-Autostart-enabled", True)
        except GLib.Error:
            pass
    os.makedirs(user_autostart(), exist_ok=True)
    kf.save_to_file(dst)


class StartupPage(Page):
    pid = "startup"
    title = _("Startup apps")

    def __init__(self, win):
        super().__init__(win)
        top = Gtk.Box()
        top.add_css_class("bios-row")
        top.append(Gtk.Box(hexpand=True))
        self.bios = label("", "bios-time")
        top.append(self.bios)
        self.append(top)
        self.table = Table([
            Column("name", _("Name"), 214), Column("publisher", _("Publisher"), 150),
            Column("status", _("Status"), 100), Column("impact", _("Startup impact"), 100),
        ], header_h=34, two_line=False)
        self.table.connect("sort-changed", lambda *_: self.refresh())
        self.table.connect("selection-changed", lambda *_: self._sync())
        self.table.connect("context-menu", self._context)
        self.append(scrolled(self.table))
        self.run_btn = ToolButton("tm-run-symbolic", _("Run new task"), lambda: run_task_dialog(self.win))
        self.en_btn = ToolButton("tm-check-symbolic", _("Enable"), lambda: self._set(True))
        self.dis_btn = ToolButton("tm-end-symbolic", _("Disable"), lambda: self._set(False))
        self.prop_btn = ToolButton("tm-properties-symbolic", _("Properties"), self.properties)
        self.entries = {}
        self.reload()
        self._bios()
        self._sync()

    def tools(self):
        return [self.run_btn, separator(), self.en_btn, self.dis_btn, self.prop_btn]

    def reload(self):
        if util.DEMO:
            from ..demo import STARTUP
            self.entries = {f"{n}.desktop": {"file": f"{n}.desktop", "name": n, "publisher": pub, "enabled": en,
                                             "icon": ic, "path": "", "user": False, "comment": "", "exec": ""}
                            for n, pub, en, ic in STARTUP}
        else:
            self.entries = read_entries()
        self.refresh()

    def _bios(self):
        if util.DEMO:
            self.bios.set_markup(_("Last BIOS time:") + "  8.9 " + _("seconds"))
            return

        def got(bus, res):
            try:
                v = bus.call_finish(res).unpack()[0]
            except GLib.Error:
                return
            fw = v.get("FirmwareTimestampMonotonic", 0)
            ld = v.get("LoaderTimestampMonotonic", 0)
            if fw and fw > ld:
                secs = (fw - ld) / 1e6
                self.bios.set_text(_("Last BIOS time:") + f"  {secs:.1f} " + _("seconds"))
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            bus.call("org.freedesktop.systemd1", "/org/freedesktop/systemd1",
                     "org.freedesktop.DBus.Properties", "GetAll",
                     GLib.Variant("(s)", ("org.freedesktop.systemd1.Manager",)), None,
                     Gio.DBusCallFlags.NONE, 2000, None, got)
        except GLib.Error:
            pass

    def set_filter(self, text):
        super().set_filter(text)
        self.refresh()

    def shown(self):
        if not util.DEMO:
            self.reload()

    def refresh(self):
        items = [e for e in self.entries.values()
                 if not self.filter or self.filter in (e["name"] + e["publisher"]).lower()]
        k, desc = self.table.sort_key, self.table.sort_desc
        keyf = {"name": lambda e: e["name"].casefold(), "publisher": lambda e: e["publisher"].casefold(),
                "status": lambda e: e["enabled"], "impact": lambda e: e["enabled"]}[k]
        items.sort(key=keyf, reverse=desc)
        rows = [Row(e["file"], cells={"name": e["name"], "publisher": e["publisher"],
                                      "status": _("Enabled") if e["enabled"] else _("Disabled"),
                                      "impact": _("Not measured") if e["enabled"] else _("None")},
                    icon=e["icon"], data=e) for e in items]
        self.table.set_rows(rows)

    def _sel(self):
        r = self.table.selected_row()
        return r.data if r else None

    def _sync(self):
        e = self._sel()
        self.en_btn.set_sensitive(e is not None and not e["enabled"])
        self.dis_btn.set_sensitive(e is not None and e["enabled"])
        self.prop_btn.set_sensitive(e is not None)

    def _set(self, on):
        e = self._sel()
        if e is None:
            return
        set_enabled(e, on)
        if util.DEMO:
            e["enabled"] = on
            self.refresh()
        else:
            self.reload()
        self._sync()

    def properties(self):
        e = self._sel()
        if e is None:
            return
        from ..widgets.common import Dialog
        grid = Gtk.Grid(column_spacing=16, row_spacing=6)
        for i, (k, v) in enumerate([(_("Name"), e["name"]), (_("Description"), e["comment"] or "—"),
                                    (_("Command line"), e["exec"] or "—"), (_("Location"), e["path"] or "—")]):
            grid.attach(label(k + ":", "dialog-key"), 0, i, 1, 1)
            lb = label(v, "dialog-body", wrap=True, selectable=True)
            lb.set_max_width_chars(48)
            grid.attach(lb, 1, i, 1, 1)
        Dialog(self.win, _("%s Properties") % e["name"], grid, None, _("Close"), width=520).show()

    def _context(self, table, x, y):
        e = self._sel()
        if e is None:
            return
        m = Menu(table)
        m.add(_("Disable") if e["enabled"] else _("Enable"), lambda: self._set(not e["enabled"]))
        m.add(_("Properties"), self.properties)
        m.popup_at(x, y)
