"""AppStream catalogue reading, shared by the flatpak and packagekit backends.

Two readers produce the same neutral `Component` records:
* gi AppStream-1.0 (the `appstream` package), when its typelib is installed;
* a small pure-Python reader of AppStream catalog XML (optionally .gz), used otherwise and
  whenever the gi reader fails (its API changed between AppStream 0.16 and 1.x).
Paths:
* Flatpak remotes: <remote appstream dir>/appstream.xml(.gz), cached icons in icons/<W>x<H>/
  (e.g. /var/lib/flatpak/appstream/flathub/x86_64/active/).
* Fedora (appstream-data): /usr/share/swcatalog/xml/*.xml.gz, icons in
  /usr/share/swcatalog/icons/<origin>/<W>x<H>/ (older releases: /usr/share/app-info).
"""
from __future__ import annotations

import glob
import gzip
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

from .. import i18n, util

XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
APP_KINDS = ("desktop-application", "desktop", "console-application")
SYSTEM_XML_DIRS = ["/usr/share/swcatalog/xml", "/var/cache/swcatalog/xml", "/usr/share/app-info/xmls",
                   "/var/cache/app-info/xmls"]
SYSTEM_ICON_DIRS = ["/usr/share/swcatalog/icons", "/var/cache/swcatalog/icons", "/usr/share/app-info/icons",
                    "/var/cache/app-info/icons"]


@dataclass
class Component:
    id: str
    kind: str = "desktop-application"
    name: str = ""
    summary: str = ""
    description: list = field(default_factory=list)
    developer: str = ""
    categories: list = field(default_factory=list)
    keywords: list = field(default_factory=list)
    icon_path: str = ""
    icon_name: str = ""
    icon_url: str = ""
    screenshots: list = field(default_factory=list)   # [(url, caption)]
    license: str = ""
    homepage: str = ""
    version: str = ""
    released: str = ""            # ISO date
    pkgname: str = ""
    bundle: str = ""              # flatpak ref
    desktop_id: str = ""
    origin: str = ""


# --------------------------------------------------------------------------- helpers

def _langs():
    return [i18n.LANG, "en", None]


def _pick(d: dict):
    for lang in _langs():
        if lang in d and d[lang]:
            return d[lang]
    return next(iter(d.values()), "") if d else ""


def _iso(ts) -> str:
    import time
    try:
        return time.strftime("%Y-%m-%d", time.gmtime(int(ts)))
    except (TypeError, ValueError, OverflowError):
        return ""


def markup_to_paragraphs(markup: str) -> list[str]:
    """AppStream description markup (<p>, <ul>/<ol><li>, <em>, <code>) -> plain paragraphs."""
    if not markup:
        return []
    try:
        root = ET.fromstring(f"<d>{markup}</d>")
    except ET.ParseError:
        text = re.sub(r"<[^>]+>", " ", markup)
        return [" ".join(text.split())] if text.strip() else []
    return _desc_from_element(root)


def _text(el) -> str:
    return " ".join("".join(el.itertext()).split())


ANY = object()


def _desc_from_element(el, lang=ANY) -> list[str]:
    """Paragraphs of a <description>; lang selects per-paragraph translations (None: untranslated)."""
    out = []
    for child in el:
        lists = child.tag in ("ul", "ol")
        if lang is not ANY and child.get(XML_LANG) != lang and not (lists and child.get(XML_LANG) is None):
            continue
        if child.tag == "p":
            t = _text(child)
            if t:
                out.append(t)
        elif lists:
            item_lang = child.get(XML_LANG)  # items inherit the list's language
            for li in child:
                if li.tag == "li" and (lang is ANY or li.get(XML_LANG, item_lang) == lang):
                    t = _text(li)
                    if t:
                        out.append("• " + t)
    return out


def _icon_file(root, origin, size, name):
    for base in ([root] if root else []):
        for sub in (os.path.join(base, origin or "", f"{size}x{size}"), os.path.join(base, f"{size}x{size}")):
            p = os.path.join(sub, name)
            if os.path.isfile(p):
                return p
    return ""


# --------------------------------------------------------------------------- XML reader

def parse_xml(path: str, icon_root: str = "", origin: str = "") -> list[Component]:
    """Pure-Python reader for an AppStream catalog XML file (plain or gzip)."""
    opener = gzip.open if path.endswith(".gz") else open
    comps = []
    with opener(path, "rb") as f:
        ctx = ET.iterparse(f, events=("start", "end"))
        for ev, el in ctx:
            if ev == "start" and el.tag == "components":
                origin = el.get("origin") or origin
            elif ev == "end" and el.tag == "component":
                c = _component_from_xml(el, icon_root, origin)
                if c is not None:
                    comps.append(c)
                el.clear()
    return comps


def _component_from_xml(el, icon_root, origin):
    kind = el.get("type", "generic")
    if kind not in APP_KINDS:
        return None
    cid = (el.findtext("id") or "").strip()
    if not cid:
        return None
    c = Component(id=cid, kind=kind, origin=origin)
    names, sums, descs = {}, {}, {}
    icons = []
    for child in el:
        tag = child.tag
        lang = child.get(XML_LANG)
        if tag == "name":
            names[lang] = _text(child)
        elif tag == "summary":
            sums[lang] = _text(child)
        elif tag == "description":
            if lang is not None:  # whole-description translation (metainfo style)
                descs[lang] = _desc_from_element(child)
            else:  # catalog style: per-paragraph xml:lang
                langs = {x.get(XML_LANG) for x in child.iter() if x is not child}
                for lg in langs:
                    d = _desc_from_element(child, lg)
                    if d:
                        descs[lg] = d
        elif tag == "developer_name" and not c.developer:
            c.developer = _text(child)
        elif tag == "developer":
            n = child.find("name")
            if n is not None and (n.get(XML_LANG) is None):
                c.developer = _text(n)
        elif tag == "categories":
            c.categories = [_text(x) for x in child if x.tag == "category"]
        elif tag == "keywords":
            kw = [_text(x) for x in child if x.tag == "keyword" and x.get(XML_LANG) in (None, i18n.LANG)]
            c.keywords = kw
        elif tag == "icon":
            icons.append((child.get("type"), int(child.get("height") or child.get("width") or 64), _text(child)))
        elif tag == "screenshots":
            for s in child:
                if s.tag != "screenshot":
                    continue
                url, best = "", None
                for im in s.findall("image"):
                    w = int(im.get("width") or 0)
                    score = abs(w - 752) if im.get("type") == "thumbnail" else 5000
                    if best is None or score < best:
                        best, url = score, _text(im)
                caps = {x.get(XML_LANG): _text(x) for x in s.findall("caption")}
                if url:
                    c.screenshots.append((url, _pick(caps)))
        elif tag == "project_license":
            c.license = _text(child)
        elif tag == "url" and child.get("type") == "homepage":
            c.homepage = _text(child)
        elif tag == "releases":
            rels = child.findall("release")
            if rels:
                c.version = rels[0].get("version", "")
                c.released = rels[0].get("date", "")[:10] or _iso(rels[0].get("timestamp"))
        elif tag == "pkgname" and not c.pkgname:
            c.pkgname = _text(child)
        elif tag == "bundle" and child.get("type") == "flatpak":
            c.bundle = _text(child)
        elif tag == "launchable" and child.get("type") == "desktop-id" and not c.desktop_id:
            c.desktop_id = _text(child)
    c.name = _pick(names) or cid
    c.summary = _pick(sums)
    c.description = _pick(descs) or []
    _choose_icon(c, icons, icon_root, origin)
    return c


def _choose_icon(c, icons, icon_root, origin):
    for kind, size, value in sorted(icons, key=lambda t: (t[0] != "cached", -t[1])):
        if kind == "cached":
            for sz in (size, 128, 64):
                p = _icon_file(icon_root, origin, sz, value)
                if p:
                    c.icon_path = p
                    return
        elif kind == "local" and os.path.isfile(value):
            c.icon_path = value
            return
        elif kind == "remote" and not c.icon_url:
            c.icon_url = value
        elif kind == "stock" and not c.icon_name:
            c.icon_name = value


# --------------------------------------------------------------------------- gi reader

def _gi():
    import gi
    gi.require_version("AppStream", "1.0")
    from gi.repository import AppStream
    return AppStream


def have_gi() -> bool:
    try:
        _gi()
        return True
    except (ImportError, ValueError):
        return False


def _safe(fn, *a, default=None):
    try:
        v = fn(*a)
        return default if v is None else v
    except Exception:  # noqa: BLE001 - API differences between AppStream versions
        return default


def _box_items(box):
    if box is None:
        return []
    if isinstance(box, list):
        return box
    if hasattr(box, "as_array"):
        try:
            return list(box.as_array())
        except Exception:  # noqa: BLE001
            pass
    n = box.get_size() if hasattr(box, "get_size") else len(box)
    return [box.index_safe(i) for i in range(n)]


def _from_gi(AS, comp, icon_root="", origin=""):
    kind = _safe(AS.ComponentKind.to_string, _safe(comp.get_kind), default="")
    if kind not in APP_KINDS:
        return None
    c = Component(id=_safe(comp.get_id, default=""), kind=kind, origin=_safe(comp.get_origin, default="") or origin)
    if not c.id:
        return None
    c.name = _safe(comp.get_name, default="") or c.id
    c.summary = _safe(comp.get_summary, default="")
    c.description = markup_to_paragraphs(_safe(comp.get_description, default=""))
    dev = _safe(comp.get_developer)
    c.developer = (_safe(dev.get_name, default="") if dev is not None and not isinstance(dev, str) else dev) or \
        _safe(getattr(comp, "get_developer_name", lambda: ""), default="")
    c.categories = list(_safe(comp.get_categories, default=[]))
    c.keywords = list(_safe(comp.get_keywords, default=[]))
    c.license = _safe(comp.get_project_license, default="")
    c.homepage = _safe(comp.get_url, AS.UrlKind.HOMEPAGE, default="")
    c.pkgname = _safe(comp.get_pkgname, default="")
    b = _safe(comp.get_bundle, AS.BundleKind.FLATPAK)
    c.bundle = _safe(b.get_id, default="") if b is not None else ""
    la = _safe(comp.get_launchable, AS.LaunchableKind.DESKTOP_ID)
    ents = _safe(la.get_entries, default=[]) if la is not None else []
    c.desktop_id = ents[0] if ents else ""
    rels = _safe(comp.get_releases_plain)
    rel_items = _safe(rels.get_entries, default=[]) if rels is not None and hasattr(rels, "get_entries") else \
        _safe(getattr(comp, "get_releases", lambda: []), default=[])
    if rel_items:
        r = rel_items[0]
        c.version = _safe(r.get_version, default="")
        c.released = _iso(_safe(r.get_timestamp, default=0))
    icons = []
    for ic in _safe(comp.get_icons, default=[]):
        k = _safe(ic.get_kind)
        kname = {AS.IconKind.CACHED: "cached", AS.IconKind.STOCK: "stock", AS.IconKind.REMOTE: "remote",
                 AS.IconKind.LOCAL: "local"}.get(k, "")
        fn = _safe(ic.get_filename, default="")
        if fn and os.path.isfile(fn):
            icons.append(("local", _safe(ic.get_height, default=64), fn))
        elif kname == "remote":
            icons.append(("remote", _safe(ic.get_height, default=64), _safe(ic.get_url, default="")))
        elif kname:
            icons.append((kname, _safe(ic.get_height, default=64) or 64, _safe(ic.get_name, default="")))
    _choose_icon(c, icons, icon_root, c.origin)
    for s in _safe(comp.get_screenshots_all, default=[]):
        best, url = None, ""
        for im in _safe(s.get_images, default=[]):
            w = _safe(im.get_width, default=0)
            score = abs(w - 752) if _safe(im.get_kind) == AS.ImageKind.THUMBNAIL else 5000
            if best is None or score < best:
                best, url = score, _safe(im.get_url, default="")
        if url:
            c.screenshots.append((url, _safe(s.get_caption, default="")))
    return c


def parse_file(path: str, icon_root: str = "", origin: str = "") -> list[Component]:
    """Read one catalog file: gi AppStream when available, XML reader otherwise."""
    if have_gi() and not os.environ.get("FENESTRA_STORE_NO_GI_APPSTREAM"):
        try:
            from gi.repository import Gio
            AS = _gi()
            md = AS.Metadata()
            md.set_locale(i18n.LANG)
            md.parse_file(Gio.File.new_for_path(path), AS.FormatKind.XML)
            out = [c for c in (_from_gi(AS, x, icon_root, origin) for x in _box_items(md.get_components())) if c]
            if out:
                return out
        except Exception as e:  # noqa: BLE001
            util.log("AppStream gi reader failed, using XML reader:", e)
    return parse_xml(path, icon_root, origin)


def system_components() -> list[Component]:
    """Applications described by the OS catalog (Fedora's appstream-data): gi Pool or XML files."""
    if have_gi() and not os.environ.get("FENESTRA_STORE_NO_GI_APPSTREAM"):
        try:
            AS = _gi()
            pool = AS.Pool()
            pool.set_locale(i18n.LANG)
            try:
                pool.set_flags(AS.PoolFlags.LOAD_OS_CATALOG)  # RPM catalog only, Flatpak is separate
            except (AttributeError, TypeError):
                pass
            pool.load(None)
            out = [c for c in (_from_gi(AS, x) for x in _box_items(pool.get_components())) if c and c.pkgname]
            if out:
                return out
        except Exception as e:  # noqa: BLE001
            util.log("AppStream pool failed, using XML files:", e)
    comps = []
    for d in SYSTEM_XML_DIRS:
        for path in sorted(glob.glob(os.path.join(d, "*.xml*"))):
            icon_root = next((r for r in SYSTEM_ICON_DIRS if os.path.isdir(r)), "")
            try:
                comps += [c for c in parse_xml(path, icon_root) if c.pkgname]
            except (OSError, ET.ParseError) as e:
                util.log("cannot read", path, e)
    return comps
