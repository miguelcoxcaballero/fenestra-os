#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Test MPRIS player (demo metadata): prints MPRIS_<METHOD> when a control is used."""
from gi.repository import Gio, GLib

XML = """<node>
<interface name="org.mpris.MediaPlayer2"><property name="Identity" type="s" access="read"/>
<property name="DesktopEntry" type="s" access="read"/></interface>
<interface name="org.mpris.MediaPlayer2.Player">
<property name="PlaybackStatus" type="s" access="read"/><property name="Metadata" type="a{sv}" access="read"/>
<property name="CanGoNext" type="b" access="read"/><property name="CanGoPrevious" type="b" access="read"/>
<method name="PlayPause"/><method name="Next"/><method name="Previous"/></interface></node>"""
state = {"status": "Playing"}


def props(iface):
    if iface == "org.mpris.MediaPlayer2":
        return {"Identity": GLib.Variant("s", "Demo Player"), "DesktopEntry": GLib.Variant("s", "org.fenestra.Paint")}
    return {"PlaybackStatus": GLib.Variant("s", state["status"]),
            "Metadata": GLib.Variant("a{sv}", {"xesam:title": GLib.Variant("s", "Canción de prueba"),
                                               "xesam:artist": GLib.Variant("as", ["Artista Demo"])}),
            "CanGoNext": GLib.Variant("b", True), "CanGoPrevious": GLib.Variant("b", True)}


def call(conn, sender, path, iface, method, params, inv):
    print("MPRIS_" + method.upper(), flush=True)
    if method == "PlayPause":
        state["status"] = "Paused" if state["status"] == "Playing" else "Playing"
        conn.emit_signal(None, path, "org.freedesktop.DBus.Properties", "PropertiesChanged",
                         GLib.Variant("(sa{sv}as)", ("org.mpris.MediaPlayer2.Player",
                                                     {"PlaybackStatus": GLib.Variant("s", state["status"])}, [])))
    inv.return_value(None)


bus = Gio.bus_get_sync(Gio.BusType.SESSION)
node = Gio.DBusNodeInfo.new_for_xml(XML)
for iface in node.interfaces:
    bus.register_object("/org/mpris/MediaPlayer2", iface, call, lambda c, s, p, i, prop: props(i)[prop], None)
Gio.bus_own_name_on_connection(bus, "org.mpris.MediaPlayer2.demo", 0, None, None)
print("MPRIS_READY", flush=True)
GLib.MainLoop().run()
