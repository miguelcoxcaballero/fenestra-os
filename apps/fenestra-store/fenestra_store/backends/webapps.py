"""Web apps: services that have no Linux app (YouTube, WhatsApp, Netflix…), installed the way
Microsoft Store installs a web app: a launcher in ~/.local/share/applications that opens the
site in its own window (`--app=URL` of a Chromium-family browser, or a new Firefox window).

The catalogue is Fenestra's short list of popular services plus GNOME Software's own web app
list (/usr/share/swcatalog/xml/gnome-pwa-list-*.xml), so both stores offer the same ones.
No artwork is shipped: the icon is the site's own, read from its web manifest (or its
apple-touch-icon / favicon) at runtime and cached; installing copies it next to the launcher.
Nothing here needs root or a daemon.
"""
from __future__ import annotations

import glob
import html.parser
import json
import os
import re
import shutil
import urllib.parse
import xml.etree.ElementTree as ET

from gi.repository import Gio, GLib

from .. import util
from ..i18n import pick
from ..model import App, StoreError, map_categories
from . import Backend

PWA_LISTS = ["/usr/share/swcatalog/xml/gnome-pwa-list-*.xml", "/usr/share/app-info/xmls/gnome-pwa-list-*.xml"]
MARK = "X-Fenestra-WebApp"

# id, name, developer, url, manifest (or ""), store categories, (light, dark) brand colours, summary, description
WEB_APPS = [
    ("web.youtube", "YouTube", "Google", "https://www.youtube.com/", "https://www.youtube.com/manifest.webmanifest",
     ["multimedia"], ("#ffe1e4", "#6b0d18"),
     {"en": "Watch videos, music and live streams", "es": "Mira vídeos, música y directos"},
     {"en": ["YouTube in its own window, with its own icon in Start and on the taskbar.",
             "It opens the YouTube website in your browser's app mode, so your account and settings are the "
             "ones you already use in the browser."],
      "es": ["YouTube en su propia ventana, con su propio icono en Inicio y en la barra de tareas.",
             "Abre el sitio web de YouTube en el modo aplicación de tu navegador, así que tu cuenta y tus ajustes "
             "son los que ya usas en el navegador."]}),
    ("web.whatsapp", "WhatsApp", "WhatsApp", "https://web.whatsapp.com/", "https://web.whatsapp.com/manifest.json",
     ["communication"], ("#d9fdd3", "#0b4a3f"),
     {"en": "Message and call your contacts from the computer", "es": "Escribe y llama a tus contactos desde el equipo"},
     {"en": ["WhatsApp in its own window. Link it to your phone once by scanning the QR code it shows.",
             "It opens WhatsApp Web in your browser's app mode."],
      "es": ["WhatsApp en su propia ventana. Vincúlalo una vez con tu teléfono escaneando el código QR que muestra.",
             "Abre WhatsApp Web en el modo aplicación de tu navegador."]}),
    ("web.netflix", "Netflix", "Netflix", "https://www.netflix.com/", "",
     ["multimedia"], ("#f6d5d6", "#3b0a0d"),
     {"en": "Series and films on demand", "es": "Series y películas a la carta"},
     {"en": ["Netflix in its own window. Sign in with your Netflix account.",
             "It opens the Netflix website in your browser's app mode; playback needs a browser with DRM "
             "support (Chrome, Brave, Edge or Firefox)."],
      "es": ["Netflix en su propia ventana. Inicia sesión con tu cuenta de Netflix.",
             "Abre el sitio web de Netflix en el modo aplicación de tu navegador; para reproducir hace falta un "
             "navegador con DRM (Chrome, Brave, Edge o Firefox)."]}),
    ("web.primevideo", "Prime Video", "Amazon", "https://www.primevideo.com/", "",
     ["multimedia"], ("#d3f0fb", "#06283b"),
     {"en": "Films, series and sport from Amazon", "es": "Películas, series y deporte de Amazon"},
     {"en": ["Prime Video in its own window. Sign in with your Amazon account.",
             "It opens the Prime Video website in your browser's app mode."],
      "es": ["Prime Video en su propia ventana. Inicia sesión con tu cuenta de Amazon.",
             "Abre el sitio web de Prime Video en el modo aplicación de tu navegador."]}),
    ("web.disneyplus", "Disney+", "Disney", "https://www.disneyplus.com/", "https://www.disneyplus.com/manifest.json",
     ["multimedia"], ("#d9e3ff", "#0c1a46"),
     {"en": "Disney, Pixar, Marvel, Star Wars and more", "es": "Disney, Pixar, Marvel, Star Wars y más"},
     {"en": ["Disney+ in its own window. Sign in with your Disney+ account.",
             "It opens the Disney+ website in your browser's app mode."],
      "es": ["Disney+ en su propia ventana. Inicia sesión con tu cuenta de Disney+.",
             "Abre el sitio web de Disney+ en el modo aplicación de tu navegador."]}),
]

CHROMIUM = {"brave": "brave", "chrome": "chrome", "chromium": "chromium", "msedge": "msedge", "edge": "msedge",
            "vivaldi": "vivaldi", "opera": "opera"}


def slug(app_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", app_id).strip("_")


# --------------------------------------------------------------------------- browser

def _browser_kind(info) -> str:
    text = f"{info.get_id() or ''} {info.get_commandline() or ''}".lower()
    for key, wm in CHROMIUM.items():
        if key in text:
            return wm
    if "firefox" in text or "librewolf" in text or "floorp" in text:
        return "firefox"
    return ""


def pick_browser():
    """(DesktopAppInfo or None, kind): the default browser when it is Chromium-based (app windows),
    else any installed Chromium-based browser, else Firefox, else (None, "")."""
    default = Gio.AppInfo.get_default_for_type("x-scheme-handler/https", False)
    cands = ([default] if default else []) + list(Gio.AppInfo.get_all_for_type("x-scheme-handler/https"))
    seen, firefox = set(), None
    for info in cands:
        if info is None or info.get_id() in seen:
            continue
        seen.add(info.get_id())
        kind = _browser_kind(info)
        if kind and kind != "firefox":
            return info, kind
        if kind == "firefox" and firefox is None:
            firefox = info
    return (firefox, "firefox") if firefox else (None, "")


def _argv_of(info) -> list[str]:
    cmd = info.get_commandline() or ""
    try:
        argv = GLib.shell_parse_argv(cmd)[1]
    except GLib.Error:
        argv = cmd.split()
    return [a for a in argv if not re.fullmatch(r"%[a-zA-Z]|@@[a-z]?", a)]


def launcher_argv(url: str, info=None, kind=None) -> list[str]:
    if info is None and kind is None:
        info, kind = pick_browser()
    if info is None:
        return ["xdg-open", url]
    argv = _argv_of(info)
    if kind == "firefox":
        return argv + ["--new-window", url]
    return argv + [f"--app={url}"]


_RESERVED = set(" \t\n\"'\\><~|&;$*?#()`")


def exec_quote(argv) -> str:
    """Desktop Entry Exec= value for argv (quoting per the specification)."""
    out = []
    for a in argv:
        a = a.replace("%", "%%")
        if any(c in _RESERVED for c in a):
            a = '"' + re.sub(r'(["`$\\])', r"\\\1", a) + '"'
        out.append(a)
    return " ".join(out)


def wm_class(url: str, kind: str) -> str:
    """Window class Chromium gives an --app window (so the taskbar groups it under the launcher)."""
    if not kind or kind == "firefox":
        return ""
    u = urllib.parse.urlsplit(url)
    path = u.path.strip("/").replace("/", "_")
    return f"{kind}-{u.netloc}__{path}-Default"


# --------------------------------------------------------------------------- icons

class _LinkParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "link":
            d = dict(attrs)
            self.links.append((d.get("rel", "") or "", d.get("href", "") or "", d.get("sizes", "") or ""))


def _size(s: str) -> int:
    m = re.match(r"(\d+)x(\d+)", (s or "").split(" ")[-1])
    return int(m.group(1)) if m else 0


def _fetch_text(url, limit=2 * 1024 * 1024) -> str:
    path = util.fetch_cached(url, limit)
    if not path:
        return ""
    with open(path, "rb") as f:
        return f.read().decode("utf-8", "replace")


def manifest_icon(manifest_url: str, text: str) -> str:
    """Best icon URL in a web manifest: a full-colour ('any') PNG/SVG, the largest up to 512 px."""
    try:
        data = json.loads(text)
    except ValueError:
        return ""
    best, best_score = "", -1
    for ic in data.get("icons", []) if isinstance(data, dict) else []:
        src = ic.get("src") or ""
        purpose = (ic.get("purpose") or "any").split()
        if not src or "monochrome" in purpose or src.lower().endswith(".svg"):
            continue
        size = max((_size(s) for s in (ic.get("sizes") or "").split()), default=0)
        score = min(size, 512) + (0 if "any" in purpose else -1000)
        if score > best_score:
            best, best_score = urllib.parse.urljoin(manifest_url, src), score
    return best


def page_icon(page_url: str, text: str) -> tuple[str, str]:
    """(manifest URL, best icon URL) from a page's <link> tags."""
    p = _LinkParser()
    try:
        p.feed(text)
    except Exception:  # noqa: BLE001 - broken HTML: use what was parsed
        pass
    manifest, best, best_score = "", "", -1
    for rel, href, sizes in p.links:
        rels = rel.lower().split()
        if "manifest" in rels and not manifest:
            manifest = urllib.parse.urljoin(page_url, href)
        elif "apple-touch-icon" in rels or "apple-touch-icon-precomposed" in rels or "icon" in rels:
            score = (_size(sizes) or (180 if "apple-touch-icon" in rels else 32)) + \
                (0 if not href.lower().endswith((".svg", ".ico")) else -100)
            if score > best_score:
                best, best_score = urllib.parse.urljoin(page_url, href), score
    return manifest, best


def resolve_icon_url(app) -> str:
    """Worker thread: the URL of the site's icon (network, cached)."""
    if app.icon_url:
        return app.icon_url
    manifest = getattr(app, "_manifest", "")
    if manifest:
        u = manifest_icon(manifest, _fetch_text(manifest))
        if u:
            return u
    text = _fetch_text(app.web_url)
    m, best = page_icon(app.web_url, text)
    if m and m != manifest:
        u = manifest_icon(m, _fetch_text(m))
        if u:
            return u
    return best or urllib.parse.urljoin(app.web_url, "/favicon.ico")


def icon_cache_path(app) -> str:
    return os.path.join(util.cache_dir("webapps"), slug(app.app_id) + ".png")


def fetch_icon(app) -> str | None:
    """Worker thread: a local copy of the web app's icon (downloaded once), or None."""
    dest = icon_cache_path(app)
    if os.path.isfile(dest):
        return dest
    if util.DEMO:
        return None
    url = resolve_icon_url(app)
    path = util.fetch_cached(url) if url else None
    if not path:
        return None
    try:   # normalise to PNG (favicons may be .ico) so launchers and the store read it alike
        import gi
        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf
        pb = GdkPixbuf.Pixbuf.new_from_file(path)
        if pb.get_width() > 256:
            pb = pb.scale_simple(256, 256, GdkPixbuf.InterpType.BILINEAR)
        pb.savev(dest + ".part", "png", [], [])
        os.replace(dest + ".part", dest)
        return dest
    except (GLib.Error, ImportError, ValueError) as e:
        util.log("web app icon unreadable", url, e)
        return None


# --------------------------------------------------------------------------- backend

class WebAppBackend(Backend):
    id = "webapp"
    label = "Web apps"

    def __init__(self, apps_dir=None, data_dir=None, pwa_lists=None):
        self.why = ""
        self.apps_dir = apps_dir or os.path.join(GLib.get_user_data_dir(), "applications")
        self.data_dir = data_dir or os.path.join(GLib.get_user_data_dir(), "fenestra-store", "webapps")
        self.pwa_lists = PWA_LISTS if pwa_lists is None else pwa_lists

    def available(self):
        return True

    def desktop_path(self, app) -> str:
        return os.path.join(self.apps_dir, f"org.fenestra.WebApp.{slug(app.app_id)}.desktop")

    def _app(self, aid, name, dev, url, cats, summary, desc, brand=("", ""), manifest="", icon_url=""):
        a = App(uid=f"webapp:{aid}", app_id=aid, backend=self.id, source="web", packaging="web", name=name,
                summary=summary, description=desc, developer=dev, categories=cats, kind="app",
                homepage=url, web_url=url, icon_url=icon_url, brand_light=brand[0], brand_dark=brand[1],
                permissions=None, details_loaded=True, origin=urllib.parse.urlsplit(url).netloc)
        a._manifest = manifest
        cached = icon_cache_path(a)
        if os.path.isfile(cached):
            a.icon_path = cached
        a.desktop_id = os.path.basename(self.desktop_path(a))
        a.installed = os.path.isfile(self.desktop_path(a))
        a.sync_state()
        return a

    def load(self):
        apps = [self._app(aid, name, dev, url, list(cats), pick(summ), list(pick(desc)), brand, manifest)
                for aid, name, dev, url, manifest, cats, brand, summ, desc in WEB_APPS]
        known = {a.web_url.rstrip("/") for a in apps}
        for pattern in self.pwa_lists:
            for path in sorted(glob.glob(pattern)):
                try:
                    root = ET.parse(path).getroot()
                except (OSError, ET.ParseError) as e:
                    util.log("cannot read", path, e)
                    continue
                for comp in root.iter("component"):
                    if comp.get("type") != "web-application":
                        continue
                    url = (comp.findtext("launchable") or comp.findtext("url") or "").strip()
                    if not url.startswith("https://") or url.rstrip("/") in known:
                        continue
                    known.add(url.rstrip("/"))
                    host = urllib.parse.urlsplit(url).netloc
                    icon = next((i.text.strip() for i in comp.findall("icon") if i.get("type") == "remote" and i.text),
                                "")
                    cats = map_categories([c.text for c in comp.iter("category") if c.text])
                    name = (comp.findtext("name") or host).strip()
                    summary = (comp.findtext("summary") or "").strip()
                    apps.append(self._app("web." + slug(host), name, "", url, cats, summary, [summary] if summary else [],
                                          icon_url=icon))
        return apps

    def details(self, app):
        app.details_loaded = True

    # ------------------------------------------------------------------ operations
    def install(self, app, progress):
        progress(None, "Downloading")
        icon = fetch_icon(app)
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.apps_dir, exist_ok=True)
        icon_dest = ""
        if icon:
            icon_dest = os.path.join(self.data_dir, slug(app.app_id) + ".png")
            shutil.copyfile(icon, icon_dest)
            app.icon_path = icon_dest
        progress(0.6, "Installing")
        info, kind = pick_browser()
        argv = launcher_argv(app.web_url, info, kind)
        cats = {"multimedia": "AudioVideo;Video;", "communication": "Network;Chat;",
                "productivity": "Office;", "games": "Game;"}.get(app.categories[0] if app.categories else "", "Network;")
        lines = ["[Desktop Entry]", "Type=Application", f"Name={app.name}", f"Comment={app.summary}",
                 f"Exec={exec_quote(argv)}", f"Icon={icon_dest or 'web-browser'}", "Terminal=false",
                 f"Categories={cats}", "StartupNotify=true"]
        wm = wm_class(app.web_url, kind)
        if wm:
            lines.append(f"StartupWMClass={wm}")
        lines += [f"{MARK}={app.app_id}", f"{MARK}-URL={app.web_url}", ""]
        path = self.desktop_path(app)
        tmp = path + ".part"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            os.chmod(tmp, 0o755)
            os.replace(tmp, path)
        except OSError as e:
            raise StoreError(str(e)) from e
        progress(1.0, "")

    def remove(self, app, progress):
        progress(None, "Uninstalling")
        for p in (self.desktop_path(app), os.path.join(self.data_dir, slug(app.app_id) + ".png")):
            try:
                os.remove(p)
            except FileNotFoundError:
                pass
            except OSError as e:
                raise StoreError(str(e)) from e
        progress(1.0, "")

    def update(self, app, progress):
        self.install(app, progress)   # rewrites the launcher for the current default browser

    def launch(self, app):
        try:
            info = Gio.DesktopAppInfo.new_from_filename(self.desktop_path(app))
        except TypeError:
            info = None
        if info is None:
            return False
        try:
            return info.launch([], None)
        except GLib.Error:
            return False
