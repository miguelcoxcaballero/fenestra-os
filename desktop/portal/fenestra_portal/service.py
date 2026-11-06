# SPDX-License-Identifier: GPL-3.0-or-later
"""D-Bus side: org.freedesktop.impl.portal.Print on /org/freedesktop/portal/desktop.

Interface: /usr/share/dbus-1/interfaces/org.freedesktop.impl.portal.Print.xml
(xdg-desktop-portal 1.22). Each call gets a Request object at its handle path so the
frontend can Close() it; the method returns (response, results) when the user is done:
0 = success, 1 = cancelled, 2 = other error.
"""
from __future__ import annotations

import os
import sys
import time

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from . import metrics, printing  # noqa: E402
from .dialog import Options, PrintDialog  # noqa: E402

BUS_NAME = "org.freedesktop.impl.portal.desktop.fenestra"
OBJECT_PATH = "/org/freedesktop/portal/desktop"

INTROSPECTION = """
<node>
  <interface name="org.freedesktop.impl.portal.Print">
    <method name="PreparePrint">
      <arg type="o" name="handle" direction="in"/>
      <arg type="s" name="app_id" direction="in"/>
      <arg type="s" name="parent_window" direction="in"/>
      <arg type="s" name="title" direction="in"/>
      <arg type="a{sv}" name="settings" direction="in"/>
      <arg type="a{sv}" name="page_setup" direction="in"/>
      <arg type="a{sv}" name="options" direction="in"/>
      <arg type="u" name="response" direction="out"/>
      <arg type="a{sv}" name="results" direction="out"/>
    </method>
    <method name="Print">
      <arg type="o" name="handle" direction="in"/>
      <arg type="s" name="app_id" direction="in"/>
      <arg type="s" name="parent_window" direction="in"/>
      <arg type="s" name="title" direction="in"/>
      <arg type="h" name="fd" direction="in"/>
      <arg type="a{sv}" name="options" direction="in"/>
      <arg type="u" name="response" direction="out"/>
      <arg type="a{sv}" name="results" direction="out"/>
    </method>
  </interface>
  <interface name="org.freedesktop.impl.portal.Request">
    <method name="Close"/>
  </interface>
</node>
"""

NODE = Gio.DBusNodeInfo.new_for_xml(INTROSPECTION)
PRINT_IFACE = NODE.lookup_interface("org.freedesktop.impl.portal.Print")
REQUEST_IFACE = NODE.lookup_interface("org.freedesktop.impl.portal.Request")

RESPONSE_OK, RESPONSE_CANCELLED, RESPONSE_OTHER = 0, 1, 2


def log(msg):
    print(f"xdg-desktop-portal-fenestra: {msg}", file=sys.stderr, flush=True)


class Request:
    """One pending call: the exported Request object plus the method invocation to answer."""

    def __init__(self, service, handle, invocation):
        self.service = service
        self.handle = handle
        self.invocation = invocation
        self.dialog = None
        self.cleanup = []
        self.closed = False
        try:
            self.reg_id = service.conn.register_object(handle, REQUEST_IFACE, self._on_call, None, None)
        except GLib.Error as e:
            log(f"cannot export {handle}: {e.message}")
            self.reg_id = 0

    def _on_call(self, conn, sender, path, iface, method, params, invocation):
        if method == "Close":
            invocation.return_value(None)
            self.closed = True
            if self.dialog is not None:
                self.dialog.finish(RESPONSE_CANCELLED)
            self.reply(RESPONSE_OTHER)

    def reply(self, response, results=None):
        if self.invocation is None:
            return
        inv, self.invocation = self.invocation, None
        inv.return_value(GLib.Variant("(ua{sv})", (response, results or {})))
        if self.reg_id:
            self.service.conn.unregister_object(self.reg_id)
            self.reg_id = 0
        for fn in self.cleanup:
            try:
                fn()
            except Exception as e:  # noqa: BLE001
                log(f"cleanup: {e}")


class PrintService:
    def __init__(self, conn: Gio.DBusConnection, demo=False):
        self.conn = conn
        self.demo = demo
        self.tokens: dict[int, tuple[printing.Choice, float]] = {}
        self._next_token = int(time.time()) & 0xFFFF
        self.reg_id = conn.register_object(OBJECT_PATH, PRINT_IFACE, self._on_call, None, None)

    # ------------------------------------------------------------------ dispatch
    def _on_call(self, conn, sender, path, iface, method, params, invocation):
        try:
            if method == "PreparePrint":
                self.prepare_print(params, invocation)
            elif method == "Print":
                self.print_(params, invocation)
            else:
                invocation.return_dbus_error("org.freedesktop.DBus.Error.UnknownMethod", method)
        except Exception as e:  # noqa: BLE001 - never leave the frontend waiting
            log(f"{method} failed: {e!r}")
            import traceback
            traceback.print_exc()
            try:
                invocation.return_value(GLib.Variant("(ua{sv})", (RESPONSE_OTHER, {})))
            except Exception:  # noqa: BLE001
                pass

    @staticmethod
    def _opts(options: dict, title: str, parent: str, demo: bool) -> Options:
        return Options(title=title, accept_label=options.get("accept_label", ""),
                       modal=options.get("modal", True),
                       has_current=options.get("has_current_page", False),
                       has_selection=options.get("has_selected_pages", False),
                       parent_window=parent, demo=demo,
                       no_save_dialog=bool(os.environ.get("FENESTRA_PORTAL_NO_SAVE_DIALOG")))

    def _expire_tokens(self):
        now = time.time()
        for t in [t for t, (_c, ts) in self.tokens.items() if now - ts > metrics.TOKEN_LIFETIME_S]:
            del self.tokens[t]

    # ------------------------------------------------------------------ PreparePrint
    def prepare_print(self, params, invocation):
        handle, app_id, parent, title = (params.get_child_value(i).unpack() for i in range(4))
        settings_v, setup_v, options_v = (params.get_child_value(i) for i in (4, 5, 6))
        options = options_v.unpack()
        log(f"PreparePrint app={app_id!r} title={title!r}")
        settings = Gtk.PrintSettings.new_from_gvariant(settings_v)
        setup = None
        if setup_v.n_children() > 0:
            try:
                setup = Gtk.PageSetup.new_from_gvariant(setup_v)
            except Exception:  # noqa: BLE001 - an incomplete page setup from the app
                setup = None
        choice = printing.choice_from_gtk(settings, setup)
        if choice.printer == printing.PDF_PRINTER:
            choice.output_uri = ""   # always ask where to save
        req = Request(self, handle, invocation)

        def done(response, ch):
            req.dialog = None
            if req.closed:
                return
            if response != RESPONSE_OK:
                req.reply(RESPONSE_CANCELLED)
                return
            s, ps = printing.choice_to_gtk(ch)
            self._expire_tokens()
            self._next_token = (self._next_token + 1) & 0xFFFFFFFF or 1
            token = self._next_token
            self.tokens[token] = (ch, time.time())
            results = {
                "settings": s.to_gvariant(),
                "page-setup": ps.to_gvariant(),
                "token": GLib.Variant("u", token),
            }
            log(f"PreparePrint -> printer={ch.printer!r} token={token}")
            req.reply(RESPONSE_OK, results)

        req.dialog = PrintDialog(title, choice, self._opts(options, title, parent, self.demo), done)
        req.dialog.present()

    # ------------------------------------------------------------------ Print
    def print_(self, params, invocation):
        handle, app_id, parent, title = (params.get_child_value(i).unpack() for i in range(4))
        fd_index = params.get_child_value(4).get_handle()
        options = params.get_child_value(5).unpack()
        log(f"Print app={app_id!r} title={title!r} token={options.get('token')}")
        fd_list = invocation.get_message().get_unix_fd_list()
        req = Request(self, handle, invocation)
        try:
            fd = fd_list.get(fd_index)
            path = printing.spool_fd(fd)
        except (GLib.Error, OSError, AttributeError) as e:
            log(f"cannot read document: {e}")
            req.reply(RESPONSE_OTHER)
            return
        req.cleanup.append(lambda: os.unlink(path))

        token = options.get("token")
        self._expire_tokens()
        if token is not None and token in self.tokens:
            choice, _ts = self.tokens.pop(token)
            self._send(req, title, path, choice, None)
            return

        # No (valid) token: ask now, with a real preview of the document.
        gi.require_version("Poppler", "0.18")
        from gi.repository import Poppler
        try:
            doc = Poppler.Document.new_from_file(Gio.File.new_for_path(path).get_uri(), None)
        except GLib.Error as e:
            log(f"not a PDF ({e.message}); showing a blank preview")
            doc = None
        choice = printing.Choice()

        def done(response, ch):
            req.dialog = None
            if req.closed:
                return
            if response != RESPONSE_OK:
                req.reply(RESPONSE_CANCELLED)
                return
            self._send(req, title, path, ch, doc)

        req.dialog = PrintDialog(title, choice, self._opts(options, title, parent, self.demo), done, doc=doc)
        req.dialog.present()

    def _send(self, req: Request, title: str, path: str, choice: printing.Choice, doc):
        """doc is the Poppler document when the app did not apply our settings itself
        (Print() without a token); None when it rendered after PreparePrint."""
        if choice.is_pdf:
            try:
                dest = printing.save_pdf(path, choice, doc)
                log(f"saved PDF to {dest}")
                req.reply(RESPONSE_OK)
            except (OSError, GLib.Error, Exception) as e:  # noqa: BLE001
                log(f"saving PDF failed: {e}")
                req.reply(RESPONSE_OTHER)
            return
        if self.demo:
            log(f"demo printer {choice.printer!r}: job not sent")
            req.reply(RESPONSE_OK)
            return

        def sent(err):
            if err:
                log(f"print job failed: {err}")
                req.reply(RESPONSE_OTHER)
            else:
                log(f"job queued on {choice.printer!r}")
                req.reply(RESPONSE_OK)

        def with_printer(printer):
            if printer is None:
                log(f"printer {choice.printer!r} not found")
                req.reply(RESPONSE_OTHER)
                return
            printing.send_to_printer(printer, title, path, choice, doc is None, sent)

        printing.find_printer(choice.printer, with_printer)
