#!/usr/bin/env python3
"""Headless smoke test: open the app with demo data and exercise every page, menu and dialog.
    WAYLAND_DISPLAY=fenestra-test GDK_BACKEND=wayland python3 tools/smoke-test.py"""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fenestra_taskmgr import app as appmod, util  # noqa: E402
from gi.repository import GLib  # noqa: E402

errors = []
sys.excepthook = lambda *a: (errors.append(a), traceback.print_exception(*a))
util.DEMO = util.READ_ONLY = True
opts = appmod.parse_args(["x", "--demo-data"])
a = appmod.App(opts)


def steps():
    w = a.win
    yield
    for pid in ("processes", "performance", "apphistory", "startup", "users", "details", "services", "settings"):
        w.navigate(pid)
        yield
        w._more(w.more_btn)
        yield
        pg = w.current
        if hasattr(pg, "table") and pg.table.rows:
            row = next((r for r in pg.table.rows if r.kind != "group"), None)
            if row:
                pg.table.select(row.key)
                pg.table.emit("context-menu", 50.0, 200.0)
                yield
                if pg.table.rows and row.expandable:
                    pg.table.toggle(row.key)
                if hasattr(pg, "properties"):
                    pg.properties()
                    yield
                    if w.dialog:
                        w.hide_dialog(w.dialog)
        w.search.set_text("pipe")
        yield
        w.search.set_text("")
    for dev in ("mem", "disk0", "net0", "cpu"):
        w.pages["performance"].select(dev)
        yield
    w.navigate("performance")
    w.pages["performance"]._cpu_mode("logical")
    yield
    w.pages["performance"]._cpu_mode("overall")
    w.navigate("processes")
    from fenestra_taskmgr.pages.processes import run_task_dialog
    run_task_dialog(w)
    yield
    w.hide_dialog(w.dialog)
    w.pages["processes"].toggle_efficiency()
    yield
    w.set_expanded(True)
    yield
    w.set_expanded(False)
    for _ in range(3):
        w.on_snapshot(w.collector.sample())
        yield


it = None


def tick():
    global it
    if a.win is None:
        return True
    if it is None:
        it = steps()
    try:
        next(it)
        return True
    except StopIteration:
        a.quit()
        return False


GLib.timeout_add(150, tick)
GLib.timeout_add(60000, lambda: (errors.append("timeout"), a.quit()))
a.run(["x"])
print("SMOKE", "FAILED" if errors else "OK", len(errors))
sys.exit(1 if errors else 0)
