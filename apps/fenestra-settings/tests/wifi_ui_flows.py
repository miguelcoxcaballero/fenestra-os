#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Drive the Wi-Fi pages like a user against the mock NetworkManager and screenshot each step.

Always on a headless compositor inside its own D-Bus session (the app must not reach the real
session bus, and the mock NetworkManager lives on a private "system" bus):

    fenestra-test-run dbus-run-session -- sh -c '
        mutter --headless --wayland --no-x11 --virtual-monitor 1280x900 --wayland-display=fwifi &
        sleep 2; WAYLAND_DISPLAY=fwifi GDK_BACKEND=wayland python3 tests/wifi_ui_flows.py OUTDIR [--dark]'
"""
import os
import sys
import time

if os.environ.get("WAYLAND_DISPLAY", "wayland-0") in ("wayland-0", "wayland-1"):
    sys.exit("refusing to run on the real desktop: set WAYLAND_DISPLAY to a test compositor")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)
from test_wifi_backend import start_private_nm  # noqa: E402

ADDR, PROCS = start_private_nm()
os.environ["DBUS_SYSTEM_BUS_ADDRESS"] = ADDR
os.environ["GSETTINGS_BACKEND"] = "memory"
os.environ.pop("DISPLAY", None)
os.environ["GTK_A11Y"] = "none"

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Graphene", "1.0")
from gi.repository import Gio, GLib, Graphene, Gsk, Gtk  # noqa: E402

from fenestra_settings import i18n, theme  # noqa: E402
from fenestra_settings.backends import wifi as wb  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "wifi-shots"
DARK = "--dark" in sys.argv
LANG = "es" if "--es" in sys.argv else "en"
os.makedirs(OUT, exist_ok=True)
FAILED, PASSED = [], [0]


def check(name, cond, detail=""):
    if cond:
        PASSED[0] += 1
        print(f"  ok   {name}")
    else:
        FAILED.append(name)
        print(f"  FAIL {name} {detail}")


def pump(secs=0.3, until=None):
    ctx = GLib.MainContext.default()
    end = time.monotonic() + secs
    while time.monotonic() < end:
        while ctx.iteration(False):
            pass
        if until is not None and until():
            pump(0.25)
            return True
        time.sleep(0.01)
    return until() if until else True


def shot(win, name):
    pump(0.35)
    w, h = win.get_width(), win.get_height()
    snap = Gtk.Snapshot()
    Gtk.WidgetPaintable.new(win).snapshot(snap, w, h)
    node = snap.to_node()
    rect = Graphene.Rect().init(0, 0, w, h)
    for make in (Gsk.GLRenderer.new, Gsk.CairoRenderer.new):
        try:
            r = make()
            r.realize_for_display(win.get_display())
            tex = r.render_texture(node, rect)
            r.unrealize()
            break
        except GLib.Error:
            continue
    p = os.path.join(OUT, name + ".png")
    tex.save_to_png(p)
    print("  shot", p)


def mock(method, *args, sig=""):
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    r = bus.call_sync("org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager", "org.fenestra.MockNM",
                      method, GLib.Variant(f"({sig})", args) if sig else None, None, 0, 5000, None)
    return r.unpack() if r is not None else None


def walk(w):
    yield w
    c = w.get_first_child()
    while c is not None:
        yield from walk(c)
        c = c.get_next_sibling()


def find_button(root, text):
    for w in walk(root):
        if isinstance(w, Gtk.Button) and w.get_mapped():
            lb = w.get_label()
            if lb is None and isinstance(w.get_child(), Gtk.Label):
                lb = w.get_child().get_label()
            if lb == text:
                return w
    return None


def click(root, text):
    b = find_button(root, text)
    if b is None or not b.get_sensitive():
        check(f"button '{text}' clickable", False, "missing" if b is None else "insensitive")
        return False
    b.emit("clicked")
    pump(0.2)
    return True


def first(root, cls):
    for w in walk(root):
        if isinstance(w, cls) and w.get_mapped():
            return w
    return None


def run(app):
    i18n.init(LANG)
    theme.init("dark" if DARK else "light")
    from fenestra_settings import pages  # noqa: F401
    from fenestra_settings.window import SettingsWindow
    win = SettingsWindow(app, "network", animate=False)
    win.set_default_size(1180, 860)
    win.present()
    w = wb.Wifi.get()
    pump(5, lambda: w.ready and w.networks())
    tr = i18n._
    win.navigate("wifi")
    page = win.pages["wifi"]
    pump(1, lambda: len(page.rows) > 5)
    check("list shows networks", len(page.rows) >= 8, len(page.rows))
    shot(win, "01-list")

    def row(ssid):
        for r in page.rows.values():
            if (ssid is None and r.net.hidden) or r.net.ssid == ssid:
                return r
        return None

    # --- known network: one click Connect
    r = row("HomeNetwork")
    page.select(r)
    pump(0.4)
    shot(win, "02-selected-known")
    click(r, tr("Connect"))
    check("connecting state shown", r.stage == "connecting" and r.status_lbl.get_label() == tr("Connecting"),
          (r.stage, r.status_lbl.get_label()))
    shot(win, "03-connecting")
    pump(6, lambda: row("HomeNetwork").net.state == "connected" and row("HomeNetwork").stage == "idle")
    r = row("HomeNetwork")
    check("connected", r.net.state == "connected", r.net.state)
    check("status Connected, secured", r.status_lbl.get_label() == tr("Connected, secured"), r.status_lbl.get_label())
    check("connected row first", list(page.rows.values())[0] is r)
    check("Disconnect offered", find_button(r, tr("Disconnect")) is not None)
    check("'<SSID> properties' row", page.cur_row.get_visible())
    shot(win, "04-connected")

    # --- new secured network: inline key, wrong key, retry
    r = row("Office-5G")
    page.select(r)
    pump(0.4)
    click(r, tr("Connect"))
    check("key field inline", r.stage == "key" and first(r, Gtk.PasswordEntry) is not None, (r.stage, r.net.known, r.net.secured))
    if r.stage != "key":
        raise SystemExit("cannot continue")
    nxt = find_button(r, tr("Next"))
    check("Next disabled while key too short", nxt is not None and not nxt.get_sensitive())
    shot(win, "05-key-prompt")
    first(r, Gtk.PasswordEntry).set_text("wrong-key!")
    pump(0.1)
    check("Next enabled with 8+ chars", find_button(r, tr("Next")).get_sensitive())
    click(r, tr("Next"))
    check("verifying text", r.status_lbl.get_label() == tr("Verifying and connecting"), r.status_lbl.get_label())
    shot(win, "06-verifying")
    pump(8, lambda: row("Office-5G").error is not None)
    r = row("Office-5G")
    check("wrong key → inline error + key field again",
          r.stage == "key" and r.error == tr("The network security key isn't correct. Please try again."),
          (r.stage, r.error))
    shot(win, "07-wrong-key")
    check("failed profile not kept", not r.net.known)
    # cancel the prompt
    click(r, tr("Cancel"))
    check("cancel returns to Connect", r.stage == "idle" and find_button(r, tr("Connect")) is not None)
    click(r, tr("Connect"))
    first(r, Gtk.PasswordEntry).set_text("office-pass")
    r.auto.set_active(False)
    pump(0.1)
    first(r, Gtk.PasswordEntry).emit("activate")     # Enter key = Next
    pump(8, lambda: row("Office-5G").net.state == "connected")
    r = row("Office-5G")
    check("right key connects", r.net.state == "connected")
    conn = r.net.best_connection()
    check("Connect automatically unchecked was saved",
          conn is not None and conn.get_setting_connection().get_autoconnect() is False)
    check("previous network now disconnected", row("HomeNetwork").net.state is None)
    shot(win, "08-connected-new")

    # --- open network: privacy note, connect directly
    r = row("Cafe-Guest")
    page.select(r)
    pump(0.4)
    shot(win, "09-open-selected")
    click(r, tr("Connect"))
    pump(6, lambda: row("Cafe-Guest").net.state == "connected")
    check("open network connects", row("Cafe-Guest").net.state == "connected")

    # --- hidden network
    r = row(None)
    page.select(r)
    pump(0.4)
    click(r, tr("Connect"))
    pump(0.3)
    check("SSID prompt", r.stage == "ssid")
    first(r, Gtk.Entry).set_text("Secret-Lab")
    shot(win, "10-hidden-ssid")
    click(r, tr("Next"))
    check("then key prompt", r.stage == "key")
    first(r, Gtk.PasswordEntry).set_text("lab-password")
    click(r, tr("Next"))
    pump(8, lambda: w.current() is not None and w.current().ssid == "Secret-Lab")
    check("hidden network connected", w.current() is not None and w.current().ssid == "Secret-Lab",
          w.current() and w.current().ssid)
    shot(win, "11-hidden-connected")

    # --- enterprise
    r = row("Campus")
    page.select(r)
    pump(0.4)
    click(r, tr("Connect"))
    ents = [x for x in walk(r) if isinstance(x, (Gtk.Entry, Gtk.PasswordEntry)) and x.get_mapped()]
    check("user + password fields", len(ents) == 2)
    ents[0].set_text("student")
    ents[1].set_text("campus-pass")
    shot(win, "12-enterprise")
    click(r, tr("Next"))
    pump(8, lambda: row("Campus").net.state == "connected")
    check("enterprise connects", row("Campus").net.state == "connected")

    # --- typing survives scans: the network disappears and reappears while typing
    r = row("WPA3-Only")
    page.select(r)
    pump(0.4)
    click(r, tr("Connect"))
    first(r, Gtk.PasswordEntry).set_text("sae-pass")
    mock("SetStrength", "WPA3-Only", 20, sig="si")
    mock("AddNetwork", "Late-Arrival", 70, 1, 0x188, 2412, sig="siuuu")
    pump(1)
    r2 = row("WPA3-Only")
    check("row kept (same widget) across list updates", r2 is r and r.stage == "key"
          and first(r, Gtk.PasswordEntry).get_text() == "sae-pass")
    check("new network appears live", row("Late-Arrival") is not None)
    click(r, tr("Cancel"))

    # --- cancel while connecting
    mock("SetDelay", 1500, sig="u")
    r = row("HomeNetwork")
    page.select(r)
    pump(0.4)
    click(r, tr("Connect"))
    pump(0.5)
    click(r, tr("Cancel"))
    pump(3)
    check("cancel stops the attempt", row("HomeNetwork").net.state is None and row("HomeNetwork").stage == "idle")
    mock("SetDelay", 300, sig="u")

    # --- disconnect
    cur = w.current()
    rr = page.rows.get(cur.key) if cur else None
    if rr is not None:
        page.select(rr)
        pump(0.4)
        click(rr, tr("Disconnect"))
        pump(3, lambda: w.current() is None)
    check("disconnect", w.current() is None)

    # --- Wi-Fi off / on
    page.toggle.sw.set_active(False)
    pump(2, lambda: w.enabled() is False)
    check("toggle off", w.enabled() is False and page.placeholder.get_parent() is not None)
    shot(win, "13-wifi-off")
    page.toggle.sw.set_active(True)
    pump(3, lambda: w.enabled() and len(page.rows) > 3)
    check("toggle on → list back", len(page.rows) > 3)

    # connect HomeNetwork again for the properties page
    r = row("HomeNetwork")
    page.select(r)
    pump(0.4)
    click(r, tr("Connect"))
    pump(6, lambda: row("HomeNetwork").net.state == "connected")
    page.open_network(row("HomeNetwork").net.best_connection())
    pump(0.5)
    check("properties page", win.current == "wifi-network")
    shot(win, "14-properties")
    np = win.pages["wifi-network"]
    tg = first(np.content, Gtk.Switch)
    tg.set_active(True)
    pump(1)
    ck = first(np.content, Gtk.CheckButton)
    ck.set_active(False)
    pump(1)
    c = row("HomeNetwork").net.best_connection()
    check("metered + autoconnect saved", int(c.get_setting_connection().get_metered()) == 1
          and not c.get_setting_connection().get_autoconnect())
    click(np.content, tr("View"))
    pump(1)
    lbls = [x.get_label() for x in walk(win) if isinstance(x, Gtk.Label) and x.get_mapped()]
    check("view key dialog shows key", "correct-horse" in lbls)
    shot(win, "15-view-key")
    click(win, tr("Close"))
    win.go_back()
    pump(0.3)

    # --- known networks: list, search, forget, add
    win.navigate("wifi-known")
    kp = win.pages["wifi-known"]
    pump(0.5)
    shot(win, "16-known")
    kp.search.set_text("5g")
    pump(0.6)
    titles = [x.title_lbl.get_label() for x in walk(kp.list) if hasattr(x, "title_lbl") and x.get_mapped()]
    check("search filters", titles == ["Office-5G"], titles)
    click(kp.list, tr("Forget"))
    pump(2, lambda: not any(cc.get_id() == "Office-5G" for cc in w.wifi_connections()))
    check("forget", not any(cc.get_id() == "Office-5G" for cc in w.wifi_connections()))
    kp.search.set_text("")
    pump(0.5)
    click(kp.box, tr("Add network"))
    pump(0.3)
    dlg_entries = [x for x in walk(win.overlay) if isinstance(x, (Gtk.Entry, Gtk.PasswordEntry)) and x.get_mapped()]
    dlg_entries[0].set_text("Added-Net")
    dlg_entries[-1].set_text("added-pass")
    shot(win, "17-add-network")
    click(win.overlay, tr("Save"))
    pump(2, lambda: any(cc.get_id() == "Added-Net" for cc in w.wifi_connections()))
    check("add network saved", any(cc.get_id() == "Added-Net" for cc in w.wifi_connections()))

    win.navigate("wifi-hardware")
    pump(0.5)
    shot(win, "18-hardware")
    log = mock("Log")[0]
    check("no mock errors", not any("BUG" in x for x in log))
    print(f"\n{PASSED[0]} passed, {len(FAILED)} failed")
    app.quit()


def main():
    app = Gtk.Application(application_id="org.fenestra.SettingsWifiTest",
                          flags=Gio.ApplicationFlags.NON_UNIQUE)
    def safe(a):
        try:
            run(a)
        except BaseException as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            FAILED.append(f"crashed: {e}")
            print(f"\n{PASSED[0]} passed, {len(FAILED)} failed")
            a.quit()
    app.connect("activate", lambda a: GLib.idle_add(lambda: (safe(a), False)[1]))
    app.hold()
    try:
        app.run([])
    finally:
        for p in PROCS:
            p.terminate()
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
