"""What comes first: Fenestra's curated list of popular apps and games, then the apps GNOME
Software itself features (its org.gnome.App-list.xml from gnome-software / appstream-data),
then the most complete listings.

Real catalogues carry no download counts, so the Store ranks with this instead of inventing
numbers. Each entry lists the ids the app has in the different sources (Flathub id, Fedora
AppStream id, web app id); the first one present in the catalogue is used.
"""
from __future__ import annotations

import glob
import os
import xml.etree.ElementTree as ET

# Ordered: the first ones lead Home's hero, the "Popular apps" panel and the Apps page.
POPULAR_APPS = [
    ("com.google.Chrome",),
    ("web.youtube",),
    ("com.spotify.Client",),
    ("com.brave.Browser",),
    ("com.discordapp.Discord",),
    ("web.whatsapp",),
    ("org.telegram.desktop", "org.telegram"),
    ("org.videolan.VLC",),
    ("us.zoom.Zoom",),
    ("org.mozilla.firefox", "firefox"),
    ("com.microsoft.Edge",),
    ("com.obsproject.Studio",),
    ("org.gimp.GIMP", "gimp"),
    ("org.libreoffice.LibreOffice", "org.libreoffice.LibreOffice.writer", "libreoffice-writer"),
    ("com.visualstudio.code",),
    ("com.slack.Slack",),
    ("web.netflix",),
    ("web.primevideo",),
    ("web.disneyplus",),
    ("org.kde.kdenlive",),
    ("org.inkscape.Inkscape",),
    ("org.audacityteam.Audacity",),
    ("org.blender.Blender",),
    ("com.github.IsmaelMartinez.teams_for_linux",),
    ("org.signal.Signal",),
    ("md.obsidian.Obsidian",),
    ("org.mozilla.Thunderbird", "org.mozilla.thunderbird"),
    ("com.bitwarden.desktop",),
    ("org.qbittorrent.qBittorrent",),
    ("com.github.tchx84.Flatseal",),
]
POPULAR_GAMES = [
    ("com.valvesoftware.Steam",),
    ("com.heroicgameslauncher.hgl",),
    ("net.lutris.Lutris",),
    ("org.prismlauncher.PrismLauncher",),
    ("com.usebottles.bottles",),
    ("net.minetest.Minetest", "org.luanti.luanti"),
    ("org.libretro.RetroArch",),
    ("net.supertuxkart.SuperTuxKart",),
    ("com.play0ad.zeroad",),
    ("org.wesnoth.Wesnoth",),
    ("io.github.ryubing.Ryujinx", "org.ppsspp.PPSSPP"),
    ("net.pcsx2.PCSX2",),
    ("org.DolphinEmu.dolphin-emu",),
    ("io.mrarm.mcpelauncher",),
]

APP_LIST_FILES = ["/usr/share/swcatalog/xml/org.gnome.App-list.xml", "/usr/share/app-info/xmls/org.gnome.App-list.xml"]

CURATED = 100000     # popularity of the first curated entry; later entries count down
GNOME_FEATURED = 600
GNOME_POPULAR = 400

_gnome_cache: dict | None = None


def gnome_picks(paths=None) -> dict:
    """{app id: weight} from GNOME Software's own list of featured and popular apps."""
    global _gnome_cache
    if _gnome_cache is not None and paths is None:
        return _gnome_cache
    out = {}
    files = paths if paths is not None else [p for pat in APP_LIST_FILES for p in glob.glob(pat)]
    for path in files:
        if not os.path.isfile(path):
            continue
        try:
            root = ET.parse(path).getroot()
        except (OSError, ET.ParseError):
            continue
        for comp in root.iter("component"):
            cid = (comp.findtext("id") or "").strip().removesuffix(".desktop")
            if not cid:
                continue
            w = 0
            if any((k.text or "").strip() == "GnomeSoftware::popular" for k in comp.iter("kudo")):
                w += GNOME_POPULAR
            if any(v.get("key") == "GnomeSoftware::FeatureTile" for v in comp.iter("value")):
                w += GNOME_FEATURED
            if w:
                out[cid] = max(out.get(cid, 0), w)
    if paths is None:
        _gnome_cache = out
    return out


def curated_order(games: bool | None = None) -> list[tuple]:
    if games is None:
        return POPULAR_APPS + POPULAR_GAMES
    return POPULAR_GAMES if games else POPULAR_APPS


def apply(apps, gnome=None) -> int:
    """Raise the popularity of curated apps (in list order) and of GNOME Software's picks.
    Returns how many curated entries were found. `apps` already carry a quality score."""
    by_id: dict[str, list] = {}
    for a in apps:
        by_id.setdefault(a.app_id, []).append(a)
        if a.pkgname:
            by_id.setdefault(a.pkgname, []).append(a)
    found = 0
    seen = set()
    # games interleave after the first apps on Home (Steam comes right after VLC)
    for lst, base in ((POPULAR_APPS, CURATED), (POPULAR_GAMES, CURATED - 75)):
        for i, ids in enumerate(lst):
            for cid in ids:
                hits = [a for a in by_id.get(cid, []) if id(a) not in seen]
                if hits:
                    found += 1
                    for a in hits:
                        a.popularity = base - i * 10
                        a.curated = True
                        seen.add(id(a))
                    break
    picks = gnome_picks() if gnome is None else gnome
    for a in apps:
        if id(a) not in seen and a.app_id in picks:
            a.popularity += picks[a.app_id]
    return found


def is_curated(app) -> bool:
    return getattr(app, "curated", False)
