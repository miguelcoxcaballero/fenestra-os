"""Shared helpers: paths, persisted options, number formatting."""
from __future__ import annotations

import json
import os
import sys

from .i18n import _

APP_ID = "org.fenestra.TaskManager"
DEMO = False          # neutral fake data (screenshots)
READ_ONLY = False     # never change anything on the system
PKG_DIR = os.path.dirname(os.path.abspath(__file__))


def data_dir() -> str:
    cands = [
        os.environ.get("FENESTRA_TASKMGR_DATA", ""),
        os.path.join(os.path.dirname(PKG_DIR), "data"),
        os.path.join(sys.prefix, "share", "fenestra-taskmgr", "data"),
        "/usr/share/fenestra-taskmgr/data",
    ]
    for c in cands:
        if c and os.path.isfile(os.path.join(c, "style.css")):
            return c
    return cands[1]


def config_dir() -> str:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "fenestra-taskmgr")


def state_dir() -> str:
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return os.path.join(base, "fenestra-taskmgr")


DEFAULTS = {
    "theme": "system",            # system | light | dark
    "start_page": "processes",
    "speed": "normal",            # high | normal | low | paused
    "always_on_top": False,
    "minimize_on_use": True,
    "hide_when_minimized": False,
    "full_account_name": False,
    "history_all": True,
    "ask_efficiency": True,
    "nav_expanded": False,
    "group_by_type": True,
    "cpu_graph": "overall",       # overall | logical
    "wm_open": True,
    "other_open": True,
}

SPEEDS = {"high": 0.5, "normal": 1.0, "low": 4.0, "paused": 0}


class Options(dict):
    def __init__(self):
        super().__init__(DEFAULTS)
        self.path = os.path.join(config_dir(), "settings.json")
        if not DEMO:
            try:
                with open(self.path) as f:
                    data = json.load(f)
                for k, v in data.items():
                    if k in DEFAULTS and type(v) is type(DEFAULTS[k]):
                        self[k] = v
            except (OSError, ValueError):
                pass

    def set(self, key, value):
        self[key] = value
        if DEMO or READ_ONLY:
            return
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(dict(self), f, indent=1)
            os.replace(tmp, self.path)
        except OSError:
            pass


options: Options | None = None


def opts() -> Options:
    global options
    if options is None:
        options = Options()
    return options


# ------------------------------------------------------------------ formatting
def _num(v: float, decimals: int) -> str:
    s = f"{v:,.{decimals}f}"
    if _("decimal_sep") == ",":
        s = s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return s


def fmt_cpu(pct: float) -> str:
    if pct < 0.05:
        return "0%"
    return _num(min(pct, 100.0), 1) + "%"


def fmt_pct0(pct: float) -> str:
    return f"{int(round(max(0.0, min(pct, 100.0))))}%"


def fmt_mb(b: float) -> str:
    return _num(b / 1048576.0, 1) + " MB"


def fmt_rate_mbs(bps: float) -> str:
    mb = bps / 1048576.0
    if mb < 0.05:
        return "0 MB/s"
    return _num(mb, 1) + " MB/s"


def fmt_mbps(bits: float) -> str:
    m = bits / 1e6
    if m < 0.05:
        return "0 Mbps"
    return _num(m, 1) + " Mbps"


def fmt_size(b: float, decimals: int = 1) -> str:
    """1.5 GB / 512 MB / 64.0 GB (binary units, Windows style)."""
    units = ["B", "KB", "MB", "GB", "TB"]
    v = float(b)
    i = 0
    while v >= 1024 and i < len(units) - 1:
        v /= 1024.0
        i += 1
    if i <= 1:
        return f"{int(v)} {units[i]}"
    if i == 2 and v >= 100:
        return f"{int(round(v))} {units[i]}"
    return _num(v, decimals) + f" {units[i]}"


def fmt_kib(b: float) -> str:
    """Details page memory: '12,345 K'."""
    return f"{int(b // 1024):,} K".replace(",", "." if _("decimal_sep") == "," else ",")


def fmt_bps_short(bytes_per_s: float) -> str:
    """Disk speed: '77.0 KB/s', '1.2 MB/s', '0 KB/s'."""
    kb = bytes_per_s / 1024.0
    if kb < 0.05:
        return "0 KB/s"
    if kb < 1024:
        return _num(kb, 1) + " KB/s"
    return _num(kb / 1024.0, 1) + " MB/s"


def fmt_bits(bits_per_s: float) -> str:
    """Network: '0 Kbps', '8.0 Kbps', '1.2 Mbps'."""
    k = bits_per_s / 1000.0
    if k < 0.05:
        return "0 Kbps"
    if k < 1000:
        return _num(k, 1) + " Kbps"
    if k < 1e6:
        return _num(k / 1000.0, 1) + " Mbps"
    return _num(k / 1e6, 1) + " Gbps"


def fmt_bits_int(bits_per_s: float) -> str:
    k = bits_per_s / 1000.0
    if k < 1000:
        return f"{int(round(k))}"
    return _num(k / 1000.0, 1) + " M"


def fmt_uptime(secs: float) -> str:
    secs = int(secs)
    d, r = divmod(secs, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    return f"{d}:{h:02d}:{m:02d}:{s:02d}"


def fmt_cputime(secs: float) -> str:
    secs = int(secs)
    h, r = divmod(secs, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}"


def fmt_ghz(khz: float) -> str:
    return _num(khz / 1e6, 2) + " GHz"


def fmt_scale(bits: float) -> str:
    """Axis label for network graphs ('1 Mbps', '100 Kbps')."""
    if bits >= 1e9:
        return f"{bits / 1e9:g} Gbps"
    if bits >= 1e6:
        return f"{bits / 1e6:g} Mbps"
    return f"{bits / 1e3:g} Kbps"


def fmt_scale_bytes(b: float) -> str:
    if b >= 1048576:
        return f"{b / 1048576:g} MB/s"
    return f"{b / 1024:g} KB/s"
