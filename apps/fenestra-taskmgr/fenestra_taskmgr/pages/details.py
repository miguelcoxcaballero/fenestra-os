"""Details page: one row per process (Windows' Details tab)."""
from __future__ import annotations

from .. import actions, apps, util
from ..i18n import _
from ..widgets.common import Menu, ToolButton, separator
from ..widgets.table import Column, Row, Table
from .base import Page, scrolled
from .processes import Entry, proc_icon, run_task_dialog, show_properties

STATE = {"R": "Running", "S": "Running", "D": "Running", "I": "Running", "T": "Suspended",
         "t": "Suspended", "Z": "Not responding", "X": "Terminated"}


class DetailsPage(Page):
    pid = "details"
    title = _("Details")

    def __init__(self, win):
        super().__init__(win)
        self.table = Table([
            Column("name", _("Name"), 146),
            Column("pid", _("PID"), 50, desc_first=False),
            Column("status", _("Status"), 160, stretch=True),
            Column("user", _("User name"), 80),
            Column("cpu", _("CPU"), 40, "right", desc_first=True),
            Column("memory", _("Memory (active private working set)"), 50, "right", desc_first=True),
            Column("arch", _("Platform"), 60),
            Column("desc", _("Description"), 100),
        ], header_h=25, row_h=25, two_line=False, name_pad=6, group_h=25, chev_w=2, right_pad=17,
           classic=True)
        self.table.sort_key = "name"
        self.table.connect("sort-changed", lambda *_: self.refresh())
        self.table.connect("selection-changed", lambda *_: self._sync())
        self.table.connect("context-menu", self._context)
        self.table.connect("delete-pressed", lambda *_: self.end_task())
        self.table.connect("row-activated", lambda *_: self.properties())
        self.append(scrolled(self.table))
        self.run_btn = ToolButton("tm-run-symbolic", _("Run new task"), lambda: run_task_dialog(self.win))
        self.end_btn = ToolButton("tm-end-symbolic", _("End task"), self.end_task)
        self.procs = {}
        self._sync()

    def tools(self):
        return [self.run_btn, separator(), self.end_btn]

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
        items = []
        for p in snap.procs.values():
            if p.kind == "kernel" and p.pid != 2:
                continue
            name = p.name if p.pid != 2 else "System"
            if self.filter and self.filter not in f"{name} {p.pid} {p.user}".lower():
                continue
            items.append((p, name))
        k, desc = self.table.sort_key, self.table.sort_desc
        keyf = {
            "name": lambda t: t[1].casefold(), "pid": lambda t: t[0].pid, "status": lambda t: t[0].state,
            "user": lambda t: t[0].user, "cpu": lambda t: t[0].cpu, "memory": lambda t: t[0].mem,
            "arch": lambda t: t[0].arch, "desc": lambda t: apps.friendly(t[1]).casefold(),
        }[k]
        items.sort(key=keyf, reverse=desc)
        rows = []
        self.procs = {}
        for p, name in items:
            key = f"p:{p.pid}"
            self.procs[key] = p
            st = STATE.get(p.state, "Running")
            rows.append(Row(key, cells={
                "name": name, "pid": str(p.pid), "status": _(st), "user": p.user,
                "cpu": f"{int(round(min(p.cpu, 99))):02d}", "memory": util.fmt_kib(p.mem),
                "arch": _(p.arch), "desc": apps.friendly(p.name) if p.kind != "kernel" else _("System")},
                icon=proc_icon(p, snap), data=p))
        self.table.set_rows(rows)

    def _sync(self):
        self.end_btn.set_sensitive(self.table.selected is not None)

    def _sel(self):
        r = self.table.selected_row()
        return r.data if r else None

    def end_task(self):
        p = self._sel()
        if p is not None and p.kind != "kernel":
            actions.end_task([p.pid])

    def properties(self):
        p = self._sel()
        if p is not None:
            show_properties(self.win, Entry(f"p:{p.pid}", p.name, None, [p], p.kind))

    def _context(self, table, x, y):
        p = self._sel()
        if p is None:
            return
        m = Menu(table)
        m.add(_("End task"), self.end_task, sensitive=p.kind != "kernel")
        m.add(_("End process tree"), lambda: actions.end_task(self._tree(p.pid)), sensitive=p.kind != "kernel")
        m.add(_("Efficiency mode"), lambda: actions.set_efficiency([p.pid], not p.efficiency),
              check=p.efficiency)
        m.add_separator()
        m.add(_("Open file location"), lambda: actions.open_file_location(p.pid))
        m.add(_("Search online"), lambda: actions.search_online(p.name))
        m.add(_("Properties"), self.properties)
        m.popup_at(x, y)

    def _tree(self, root):
        kids = {}
        for q in self.snap.procs.values():
            kids.setdefault(q.ppid, []).append(q.pid)
        out, todo = [], [root]
        while todo:
            x = todo.pop()
            out.append(x)
            todo.extend(kids.get(x, []))
        return out
