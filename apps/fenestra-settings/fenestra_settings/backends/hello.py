"""Fenestra Hello backends: face recognition (Howdy) and fingerprints (fprintd)."""
from __future__ import annotations

import configparser
import os

from gi.repository import Gio, GLib

from .. import util
from ..i18n import N_

HOWDY_CONFIGS = ["/etc/howdy/config.ini", "/usr/lib64/security/howdy/config.ini",
                 "/usr/lib/security/howdy/config.ini"]
HOWDY_MODEL_DIRS = ["/etc/howdy/models", "/usr/lib64/security/howdy/models",
                    "/usr/lib/security/howdy/models"]

FPRINT = "net.reactivated.Fprint"
FPRINT_MGR = "/net/reactivated/Fprint/Manager"

FINGERS = ["right-index-finger", "left-index-finger", "right-thumb", "left-thumb",
           "right-middle-finger", "left-middle-finger", "right-ring-finger", "left-ring-finger",
           "right-little-finger", "left-little-finger"]


def _user():
    from .accounts import current_user
    return current_user().username


# =========================================================================== Howdy
def howdy_available() -> bool:
    if util.DEMO:
        return True
    return util.have("howdy") and howdy_config_path() is not None


def howdy_config_path():
    for p in HOWDY_CONFIGS:
        if os.path.isfile(p):
            return p
    return None


def howdy_config() -> configparser.ConfigParser:
    cp = configparser.ConfigParser(interpolation=None)
    p = howdy_config_path()
    if p:
        try:
            cp.read(p)
        except configparser.Error:
            pass
    return cp


def howdy_device() -> str | None:
    if util.DEMO:
        return None
    dev = howdy_config().get("video", "device_path", fallback="")
    return dev if dev and os.path.exists(dev) else None


def howdy_enrolled() -> bool:
    """A model file exists for the user (directory is world-readable, file is not)."""
    if util.DEMO:
        return False
    for d in HOWDY_MODEL_DIRS:
        if os.path.exists(os.path.join(d, _user() + ".dat")):
            return True
    return False


def howdy_auto_dismiss() -> bool:
    if util.DEMO:
        return True
    return howdy_config().getboolean("core", "no_confirmation", fallback=False)


def _pkexec_howdy(args, callback):
    """Howdy needs root: run it through pkexec (polkit asks for the admin password)."""
    if not util.have("pkexec"):
        GLib.idle_add(lambda: (callback(False, "pkexec is not installed"), False)[1])
        return
    howdy = GLib.find_program_in_path("howdy") or "/usr/bin/howdy"

    def done(ok, out, err):
        text = (out + "\n" + err).strip()
        if not ok:
            low = text.lower()
            if "not authorized" in low or "dismissed" in low or "authentication" in low or not text:
                text = "auth"
        callback(ok, text)
    util.run_async(["pkexec", howdy, "-U", _user(), "-y"] + args, done, mutating=True)


def howdy_add(callback, label="Fenestra"):
    """callback(ok, message). Captures the face model (takes a few seconds)."""
    _pkexec_howdy(["add", label], callback)


def howdy_clear(callback):
    _pkexec_howdy(["clear"], callback)


def howdy_set_auto_dismiss(on: bool, callback):
    _pkexec_howdy(["set", "no_confirmation", "true" if on else "false"], callback)


def howdy_error_text(msg: str) -> str:
    from ..i18n import _
    low = (msg or "").lower()
    if msg == "auth":
        return _("Authentication was cancelled or failed.")
    if "no face detected" in low:
        return _("We couldn't see your face. Make sure you're looking directly at the camera.")
    if "multiple faces" in low:
        return _("More than one face was detected. Make sure you're alone in front of the camera.")
    if "dark" in low or "black frames" in low:
        return _("The camera image was too dark. Check that the infrared camera is working.")
    if "pkexec is not installed" in low:
        return _("pkexec is not installed, so Fenestra Hello can't be configured.")
    return _("We couldn't set up facial recognition.")


# =========================================================================== fprintd
class FingerprintDevice:
    """Thin async wrapper around one fprintd device."""

    def __init__(self, path, name, stages, scan_type):
        self.path, self.name, self.stages, self.scan_type = path, name, stages, scan_type
        self._sub = 0
        self.claimed = False

    def _call(self, method, args=None, callback=None, reply=None):
        util.dbus_call(Gio.BusType.SYSTEM, FPRINT, self.path, FPRINT + ".Device", method, args,
                       callback, mutating=method not in ("ListEnrolledFingers",), interactive=True,
                       reply_type=GLib.VariantType(reply) if reply else None)

    def list_fingers(self, callback):
        if util.DEMO:
            GLib.idle_add(lambda: (callback(["right-index-finger"]), False)[1])
            return
        def done(ok, res):
            if ok and res:
                callback(list(res[0]))
            else:
                callback([])  # "no enrolled prints" is reported as an error
        self._call("ListEnrolledFingers", GLib.Variant("(s)", (_user(),)), done, "(as)")

    def claim(self, callback):
        def done(ok, res):
            self.claimed = ok
            callback(ok, res)
        self._call("Claim", GLib.Variant("(s)", ("",)), done)

    def release(self):
        if self.claimed:
            self._call("Release", None, lambda *_: None)
            self.claimed = False

    def enroll(self, finger, on_status, callback):
        """on_status(result, done). callback(ok, error) after EnrollStart returns."""
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

        def sig(_conn, _sender, _path, _iface, _name, params):
            result, done = params.unpack()
            on_status(result, done)
            if done:
                self.stop_listening()
        self._bus = bus
        self._sub = bus.signal_subscribe(FPRINT, FPRINT + ".Device", "EnrollStatus", self.path, None,
                                         Gio.DBusSignalFlags.NONE, sig)
        self._call("EnrollStart", GLib.Variant("(s)", (finger,)), callback)

    def stop_listening(self):
        if self._sub:
            self._bus.signal_unsubscribe(self._sub)
            self._sub = 0

    def enroll_stop(self):
        self.stop_listening()
        self._call("EnrollStop", None, lambda *_: None)

    def delete_all(self, callback):
        self._call("DeleteEnrolledFingers2", None, callback)


def fingerprint_device(callback):
    """callback(FingerprintDevice or None)."""
    if util.DEMO:
        GLib.idle_add(lambda: (callback(FingerprintDevice("/demo", "Fingerprint sensor", 10, "press")),
                               False)[1])
        return

    def got(ok, res):
        if not ok or not res:
            callback(None)
            return
        path = res[0]
        p = util.dbus_proxy_sync(Gio.BusType.SYSTEM, FPRINT, path, FPRINT + ".Device")
        callback(FingerprintDevice(path, util.prop(p, "name", ""), util.prop(p, "num-enroll-stages", 5) or 5,
                                   util.prop(p, "scan-type", "press")))
    util.dbus_call(Gio.BusType.SYSTEM, FPRINT, FPRINT_MGR, FPRINT + ".Manager", "GetDefaultDevice", None, got,
                   mutating=False, interactive=False, reply_type=GLib.VariantType("(o)"))


def next_finger(enrolled):
    for f in FINGERS:
        if f not in enrolled:
            return f
    return None


FINGER_LABELS = {
    "right-index-finger": N_("Right index finger"), "left-index-finger": N_("Left index finger"),
    "right-thumb": N_("Right thumb"), "left-thumb": N_("Left thumb"),
    "right-middle-finger": N_("Right middle finger"), "left-middle-finger": N_("Left middle finger"),
    "right-ring-finger": N_("Right ring finger"), "left-ring-finger": N_("Left ring finger"),
    "right-little-finger": N_("Right little finger"), "left-little-finger": N_("Left little finger"),
}
