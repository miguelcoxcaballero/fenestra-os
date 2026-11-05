"""User account creation through AccountsService (org.freedesktop.Accounts)."""

import grp
import pwd
import re
import time
import unicodedata

from gi.repository import GLib

from . import dbus, log
from .crypt import hash_password

ACCOUNTS = "org.freedesktop.Accounts"
ACCOUNTS_PATH = "/org/freedesktop/Accounts"
USER_IFACE = "org.freedesktop.Accounts.User"
ACCOUNT_TYPE_ADMIN = 1

USERNAME_MAX = 32
# Names that must never be offered even if no such user exists yet.
RESERVED_USERNAMES = {
    "root", "admin", "administrator", "guest", "nobody", "daemon", "bin", "sys", "adm",
    "wheel", "users", "user", "gdm", "gnome-initial-setup", "system", "operator", "ftp",
    "mail", "sshd", "polkitd", "dbus", "systemd", "test",
}
_USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_-]*$")


def system_name_taken(name: str) -> bool:
    """True if a user *or group* with this name already exists."""
    for getter in (pwd.getpwnam, grp.getgrnam):
        try:
            getter(name)
            return True
        except KeyError:
            pass
    return False


def validate_username(name: str, taken=system_name_taken) -> str | None:
    """Return an error code for an invalid username or None if it's fine."""
    if not name:
        return "empty"
    if len(name) > USERNAME_MAX:
        return "too-long"
    if not _USERNAME_RE.match(name):
        return "invalid-chars"
    if name in RESERVED_USERNAMES:
        return "reserved"
    if taken(name):
        return "taken"
    return None


def _ascii_tokens(full_name: str) -> list[str]:
    norm = unicodedata.normalize("NFKD", full_name.lower())
    norm = "".join(c for c in norm if not unicodedata.combining(c))
    norm = norm.replace("ß", "ss").replace("ø", "o").replace("æ", "ae").replace("đ", "d").replace("ł", "l")
    norm = norm.lower()
    return re.findall(r"[a-z0-9]+", norm)


def username_candidates(full_name: str) -> list[str]:
    tokens = _ascii_tokens(full_name)
    if not tokens:
        return []
    if tokens[0][0].isdigit():
        tokens = ["user"] + tokens
    first, last = tokens[0], tokens[-1]
    cands = [first]
    if len(tokens) > 1:
        cands += [first + last, first[0] + last, "".join(tokens)]
    out = []
    for cand in cands:
        cand = cand[:USERNAME_MAX]
        if cand not in out:
            out.append(cand)
    return out


def derive_username(full_name: str, taken=system_name_taken) -> str | None:
    """Derive a valid, unused Unix username from a display name.

    "Miguel Cox Caballero" -> "miguel" (or "miguelcaballero", "mcaballero",
    ..., "miguel2" when those are taken).
    """
    cands = username_candidates(full_name)
    if not cands:
        return None
    for cand in cands:
        if validate_username(cand, taken) is None:
            return cand
    base = cands[0][: USERNAME_MAX - 3]
    for n in range(2, 1000):
        cand = f"{base}{n}"
        if validate_username(cand, taken) is None:
            return cand
    return None


class AccountsBackend:
    def __init__(self, demo: bool):
        self.demo = demo
        self._created: dict[str, str] = {}

    def create_user(self, full_name: str, username: str, password: str, hint: str = "",
                    language: str = "", formats: str = "") -> int:
        """Create an administrator account and return its uid.  Blocking."""
        if self.demo:
            time.sleep(1.2)
            log.info("[demo] would create admin user %r (%s), lang=%s formats=%s",
                     username, full_name, language, formats)
            return 60000
        crypted = hash_password(password)
        path = self._created.get(username)
        if path is None:
            (path,) = dbus.call(ACCOUNTS, ACCOUNTS_PATH, ACCOUNTS, "CreateUser",
                                GLib.Variant("(ssi)", (username, full_name, ACCOUNT_TYPE_ADMIN)), "(o)")
            # Remember it so "Try again" after a later failure doesn't recreate it.
            self._created[username] = path
            log.info("created user %s at %s", username, path)
        dbus.call(ACCOUNTS, path, USER_IFACE, "SetPassword",
                  GLib.Variant("(ss)", (crypted, hint or "")))
        if language:
            try:
                dbus.call(ACCOUNTS, path, USER_IFACE, "SetLanguage", GLib.Variant("(s)", (language,)))
            except GLib.Error as exc:
                log.warning("SetLanguage failed: %s", exc.message)
        if formats:
            try:  # newer accountsservice only
                dbus.call(ACCOUNTS, path, USER_IFACE, "SetFormatsLocale", GLib.Variant("(s)", (formats,)))
            except GLib.Error as exc:
                log.info("SetFormatsLocale unavailable: %s", exc.message)
        uid = dbus.get_property(ACCOUNTS, path, USER_IFACE, "Uid")
        return int(uid)

    def user_formats_locale(self, username: str) -> str:
        """Read FormatsLocale of a user (empty if unknown)."""
        try:
            (path,) = dbus.call(ACCOUNTS, ACCOUNTS_PATH, ACCOUNTS, "FindUserByName",
                                GLib.Variant("(s)", (username,)), "(o)", interactive=False)
            return dbus.get_property(ACCOUNTS, path, USER_IFACE, "FormatsLocale") or ""
        except GLib.Error:
            return ""
