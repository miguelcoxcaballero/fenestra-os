"""Shared helpers: modes, data paths, threads, GSettings, sizes, text matching, media cache."""
from __future__ import annotations

import hashlib
import os
import shutil
import sys
import threading
import time
import unicodedata

from gi.repository import Gio, GLib

APP_ID = "org.fenestra.Store"
PKG_DIR = os.path.dirname(os.path.abspath(__file__))

# Demo mode (--demo-data, --screenshot, tests): the deterministic in-memory catalogue only.
DEMO = False
# Never change the system (real backends refuse installs/removals/source changes).
READ_ONLY = False
# Speed factor for simulated demo operations (tests set it low).
DEMO_SPEED = float(os.environ.get("FENESTRA_STORE_DEMO_SPEED", "1.0"))


def data_dir() -> str:
    """Location of data/ (source tree or installed share dir)."""
    cands = [
        os.environ.get("FENESTRA_STORE_DATA", ""),
        os.path.join(os.path.dirname(PKG_DIR), "data"),
        os.path.join(sys.prefix, "share", "fenestra-store", "data"),
        "/usr/share/fenestra-store/data",
    ]
    for c in cands:
        if c and os.path.isfile(os.path.join(c, "style.css")):
            return c
    return cands[1]


def cache_dir(*parts) -> str:
    d = os.path.join(GLib.get_user_cache_dir(), "fenestra-store", *parts)
    os.makedirs(d, exist_ok=True)
    return d


def state_file() -> str:
    d = os.path.join(GLib.get_user_config_dir(), "fenestra-store")
    return os.path.join(d, "state.ini")


def log(*args):
    if os.environ.get("FENESTRA_STORE_DEBUG"):
        print("[fenestra-store]", *args, file=sys.stderr, flush=True)


def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


# --------------------------------------------------------------------------- threads

def in_thread(fn, *args, on_done=None, on_error=None, name="fenestra-store-worker"):
    """Run fn(*args) in a daemon thread; on_done(result) / on_error(exc) run on the UI thread."""
    def run():
        try:
            res = fn(*args)
        except Exception as e:  # noqa: BLE001 - reported to the caller on the UI thread
            log("worker error", fn, e)
            if on_error:
                GLib.idle_add(_once, on_error, e)
            return
        if on_done:
            GLib.idle_add(_once, on_done, res)
    t = threading.Thread(target=run, name=name, daemon=True)
    t.start()
    return t


def _once(cb, arg):
    cb(arg)
    return False


def ui(cb, *args):
    """Schedule cb(*args) on the UI (main) thread."""
    GLib.idle_add(lambda: (cb(*args), False)[1])


# --------------------------------------------------------------------------- gsettings

_settings_cache: dict[str, Gio.Settings | None] = {}


def settings(schema_id: str) -> Gio.Settings | None:
    if schema_id in _settings_cache:
        return _settings_cache[schema_id]
    src = Gio.SettingsSchemaSource.get_default()
    s = Gio.Settings.new(schema_id) if src and src.lookup(schema_id, True) else None
    _settings_cache[schema_id] = s
    return s


def gget(schema_id: str, key: str, default=None):
    s = settings(schema_id)
    if not s or not s.props.settings_schema.has_key(key):
        return default
    return s.get_value(key).unpack()


def gconnect(schema_id: str, key: str, cb):
    s = settings(schema_id)
    if s and s.props.settings_schema.has_key(key):
        return s.connect(f"changed::{key}", lambda *_: cb())
    return None


# --------------------------------------------------------------------------- formatting

def human_size(n) -> str:
    if n is None or n <= 0:
        return ""
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    n = float(n)
    while n >= 1000 and i < len(units) - 1:
        n /= 1000.0
        i += 1
    if i == 0:
        return f"{int(n)} {units[i]}"
    from .i18n import decimal
    s = f"{n:.1f}" if n < 100 else f"{n:.0f}"
    return f"{decimal(s)} {units[i]}"


def relative_time(ts: float | None) -> str:
    from .i18n import _
    if not ts:
        return _("Never")
    d = max(0, time.time() - ts)
    if d < 60:
        return _("Just now")
    if d < 3600:
        m = int(d // 60)
        return (_("1 minute ago") if m == 1 else _("%d minutes ago") % m)
    if d < 86400:
        h = int(d // 3600)
        return (_("1 hour ago") if h == 1 else _("%d hours ago") % h)
    days = int(d // 86400)
    return _("Yesterday") if days == 1 else _("%d days ago") % days


def fold(s: str) -> str:
    """Lower-case, accent-free form for matching ('Rápidas' -> 'rapidas')."""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).casefold()


def stable_hash(s: str) -> int:
    return int(hashlib.sha1(s.encode("utf-8")).hexdigest()[:8], 16)


# --------------------------------------------------------------------------- media

def fetch_cached(url: str, max_bytes=20 * 1024 * 1024) -> str | None:
    """Download url once into the cache (worker threads only); returns the local path."""
    if not url:
        return None
    if url.startswith("file://"):
        return url[7:]
    if url.startswith("/"):
        return url
    ext = os.path.splitext(url.split("?")[0])[1][:5] or ".img"
    path = os.path.join(cache_dir("media"), hashlib.sha1(url.encode()).hexdigest() + ext)
    if os.path.exists(path):
        return path
    if DEMO:
        return None
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "fenestra-store/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read(max_bytes + 1)
        if len(data) > max_bytes:
            return None
        tmp = path + ".part"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
        return path
    except Exception as e:  # noqa: BLE001 - network is optional
        log("download failed", url, e)
        return None
