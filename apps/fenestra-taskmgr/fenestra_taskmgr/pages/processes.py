"""Processes page: Apps / Background processes / System processes with heat-map columns."""
from __future__ import annotations

import os
import time

from gi.repository import Gtk

from .. import actions, apps, theme, util
from ..i18n import _
from ..widgets.common import Dialog, Menu, ToolButton, label, separator
from ..widgets.table import Column, Row, Table
from .base import Page, scrolled

DISK_FULL = 100 * 1048576.0   # MB/s that maps to the hottest disk heat level


class Entry:
    __slots__ = ("key", "name", "icon", "procs", "kind", "cgroup", "cpu", "mem", "disk", "expandable",
                 "status", "app_id", "search")

    def __init__(self, key, name, icon, procs, kind, cgroup=None, expandable=False, app_id=None):
        self.key, self.name, self.icon, self.procs, self.kind = key, name, icon, procs, kind
        self.cgroup, self.expandable, self.app_id = cgroup, expandable, app_id
        self.cpu = sum(p.cpu for p in procs)
        self.mem = sum(p.mem for p in procs)
        self.disk = sum(p.disk for p in procs)
        if procs and all(p.state == "T" for p in procs):
            self.status = "susp"
        elif procs and (procs[0].efficiency if len(procs) > 1 else procs[0].efficiency) and \
                sum(p.efficiency for p in procs) * 2 >= len(procs):
            self.status = "eff"
        else:
            self.status = None
        self.search = None

    def matches(self, text):
        if not text:
            return True
        if self.search is None:
            parts = [self.name]
            for p in self.procs:
                parts += [str(p.pid), p.name, p.user, " ".join(p.cmdline[:2])]
            self.search = "\n".join(parts).lower()
        return text in self.search


def proc_icon(p, snap):
    if p.icon:
        return p.icon
    if p.app_id and p.app_id in snap.apps and snap.apps[p.app_id]:
        return snap.apps[p.app_id][1] or "tm-process"
    if p.kind == "kernel":
        return "tm-process"
    did = apps.desktop_for_exec(p.name)
    if did:
        info = apps.app_info(did)
        if info and info[1]:
            return info[1]
    return "tm-process"


def proc_title(p):
    return apps.friendly(p.name) if not p.desc or p.desc == p.name else p.desc


def build_entries(snap, uid_filter=None):
    """Group processes the Windows way. Returns {"app": [...], "bg": [...], "sys": [...]}."""
    groups = {"app": [], "bg": [], "sys": []}
    by_app, by_unit, kernel = {}, {}, []
    for p in snap.procs.values():
        if uid_filter is not None and p.uid != uid_filter:
            continue
        if p.kind == "kernel":
            kernel.append(p)
        elif p.kind == "app":
            by_app.setdefault(p.app_id, []).append(p)
        else:
            by_unit.setdefault((p.kind, p.cgroup or f"pid{p.pid}"), []).append(p)
    for aid, procs in by_app.items():
        info = snap.apps.get(aid)
        name = info[0] if info else aid
        ic = (info[1] if info else None) or "tm-process"
        procs.sort(key=lambda p: p.pid)
        cg = procs[0].cgroup if len({p.cgroup for p in procs}) == 1 else None
        groups["app"].append(Entry("a:" + aid, name, ic, procs, "app", cg, True, aid))
    for (kind, cg), procs in by_unit.items():
        procs.sort(key=lambda p: (p.ppid in {q.pid for q in procs}, p.pid))
        main = procs[0]
        if len(procs) > 1:
            e = Entry("u:" + cg, proc_title(main), proc_icon(main, snap), procs, kind, cg, True)
        else:
            e = Entry(f"p:{main.pid}", proc_title(main), proc_icon(main, snap), procs, kind, cg)
        groups[kind].append(e)
    if kernel and uid_filter in (None, 0):
        e = Entry("k:system", _("System"), "tm-process", kernel, "sys")
        e.mem = sum(p.mem for p in kernel)
        groups["sys"].append(e)
    return groups


def sort_entries(entries, key, desc):
    if key == "name":
        entries.sort(key=lambda e: e.name.casefold(), reverse=desc)
    elif key == "status":
        entries.sort(key=lambda e: (e.status or "", e.name.casefold()), reverse=desc)
    else:
        attr = {"cpu": "cpu", "memory": "mem", "disk": "disk", "network": "cpu"}[key]
        entries.sort(key=lambda e: (getattr(e, attr) if key != "network" else 0, e.name.casefold()),
                     reverse=desc)


def proc_columns():
    return [
        Column("name", _("Name"), 233),
        Column("status", _("Status"), 120),
        Column("cpu", _("CPU"), 73, "right", heat=True, desc_first=True),
        Column("memory", _("Memory"), 73, "right", heat=True, desc_first=True),
        Column("disk", _("Disk"), 73, "right", heat=True, desc_first=True),
        Column("network", _("Network"), 73, "right", heat=True, desc_first=True),
    ]


def entry_cells(e, total_mem):
    th = theme.get()
    cells = {"name": e.name, "cpu": util.fmt_cpu(e.cpu), "memory": util.fmt_mb(e.mem),
             "disk": util.fmt_rate_mbs(e.disk), "network": util.fmt_mbps(0)}
    heat = {"cpu": th.heat_for(e.cpu / 100.0), "memory": th.heat_for(e.mem / max(1, total_mem)),
            "disk": th.heat_for(e.disk / DISK_FULL), "network": 0}
    return cells, heat


def header_values(table, snap):
    th = theme.get()
    cols = {c.key: c for c in table.columns}
    mem = snap.mem or {"used": 0, "total": 1}
    disk = max([d["active"] for d in snap.disks] or [0])
    net = 0.0
    for n in snap.nets:
        speed = n.get("speed", -1)
        speed = speed * 1e6 if speed and speed > 0 else 1e9
        net = max(net, (n["send"] + n["recv"]) / speed * 100)
    vals = {"cpu": snap.cpu_total, "memory": mem["used"] / max(1, mem["total"]) * 100,
            "disk": disk, "network": net}
    for k, v in vals.items():
        if k in cols:
            cols[k].value = util.fmt_pct0(v)
            cols[k].value_heat = th.heat_for(v / 100.0) if v >= 70 else None


class ProcessesPage(Page):
    pid = "processes"
    title = _("Processes")

    def __init__(self, win):
        super().__init__(win)
        self.table = Table(proc_columns(), header_h=49)
        self.table.header_focus = True
        self.table.connect("sort-changed", lambda *_: self.refresh())
        self.table.connect("expand-toggled", lambda *_: self.refresh())
        self.table.connect("selection-changed", lambda *_: self._sync_tools())
        self.table.connect("context-menu", self._context)
        self.table.connect("delete-pressed", lambda *_: self.end_task())
        self.table.connect("row-activated", lambda *_: self.properties())
        self.append(scrolled(self.table))
        self.entries = {}
        self.run_btn = ToolButton("tm-run-symbolic", _("Run new task"), lambda: run_task_dialog(self.win))
        self.end_btn = ToolButton("tm-end-symbolic", _("End task"), self.end_task)
        self.eff_btn = ToolButton("tm-leaf-symbolic", _("Efficiency mode"), self.toggle_efficiency)
        self._sync_tools()

    def tools(self):
        return [self.run_btn, separator(), self.end_btn, self.eff_btn]

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
        t = self.table
        header_values(t, snap)
        groups = build_entries(snap)
        total_mem = (snap.mem or {}).get("total", 1)
        rows = []
        self.entries = {}
        grouped = util.opts()["group_by_type"]
        sections = [("app", _("Apps")), ("bg", _("Background processes")), ("sys", _("System processes"))]
        if not grouped:
            allg = groups["app"] + groups["bg"] + groups["sys"]
            sections = [("all", None)]
            groups = {"all": allg}
        for gk, gname in sections:
            ents = [e for e in groups[gk] if e.matches(self.filter)]
            if not ents:
                continue
            sort_entries(ents, t.sort_key, t.sort_desc)
            if gname:
                rows.append(Row(f"g:{gk}", "group", cells={"name": f"{gname} ({len(ents)})"}))
            for e in ents:
                self.entries[e.key] = e
                cells, heat = entry_cells(e, total_mem)
                n = len(e.procs)
                if e.expandable and n > 1:
                    cells["name"] = f"{e.name} ({n})"
                rows.append(Row(e.key, cells=cells, heat=heat, icon=e.icon, expandable=e.expandable,
                                status=e.status, data=e))
                if e.expandable and e.key in t.expanded:
                    kids = list(e.procs)
                    for p in kids:
                        ce = Entry(f"c:{p.pid}", proc_title(p), proc_icon(p, snap), [p], e.kind, None)
                        sort_entries([ce], t.sort_key, t.sort_desc)
                        self.entries[ce.key] = ce
                        c2, h2 = entry_cells(ce, total_mem)
                        rows.append(Row(ce.key, level=1, cells=c2, heat=h2, icon=ce.icon, status=ce.status,
                                        data=ce))
        t.set_rows(rows)
        self._sync_tools()

    # ------------------------------------------------------------ actions
    def selected(self):
        r = self.table.selected_row()
        return r.data if r is not None else None

    def _sync_tools(self):
        e = self.selected()
        self.end_btn.set_sensitive(e is not None and e.key != "k:system")
        self.eff_btn.set_sensitive(e is not None and e.kind != "sys")

    def end_task(self):
        e = self.selected()
        if e is None or e.key == "k:system":
            return
        pids = [p.pid for p in e.procs]
        if e.kind == "sys":
            Dialog(self.win, _("Do you want to end %s?") % e.name,
                   _("Ending a system process can make the system unstable. You will be asked to "
                     "authenticate."), _("End process"),
                   on_primary=lambda: actions.end_task(pids, e.cgroup)).show()
            return
        actions.end_task(pids, e.cgroup if e.kind == "app" else None)

    def toggle_efficiency(self):
        e = self.selected()
        if e is None:
            return
        on = e.status != "eff"
        pids = [p.pid for p in e.procs]

        def go():
            actions.set_efficiency(pids, on)
            if self.win.app.sampler:
                self.win.app.sampler.refresh()
        if on and util.opts()["ask_efficiency"]:
            Dialog(self.win, _("Turn on Efficiency mode?"),
                   _("Efficiency mode lowers the process priority and its disk priority. This can "
                     "make it run slower, but improves the responsiveness of everything else."),
                   _("Turn on Efficiency mode"), on_primary=go).show()
        else:
            go()

    def _context(self, table, x, y):
        e = self.selected()
        if e is None:
            return
        m = Menu(table)
        row = table.selected_row()
        if row.expandable:
            m.add(_("Collapse") if row.key in table.expanded else _("Expand"), lambda: table.toggle(row.key))
            m.add_separator()
        m.add(_("End task"), self.end_task, sensitive=e.key != "k:system")
        m.add(_("Efficiency mode"), self.toggle_efficiency, check=e.status == "eff",
              sensitive=e.kind != "sys")
        m.add_separator()
        m.add(_("Go to details"), lambda: self.go_details(e))
        m.add(_("Open file location"), lambda: actions.open_file_location(e.procs[0].pid),
              sensitive=e.key != "k:system")
        m.add(_("Search online"), lambda: actions.search_online(e.procs[0].name))
        m.add(_("Properties"), self.properties)
        m.popup_at(x, y)

    def go_details(self, e):
        self.win.navigate("details")
        d = self.win.pages.get("details")
        if d is not None and e.procs:
            d.table.select(f"p:{e.procs[0].pid}")
            i = d.table._index.get(f"p:{e.procs[0].pid}")
            if i is not None:
                d.table.ensure_visible(i)

    def properties(self):
        e = self.selected()
        if e is not None:
            show_properties(self.win, e)

    def more_menu(self, m):
        m.add(_("Expand all"), self._expand_all)
        m.add(_("Collapse all"), self._collapse_all)
        m.add(_("Group by type"), self._toggle_group, check=util.opts()["group_by_type"])
        m.add_separator()

    def _expand_all(self):
        self.table.expanded |= {k for k, e in self.entries.items() if e.expandable}
        self.refresh()

    def _collapse_all(self):
        self.table.expanded.clear()
        self.refresh()

    def _toggle_group(self):
        util.opts().set("group_by_type", not util.opts()["group_by_type"])
        self.refresh()


def show_properties(win, e):
    p = e.procs[0]
    grid = Gtk.Grid(column_spacing=16, row_spacing=6)
    try:
        exe = os.readlink(f"/proc/{p.pid}/exe") if not util.DEMO else p.cmdline[0]
    except OSError:
        exe = p.cmdline[0] if p.cmdline else "—"
    started = "—"
    if p.start and getattr(win.snap, "boot_time", 0):
        from ..procdata import CLK_TCK
        started = time.strftime("%x %X", time.localtime(win.snap.boot_time + p.start / CLK_TCK))
    rows = [
        (_("Name"), e.name),
        (_("PID"), ", ".join(str(q.pid) for q in e.procs[:8]) + (" …" if len(e.procs) > 8 else "")),
        (_("User name"), p.user),
        (_("Location"), exe),
        (_("Command line"), " ".join(p.cmdline) or "—"),
        (_("Started"), started),
        (_("CPU time"), util.fmt_cputime(sum(q.cputime for q in e.procs))),
        (_("Memory"), util.fmt_mb(e.mem)),
        (_("Threads"), str(sum(q.threads for q in e.procs))),
    ]
    for i, (k, v) in enumerate(rows):
        grid.attach(label(k + ":", "dialog-key"), 0, i, 1, 1)
        lb = label(v, "dialog-body", wrap=True, selectable=True)
        lb.set_max_width_chars(48)
        grid.attach(lb, 1, i, 1, 1)
    Dialog(win, _("%s Properties") % e.name, grid, None, _("Close"), width=520).show()


def run_task_dialog(win):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    box.append(label(_("Type the name of a program, folder, document, or Internet resource, and "
                       "Fenestra will open it for you."), "dialog-body", wrap=True))
    entry = Gtk.Entry()
    entry.add_css_class("fluent-entry")
    entry.set_placeholder_text(_("Open:"))
    box.append(entry)
    admin = Gtk.CheckButton(label=_("Create this task with administrative privileges."))
    admin.add_css_class("fluent-check")
    box.append(admin)
    err = label("", "dialog-error", wrap=True)
    err.set_visible(False)
    box.append(err)

    def ok():
        if actions.run_task(entry.get_text(), admin.get_active()):
            if util.opts()["minimize_on_use"]:
                win.minimize()
            return None
        err.set_text(_("Fenestra cannot find '%s'. Make sure you typed the name correctly, and then "
                       "try again.") % entry.get_text().strip())
        err.set_visible(True)
        return True
    dlg = Dialog(win, _("Create new task"), box, _("OK"), _("Cancel"), on_primary=ok)
    entry.connect("activate", lambda *_: dlg._done(ok))
    dlg.show()
    entry.grab_focus()
