#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Wi-Fi backend (backends/wifi.py) against the mock NetworkManager on a private bus.

Never touches the real NetworkManager: a private dbus-daemon is started and used as the
"system" bus of this process only.

    python3 tests/test_wifi_backend.py        # exit 0 when every check passes
"""
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)


def start_private_nm():
    """Private bus + mock NM; returns (env address, [processes])."""
    base = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
    d = tempfile.mkdtemp(prefix="fwnm-", dir=base)   # short path: unix socket names are limited
    addr = f"unix:path={d}/bus"
    bus = subprocess.Popen(["dbus-daemon", "--session", f"--address={addr}", "--nofork"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        if os.path.exists(f"{d}/bus"):
            break
        time.sleep(0.05)
    env = dict(os.environ, DBUS_SYSTEM_BUS_ADDRESS=addr)
    mock = subprocess.Popen([sys.executable, "-u", os.path.join(HERE, "mock_networkmanager.py")], env=env,
                            stdout=subprocess.PIPE, stderr=sys.stderr, text=True)
    mock.stdout.readline()   # "mock NetworkManager ready"
    return addr, [mock, bus]


if __name__ == "__main__":
    ADDR, PROCS = start_private_nm()
    os.environ["DBUS_SYSTEM_BUS_ADDRESS"] = ADDR
    os.environ["FENESTRA_SETTINGS_LANG"] = "en"

from gi.repository import Gio, GLib  # noqa: E402

from fenestra_settings import i18n  # noqa: E402
from fenestra_settings.backends import wifi  # noqa: E402

FAILED, PASSED = [], [0]


def check(name, cond, detail=""):
    if cond:
        PASSED[0] += 1
        print(f"  ok   {name}")
    else:
        FAILED.append(name)
        print(f"  FAIL {name} {detail}")


def pump(secs=0.2, until=None):
    ctx = GLib.MainContext.default()
    end = time.monotonic() + secs
    while time.monotonic() < end:
        ctx.iteration(False)
        if until is not None and until():
            # let the coalesced change notification run too
            e2 = time.monotonic() + 0.15
            while time.monotonic() < e2:
                ctx.iteration(False)
                time.sleep(0.005)
            return True
        time.sleep(0.005)
    return until() if until else True


def mock(method, *args, sig=""):
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    r = bus.call_sync("org.freedesktop.NetworkManager", "/org/freedesktop/NetworkManager", "org.fenestra.MockNM",
                      method, GLib.Variant(f"({sig})", args) if sig else None, None, 0, 5000, None)
    return r.unpack() if r is not None else None


def net(w, ssid):
    for n in w.networks():
        if (ssid is None and n.hidden) or n.ssid == ssid:
            return n
    return None


def profiles(w, ssid):
    return [c for c in w.wifi_connections() if wifi.ssid_text(wifi._bytes(c.get_setting_wireless().get_ssid())) == ssid]


def run_connect(w, n, timeout=8, **kw):
    att = w.connect(n, **kw)
    pump(timeout, lambda: att.phase != "connecting")
    return att


def main():
    i18n.init("en")
    w = wifi.Wifi.get()
    pump(5, lambda: w.ready)
    check("client ready", w.available(), w.error)
    check("wifi enabled", w.enabled() is True)
    nets = w.networks()
    names = [n.ssid for n in nets]
    check("one row per SSID", names.count("HomeNetwork") == 1, names)
    check("strongest AP of the SSID", net(w, "HomeNetwork").strength == 82)
    check("hidden entry last", nets[-1].hidden, names)
    check("security PSK", net(w, "HomeNetwork").security == wifi.PSK)
    check("security SAE-only", net(w, "WPA3-Only").security == wifi.SAE)
    check("security transition = PSK", net(w, "Office-5G").security == wifi.PSK)
    check("security EAP", net(w, "Campus").security == wifi.EAP)
    check("security WEP", net(w, "Old-WEP").security == wifi.WEP)
    check("security open", net(w, "Cafe-Guest").security == wifi.OPEN)
    check("known network", net(w, "HomeNetwork").known and not net(w, "Office-5G").known)
    check("odd SSID decoded", net(w, 'Ca:fé "quoted"') is not None, names)
    check("Windows security names", net(w, "Office-5G").security_name == "WPA2/WPA3-Personal",
          net(w, "Office-5G").security_name)

    print("connect to a known network")
    att = run_connect(w, net(w, "HomeNetwork"))
    check("known → connected", att.phase == "connected", (att.phase, att.error))
    check("row shows Connected, secured", net(w, "HomeNetwork").status_text() == "Connected, secured")
    check("connected network first", w.networks()[0].ssid == "HomeNetwork")
    det = dict(w.details())
    check("properties: SSID/band/IPv4", det.get("SSID") == "HomeNetwork" and det.get("Network band") == "5 GHz"
          and det.get("IPv4 address") == "192.168.1.23", det)

    print("new network, wrong key")
    att = run_connect(w, net(w, "Office-5G"), key="wrong-key!", autoconnect=False)
    check("wrong key detected", att.phase == "failed" and att.error == "wrong-key", (att.phase, att.error))
    pump(1.0)
    check("no profile left behind", not profiles(w, "Office-5G"), [c.get_id() for c in profiles(w, "Office-5G")])

    print("new network, right key, Connect automatically off")
    att = run_connect(w, net(w, "Office-5G"), key="office-pass", autoconnect=False)
    check("connected", att.phase == "connected", (att.phase, att.error))
    p = profiles(w, "Office-5G")
    check("one profile saved", len(p) == 1, len(p))
    check("autoconnect off saved", p and p[0].get_setting_connection().get_autoconnect() is False)
    check("key-mgmt wpa-psk", p and p[0].get_setting_wireless_security().get_key_mgmt() == "wpa-psk")
    check("previous network no longer connected", net(w, "HomeNetwork").state is None)

    print("WPA3-only, open, enterprise, WEP, hidden")
    att = run_connect(w, net(w, "WPA3-Only"), key="sae-password")
    check("SAE connected", att.phase == "connected", (att.phase, att.error))
    check("key-mgmt sae", profiles(w, "WPA3-Only")[0].get_setting_wireless_security().get_key_mgmt() == "sae")
    att = run_connect(w, net(w, "Cafe-Guest"))
    check("open connected", att.phase == "connected", (att.phase, att.error))
    att = run_connect(w, net(w, "Campus"), identity="student", key="campus-pass")
    check("enterprise connected", att.phase == "connected", (att.phase, att.error))
    att = run_connect(w, net(w, "Old-WEP"), key="abcde")
    check("WEP connected", att.phase == "connected", (att.phase, att.error))
    att = run_connect(w, net(w, None), hidden_ssid="Secret-Lab", key="lab-password")
    check("hidden connected", att.phase == "connected", (att.phase, att.error))
    hp = profiles(w, "Secret-Lab")
    check("hidden profile marked hidden", hp and hp[0].get_setting_wireless().get_hidden())

    print("saved profile with a wrong key, then the right one")
    att = run_connect(w, net(w, "HomeNetwork"), key="not-the-key")
    check("wrong key on known network", att.error == "wrong-key", (att.phase, att.error))
    check("known profile kept", len(profiles(w, "HomeNetwork")) == 1)
    att = run_connect(w, net(w, "HomeNetwork"), key="correct-horse")
    check("retry with right key connects", att.phase == "connected", (att.phase, att.error))
    check("still one profile (updated, not duplicated)", len(profiles(w, "HomeNetwork")) == 1)

    print("cancel while connecting")
    mock("SetDelay", 1500, sig="u")
    att = w.connect(net(w, "Cafe-Guest"))
    pump(0.6)
    check("in progress", net(w, "Cafe-Guest").state == "connecting" or att.phase == "connecting")
    w.cancel()
    pump(2.5)
    check("cancelled: not connected", net(w, "Cafe-Guest").state is None and w.attempt is None)
    mock("SetDelay", 300, sig="u")

    print("out of range")
    att = run_connect(w, net(w, "HomeNetwork"))
    nh = net(w, "HomeNetwork")
    mock("RemoveNetwork", "Cafe-Guest", sig="s")
    pump(1, lambda: net(w, "Cafe-Guest") is None)
    check("AP removal reflected live", net(w, "Cafe-Guest") is None)
    mock("SetStrength", "Campus", 99, sig="si")
    pump(1, lambda: net(w, "Campus").strength == 99)
    check("strength change reflected live", net(w, "Campus").strength == 99)

    print("disconnect / forget / update / add / key")
    ok = []
    w.disconnect(lambda r: ok.append(r))
    pump(2, lambda: ok and net(w, "HomeNetwork").state is None)
    check("disconnected", ok == [True] and nh is not None and net(w, "HomeNetwork").state is None)
    conn = profiles(w, "HomeNetwork")[0]
    ok = []
    w.update(conn, lambda r: ok.append(r), autoconnect=False, metered=True)
    pump(2, lambda: ok)
    conn = profiles(w, "HomeNetwork")[0]
    check("update autoconnect/metered", ok == [True] and conn.get_setting_connection().get_autoconnect() is False
          and int(conn.get_setting_connection().get_metered()) == 1)
    key = []
    w.get_key(conn, lambda k: key.append(k))
    pump(2, lambda: key)
    check("view key", key == ["correct-horse"], key)
    ok = []
    w.forget(profiles(w, "HomeNetwork"), lambda r: ok.append(r))
    pump(2, lambda: ok and not profiles(w, "HomeNetwork"))
    check("forget", ok == [True] and not profiles(w, "HomeNetwork") and not net(w, "HomeNetwork").known)
    ok = []
    w.add_network("Added-Net", wifi.PSK, "added-pass", autoconnect=True, hidden=True, cb=lambda r, m: ok.append(r))
    pump(2, lambda: ok and profiles(w, "Added-Net"))
    check("add a network", ok == [True] and profiles(w, "Added-Net") and
          profiles(w, "Added-Net")[0].get_setting_wireless().get_hidden())
    ok = []
    w.add_network("Bad-Key", wifi.PSK, "short", cb=lambda r, m: ok.append((r, m)))
    pump(2, lambda: ok)
    check("add with an invalid key refused", ok and ok[0][0] is False, ok)

    print("radio")
    ok = []
    w.set_enabled(False, lambda r: ok.append(r))
    pump(2, lambda: w.enabled() is False)
    check("Wi-Fi off", w.enabled() is False and w.networks() == [])
    w.set_enabled(True, lambda r: ok.append(r))
    pump(2, lambda: w.enabled() is True)
    check("Wi-Fi on", w.enabled() is True and len(w.networks()) > 3)
    w.scan(force=True)
    pump(0.5)
    log = mock("Log")[0]
    check("scan requested", any("RequestScan" in x for x in log))
    check("no mock errors", not any(x.startswith("MOCK BUG") for x in log), [x for x in log if "BUG" in x])

    print(f"\n{PASSED[0]} passed, {len(FAILED)} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    try:
        rc = main()
    finally:
        for p in PROCS:
            p.terminate()
    sys.exit(rc)
