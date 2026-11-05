"""Users page: per-user CPU / memory / disk with the user's apps nested."""
from __future__ import annotations

import pwd

from .. import actions, util
from ..i18n import _
from ..widgets.common import ToolButton, separator
from ..widgets.table import Column, Row, Table
from .base import Page, scrolled
from .processes import Entry, entry_cells, header_values, run_task_dialog


class UsersPage(Page):
    pid = "users"
    title = _("Users")

    def __init__(self, win):
        super().__init__(win)
        cols = [Column("name", _("User"), 214), Column("status", _("Status"), 120),
                Column("cpu", _("CPU"), 73, "right", heat=True, desc_first=True),
                Column("memory", _("Memory"), 73, "right", heat=True, desc_first=True),
                Column("disk", _("Disk"), 73, "right", heat=True, desc_first=True),
                Column("network", _("Network"), 73, "right", heat=True, desc_first=True)]
        self.table = Table(cols, header_h=49)
        self.table.connect("sort-changed", lambda *_: self.refresh())
        self.table.connect("expand-toggled", lambda *_: self.refresh())
        self.append(scrolled(self.table))
        self.run_btn = ToolButton("tm-run-symbolic", _("Run new task"), lambda: run_task_dialog(self.win))
        self.disc_btn = ToolButton("tm-disconnect-symbolic", _("Disconnect"))
        self.disc_btn.set_sensitive(False)
        self.manage_btn = ToolButton("tm-manage-users-symbolic", _("Manage user accounts"),
                                     actions.open_users_settings)

    def tools(self):
        return [self.run_btn, separator(), self.disc_btn, self.manage_btn]

    def set_filter(self, text):
        super().set_filter(text)
        self.refresh()

    def update(self, snap):
        self.snap = snap
        self.refresh()

    def refresh(self):
        snap = getattr(self, "snap", None)
        if snap is None:
            return
        header_values(self.table, snap)
        users = {}
        for p in snap.procs.values():
            if p.uid >= 1000 and p.uid != 65534 and p.kind != "kernel":
                users.setdefault(p.uid, []).append(p)
        total = (snap.mem or {}).get("total", 1)
        rows = []
        full = util.opts()["full_account_name"]
        for uid, procs in sorted(users.items()):
            name = procs[0].user
            if full and not util.DEMO:
                try:
                    gecos = pwd.getpwuid(uid).pw_gecos.split(",")[0]
                    name = f"{name} ({gecos})" if gecos else name
                except KeyError:
                    pass
            if self.filter and self.filter not in name.lower():
                continue
            e = Entry(f"u:{uid}", name, "tm-user", procs, "bg", expandable=True)
            cells, heat = entry_cells(e, total)
            cells["name"] = f"{name} ({len(procs)})"
            rows.append(Row(e.key, cells=cells, heat=heat, icon="tm-user", expandable=True, data=e))
            if e.key in self.table.expanded:
                from .processes import build_entries, sort_entries
                g = build_entries(snap, uid_filter=uid)
                ents = g["app"] + g["bg"] + g["sys"]
                sort_entries(ents, self.table.sort_key, self.table.sort_desc)
                for c in ents:
                    c2, h2 = entry_cells(c, total)
                    if len(c.procs) > 1:
                        c2["name"] = f"{c.name} ({len(c.procs)})"
                    rows.append(Row(f"{e.key}/{c.key}", level=1, cells=c2, heat=h2, icon=c.icon,
                                    status=c.status, data=c))
        self.table.set_rows(rows)
