"""App history: CPU time used by applications (current session, accumulated across runs)."""
from __future__ import annotations

import json
import os
import time

from .. import util
from ..i18n import _
from ..widgets.common import ToolButton, label, separator
from ..widgets.table import Column, Row, Table
from .base import Page, scrolled
from .processes import run_task_dialog


class AppHistoryPage(Page):
    pid = "apphistory"
    title = _("App history")

    def __init__(self, win):
        super().__init__(win)
        self.path = os.path.join(util.state_dir(), "app-history.json")
        self.saved = {}
        self.since = time.time()
        if not util.DEMO:
            try:
                with open(self.path) as f:
                    data = json.load(f)
                self.saved = data.get("apps", {})
                self.since = data.get("since", self.since)
            except (OSError, ValueError):
                pass
        info = Gtk_box()
        self.info = label("", "info-line")
        info.append(self.info)
        link = label(_("Delete usage history"), "link")
        link.set_cursor_from_name("pointer")
        from gi.repository import Gtk
        click = Gtk.GestureClick()
        click.connect("released", lambda *_: self.delete_history())
        link.add_controller(click)
        info.append(link)
        self.append(info)
        self.table = Table([
            Column("name", _("Name"), 198),
            Column("cputime", _("CPU time"), 107, "right", heat=True, desc_first=True),
            Column("network", _("Network"), 107, "right", heat=True, desc_first=True),
            Column("notif", _("Notifications"), 107, "right", heat=True, desc_first=True),
        ], header_h=34, two_line=False, icon_col=True)
        self.table.header_h = 34
        self.table.connect("sort-changed", lambda *_: self.refresh())
        self.append(scrolled(self.table))
        self.run_btn = ToolButton("tm-run-symbolic", _("Run new task"), lambda: run_task_dialog(self.win))
        self._last_save = 0

    def tools(self):
        if not hasattr(self, "_sep"):
            self._sep = separator()
        return [self.run_btn, self._sep]  # the reference shows a separator after it

    def more_menu(self, m):
        m.add(_("Delete usage history"), self.delete_history)
        m.add_separator()

    def set_filter(self, text):
        super().set_filter(text)
        self.refresh()

    def delete_history(self):
        self.saved = {}
        self.since = time.time()
        self.base = {k: sum(v["pids"].values()) + v.get("done", 0.0) for k, v in self.win.app_cpu.items()}
        self._save()
        self.refresh()

    def _totals(self):
        base = getattr(self, "base", {})
        out = {}
        for aid, rec in self.win.app_cpu.items():
            live = sum(rec["pids"].values()) + rec.get("done", 0.0) - base.get(aid, 0)
            prev = self.saved.get(aid, {}).get("cpu", 0)
            out[aid] = (rec["name"], rec["icon"], prev + max(0.0, live))
        for aid, rec in self.saved.items():
            if aid not in out:
                out[aid] = (rec.get("name", aid), rec.get("icon"), rec.get("cpu", 0))
        return out

    def _save(self):
        if util.DEMO or util.READ_ONLY:
            return
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            data = {"since": self.since,
                    "apps": {k: {"name": n, "icon": i, "cpu": c} for k, (n, i, c) in self._totals().items()}}
            with open(self.path + ".tmp", "w") as f:
                json.dump(data, f)
            os.replace(self.path + ".tmp", self.path)
        except OSError:
            pass

    def update(self, snap):
        self.snap = snap
        if time.time() - self._last_save > 60:
            self._last_save = time.time()
            self._save()
        self.refresh()

    def refresh(self):
        fmt = _("date_fmt")
        day = time.strftime("%m/%d/%Y" if fmt == "date_fmt" else fmt, time.localtime(self.since))
        self.info.set_text(_("Resource usage since %s for current user and system accounts.") % day)
        if util.DEMO:
            from ..demo import HISTORY_APPS
            items = [(n, ic, (i * 7) % 3 if n in ("Files", "GNOME Shell", "Xwayland", "PipeWire") else 0)
                     for i, (n, ic) in enumerate(HISTORY_APPS)]
        else:
            items = list(self._totals().values())
        if self.filter:
            items = [t for t in items if self.filter in t[0].lower()]
        k, desc = self.table.sort_key, self.table.sort_desc
        items.sort(key=(lambda t: t[0].casefold()) if k == "name" else (lambda t: t[2]), reverse=desc)
        rows = []
        for name, ic, cpu in items:
            rows.append(Row(f"a:{name}", cells={"name": name, "cputime": util.fmt_cputime(cpu),
                                                "network": "0 MB", "notif": "0 MB"},
                            heat={"cputime": 0, "network": 0, "notif": 0}, icon=ic or "tm-process"))
        self.table.set_rows(rows)


def Gtk_box():
    from gi.repository import Gtk
    b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
    b.add_css_class("apphistory-info")
    return b
