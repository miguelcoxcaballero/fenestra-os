"""Log the freshly created user in through GDM's greeter API.

This mirrors what gnome-initial-setup's summary page does in new-user mode:

  client   = GdmClient()
  greeter  = client.get_greeter_sync()
  verifier = client.get_user_verifier_sync()
  verifier.begin_verification_for_user("gdm-password", user)
    -> "secret-info-query" : verifier.answer_query(service, password)
    -> greeter "session-opened" : greeter.start_session_when_ready(service, True)

GDM then replaces the initial-setup session with the user's session and the
OOBE process is terminated.  If anything fails we simply quit and GDM shows
its regular login screen.
"""

import os

from gi.repository import GLib

from . import log

SERVICE = "gdm-password"
LOGIN_TIMEOUT_S = 25


class GdmLogin:
    def __init__(self, demo: bool):
        self.demo = demo
        self.client = None
        self.greeter = None
        self.verifier = None
        self._password = None
        self._done = False
        self._on_failed = None
        self._timeout_id = 0

    def prepare(self) -> bool:
        """Connect to GDM early (like gis-driver).  Safe to call repeatedly."""
        if self.demo:
            return False
        if self.greeter is not None and self.verifier is not None:
            return True
        try:
            import gi
            gi.require_version("Gdm", "1.0")
            from gi.repository import Gdm
        except (ImportError, ValueError) as exc:
            log.warning("Gdm typelib unavailable: %s", exc)
            return False
        try:
            self.client = Gdm.Client.new()
            self.greeter = self.client.get_greeter_sync(None)
            self.verifier = self.client.get_user_verifier_sync(None)
            return True
        except GLib.Error as exc:
            log.warning("No GDM greeter connection: %s", exc.message)
            self.greeter = self.verifier = None
            return False

    @staticmethod
    def write_uid_file(uid: int):
        """GDM chowns the initial-setup home to this uid after login (like g-i-s)."""
        try:
            path = os.path.join(os.path.expanduser("~"), "gnome-initial-setup-uid")
            with open(path, "w", encoding="ascii") as fh:
                fh.write(str(uid))
        except OSError as exc:
            log.warning("could not write uid file: %s", exc)

    def login(self, username: str, password: str, on_failed) -> bool:
        """Start the login.  Returns False immediately if it can't be attempted."""
        if self.demo or not self.prepare():
            return False
        self._password = password
        self._on_failed = on_failed
        v, g = self.verifier, self.greeter
        v.connect("info", lambda _v, _s, msg: log.info("gdm info: %s", msg))
        v.connect("problem", lambda _v, _s, msg: log.warning("gdm problem: %s", msg))
        v.connect("info-query", self._on_info_query)
        v.connect("secret-info-query", self._on_secret_query)
        v.connect("verification-failed", lambda *_: self._fail("verification failed"))
        v.connect("service-unavailable", lambda _v, _s, msg: self._fail(f"service unavailable: {msg}"))
        g.connect("session-opened", self._on_session_opened)
        self._timeout_id = GLib.timeout_add_seconds(LOGIN_TIMEOUT_S, self._on_timeout)
        v.call_begin_verification_for_user(SERVICE, username, None, self._on_begin_done)
        return True

    # -- callbacks -------------------------------------------------------
    def _on_begin_done(self, verifier, result):
        try:
            verifier.call_begin_verification_for_user_finish(result)
        except GLib.Error as exc:
            self._fail(f"begin verification: {exc.message}")

    def _on_info_query(self, verifier, service, question):
        # Should not happen for gdm-password with a known user name.
        log.info("gdm asks (non-secret): %s", question)

    def _on_secret_query(self, verifier, service, question):
        if self._password is None:
            self._fail("password requested twice")
            return
        password, self._password = self._password, None
        verifier.call_answer_query(service, password, None, self._on_answer_done)

    def _on_answer_done(self, verifier, result):
        try:
            verifier.call_answer_query_finish(result)
        except GLib.Error as exc:
            self._fail(f"answer query: {exc.message}")

    def _on_session_opened(self, greeter, service, *_args):
        log.info("gdm session opened for %s, starting it", service)
        self._done = True
        if self._timeout_id:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = 0
        try:
            greeter.call_start_session_when_ready_sync(service, True, None)
        except GLib.Error as exc:
            self._fail(f"start session: {exc.message}")

    def _on_timeout(self):
        self._timeout_id = 0
        if not self._done:
            self._fail("timed out")
        return False

    def _fail(self, reason):
        if self._done:
            return
        self._done = True
        log.warning("automatic login failed: %s", reason)
        if self._timeout_id:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = 0
        cb, self._on_failed = self._on_failed, None
        if cb:
            cb(reason)
