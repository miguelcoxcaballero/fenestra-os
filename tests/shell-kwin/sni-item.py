#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Test StatusNotifierItem with a two-entry com.canonical.dbusmenu menu. Prints
"SNI_ACTIVATE x y" and "SNI_MENU_CLICKED id" so the bench can check the shell's tray host."""
import os
import sys

from gi.repository import Gio, GLib

ITEM_XML = """<node><interface name="org.kde.StatusNotifierItem">
<property name="Category" type="s" access="read"/><property name="Id" type="s" access="read"/>
<property name="Title" type="s" access="read"/><property name="Status" type="s" access="read"/>
<property name="IconName" type="s" access="read"/><property name="Menu" type="o" access="read"/>
<property name="ItemIsMenu" type="b" access="read"/>
<method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
<method name="ContextMenu"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
<signal name="NewIcon"/></interface></node>"""
MENU_XML = """<node><interface name="com.canonical.dbusmenu">
<method name="GetLayout"><arg type="i" direction="in"/><arg type="i" direction="in"/><arg type="as" direction="in"/>
<arg type="u" direction="out"/><arg type="(ia{sv}av)" direction="out"/></method>
<method name="AboutToShow"><arg type="i" direction="in"/><arg type="b" direction="out"/></method>
<method name="Event"><arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="in"/><arg type="u" direction="in"/></method>
</interface></node>"""
PROPS = {"Category": GLib.Variant("s", "ApplicationStatus"), "Id": GLib.Variant("s", "fenestra-test"),
         "Title": GLib.Variant("s", "Test item"), "Status": GLib.Variant("s", "Active"),
         "IconName": GLib.Variant("s", "fenestra-settings"), "Menu": GLib.Variant("o", "/Menu"),
         "ItemIsMenu": GLib.Variant("b", False)}


def entry(i, label):
    return GLib.Variant("(ia{sv}av)", (i, {"label": GLib.Variant("s", label)}, []))


def on_item(conn, sender, path, iface, method, params, inv):
    if method == "Activate":
        print("SNI_ACTIVATE", *params.unpack(), flush=True)
    inv.return_value(None)


def on_menu(conn, sender, path, iface, method, params, inv):
    if method == "GetLayout":
        root = (0, {"children-display": GLib.Variant("s", "submenu")}, [entry(1, "_Open"), entry(2, "Quit")])
        inv.return_value(GLib.Variant("(u(ia{sv}av))", (1, root)))
    elif method == "AboutToShow":
        inv.return_value(GLib.Variant("(b)", (False,)))
    else:
        print("SNI_MENU_CLICKED", params.unpack()[0], flush=True)
        inv.return_value(None)


def main():
    bus = Gio.bus_get_sync(Gio.BusType.SESSION)
    bus.register_object("/StatusNotifierItem", Gio.DBusNodeInfo.new_for_xml(ITEM_XML).interfaces[0], on_item,
                        lambda *a: PROPS[a[4]], None)
    bus.register_object("/Menu", Gio.DBusNodeInfo.new_for_xml(MENU_XML).interfaces[0], on_menu, None, None)
    name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
    Gio.bus_own_name_on_connection(bus, name, 0, None, None)
    bus.call_sync("org.kde.StatusNotifierWatcher", "/StatusNotifierWatcher", "org.kde.StatusNotifierWatcher",
                  "RegisterStatusNotifierItem", GLib.Variant("(s)", (name,)), None, 0, 5000, None)
    print("SNI_REGISTERED", name, flush=True)
    GLib.MainLoop().run()


if __name__ == "__main__":
    sys.exit(main())
