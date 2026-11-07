"""Services: systemd system and user services."""
from __future__ import annotations

import json
import subprocess
import threading

from gi.repository import GLib

from .. import actions, util
from ..i18n import _
from ..widgets.common import Menu, ToolButton, separator
from ..widgets.table import Column, Row, Table
from .base import Page, scrolled
from .processes import run_task_dialog


def list_services():
    out = []
    for user in (False, True):
        argv = ["systemctl"] + (["--user"] if user else []) + [
            "list-units", "--type=service", "--all", "--output=json", "--no-pager"]
        try:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=5)
            data = json.loads(r.stdout or "[]")
        except (OSError, subprocess.SubprocessError, ValueError):
            data = []
        for u in data:
            unit = u.get("unit", "")
            if not unit.endswith(".service") or u.get("load") == "not-found":
                continue
            out.append({"unit": unit, "name": unit[:-8], "desc": u.get("description", ""),
                        "running": u.get("active") == "active" and u.get("sub") == "running",
                        "user": user, "active": u.get("active"), "sub": u.get("sub")})
    return out


class ServicesPage(Page):
    pid = "services"
    title = _("Services")

    def __init__(self, win):
        super().__init__(win)
        self.table = Table([
            Column("name", _("Name"), 180), Column("pid", _("PID"), 50),
            Column("desc", _("Description"), 267, stretch=True),
            Column("status", _("Status"), 100), Column("group", _("Group"), 100),
        ], header_h=25, row_h=25, two_line=False, name_pad=6, group_h=25, chev_w=2, right_pad=17,
           classic=True)
        self.table.connect("sort-changed", lambda *_: self.refresh())
        self.table.connect("selection-changed", lambda *_: self._sync())
        self.table.connect("context-menu", self._context)
        self.append(scrolled(self.table))
        self.run_btn = ToolButton("tm-run-symbolic", _("Run new task"), lambda: run_task_dialog(self.win))
        self.start_btn = ToolButton("tm-play-symbolic", _("Start"), lambda: self._act("start"))
        self.stop_btn = ToolButton("tm-stop-symbolic", _("Stop"), lambda: self._act("stop"))
        self.restart_btn = ToolButton("tm-restart-symbolic", _("Restart"), lambda: self._act("restart"))
        self.open_btn = ToolButton("tm-open-services-symbolic", _("Open Services"), actions.open_services_tool)
        self.open_btn.set_sensitive(actions.has_services_tool() or util.DEMO)
        self.services = []
        self.loading = False
        self._timer = 0
        self.reload()
        self._sync()

    def tools(self):
        return [self.run_btn, separator(), self.start_btn, self.stop_btn, self.restart_btn, separator(),
                self.open_btn]

    def reload(self):
        if util.DEMO:
            from ..demo import SERVICES
            self.services = [{"unit": n + ".service", "name": n, "desc": d, "running": r, "user": False,
                              "group": g} for n, d, r, g in SERVICES]
            self.refresh()
            return
        if self.loading:
            return
        self.loading = True

        def work():
            data = list_services()
            GLib.idle_add(self._loaded, data)
        threading.Thread(target=work, daemon=True).start()

    def _loaded(self, data):
        self.loading = False
        self.services = data
        self.refresh()
        return False

    def shown(self):
        self.reload()
        if not self._timer and not util.DEMO:
            self._timer = GLib.timeout_add_seconds(10, self._tick)

    def _tick(self):
        if self.win.current is not self:
            self._timer = 0
            return False
        self.reload()
        return True

    def set_filter(self, text):
        super().set_filter(text)
        self.refresh()

    def update(self, snap):
        self.snap = snap

    def _pids(self):
        """unit -> (main pid, slice) from the sampled processes' cgroups."""
        out = {}
        snap = getattr(self, "snap", None) or self.win.snap
        if snap is None:
            return out
        for p in sorted(snap.procs.values(), key=lambda p: p.pid):
            if p.unit and p.unit.endswith(".service") and p.unit not in out:
                parts = p.cgroup.strip("/").split("/")
                sl = parts[-2] if len(parts) >= 2 else ""
                out[p.unit] = (p.pid, sl)
        return out

    def refresh(self):
        pids = self._pids()
        items = []
        for s in self.services:
            pid, grp = pids.get(s["unit"], (None, s.get("group", "")))
            if util.DEMO:
                pid = (sum(map(ord, s["name"])) * 7) % 9000 + 500 if s["running"] else None
                grp = s.get("group", "")
            if self.filter and self.filter not in f"{s['name']} {s['desc']} {pid or ''}".lower():
                continue
            items.append((s, pid if s["running"] else None, grp if s["running"] else ""))
        k, desc = self.table.sort_key, self.table.sort_desc
        keyf = {"name": lambda t: t[0]["name"].casefold(), "pid": lambda t: t[1] or 0,
                "desc": lambda t: t[0]["desc"].casefold(), "status": lambda t: not t[0]["running"],
                "group": lambda t: t[2]}[k]
        items.sort(key=keyf, reverse=desc)
        rows = [Row(("u:" if s["user"] else "s:") + s["unit"],
                    cells={"name": s["name"], "pid": str(pid) if pid else "", "desc": s["desc"],
                           "status": _("Running") if s["running"] else _("Stopped"), "group": grp},
                    icon="tm-service", data=s) for s, pid, grp in items]
        self.table.set_rows(rows)
        self._sync()

    def _sel(self):
        r = self.table.selected_row()
        return r.data if r else None

    def _sync(self):
        s = self._sel()
        self.start_btn.set_sensitive(s is not None and not s["running"])
        self.stop_btn.set_sensitive(s is not None and s["running"])
        self.restart_btn.set_sensitive(s is not None and s["running"])

    def _act(self, action):
        s = self._sel()
        if s is not None:
            actions.service_action(action, s["unit"], s["user"], done=lambda: GLib.idle_add(self._after))

    def _after(self):
        self.reload()
        return False

    def _context(self, table, x, y):
        s = self._sel()
        if s is None:
            return
        m = Menu(table, classic=True)
        m.add(_("Start"), lambda: self._act("start"), sensitive=not s["running"])
        m.add(_("Stop"), lambda: self._act("stop"), sensitive=s["running"])
        m.add(_("Restart"), lambda: self._act("restart"), sensitive=s["running"])
        m.add_separator()
        m.add(_("Open Services"), actions.open_services_tool, sensitive=actions.has_services_tool())
        m.add(_("Search online"), lambda: actions.search_online(s["name"] + " service"))
        m.add(_("Go to details"), lambda: self._go_details(s))
        m.popup_at(x, y)

    def _go_details(self, s):
        pid = self._pids().get(s["unit"], (None,))[0]
        self.win.navigate("details")
        if pid:
            d = self.win.pages["details"]
            d.table.select(f"p:{pid}")
            i = d.table._index.get(f"p:{pid}")
            if i is not None:
                d.table.ensure_visible(i)
