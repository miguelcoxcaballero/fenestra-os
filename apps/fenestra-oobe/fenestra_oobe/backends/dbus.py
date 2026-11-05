"""Tiny synchronous D-Bus helpers (call them from worker threads)."""

from gi.repository import Gio, GLib

_TIMEOUT_MS = 60_000


def system_bus():
    return Gio.bus_get_sync(Gio.BusType.SYSTEM, None)


def call(bus_name, path, iface, method, params=None, reply_type=None, timeout=_TIMEOUT_MS,
         interactive=True):
    """Call a method on the system bus and return the unpacked reply tuple."""
    bus = system_bus()
    flags = Gio.DBusCallFlags.ALLOW_INTERACTIVE_AUTHORIZATION if interactive else Gio.DBusCallFlags.NONE
    reply = bus.call_sync(
        bus_name, path, iface, method, params,
        GLib.VariantType.new(reply_type) if reply_type else None,
        flags, timeout, None,
    )
    return reply.unpack() if reply is not None else ()


def get_property(bus_name, path, iface, prop):
    bus = system_bus()
    reply = bus.call_sync(
        bus_name, path, "org.freedesktop.DBus.Properties", "Get",
        GLib.Variant("(ss)", (iface, prop)), GLib.VariantType.new("(v)"),
        Gio.DBusCallFlags.NONE, 5000, None,
    )
    return reply.unpack()[0]
