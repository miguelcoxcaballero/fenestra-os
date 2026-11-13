"""How much an app is used, for the result cards: several packages often carry the same name
and the card is where one is told from the other.

Each source says what it publishes, and nothing is made up for the others:
* Flathub     installs in the last month (flathub.org/api/v2/stats/<id>)
* Fedora RPM  Fedora publishes no figures. Two that exist for the same software: the installs
              Debian's popularity contest counts for the package of that name (popcon.debian.org,
              machines that opted in: a relative figure, good for telling the usual package from
              the obscure one), and the stars of the project when it lives on GitHub
* Snap Store  no figures exist either: whether the publisher is verified, and the GitHub stars
              of the project the snap links to (not of a repository that only packages the snap)

GitHub answers 60 questions an hour without an account: past that the stars are simply left
out. Answers are kept on disk (a day for installs, a week for the rest) and in memory;
everything runs in worker threads, never on the UI thread. Only app ids, package and repository
names are sent."""
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


_popcon = None
_popcon_lock = __import__("threading").Lock()


def popcon() -> dict:
    """Debian package name -> installs, from popcon.debian.org/by_inst.gz (refreshed weekly)."""
    global _popcon
    with _popcon_lock:
        if _popcon is not None:
            return _popcon
        import gzip
        path = os.path.join(util.cache_dir("metrics"), "popcon-by_inst.gz")
        fresh = os.path.exists(path) and time.time() - os.path.getmtime(path) < 7 * DAY
        if not fresh and not util.DEMO:
            import urllib.request
            try:
                req = urllib.request.Request("https://popcon.debian.org/by_inst.gz", headers={"User-Agent": "fenestra-store/1.0"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    data = r.read(32 * 1024 * 1024)
                with open(path + ".part", "wb") as f:
                    f.write(data)
                os.replace(path + ".part", path)
            except Exception as e:  # noqa: BLE001 - an older copy, or none, will do
                util.log("popcon download failed", e)
        table = {}
        try:
            with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.startswith("#"):
                        continue
                    parts = line.split(None, 3)
                    if len(parts) >= 3 and parts[2].isdigit() and int(parts[2]) >= 20:
                        table[parts[1]] = int(parts[2])
        except (OSError, EOFError):
            pass
        _popcon = table
        return table


def debian_installs(pkgname: str) -> int:
    """Installs of the Debian package that is the same software as this Fedora one: the same
    name, or the name without Fedora's own suffixes (ffmpeg-free is Debian's ffmpeg)."""
    t = popcon()
    name = pkgname.lower()
    for candidate in (name, name.removesuffix("-free"), name.removesuffix("-freeworld"), name.replace("_", "-")):
        if candidate in t:
            return t[candidate]
    return 0


def _stars(url: str) -> tuple[int, str]:
    """(stars, "owner/repo") of the GitHub repository at url, (0, "") when it is not one."""
    m = _GITHUB.match(url or "")
    if not m:
        return 0, ""
    d = _json(f"https://api.github.com/repos/{m.group(1)}/{m.group(2)}", 7 * DAY) or {}
    return int(d.get("stargazers_count") or 0), f"{m.group(1)}/{m.group(2)}"


def _job(app, backend):
    """Worker: (text, tooltip) for the card, ("", "") when nothing is published for it."""
    if app.packaging == "flatpak" and app.source == "flathub":
        d = _json("https://flathub.org/api/v2/stats/" + flatpak_id(app), DAY) or {}
        month, total = int(d.get("installs_last_month") or 0), int(d.get("installs_total") or 0)
        if month:
            return _("↓ %s/month") % human(month), _("%s installs in total (Flathub)") % human(total)
        return "", ""
    parts, tips = [], []
    if app.packaging == "snap":
        if app.verified:
            parts.append(_("✓ verified"))
            tips.append(_("Verified publisher: %s") % app.developer)
        # The project itself, not a repository that only holds the snap's packaging.
        for url in app.project_urls:
            stars, repo = _stars(url)
            if stars and "snap" not in repo.split("/")[1].lower():
                parts.append("★ " + human(stars))
                tips.append(_("%s stars on GitHub (%s)") % (human(stars), repo))
                break
    elif app.packaging == "rpm":
        n = debian_installs(app.pkgname or app.app_id)
        if n:
            parts.append(_("↓ %s Debian") % human(n))
            tips.append(_("%s installs counted by Debian for this package (popcon)") % human(n))
        if not app.homepage and backend is not None and not app.details_loaded:
            try:
                backend.details(app)       # one PackageKit question: the project's address
            except Exception as e:  # noqa: BLE001
                util.log("details for metric failed", app.pkgname, e)
        stars, repo = _stars(app.homepage)
        if stars:
            parts.append("★ " + human(stars))
            tips.append(_("%s stars on GitHub (%s)") % (human(stars), repo))
    return " · ".join(parts), "\n".join(tips)


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
