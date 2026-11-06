"""Catalogue data model shared by every backend and the UI."""
from __future__ import annotations

from dataclasses import dataclass, field

from .i18n import N_

# Store categories, in display order: (key, English title, icon)
CATEGORIES = [
    ("productivity", N_("Productivity"), "st-cat-productivity-symbolic"),
    ("creativity", N_("Creativity"), "st-cat-creativity-symbolic"),
    ("multimedia", N_("Music and video"), "st-cat-multimedia-symbolic"),
    ("communication", N_("Internet and chat"), "st-cat-communication-symbolic"),
    ("utilities", N_("Utilities"), "st-cat-utilities-symbolic"),
    ("education", N_("Education and science"), "st-cat-education-symbolic"),
    ("development", N_("Development"), "st-cat-development-symbolic"),
    ("games", N_("Games"), "st-cat-games-symbolic"),
]
CATEGORY_TITLES = {k: t for k, t, _i in CATEGORIES}
CATEGORY_ICONS = {k: i for k, _t, i in CATEGORIES}

# freedesktop.org menu categories -> store category (first match wins)
FDO_MAP = [
    ("Game", "games"),
    ("Development", "development"), ("IDE", "development"), ("Debugger", "development"),
    ("Education", "education"), ("Science", "education"), ("Math", "education"),
    ("Office", "productivity"), ("Calendar", "productivity"), ("ProjectManagement", "productivity"),
    ("WordProcessor", "productivity"), ("Spreadsheet", "productivity"), ("ContactManagement", "productivity"),
    ("Graphics", "creativity"), ("2DGraphics", "creativity"), ("3DGraphics", "creativity"),
    ("Photography", "creativity"), ("AudioVideoEditing", "creativity"),
    ("AudioVideo", "multimedia"), ("Audio", "multimedia"), ("Video", "multimedia"), ("Player", "multimedia"),
    ("Network", "communication"), ("Chat", "communication"), ("Email", "communication"),
    ("WebBrowser", "communication"), ("InstantMessaging", "communication"),
    ("Utility", "utilities"), ("System", "utilities"), ("Settings", "utilities"),
    ("Accessibility", "utilities"), ("FileTools", "utilities"), ("Archiving", "utilities"),
]


def map_categories(fdo_categories) -> list[str]:
    cats = []
    fdo = set(fdo_categories or [])
    for name, key in FDO_MAP:
        if name in fdo and key not in cats:
            cats.append(key)
    return cats or ["utilities"]


# Source keys and labels
SOURCES = {"flathub": N_("Flathub"), "fedora": N_("Fedora")}

# Flatpak permission keys -> (English description, icon, sensitive?)
PERMISSIONS = {
    "network": (N_("Network access"), "st-perm-network-symbolic", False),
    "home": (N_("Read and write your home folder"), "st-perm-folder-symbolic", True),
    "host": (N_("Read and write all your files"), "st-perm-folder-symbolic", True),
    "host-ro": (N_("Read all your files"), "st-perm-folder-symbolic", True),
    "downloads": (N_("Your Downloads folder"), "st-perm-folder-symbolic", False),
    "documents": (N_("Your Documents folder"), "st-perm-folder-symbolic", False),
    "pictures": (N_("Your Pictures folder"), "st-perm-folder-symbolic", False),
    "music": (N_("Your Music folder"), "st-perm-folder-symbolic", False),
    "videos": (N_("Your Videos folder"), "st-perm-folder-symbolic", False),
    "devices": (N_("All devices (for example cameras)"), "st-perm-device-symbolic", True),
    "dri": (N_("Graphics acceleration"), "st-perm-device-symbolic", False),
    "audio": (N_("Play and record sound"), "st-perm-audio-symbolic", False),
    "x11": (N_("Legacy display system (X11)"), "st-perm-window-symbolic", True),
    "wayland": (N_("Wayland display"), "st-perm-window-symbolic", False),
    "bluetooth": (N_("Bluetooth"), "st-perm-device-symbolic", False),
    "system-bus": (N_("System services"), "st-perm-shield-symbolic", True),
    "session-bus": (N_("All desktop services"), "st-perm-shield-symbolic", True),
    "settings": (N_("Read and change desktop settings"), "st-perm-shield-symbolic", True),
    "none": (N_("No special permissions"), "st-perm-shield-symbolic", False),
}

# Operation states shown on buttons
AVAILABLE, QUEUED, INSTALLING, REMOVING, UPDATING, INSTALLED = (
    "available", "queued", "installing", "removing", "updating", "installed")
BUSY = (QUEUED, INSTALLING, REMOVING, UPDATING)


@dataclass
class Screenshot:
    url: str = ""                 # remote URL (downloaded into the cache) or local path
    caption: str = ""
    art: int = 0                  # demo: layout variant drawn by art.py


@dataclass
class App:
    uid: str                      # unique in the store: "<backend>:<id>"
    app_id: str                   # AppStream component id / package name
    backend: str                  # backend id that handles operations
    source: str                   # "flathub" | "fedora"
    name: str
    summary: str = ""
    description: list = field(default_factory=list)   # paragraphs; bullet lines start with "• "
    developer: str = ""
    categories: list = field(default_factory=list)    # store category keys
    kind: str = "app"             # "app" | "game"
    version: str = ""
    update_version: str = ""      # non-empty when an update is available
    download_size: int = 0
    installed_size: int = 0
    license: str = ""
    permissions: list | None = None   # None: unknown / not sandboxed (RPM)
    homepage: str = ""
    keywords: list = field(default_factory=list)
    icon_path: str = ""           # local icon file
    icon_url: str = ""            # remote icon
    screenshots: list = field(default_factory=list)   # [Screenshot]
    art: tuple = ()               # demo: (hue 0..1, glyph name) for generated icons
    installed: bool = False
    featured: bool = False
    popularity: int = 0           # higher = more popular (demo / install counts when known)
    released: str = ""            # ISO date of the latest release
    state: str = AVAILABLE
    progress: float = 0.0
    status_text: str = ""
    ref: str = ""                 # flatpak ref ("app/org.x.Y/x86_64/stable") or package id
    origin: str = ""              # flatpak remote / rpm repo
    desktop_id: str = ""          # for launching
    details_loaded: bool = False

    @property
    def is_game(self) -> bool:
        return self.kind == "game" or "games" in self.categories

    @property
    def has_update(self) -> bool:
        return self.installed and bool(self.update_version)

    @property
    def busy(self) -> bool:
        return self.state in BUSY

    def sync_state(self):
        if not self.busy:
            self.state = INSTALLED if self.installed else AVAILABLE


@dataclass
class Source:
    id: str                       # e.g. "flathub", "fedora", "updates", "rpmfusion-free"
    backend: str
    kind: str                     # "flathub" | "fedora"
    title: str
    description: str = ""
    enabled: bool = True
    can_toggle: bool = True


class StoreError(Exception):
    """An operation failed; the message is shown to the user."""
