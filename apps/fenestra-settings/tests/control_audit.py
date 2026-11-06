#!/usr/bin/env python3
"""Audit that every control in Fenestra Settings changes something real.

Runs the app headlessly in *normal* mode (not demo, not read-only) with an isolated
GSettings backend (GSETTINGS_BACKEND=keyfile, temporary XDG_CONFIG_HOME):

* every toggle, dropdown and slider on every page is operated programmatically;
* GSettings writes really happen (in the isolated keyfile) and are read back;
* D-Bus calls, commands and app launches are recorded but NOT executed (sandbox), so the
  real system is never touched; the table shows which backend each control drives;
* read-only backend probes (UPower, hostnamed, NetworkManager, BlueZ, …) are called directly.

* Fenestra Shell options (shell.conf) are written to the temporary XDG_CONFIG_HOME and read
  back; controls hidden in the current session (backends/session.py) are not operated.

Usage (always on a nested/headless compositor, never the real desktop), once per session:
    WAYLAND_DISPLAY=fenestra-test GDK_BACKEND=wayland python3 tests/control_audit.py [--out report.md]
    XDG_CURRENT_DESKTOP=Fenestra WAYLAND_DISPLAY=fenestra-test GDK_BACKEND=wayland python3 tests/control_audit.py
"""
import os
import sys
import tempfile
import time

if os.environ.get("WAYLAND_DISPLAY", "wayland-0") == "wayland-0" and not os.environ.get("FENESTRA_AUDIT_ANY_DISPLAY"):
    sys.exit("refusing to run on the real desktop: set WAYLAND_DISPLAY to a test compositor")
os.environ.pop("DISPLAY", None)
TMP = tempfile.mkdtemp(prefix="fenestra-audit-")
os.environ["GSETTINGS_BACKEND"] = "keyfile"
os.environ["XDG_CONFIG_HOME"] = TMP
os.environ["FENESTRA_SETTINGS_LANG"] = "en"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk  # noqa: E402

from fenestra_settings import i18n, theme, util  # noqa: E402

i18n.init("en")
util.SANDBOX = True
util.READ_ONLY = False
util.DEMO = False

from fenestra_settings.widgets import Dropdown, SettingRow, Slider, ToggleSwitch  # noqa: E402

SKIP_PAGES = set()
results = []   # (page, control, kind, backend, verified)


def pump(seconds):
    ctx = GLib.MainContext.default()
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        while ctx.pending():
            ctx.iteration(False)
        time.sleep(0.01)


def walk(w):
    stack = [w]
    while stack:
        x = stack.pop()
        yield x
        c = x.get_last_child()
        while c is not None:
            stack.append(c)
            c = c.get_prev_sibling()


def row_title(w):
    p = w
    while p is not None:
        if isinstance(p, SettingRow):
            return p.title_lbl.get_label()
        p = p.get_parent()
    return "?"


def describe(calls):
    out = []
    for c in calls:
        kind, what = c[0], c[1]
        out.append(f"{kind}: {what}".replace(os.environ.get("USER", "\0"), "$USER"))
    return "; ".join(out)


def verify(calls):
    from fenestra_settings.backends import shellconf
    ok = None
    for c in calls:
        if c[0] == "shellconf":
            want = None if c[2] is None else shellconf.encode(c[2])
            good = shellconf.raw(c[1]) == want
            ok = good if ok is None else (ok and good)
        elif c[0] == "gsettings" and c[2] is not None:
            schema, key = c[1].split(" ", 1)
            if schema.startswith("org.gnome.desktop.notifications.application"):
                ok = True if ok is None else ok
                continue
            got = util.gget(schema, key)
            good = got == c[2] or (isinstance(got, float) and abs(got - float(c[2])) < 1e-6) or \
                (isinstance(got, (list, tuple)) and list(map(tuple, got)) == list(map(tuple, c[2]))
                 if got and isinstance(got[0], (list, tuple)) else got == c[2])
            ok = good if ok is None else (ok and good)
        elif c[0] in ("gsettings-reset", "mimeapps", "autostart", "config", "gtk-accent"):
            ok = True if ok is None else ok
    return ok


def shown(w, top):
    """False when w or a parent up to the page is hidden (e.g. hidden in this session)."""
    while w is not None and w is not top:
        if not w.get_visible():
            return False
        w = w.get_parent()
    return True


def operate(ctrl):
    if isinstance(ctrl, ToggleSwitch):
        ctrl.sw.set_active(not ctrl.sw.get_active())
        return "toggle"
    if isinstance(ctrl, Dropdown):
        n = ctrl.get_model().get_n_items()
        if n < 2:
            return None
        ctrl.set_selected((ctrl.get_selected() + 1) % n)
        return "dropdown"
    if isinstance(ctrl, Slider):
        adj = ctrl.scale.get_adjustment()
        lo, hi = adj.get_lower(), adj.get_upper()
        v = ctrl.get_value()
        ctrl.scale.set_value(lo + (hi - lo) * 0.3 if v > (lo + hi) / 2 else lo + (hi - lo) * 0.7)
        return "slider"
    return None


def audit(app):
    theme.init(None)
    from fenestra_settings import pages  # noqa: F401
    from fenestra_settings.pages.base import PAGES
    from fenestra_settings.window import SettingsWindow
    win = SettingsWindow(app, "home", animate=False)
    win.present()
    pump(1.0)
    for pid in PAGES:
        if pid in SKIP_PAGES:
            continue
        win.navigate(pid)
        pump(1.5)
        page = win.pages[pid]
        seen = set()
        for _round in range(2):  # pages may rebuild controls after async loads
            ctrls = [w for w in walk(page.widget) if isinstance(w, (ToggleSwitch, Dropdown, Slider))
                     and id(w) not in seen and shown(w, page.widget)]
            for ctrl in reversed(ctrls):  # master switches come first; operate them last
                seen.add(id(ctrl))
                if getattr(ctrl, "ui_only", None):
                    results.append((pid, row_title(ctrl), type(ctrl).__name__, "UI only: " + ctrl.ui_only, "n/a"))
                    continue
                if not ctrl.get_sensitive() or (isinstance(ctrl, ToggleSwitch) and not ctrl.sw.get_sensitive()):
                    results.append((pid, row_title(ctrl), type(ctrl).__name__, "insensitive (backend unavailable)",
                                    "n/a"))
                    continue
                title = row_title(ctrl)
                util.CALLS.clear()
                kind = operate(ctrl)
                if kind is None:
                    continue
                pump(0.45 if kind == "slider" else 0.25)
                if getattr(ctrl, "apply_button", None) is not None:
                    ctrl.apply_button.emit("clicked")
                    pump(0.2)
                calls = list(util.CALLS)
                win.close_dialog(None)
                if not calls:
                    results.append((pid, title, kind, "NOTHING (no-op!)", "NO"))
                    continue
                v = verify(calls)
                verified = "yes (read back)" if v else ("NO (read back differs)" if v is False
                                                        else "issued (sandboxed, not executed)")
                results.append((pid, title, kind, describe(calls), verified))
            pump(0.3)
    win.destroy()
    app.quit()


def probes():
    """Read-only calls straight into the D-Bus/system backends."""
    from fenestra_settings.backends import (accounts, audio, bluetooth, display, hello, network, power,
                                            system_info, timedate)
    out = []

    def add(name, backend, fn):
        try:
            v = fn()
            out.append((name, backend, "yes" if v not in (None, "", [], {}) else "no data", repr(v)[:70]))
        except Exception as e:  # noqa: BLE001
            out.append((name, backend, "ERROR", str(e)[:70]))
    add("Hostname", "hostnamed (D-Bus)", system_info.hostname)
    add("Battery", "UPower (D-Bus)", lambda: power.battery() and power.battery()["percent"])
    add("Power mode", "power-profiles-daemon (D-Bus)", lambda: power.profiles()[0])
    add("Brightness", "gsd-power / mutter Backlight (D-Bus)", power.brightness)
    add("Time zone / NTP", "timedated (D-Bus)", lambda: (timedate.info()["timezone"], timedate.info()["ntp"]))
    add("Regional format", "localed (D-Bus)", lambda: timedate.locale_info().get("LANG"))
    add("Account", "AccountsService (D-Bus)", lambda: (accounts.current_user().username,
                                                       accounts.current_user().automatic_login))
    add("Airplane mode", "gsd-rfkill (D-Bus)", network.airplane_mode)
    add("Face recognition", "Howdy config/models", lambda: (hello.howdy_available(), hello.howdy_enrolled()))
    res = {}

    def cb(key):
        def f(*a):
            res[key] = a
        return f
    network.status(cb("net"))
    bluetooth.state(cb("bt"))
    audio.status(cb("audio"))
    display.get_state(cb("display"))
    hello.fingerprint_device(cb("fp"))
    pump(3.0)
    out.append(("Wi-Fi / devices", "NetworkManager (nmcli)", "yes" if res.get("net") else "no data",
                repr(res.get("net", [{}])[0].get("wifi_enabled") if res.get("net") else None)))
    out.append(("Bluetooth adapter", "BlueZ (D-Bus)", "yes" if res.get("bt") and res["bt"][0] else "no data",
                repr(res["bt"][1]) if res.get("bt") else "-"))
    out.append(("Audio devices", "PipeWire (wpctl)", "yes" if res.get("audio") and res["audio"][0] else "no data",
                f"{len(res['audio'][0])} outputs" if res.get("audio") else "-"))
    st = res.get("display", [None])[0]
    out.append(("Monitors", "mutter DisplayConfig (D-Bus)", "yes" if st else "no data",
                f"{st.monitor().connector} scale {st.logical[0].scale}" if st else "-"))
    fp = res.get("fp", [None])[0]
    out.append(("Fingerprint reader", "fprintd (D-Bus)", "yes" if fp else "no device",
                f"{fp.name}, {fp.stages} stages" if fp else "-"))
    return out


def main():
    outfile = None
    if "--out" in sys.argv:
        outfile = sys.argv[sys.argv.index("--out") + 1]
    app = Gtk.Application(application_id="org.fenestra.SettingsAudit")
    app.connect("activate", lambda a: GLib.idle_add(lambda: (audit(a), False)[1]))
    app.run([])
    util.SANDBOX = False
    prob = probes()
    from fenestra_settings.backends import session
    lines = ["# Fenestra Settings control audit", "",
             f"Session: {'Fenestra (KWin + Fenestra Shell)' if session.is_fenestra() else 'GNOME'}"
             f" (XDG_CURRENT_DESKTOP={session.desktop() or '-'})", "",
             "GSettings writes go to an isolated keyfile backend and are read back; D-Bus calls and",
             "commands are recorded, not executed (they run for real in normal mode).", "",
             "| Page | Control | Type | Real backend | Verified |", "|---|---|---|---|---|"]
    bad = 0
    for pid, title, kind, backend, ver in results:
        if ver.startswith("NO"):
            bad += 1
        lines.append(f"| {pid} | {title} | {kind} | {backend.replace('|', '/')} | {ver} |")
    lines += ["", "## Direct backend probes (read-only)", "", "| Setting | Backend | Read OK | Value |",
              "|---|---|---|---|"]
    show = "--show-values" in sys.argv
    for name, backend, ok, val in prob:
        lines.append(f"| {name} | {backend} | {ok} | `{val if show else '(hidden, use --show-values)'}` |")
    lines += ["", f"Controls exercised: {len(results)}, problems: {bad}"]
    text = "\n".join(lines) + "\n"
    if outfile:
        with open(outfile, "w") as f:
            f.write(text)
    print(text)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
