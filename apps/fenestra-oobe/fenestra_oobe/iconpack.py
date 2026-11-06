"""Icon pack recognition and previews for the "Personalize your icons" step.

Validation is done by the canonical implementation in
``fenestra-import-windows-assets`` (loaded as a module), so the OOBE, Fenestra
Settings and the command line tool all accept and refuse exactly the same
zips. See docs/ICON-PACK-FORMAT.md.
"""

import importlib.machinery
import importlib.util
import io
import re
import zipfile
from dataclasses import dataclass, field

from . import paths

_importer = None


class PackError(Exception):
    pass


def load_importer():
    """Import fenestra-import-windows-assets as a Python module (cached)."""
    global _importer
    if _importer is None:
        path = paths.importer()
        if path is None:
            raise PackError("the icon pack importer (fenestra-import-windows-assets) isn't installed")
        loader = importlib.machinery.SourceFileLoader("fenestra_import_windows_assets", path)
        spec = importlib.util.spec_from_loader(loader.name, loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
        _importer = mod
    return _importer


@dataclass
class PackInfo:
    path: str
    kind: str                      # "fenestra" or "theme"
    manifest: dict
    prefix: str
    names: list = field(default_factory=list)
    total: int = 0

    @property
    def name(self) -> str:
        return str(self.manifest.get("name") or self.manifest.get("id") or "")

    @property
    def source(self) -> dict:
        src = self.manifest.get("source")
        return src if isinstance(src, dict) else {}

    @property
    def contents(self) -> list:
        c = self.manifest.get("contents")
        if isinstance(c, list):
            return [str(x) for x in c]
        tops = {n[len(self.prefix):].split("/", 1)[0] for n in self.names if n.startswith(self.prefix)}
        return sorted(t for t in tops if t in ("fonts", "cursors", "assets", "icons", "glyphs", "apps", "bitmaps", "raw"))


def inspect(path: str) -> PackInfo:
    """Validate ``path``; raises PackError with a user-readable reason."""
    mod = load_importer()
    try:
        info = mod.inspect_pack(path)
    except mod.PackError as exc:
        raise PackError(str(exc)) from None
    return PackInfo(path, info["kind"], info["manifest"], info["prefix"], info["names"], info["total"])


def looks_like_zip(path: str) -> bool:
    try:
        return zipfile.is_zipfile(path)
    except OSError:
        return False


# -------------------------------------------------------------- previews ---
_SIZE_RANK = {"scalable": 10_000}


def _size_of(member: str) -> int:
    for part in member.split("/"):
        if part in _SIZE_RANK:
            return _SIZE_RANK[part]
        m = re.match(r"^(\d+)x\d+(@\d+)?$", part)
        if m:
            return int(m.group(1))
    return 0


def _best(names, pattern):
    rx = re.compile(pattern, re.I)
    hits = [n for n in names if rx.search(n)]
    if not hits:
        return None
    # Prefer large raster sizes up to 256, then scalable, then anything.
    return max(hits, key=lambda n: (min(_size_of(n), 256) if _size_of(n) != 10_000 else 200,
                                    n.lower().endswith(".svg")))


# (label, regex relative to the pack root, dark tile?)
PREVIEW_RULES = [
    ("Folder", r"^assets/folders/folder-empty\.(png|svg)$", False),
    ("Full folder", r"^assets/folders/folder-full\.(png|svg)$", False),
    ("This PC", r"^icons/[^/]+/.*/(computer|user-desktop)\.(png|svg)$", False),
    ("Start", r"^assets/branding/start-button\.(svg|png)$", True),
    ("Search", r"^assets/search/search\.(png|svg)$", True),
    ("Folder", r"^icons/[^/]+/.*/places/.*/?folder\.(png|svg)$|^icons/[^/]+/.*/folder\.(png|svg)$", False),
    ("Documents", r"^icons/[^/]+/.*/folder-documents\.(png|svg)$", False),
    ("Downloads", r"^icons/[^/]+/.*/folder-download\.(png|svg)$", False),
    ("Pictures", r"^icons/[^/]+/.*/folder-pictures\.(png|svg)$", False),
    ("Recycle Bin", r"^icons/[^/]+/.*/user-trash(-full)?\.(png|svg)$", False),
    ("Battery", r"^assets/battery/normal-0-(10|8)\.svg$", True),
    ("Network", r"^assets/status/[^/]*(wifi|wireless|network)[^/]*\.svg$", True),
    ("Volume", r"^assets/status/[^/]*(volume|speaker|audio)[^/]*\.svg$", True),
    ("Tray", r"^assets/status/[^/]+\.svg$", True),
    # Segoe Fluent glyphs (glyphs/, fill="currentColor": black on a light tile)
    ("Settings glyph", r"^glyphs/preferences-system\.svg$", False),
    ("Search glyph", r"^glyphs/system-search\.svg$", False),
    ("Calculator", r"^icons/[^/]+/48x48/apps/calculator\.png$", False),
]

# Generic themes: same idea relative to the theme directory.
THEME_RULES = [
    ("This PC", r"/(computer|user-desktop)\.(png|svg)$", False),
    ("Folder", r"/folder\.(png|svg)$", False),
    ("Home", r"/user-home\.(png|svg)$", False),
    ("Documents", r"/folder-documents\.(png|svg)$", False),
    ("Downloads", r"/folder-download\.(png|svg)$", False),
    ("Pictures", r"/folder-pictures\.(png|svg)$", False),
    ("Music", r"/folder-music\.(png|svg)$", False),
    ("Recycle Bin", r"/user-trash\.(png|svg)$", False),
    ("Settings", r"/(preferences-system|org\.gnome\.Settings)\.(png|svg)$", False),
    ("Terminal", r"/(utilities-terminal|org\.gnome\.Terminal)\.(png|svg)$", False),
]


def previews(info: PackInfo, limit: int = 12):
    """Return [(label, kind, data, dark_tile)] with kind 'png' or 'svg'."""
    rel = [n[len(info.prefix):] for n in info.names if n.startswith(info.prefix)]
    rules = PREVIEW_RULES if info.kind == "fenestra" else [(l, "^" + "(.*)" + p, d) for l, p, d in THEME_RULES]
    out, used = [], set()
    with zipfile.ZipFile(info.path) as zf:
        for label, pattern, dark in rules:
            if len(out) >= limit:
                break
            member = _best([n for n in rel if n not in used], pattern)
            if member is None:
                continue
            used.add(member)
            try:
                data = zf.read(info.prefix + member)
            except KeyError:
                continue
            if len(data) > 4 * 1024 * 1024:
                continue
            out.append((label, "svg" if member.lower().endswith(".svg") else "png", data, dark))
    return out


# ------------------------------------------------------------ demo pack ---
def _svg(body, size=48):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
            f'viewBox="0 0 48 48">{body}</svg>\n').encode()


_FOLDER = ('<path d="M4 12a3 3 0 0 1 3-3h11l4 4h19a3 3 0 0 1 3 3v21a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3z" '
           'fill="#e8a93b"/><path d="M4 18h40v19a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3z" fill="#f6c453"/>')
DEMO_ICONS = {
    "assets/folders/folder-empty.svg": _svg(_FOLDER),
    "assets/folders/folder-full.svg": _svg(_FOLDER + '<rect x="10" y="12" width="26" height="8" rx="1" fill="#fff"/>'),
    "assets/branding/start-button.svg": _svg(
        '<circle cx="24" cy="24" r="18" fill="#3aa0ff"/><path d="M24 12l10 12-10 12-10-12z" fill="#fff"/>'),
    "assets/search/search.svg": _svg(
        '<circle cx="21" cy="21" r="11" fill="none" stroke="#fff" stroke-width="4"/>'
        '<path d="M29 29l9 9" stroke="#fff" stroke-width="4" stroke-linecap="round"/>'),
    "assets/battery/normal-0-10.svg": _svg(
        '<rect x="6" y="15" width="32" height="18" rx="3" fill="none" stroke="#fff" stroke-width="2.5"/>'
        '<rect x="10" y="19" width="24" height="10" rx="1" fill="#fff"/><rect x="39" y="20" width="3" height="8" fill="#fff"/>'),
    "assets/status/network-wifi.svg": _svg(
        '<path d="M6 18a26 26 0 0 1 36 0M12 25a17 17 0 0 1 24 0M18 32a8 8 0 0 1 12 0" '
        'fill="none" stroke="#fff" stroke-width="3.5" stroke-linecap="round"/><circle cx="24" cy="38" r="3" fill="#fff"/>'),
    "assets/status/volume.svg": _svg(
        '<path d="M8 19h8l10-8v26l-10-8H8z" fill="#fff"/><path d="M32 17a10 10 0 0 1 0 14M37 12a17 17 0 0 1 0 24" '
        'fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round"/>'),
    "icons/Fenestra-Demo/scalable/places/computer.svg": _svg(
        '<rect x="5" y="8" width="38" height="26" rx="3" fill="#2b6cb0"/><rect x="8" y="11" width="32" height="20" '
        'fill="#8fd0ff"/><rect x="18" y="36" width="12" height="3" fill="#555"/><rect x="13" y="39" width="22" height="3" rx="1.5" fill="#777"/>'),
    "icons/Fenestra-Demo/scalable/places/folder-documents.svg": _svg(
        _FOLDER + '<rect x="17" y="21" width="14" height="16" rx="1" fill="#fff"/><path d="M20 26h8M20 30h8M20 34h5" stroke="#2b6cb0" stroke-width="1.5"/>'),
    "icons/Fenestra-Demo/scalable/places/folder-download.svg": _svg(
        _FOLDER + '<path d="M24 21v12m-5-5l5 5 5-5" fill="none" stroke="#2f855a" stroke-width="3" stroke-linecap="round"/>'),
    "icons/Fenestra-Demo/scalable/places/folder-pictures.svg": _svg(
        _FOLDER + '<rect x="15" y="22" width="18" height="13" rx="1" fill="#fff"/><path d="M17 33l5-6 4 4 3-3 3 5z" fill="#3aa0ff"/>'),
    "icons/Fenestra-Demo/scalable/places/user-trash.svg": _svg(
        '<path d="M13 14h22l-2 28H15z" fill="#cfd8e3"/><rect x="10" y="10" width="28" height="4" rx="2" fill="#a0aec0"/>'),
    "icons/Fenestra-Demo/index.theme": (b"[Icon Theme]\nName=Fenestra-Demo\nComment=Demo pack\nInherits=Fenestra\n"
                                        b"Directories=scalable/places\n\n[scalable/places]\nSize=48\nType=Scalable\n"
                                        b"MinSize=16\nMaxSize=512\nContext=Places\n"),
}


def make_demo_pack(path: str, name: str = "Demo icon pack"):
    """Build a small, original (non-Microsoft) pack used for demos, screenshots and tests."""
    import json
    manifest = {
        "format": "fenestra-icon-pack", "version": 1, "id": "fenestra-demo-pack", "name": name,
        "generator": "Fenestra OOBE demo", "source": {"os": "Windows 11", "build": "26200.6584", "locale": "en-US"},
        "created": "2026-11-05T20:00:00Z", "contents": ["assets", "icons"],
        "icon_theme": "Fenestra-Demo",
        "licence_note": "Demo artwork drawn for Fenestra; free to use.",
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("fenestra-pack.json", json.dumps(manifest, indent=2))
        for member, data in DEMO_ICONS.items():
            zf.writestr(member, data)
    with open(path, "wb") as fh:
        fh.write(buf.getvalue())
    return path
