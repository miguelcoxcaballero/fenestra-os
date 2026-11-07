#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""A real MPRIS player on the session bus for the lock screen bench (tests/lockscreen): what
Spotify or Firefox publish (identity, metadata with art, status, capabilities). Every control
that reaches it is printed as MPRIS_<METHOD> <status after> (and appended to /out/mpris.log)."""
import sys
from gi.repository import Gio, GLib

XML = """<node>
<interface name="org.mpris.MediaPlayer2">
 <method name="Raise"/><method name="Quit"/>
 <property name="Identity" type="s" access="read"/><property name="DesktopEntry" type="s" access="read"/>
 <property name="CanQuit" type="b" access="read"/><property name="CanRaise" type="b" access="read"/>
 <property name="HasTrackList" type="b" access="read"/>
 <property name="SupportedUriSchemes" type="as" access="read"/><property name="SupportedMimeTypes" type="as" access="read"/>
</interface>
<interface name="org.mpris.MediaPlayer2.Player">
 <method name="Next"/><method name="Previous"/><method name="Pause"/><method name="PlayPause"/>
 <method name="Stop"/><method name="Play"/>
 <method name="Seek"><arg direction="in" name="Offset" type="x"/></method>
 <method name="SetPosition"><arg direction="in" name="TrackId" type="o"/><arg direction="in" name="Position" type="x"/></method>
 <signal name="Seeked"><arg name="Position" type="x"/></signal>
 <property name="PlaybackStatus" type="s" access="read"/><property name="LoopStatus" type="s" access="read"/>
 <property name="Rate" type="d" access="read"/><property name="Shuffle" type="b" access="read"/>
 <property name="Metadata" type="a{sv}" access="read"/><property name="Volume" type="d" access="read"/>
 <property name="Position" type="x" access="read"/><property name="MinimumRate" type="d" access="read"/>
 <property name="MaximumRate" type="d" access="read"/><property name="CanGoNext" type="b" access="read"/>
 <property name="CanGoPrevious" type="b" access="read"/><property name="CanPlay" type="b" access="read"/>
 <property name="CanPause" type="b" access="read"/><property name="CanSeek" type="b" access="read"/>
 <property name="CanControl" type="b" access="read"/>
</interface></node>"""
TRACKS = [("Mediterráneo", "Joan Manuel Serrat"), ("Lucha de gigantes", "Nacha Pop"), ("La flaca", "Jarabe de Palo")]
state = {"status": "Playing", "track": 0}
ART = sys.argv[1] if len(sys.argv) > 1 else ""


def metadata():
    title, artist = TRACKS[state["track"]]
    md = {"mpris:trackid": GLib.Variant("o", f"/org/fenestra/bench/track/{state['track']}"),
          "mpris:length": GLib.Variant("x", 213_000_000), "xesam:title": GLib.Variant("s", title),
          "xesam:artist": GLib.Variant("as", [artist]), "xesam:album": GLib.Variant("s", "Bench")}
    if ART:
        md["mpris:artUrl"] = GLib.Variant("s", "file://" + ART)
    return md


def props(iface):
    if iface == "org.mpris.MediaPlayer2":
        return {"Identity": GLib.Variant("s", "Spotify"), "DesktopEntry": GLib.Variant("s", "spotify"),
                "CanQuit": GLib.Variant("b", False), "CanRaise": GLib.Variant("b", False),
                "HasTrackList": GLib.Variant("b", False), "SupportedUriSchemes": GLib.Variant("as", []),
                "SupportedMimeTypes": GLib.Variant("as", [])}
    return {"PlaybackStatus": GLib.Variant("s", state["status"]), "LoopStatus": GLib.Variant("s", "None"),
            "Rate": GLib.Variant("d", 1.0), "Shuffle": GLib.Variant("b", False), "Metadata": GLib.Variant("a{sv}", metadata()),
            "Volume": GLib.Variant("d", 1.0), "Position": GLib.Variant("x", 0), "MinimumRate": GLib.Variant("d", 1.0),
            "MaximumRate": GLib.Variant("d", 1.0), "CanGoNext": GLib.Variant("b", True), "CanGoPrevious": GLib.Variant("b", True),
            "CanPlay": GLib.Variant("b", True), "CanPause": GLib.Variant("b", True), "CanSeek": GLib.Variant("b", False),
            "CanControl": GLib.Variant("b", True)}


def changed(conn, names):
    p = props("org.mpris.MediaPlayer2.Player")
    conn.emit_signal(None, "/org/mpris/MediaPlayer2", "org.freedesktop.DBus.Properties", "PropertiesChanged",
                     GLib.Variant("(sa{sv}as)", ("org.mpris.MediaPlayer2.Player", {n: p[n] for n in names}, [])))


def call(conn, sender, path, iface, method, params, inv):
    if method in ("PlayPause", "Play", "Pause", "Stop"):
        state["status"] = {"PlayPause": "Paused" if state["status"] == "Playing" else "Playing",
                           "Play": "Playing", "Pause": "Paused", "Stop": "Stopped"}[method]
        changed(conn, ["PlaybackStatus"])
    elif method in ("Next", "Previous"):
        state["track"] = (state["track"] + (1 if method == "Next" else -1)) % len(TRACKS)
        changed(conn, ["Metadata"])
    line = f"MPRIS_{method.upper()} {state['status']} {TRACKS[state['track']][0]}"
    print(line, flush=True)
    try:
        with open("/out/mpris.log", "a") as f:
            f.write(line + "\n")
    except OSError:
        pass
    inv.return_value(None)


def get_prop(conn, sender, path, iface, name):
    return props(iface)[name]


def acquired(conn, name):
    for i in Gio.DBusNodeInfo.new_for_xml(XML).interfaces:
        conn.register_object("/org/mpris/MediaPlayer2", i, call, get_prop, None)


Gio.bus_own_name(Gio.BusType.SESSION, "org.mpris.MediaPlayer2.spotify", Gio.BusNameOwnerFlags.NONE,
                 acquired, lambda *a: print("MPRIS_READY", flush=True), lambda *a: print("MPRIS_LOST", flush=True))
GLib.MainLoop().run()
