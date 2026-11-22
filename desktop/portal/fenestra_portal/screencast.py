# SPDX-License-Identifier: GPL-3.0-or-later
"""org.freedesktop.impl.portal.ScreenCast, passed through to KDE's backend (which records the
screen through KWin), with one difference taken from Windows: casting to a wireless display.

On Windows, choosing a display in the Cast page (Win+K) is the whole consent: the screen is
duplicated on it straight away, with no "what do you want to share" step. GNOME Network Displays
asks the screencast portal for a monitor, so KDE would show its chooser. When Fenestra Shell has
just started a stream (the user clicked a display), it leaves a grant in
$XDG_RUNTIME_DIR/fenestra/cast-grant with the main screen's position; the next screencast
session from an unsandboxed process gets KDE restore data naming that screen, and KDE starts it
without asking. Every other request reaches KDE unchanged and shows its chooser as before.

KDE's restore data (xdg-desktop-portal-kde src/restoredata.cpp, screencast.cpp):
("KDE", 1, <QDataStream of a QVariantMap {"outputs": [unique id]}>), where an output's unique id
is the screen's logical position, "XxY".
"""
from __future__ import annotations

import json
import os
import struct
import time

from gi.repository import Gio, GLib

KDE = "org.freedesktop.impl.portal.desktop.kde"
PATH = "/org/freedesktop/portal/desktop"
IFACE = "org.freedesktop.impl.portal.ScreenCast"
SESSION_IFACE = "org.freedesktop.impl.portal.Session"
REQUEST_IFACE = "org.freedesktop.impl.portal.Request"
GRANT = os.path.join(GLib.get_user_runtime_dir(), "fenestra", "cast-grant")
GRANT_MAX_AGE_S = 30
FOREVER = GLib.MAXINT   # the chooser may stay open as long as the user likes

INTROSPECTION = """
<node>
  <interface name="org.freedesktop.impl.portal.ScreenCast">
    <method name="CreateSession">
      <arg type="o" name="handle" direction="in"/>
      <arg type="o" name="session_handle" direction="in"/>
      <arg type="s" name="app_id" direction="in"/>
      <arg type="a{sv}" name="options" direction="in"/>
      <arg type="u" name="response" direction="out"/>
      <arg type="a{sv}" name="results" direction="out"/>
    </method>
    <method name="SelectSources">
      <arg type="o" name="handle" direction="in"/>
      <arg type="o" name="session_handle" direction="in"/>
      <arg type="s" name="app_id" direction="in"/>
      <arg type="a{sv}" name="options" direction="in"/>
      <arg type="u" name="response" direction="out"/>
      <arg type="a{sv}" name="results" direction="out"/>
    </method>
    <method name="Start">
      <arg type="o" name="handle" direction="in"/>
      <arg type="o" name="session_handle" direction="in"/>
      <arg type="s" name="app_id" direction="in"/>
      <arg type="s" name="parent_window" direction="in"/>
      <arg type="a{sv}" name="options" direction="in"/>
      <arg type="u" name="response" direction="out"/>
      <arg type="a{sv}" name="results" direction="out"/>
    </method>
    <property name="AvailableSourceTypes" type="u" access="read"/>
    <property name="AvailableCursorModes" type="u" access="read"/>
    <property name="version" type="u" access="read"/>
  </interface>
  <interface name="org.freedesktop.impl.portal.Session">
    <method name="Close"/>
    <signal name="Closed"/>
    <property name="version" type="u" access="read"/>
  </interface>
  <interface name="org.freedesktop.impl.portal.Request">
    <method name="Close"/>
  </interface>
</node>
"""
NODE = Gio.DBusNodeInfo.new_for_xml(INTROSPECTION)


def _log(msg):
    import sys
    print(f"xdg-desktop-portal-fenestra: screencast: {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------- Qt's QDataStream (big endian)
def _qstring(s: str) -> bytes:
    data = s.encode("utf-16-be")
    return struct.pack(">I", len(data)) + data


def _qvariant_string(s: str) -> bytes:
    return struct.pack(">Ib", 10, 0) + _qstring(s)            # QMetaType::QString, not null


def _qvariant_list(items: list[bytes]) -> bytes:
    return struct.pack(">IbI", 9, 0, len(items)) + b"".join(items)   # QMetaType::QVariantList


def kde_restore_data(output_id: str) -> GLib.Variant:
    payload = struct.pack(">I", 1) + _qstring("outputs") + _qvariant_list([_qvariant_string(output_id)])
    return GLib.Variant("(suv)", ("KDE", 1, GLib.Variant("ay", payload)))


def take_grant() -> str | None:
    """The main screen's id if Fenestra Shell started a cast a moment ago (used once)."""
    try:
        with open(GRANT, encoding="utf-8") as f:
            grant = json.load(f)
        os.unlink(GRANT)
    except (OSError, ValueError):
        return None
    if time.time() - float(grant.get("time", 0)) > GRANT_MAX_AGE_S:
        return None
    output = str(grant.get("output") or "")
    return output or None


class ScreenCastProxy:
    def __init__(self, conn: Gio.DBusConnection):
        self.conn = conn
        self.sessions: dict[str, int] = {}     # session path -> registration id
        self.granted: dict[str, str] = {}       # session -> screen, for casts the user just chose
        conn.register_object(PATH, NODE.lookup_interface(IFACE), self._on_call, self._on_get, None)
        # KDE closes a session itself when the stream ends ("Stop sharing", the display went away)
        conn.signal_subscribe(KDE, SESSION_IFACE, "Closed", None, None,
                              Gio.DBusSignalFlags.NONE, self._kde_closed)

    # -------------------------------------------------------------- properties (KDE's values)
    def _on_get(self, conn, sender, path, iface, prop):
        try:
            r = conn.call_sync(KDE, PATH, "org.freedesktop.DBus.Properties", "Get",
                               GLib.Variant("(ss)", (IFACE, prop)), GLib.VariantType("(v)"),
                               Gio.DBusCallFlags.NONE, 5000, None)
            return r.get_child_value(0).get_variant()
        except GLib.Error as e:
            _log(f"{prop}: {e.message}")
            return GLib.Variant("u", 0)

    # -------------------------------------------------------------- methods
    def _on_call(self, conn, sender, path, iface, method, params, invocation):
        handle, session = params.get_child_value(0).get_string(), params.get_child_value(1).get_string()
        app_id = params.get_child_value(2).get_string()
        if method == "CreateSession":
            self._export_session(session)
            if not app_id:
                output = take_grant()
                if output:
                    self.granted[session] = output
        elif method == "SelectSources" and session in self.granted:
            given = params.get_child_value(3)
            opts = {}
            for i in range(given.n_children()):
                entry = given.get_child_value(i)
                opts[entry.get_child_value(0).get_string()] = entry.get_child_value(1).get_variant()
            opts["restore_data"] = kde_restore_data(self.granted[session])
            params = GLib.Variant("(oosa{sv})", (handle, session, app_id, opts))
            _log(f"{session}: the user chose a wireless display; sharing screen {self.granted[session]}")
        request = self._export_request(handle)

        def done(c, res):
            self._unexport(request)
            try:
                invocation.return_value(c.call_finish(res))
            except GLib.Error as e:
                _log(f"{method}: {e.message}")
                invocation.return_value(GLib.Variant("(ua{sv})", (2, {})))
        conn.call(KDE, PATH, IFACE, method, params, GLib.VariantType("(ua{sv})"),
                  Gio.DBusCallFlags.NONE, FOREVER, None, done)

    # -------------------------------------------------------------- Session / Request objects
    def _export_session(self, path):
        if path in self.sessions:
            return

        def call(conn, sender, p, iface, method, params, invocation):
            if method == "Close":
                conn.call(KDE, p, SESSION_IFACE, "Close", None, None, Gio.DBusCallFlags.NONE, -1, None, None)
                self._drop_session(p)
                invocation.return_value(None)

        def get(conn, sender, p, iface, prop):
            return GLib.Variant("u", 1)
        try:
            self.sessions[path] = self.conn.register_object(path, NODE.lookup_interface(SESSION_IFACE), call, get, None)
        except GLib.Error as e:
            _log(f"cannot export {path}: {e.message}")

    def _drop_session(self, path):
        reg = self.sessions.pop(path, 0)
        if reg:
            self.conn.unregister_object(reg)
        self.granted.pop(path, None)

    def _kde_closed(self, conn, sender, path, iface, signal, params):
        if path in self.sessions:
            self.conn.emit_signal(None, path, SESSION_IFACE, "Closed", None)
            self._drop_session(path)

    def _export_request(self, path):
        def call(conn, sender, p, iface, method, params, invocation):
            if method == "Close":
                conn.call(KDE, p, REQUEST_IFACE, "Close", None, None, Gio.DBusCallFlags.NONE, -1, None, None)
                invocation.return_value(None)
        try:
            return self.conn.register_object(path, NODE.lookup_interface(REQUEST_IFACE), call, None, None)
        except GLib.Error:
            return 0

    def _unexport(self, reg):
        if reg:
            self.conn.unregister_object(reg)
