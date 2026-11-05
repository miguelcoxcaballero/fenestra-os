"""AccountsService (current user) + fprintd probing."""
from __future__ import annotations

import os
import pwd

from gi.repository import Gio, GLib

from .. import util

ACC = "org.freedesktop.Accounts"


class CurrentUser:
    def __init__(self):
        self.uid = os.getuid()
        pw = pwd.getpwuid(self.uid)
        self.username = pw.pw_name
        gecos = (pw.pw_gecos or "").split(",")[0]
        self.real_name = gecos or self.username
        self.icon_file = None
        self.account_type = 0
        self.email = ""
        self.path = None
        self.proxy = None
        if util.DEMO:
            from . import demo
            self.username, self.real_name, self.account_type = demo.USER_LOGIN, demo.USER_NAME, 1
            return
        self._load()

    def _load(self):
        if util.DEMO:
            return
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            r = bus.call_sync(ACC, "/org/freedesktop/Accounts", ACC, "FindUserById",
                              GLib.Variant("(x)", (self.uid,)), GLib.VariantType("(o)"),
                              Gio.DBusCallFlags.NONE, 2000, None)
            self.path = r.unpack()[0]
            self.proxy = Gio.DBusProxy.new_sync(bus, Gio.DBusProxyFlags.NONE, None, ACC,
                                                self.path, ACC + ".User", None)
        except GLib.Error:
            self.proxy = None
        if self.proxy:
            self.real_name = util.prop(self.proxy, "RealName") or self.real_name
            ic = util.prop(self.proxy, "IconFile")
            if ic and os.path.isfile(ic) and os.access(ic, os.R_OK) and os.path.getsize(ic) > 0:
                self.icon_file = ic
            self.account_type = util.prop(self.proxy, "AccountType", 0)
            self.email = util.prop(self.proxy, "Email", "") or ""
        if not self.icon_file:
            face = os.path.expanduser("~/.face")
            if os.path.isfile(face):
                self.icon_file = face

    @property
    def is_admin(self) -> bool:
        return self.account_type == 1

    def initials(self) -> str:
        parts = [p for p in self.real_name.replace(".", " ").split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:1].upper()
        return (parts[0][:1] + parts[-1][:1]).upper()

    def set_icon_file(self, path, callback=None):
        if not self.path:
            if callback:
                callback(False, "AccountsService unavailable")
            return
        util.dbus_call(Gio.BusType.SYSTEM, ACC, self.path, ACC + ".User", "SetIconFile",
                       GLib.Variant("(s)", (path,)), callback)

    def set_real_name(self, name, callback=None):
        if not self.path:
            return
        util.dbus_call(Gio.BusType.SYSTEM, ACC, self.path, ACC + ".User", "SetRealName",
                       GLib.Variant("(s)", (name,)), callback)


_user = None


def current_user() -> CurrentUser:
    global _user
    if _user is None:
        _user = CurrentUser()
    return _user


def list_users():
    """Other human users (uid >= 1000)."""
    if util.DEMO:
        from . import demo
        return demo.users()
    out = []
    for pw in pwd.getpwall():
        if 1000 <= pw.pw_uid < 60000 and pw.pw_shell not in ("/sbin/nologin", "/usr/sbin/nologin", "/bin/false"):
            out.append((pw.pw_name, (pw.pw_gecos or "").split(",")[0] or pw.pw_name, pw.pw_uid))
    return out


def fingerprint_status(callback):
    """callback(state) with state in 'none', 'enrolled', 'not-enrolled'."""
    if util.DEMO:
        from . import demo
        demo.later(callback, "not-enrolled")
        return
    if not util.have("fprintd-list"):
        GLib.idle_add(lambda: (callback("none"), False)[1])
        return

    def done(ok, out, err):
        text = (out + err).lower()
        if "no devices available" in text or "no devices" in text:
            callback("none")
        elif "fingers" in text and "has no fingers" not in text and "#" in text:
            callback("enrolled")
        elif "fingerprint" in text or "device" in text:
            callback("not-enrolled")
        else:
            callback("none")
    util.run_async(["fprintd-list", current_user().username], done)
