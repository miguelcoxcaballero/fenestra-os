# SPDX-License-Identifier: GPL-3.0-or-later
"""Command line: run the portal service, or show the dialog alone (tests, screenshots)."""
from __future__ import annotations

import argparse
import os
import sys

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from . import i18n  # noqa: E402


def parse_args(argv):
    p = argparse.ArgumentParser(prog="xdg-desktop-portal-fenestra",
                                description="Fenestra xdg-desktop-portal backend (Print).")
    p.add_argument("-r", "--replace", action="store_true", help="replace a running instance")
    p.add_argument("--demo", action="store_true", help="list made-up printers; never send jobs")
    p.add_argument("--lang", help="language (en, es); default from the environment")
    p.add_argument("--theme", choices=("light", "dark"), help="force light or dark")
    p.add_argument("--dialog", action="store_true", help="show the print dialog alone and print the result")
    p.add_argument("--screenshot", metavar="OUT.png", help="render the dialog to a PNG and exit")
    p.add_argument("--pdf", metavar="FILE", help="with --dialog/--screenshot: preview this PDF (as Print without a token)")
    p.add_argument("--page", choices=("main", "more"), default="main", help="with --screenshot: which settings page")
    p.add_argument("--ui", action="append", default=[], metavar="KEY=VALUE",
                   help="with --screenshot: dialog state, e.g. focus=none, menu=orientation, "
                        "to_file=1, allow_app=0, printer=NAME, hover=print")
    p.add_argument("--title", default="", help="document title for --dialog/--screenshot")
    p.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                   help="with --dialog/--screenshot: initial print setting (e.g. orientation=landscape)")
    return p.parse_args(argv[1:])


def _standalone(o):
    """--dialog / --screenshot: the same dialog the D-Bus path shows, without D-Bus."""
    from . import printing
    from .dialog import Options, PrintDialog
    doc = None
    if o.pdf:
        gi.require_version("Poppler", "0.18")
        from gi.repository import Poppler
        doc = Poppler.Document.new_from_file(Gio.File.new_for_path(os.path.abspath(o.pdf)).get_uri(), None)
    settings = Gtk.PrintSettings.new()
    for kv in o.set:
        k, _, v = kv.partition("=")
        settings.set(k, v)
    choice = printing.choice_from_gtk(settings, None)
    loop = GLib.MainLoop()
    result = {"code": 0}

    def done(response, ch):
        if not o.screenshot:
            s, ps = printing.choice_to_gtk(ch)
            print("response", response)
            if response == 0:
                print("settings", s.to_gvariant().print_(True))
                print("page-setup", ps.to_gvariant().print_(True))
        loop.quit()

    ui = dict(kv.partition("=")[::2] for kv in o.ui)
    opts = Options(title=o.title, demo=(o.demo or bool(o.screenshot)) and ui.get("demo") != "0",
                   no_save_dialog=True)
    dlg = PrintDialog(o.title or "Document", choice, opts, done, doc=doc)
    if o.page == "more":
        dlg.stack.set_transition_type(Gtk.StackTransitionType.NONE)
        dlg.stack.set_visible_child_name("more")
    dlg.present()
    if "printer" in ui:
        name = printing.PDF_PRINTER if ui["printer"] == "pdf" else ui["printer"]
        GLib.timeout_add(300, lambda: dlg._select_printer(name) and False)
    if ui.get("to_file"):
        dlg.to_file.set_active(ui["to_file"] in ("1", "on"))
    if ui.get("allow_app"):
        dlg.allow_app.set_active(ui["allow_app"] in ("1", "on"))
    for st in ("hover", "pressed"):
        if ui.get(st):
            dlg.force_state(ui[st], st)
    if ui.get("focus") == "none":
        dlg.set_focus_visible(False)
        dlg.set_focus(None)
    if ui.get("menu"):
        def open_menu():
            from .dialog import dropdown_popover
            dd = {"printer": dlg.printer_dd}.get(ui["menu"]) or getattr(dlg, ui["menu"])
            dd.grab_focus()
            dropdown_popover(dd).popup()
            return False
        GLib.timeout_add(600, open_menu)
    if o.screenshot:
        tries = {"n": 0}

        def shoot():
            if dlg.save_screenshot(o.screenshot):
                dlg.finish(1)
                return False
            tries["n"] += 1
            if tries["n"] > 20:
                result["code"] = 1
                loop.quit()
                return False
            return True
        GLib.timeout_add(int(os.environ.get("FENESTRA_SHOT_DELAY", "1200")), shoot)
    loop.run()
    return result["code"]


def main(argv=None):
    argv = argv or sys.argv
    o = parse_args(argv)
    i18n.init(o.lang)
    Gtk.init()
    from . import theme
    theme.init(o.theme, fixed_accent=bool(o.screenshot))
    if o.dialog or o.screenshot:
        return _standalone(o)

    from .service import BUS_NAME, PrintService, log
    loop = GLib.MainLoop()
    demo = o.demo or bool(os.environ.get("FENESTRA_PORTAL_DEMO"))
    state = {}

    def on_bus(conn, _name):
        state["service"] = PrintService(conn, demo=demo)

    def on_name(_conn, name):
        log(f"serving {name}{' (demo printers)' if demo else ''}")

    def on_lost(_conn, name):
        log(f"lost or could not own {name}; exiting")
        loop.quit()

    flags = Gio.BusNameOwnerFlags.ALLOW_REPLACEMENT
    if o.replace:
        flags |= Gio.BusNameOwnerFlags.REPLACE
    Gio.bus_own_name(Gio.BusType.SESSION, BUS_NAME, flags, on_bus, on_name, on_lost)
    loop.run()
    return 0
