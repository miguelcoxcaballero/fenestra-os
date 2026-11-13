"""How much an app is used, for the result cards: several packages often carry the same name
and the card is where one is told from the other.

Each source says what it publishes, and nothing is made up for the others:
* Flathub     installs in the last month (flathub.org/api/v2/stats/<id>)
* Snap Store  whether the publisher is verified (snapd's search result; no download figures exist)
* Fedora RPM  no figures exist; when the project lives on GitHub, its stars
              (api.github.com/repos/<owner>/<repo>, 60 requests an hour without an account:
              past that the cards simply show nothing)

Answers are kept on disk (a day for installs, a week for stars) and in memory; everything runs
in the media workers, never on the UI thread. Only app ids and repository names are sent."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time

from . import i18n, util
from .i18n import _

DAY = 86400
_GITHUB = re.compile(r"^https?://(?:www\.)?github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?(?:[#?].*)?$")
_blocked_until = 0.0     # GitHub said "rate limit": no more questions until then


def human(n: int) -> str:
    """1234 -> "1.2 k" (decimal comma in Spanish), 2500000 -> "2.5 M"."""
    if n < 1000:
        return str(n)
    v, unit = (n / 1e6, "M") if n >= 1e6 else (n / 1e3, "k")
    s = f"{v:.1f}" if v < 100 else f"{v:.0f}"
    s = s.removesuffix(".0")
    return (s.replace(".", ",") if i18n.LANG == "es" else s) + " " + unit


def _json(url: str, max_age: float):
    """The JSON at url, from the disk cache while it is fresh. None when it cannot be had."""
    global _blocked_until
    path = os.path.join(util.cache_dir("metrics"), hashlib.sha1(url.encode()).hexdigest() + ".json")
    try:
        if time.time() - os.path.getmtime(path) < max_age:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except (OSError, ValueError):
        pass
    if util.DEMO or ("api.github.com" in url and time.time() < _blocked_until):
        return None
    import urllib.error
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "fenestra-store/1.0", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read(4 * 1024 * 1024).decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        if e.code in (403, 429) and "api.github.com" in url:
            _blocked_until = time.time() + 30 * 60
        data = {} if e.code == 404 else None     # "no such app" is an answer worth remembering
    except Exception as e:  # noqa: BLE001 - the network is optional
        util.log("metric failed", url, e)
        return None
    if data is not None:
        try:
            with open(path + ".part", "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(path + ".part", path)
        except OSError:
            pass
    return data


def flatpak_id(app) -> str:
    parts = (app.ref or "").split("/")
    return parts[1] if len(parts) >= 2 and parts[0] in ("app", "runtime") else app.app_id


def _job(app, backend):
    """Worker: (text, tooltip) for the card, ("", "") when the source publishes nothing."""
    if app.packaging == "flatpak" and app.source == "flathub":
        d = _json("https://flathub.org/api/v2/stats/" + flatpak_id(app), DAY) or {}
        month, total = int(d.get("installs_last_month") or 0), int(d.get("installs_total") or 0)
        if month:
            return _("%s installs/month") % human(month), _("%s installs in total (Flathub)") % human(total)
        return "", ""
    if app.packaging == "snap":
        return (_("Verified publisher"), app.developer) if app.verified else ("", "")
    if app.packaging == "rpm":
        if not app.homepage and backend is not None and not app.details_loaded:
            try:
                backend.details(app)       # one PackageKit question: the project's address
            except Exception as e:  # noqa: BLE001
                util.log("details for metric failed", app.pkgname, e)
        m = _GITHUB.match(app.homepage or "")
        if m:
            d = _json(f"https://api.github.com/repos/{m.group(1)}/{m.group(2)}", 7 * DAY) or {}
            stars = int(d.get("stargazers_count") or 0)
            if stars:
                return _("★ %s on GitHub") % human(stars), f"github.com/{m.group(1)}/{m.group(2)}"
    return "", ""


_loader = None


def request(store, app, cb):
    """cb((text, tooltip)) on the UI thread."""
    global _loader
    from . import media
    if util.DEMO:
        media._call(cb, ("", ""))
        return
    if _loader is None:
        _loader = media.Loader(workers=3, keep=4000)   # its own workers: pictures never wait for figures
    _loader.get(("metric", app.uid), lambda: _job(app, store.backends.get(app.backend)), cb)
