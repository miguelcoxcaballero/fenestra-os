#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Check the session split of Fenestra Settings (backends/session.py, appearance,
shell_options, notifications, shellconf) without touching the real desktop.

HOME, XDG_CONFIG_HOME and XDG_DATA_HOME point to a new temporary directory and GSettings use
the keyfile backend inside it, so nothing outside that directory changes. Run from anywhere:

    python3 tools/test_session_backends.py          # exit 0 when every check passes

Optional cross-checks run when the tools are installed: the colour maths against the
original appearance.js (gjs), and shell.conf as read by Qt's QSettings (g++ + Qt 6 Core).
"""
import os
import shutil
import subprocess
import sys
import tempfile

TMP = tempfile.mkdtemp(prefix="fenestra-session-test-")
os.environ.update({"HOME": TMP, "GSETTINGS_BACKEND": "keyfile", "XDG_CURRENT_DESKTOP": "Fenestra",
                   "FENESTRA_SETTINGS_LANG": "en"})
for var in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "DBUS_SESSION_BUS_ADDRESS"):
    os.environ.pop(var, None)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(ROOT))
sys.path.insert(0, ROOT)

from fenestra_settings import util  # noqa: E402
from fenestra_settings.backends import (appearance, notifications, session, shell_options,  # noqa: E402
                                        shellconf)
from fenestra_settings.backends.appearance import gtkaccent  # noqa: E402

CONF = os.path.join(TMP, ".config", "fenestra", "shell.conf")
IFACE = "org.gnome.desktop.interface"
FAILED = []
PASSED = [0]


def check(name, cond, detail=""):
    if cond:
        PASSED[0] += 1
        print(f"  ok   {name}")
    else:
        FAILED.append(name)
        print(f"  FAIL {name} {detail}")


def text():
    with open(CONF, encoding="utf-8") as f:
        return f.read()


def section(name):
    """Lines of [name] in shell.conf."""
    out, cur = [], None
    for line in text().splitlines():
        if line.startswith("["):
            cur = line.strip("[]")
        elif cur == name and line.strip():
            out.append(line)
    return out


def desktop(name):
    os.environ["XDG_CURRENT_DESKTOP"] = name


# --------------------------------------------------------------------------------------------
print("session detection")
for value, fen in (("Fenestra", True), ("fenestra", True), ("KDE:Fenestra", True), ("GNOME", False),
                   ("ubuntu:GNOME", False), ("", False), ("FenestraX", False)):
    desktop(value)
    check(f"is_fenestra({value!r}) == {fen}", session.is_fenestra() is fen and session.is_gnome() is (not fen))
desktop("GNOME")
check("GNOME: nothing hidden", not session.hidden_pages() and not any(
    session.hidden_rows(p) for p in session.ROW_FEATURES))
check("GNOME: GNOME panels open GNOME Settings", session.panel_target("display") == (
    "gcc", ["gnome-control-center", "display"]))
check("GNOME: Spotlight wallpaper not offered", not session.supports("wallpaper-spotlight"))
desktop("Fenestra")
hp = session.hidden_pages()
for pid in ("fx-extensions", "fx-desktop-icons", "fx-workspaces", "multitasking", "fx-shortcuts"):
    check(f"Fenestra: page {pid} hidden", pid in hp)
check("Fenestra: dynamic workspaces etc. unsupported", not any(session.supports(f) for f in (
    "dynamic-workspaces", "workspaces-only-on-primary", "attach-modal-dialogs", "hot-corner")))
check("Fenestra: attach-modal row hidden", "attach-modal" in session.hidden_rows("fx-windows"))
check("Fenestra: title bar buttons row kept", "button-layout" not in session.hidden_rows("fx-windows"))
check("Fenestra: GNOME Settings / Tweaks / extension rows hidden",
      session.launch_target(["gnome-control-center", "power"]) is None
      and session.launch_target(["gnome-tweaks"]) is None
      and session.launch_target(["extension-manager"]) is None)
check("Fenestra: standalone tools still launch", session.launch_target(["gnome-disks"]) == ("argv", ["gnome-disks"]))
check("Fenestra: Spotlight wallpaper offered", session.supports("wallpaper-spotlight"))

# --------------------------------------------------------------------------------------------
print("shell.conf codec")
for v in ("center", "/usr/share/backgrounds/a b.jpg", "a,b", "say \"hi\"", "back\\slash", " lead", "@at",
          "#0078D4", "https://www.example.org/search?q=", "x=y;z", "ñandú"):
    check(f"string {v!r} round-trips", shellconf.decode(shellconf.encode(v)) == v, shellconf.encode(v))
for v in (["org.a.desktop", "org.b.desktop"], ["a, b", "c"], ["only.desktop", "x"]):
    check(f"list {v!r} round-trips", shellconf.decode(shellconf.encode(v)) == v, shellconf.encode(v))
check("list format is comma + space", shellconf.encode(["org.a.desktop", "org.b.desktop"])
      == "org.a.desktop, org.b.desktop")
check("empty list is @Invalid()", shellconf.encode([]) == "@Invalid()" and shellconf.decode("@Invalid()") is None)
check("bools are true/false", shellconf.encode(True) == "true" and shellconf.encode(False) == "false")

# --------------------------------------------------------------------------------------------
print("Fenestra session: shell.conf writes")
desktop("Fenestra")
os.makedirs(os.path.dirname(CONF))
with open(CONF, "w", encoding="utf-8") as f:
    f.write("; written by hand\n[Search]\nWebUrl=https://search.example.org/?q=\n\n[Taskbar]\nAlignment=center\n")
ino = os.stat(CONF).st_ino

check("set_color_scheme('dark') returns True", appearance.set_color_scheme("dark"))
check("[Appearance] ColorScheme=dark", "ColorScheme=dark" in section("Appearance"), section("Appearance"))
check("mirror: color-scheme = prefer-dark", util.gget(IFACE, "color-scheme") == "prefer-dark")
check("color_scheme() == 'dark'", appearance.color_scheme() == "dark")
check("file replaced atomically (new inode, no temp file left)", os.stat(CONF).st_ino != ino and not [
    n for n in os.listdir(os.path.dirname(CONF)) if n != "shell.conf"], os.listdir(os.path.dirname(CONF)))
check("unrelated keys and comments kept", "WebUrl=https://search.example.org/?q=" in section("Search")
      and text().startswith("; written by hand\n"))

check("set_accent('#e81123')", appearance.set_accent("#e81123"))
check("[Appearance] Accent=#E81123", "Accent=#E81123" in section("Appearance"), section("Appearance"))
check("mirror: accent-color = red", util.gget(IFACE, "accent-color") == "red")
check("accent() == '#E81123'", appearance.accent() == "#E81123", appearance.accent())
check("set_accent('teal') writes the teal base colour", appearance.set_accent("teal")
      and "Accent=#038387" in section("Appearance") and util.gget(IFACE, "accent-color") == "teal")
check("accent() reports the name back", appearance.accent() == "teal", appearance.accent())
appearance.set_color_scheme("light")
check("light: ColorScheme=light + mirror default", "ColorScheme=light" in section("Appearance")
      and util.gget(IFACE, "color-scheme") == "default")

wp = os.path.join(TMP, "wall.jpg")
open(wp, "wb").close()
check("set_wallpaper(path)", appearance.set_wallpaper(wp) and f"Wallpaper={wp}" in section("Appearance"))
check("wallpaper mirrored to picture-uri", (util.gget("org.gnome.desktop.background", "picture-uri") or "")
      .endswith("/wall.jpg"))
check("wallpaper() returns it", appearance.wallpaper(False) == wp)
check("spotlight mode", appearance.set_background_mode("spotlight") and "Wallpaper=spotlight" in
      section("Appearance") and appearance.background_mode() == "spotlight")
check("solid mode writes a colour", appearance.set_background_mode("solid")
      and appearance.background_mode() == "solid" and any(
          line.startswith("Wallpaper=#") for line in section("Appearance")))
check("picture mode goes back to the picture", appearance.set_background_mode("picture")
      and f"Wallpaper={wp}" in section("Appearance"))
check("animations off -> ReduceMotion=true", appearance.set_animations(False)
      and "ReduceMotion=true" in section("Appearance") and util.gget(IFACE, "enable-animations") is False)
appearance.set_animations(True)
check("set_cursor_size(32) -> GSettings + kcminputrc", appearance.set_cursor_size(32)
      and util.gget(IFACE, "cursor-size") == 32
      and shellconf.get("Mouse/cursorSize", file=os.path.join(TMP, ".config", "kcminputrc")) == "32")
check("fonts and text scale are mirrored", appearance.set_text_scale(1.25)
      and util.gget(IFACE, "text-scaling-factor") == 1.25)

check("set_alignment('left')", shell_options.set_alignment("left"))
check("[Taskbar] Alignment=left (replaced in place)", section("Taskbar").count("Alignment=left") == 1
      and "Alignment=center" not in section("Taskbar"), section("Taskbar"))
check("alignment() == 'left'", shell_options.alignment() == "left")
for mode, shell_value in (("hide", "hidden"), ("icon", "icon"), ("icon-label", "iconLabel"), ("box", "box")):
    shell_options.set_search_mode(mode)
    check(f"search mode {mode} -> SearchMode={shell_value}", f"SearchMode={shell_value}" in section("Taskbar")
          and shell_options.search_mode() == mode)
check("weather off -> Weather=false", shell_options.set_weather(False) and "Weather=false" in section("Taskbar")
      and shell_options.weather() is False)
pins = ["org.gnome.Nautilus.desktop", "org.mozilla.firefox.desktop"]
check("taskbar pins", shell_options.set_taskbar_pins(pins)
      and "Pinned=org.gnome.Nautilus.desktop, org.mozilla.firefox.desktop" in section("Taskbar"))
check("start pins", shell_options.set_start_pins(pins[::-1])
      and "Pinned=org.mozilla.firefox.desktop, org.gnome.Nautilus.desktop" in section("Start")
      and shell_options.start_pins() == pins[::-1] and shell_options.pinned_count() == 2)
check("reset start pins removes the key (shell defaults)", shell_options.reset_start_pins()
      and not any(line.startswith("Pinned=") for line in section("Start"))
      and shell_options.pinned_count() == len(shell_options.fenestra.DEFAULT_START_PINS))
check("unsupported taskbar options report False", not shell_options.supports("taskbar-autohide")
      and not shell_options.supports("taskbar-position") and shell_options.supports("alignment"))

check("set_dnd(True) -> [Notifications] DoNotDisturb=true", notifications.set_dnd(True)
      and "DoNotDisturb=true" in section("Notifications") and notifications.dnd() is True)
check("set_dnd(False)", notifications.set_dnd(False) and "DoNotDisturb=false" in section("Notifications")
      and notifications.dnd() is False)
check("lock screen notifications unsupported", not notifications.supports("lock-screen-notifications"))

util.READ_ONLY = True
before = text()
check("read-only: writes refused", not shell_options.set_alignment("center") and text() == before)
util.READ_ONLY = False

# --------------------------------------------------------------------------------------------
print("GTK accent theme (port of fenestra-tray appearance.js)")
for mode in ("Dark", "Light"):
    for ver in ("gtk-3.0", "gtk-4.0"):
        d = os.path.join(TMP, ".local", "share", "themes", f"Fenestra-{mode}", ver)
        os.makedirs(d)
        for f in ("gtk.css", "gtk-dark.css"):
            open(os.path.join(d, f), "w").close()
util.gset(IFACE, "gtk-theme", "Fenestra-Light")
appearance.set_accent("#E81123")
check("light mode: light accent wrapper", util.gget(IFACE, "gtk-theme") == "Fenestra-Light-AccentA",
      util.gget(IFACE, "gtk-theme"))
appearance.set_color_scheme("dark")
themes = os.path.join(TMP, ".local", "share", "themes")
check("dark mode: gtk-theme switched to the dark wrapper (letter alternates)",
      util.gget(IFACE, "gtk-theme") == "Fenestra-Dark-AccentB", util.gget(IFACE, "gtk-theme"))
wrapper = os.path.join(themes, "Fenestra-Dark-AccentB", "gtk-4.0", "gtk.css")
p = gtkaccent.palette("#e81123", True)
check("wrapper imports the base theme and defines the accent", os.path.isfile(wrapper) and
      f'@import url("file://{themes}/Fenestra-Dark/gtk-4.0/gtk.css");' in open(wrapper).read()
      and f"@define-color accent_bg_color {p['fill']};" in open(wrapper).read())
acc = os.path.join(TMP, ".config", "gtk-4.0", "fenestra-accent.css")
check("~/.config/gtk-4.0/fenestra-accent.css written", os.path.isfile(acc) and
      f"--accent-bg-color: {p['fill']};" in open(acc).read())
appearance.set_color_scheme("dark")
check("unchanged accent keeps the same wrapper", util.gget(IFACE, "gtk-theme") == "Fenestra-Dark-AccentB")
appearance.set_accent("#0078D4")
check("new accent alternates the wrapper name", util.gget(IFACE, "gtk-theme") == "Fenestra-Dark-AccentA")
check("palette for GNOME names uses the fixed table", gtkaccent.palette("blue", True)["fill"] == "#4cc2ff"
      and gtkaccent.palette("blue", False)["fill"] == "#005fb8")

gjs = shutil.which("gjs")
js = os.path.join(REPO, "desktop", "extensions", "fenestra-tray@fenestra-os.github.io", "appearance.js")
if gjs and os.path.isfile(js):
    src = open(js, encoding="utf-8").read()
    body = src[src.index("const ENUM"):src.index("// ---- helpers")].replace("export ", "")
    colors = ["#e81123", "#0078d4", "#ffb900", "#038387", "#68768a", "#000000", "#ffffff", "#7a7574",
              "#8e8cd8", "#00b7c3", "#ca5010", "#2d7d9a", "#486860", "#ff4343", "#9a0089", "#107c10"]
    harness = os.path.join(TMP, "palette.js")
    with open(harness, "w") as f:
        f.write(body + "\nconst out = [];\nfor (const c of %r) for (const d of [true, false]) {\n"
                "  const p = palette(c, d); out.push([c, d, p.fill, p.on, p.text, p.hover, p.press, p.textOn].join(' '));\n"
                "}\nprint(out.join('\\n'));\n" % colors)
    res = subprocess.run([gjs, harness], capture_output=True, text=True)
    want = res.stdout.split()
    got = " ".join(" ".join([c, "true" if d else "false"] + [gtkaccent.palette(c, d)[k] for k in (
        "fill", "on", "text", "hover", "press", "textOn")]) for c in colors for d in (True, False)).split()
    check(f"palette() matches appearance.js for {len(colors)} colours (gjs)", res.returncode == 0 and got == want,
          res.stderr[:300] or next((f"{a} != {b}" for a, b in zip(got, want) if a != b), ""))
else:
    print("  skip palette cross-check (gjs or appearance.js not found)")

# --------------------------------------------------------------------------------------------
print("GNOME session: GNOME keys only")
desktop("GNOME")
before = text()
check("set_color_scheme under GNOME", appearance.set_color_scheme("light") and util.gget(IFACE, "color-scheme")
      == "default")
check("set_accent under GNOME", appearance.set_accent("#107C10") and util.gget(IFACE, "accent-color") == "green")
notifications.set_dnd(True)
check("DND under GNOME = show-banners false", util.gget("org.gnome.desktop.notifications", "show-banners") is False)
check("GNOME: shell.conf untouched", text() == before)
desktop("Fenestra")

# --------------------------------------------------------------------------------------------
cxx = shutil.which("g++")
inc = "/usr/include/qt6"
if cxx and os.path.isdir(os.path.join(inc, "QtCore")):
    print("shell.conf as read by Qt QSettings")
    shellconf.set_many({"Taskbar/Pinned": ["org.a.desktop", "org.b.desktop"], "Start/Pinned": ["x.desktop"],
                        "Search/WebUrl": "https://example.org/s?q=a,b", "Appearance/Wallpaper": "/tmp/a b.jpg"})
    cpp = os.path.join(TMP, "qs.cpp")
    with open(cpp, "w") as f:
        f.write('#include <QSettings>\n#include <QStringList>\n#include <cstdio>\nint main(int, char **argv) {\n'
                '  QSettings s(QString::fromLocal8Bit(argv[1]), QSettings::IniFormat);\n'
                '  const char *keys[] = {"Taskbar/Alignment", "Taskbar/SearchMode", "Appearance/ColorScheme",\n'
                '    "Appearance/Accent", "Appearance/Wallpaper", "Search/WebUrl"};\n'
                '  for (const char *k : keys) printf("%s=%s\\n", k, qPrintable(s.value(QLatin1String(k)).toString()));\n'
                '  printf("Taskbar/Weather=%d\\n", s.value(QStringLiteral("Taskbar/Weather"), true).toBool());\n'
                '  printf("Notifications/DoNotDisturb=%d\\n", s.value(QStringLiteral("Notifications/DoNotDisturb")).toBool());\n'
                '  printf("Taskbar/Pinned=%s\\n", qPrintable(s.value(QStringLiteral("Taskbar/Pinned")).toStringList().join(QLatin1Char(\'|\'))));\n'
                '  printf("Start/Pinned=%s\\n", qPrintable(s.value(QStringLiteral("Start/Pinned")).toStringList().join(QLatin1Char(\'|\'))));\n'
                '  return s.status();\n}\n')
    exe = os.path.join(TMP, "qs")
    lib = "/usr/lib64" if os.path.isdir("/usr/lib64") else "/usr/lib"
    build = subprocess.run([cxx, "-std=c++17", "-fPIC", cpp, "-o", exe, f"-I{inc}", f"-I{inc}/QtCore", "-lQt6Core",
                            f"-L{lib}"], capture_output=True, text=True)
    if build.returncode != 0:
        print("  skip (cannot build the Qt reader):", build.stderr[:200])
    else:
        res = subprocess.run([exe, CONF], capture_output=True, text=True)
        got = dict(line.split("=", 1) for line in res.stdout.splitlines())
        want = {"Taskbar/Alignment": "left", "Taskbar/SearchMode": "box", "Appearance/ColorScheme": "dark",
                "Appearance/Accent": "#0078D4", "Appearance/Wallpaper": "/tmp/a b.jpg",
                "Search/WebUrl": "https://example.org/s?q=a,b", "Taskbar/Weather": "0",
                "Notifications/DoNotDisturb": "0", "Taskbar/Pinned": "org.a.desktop|org.b.desktop",
                "Start/Pinned": "x.desktop"}
        for k, v in want.items():
            check(f"QSettings reads {k} = {v!r}", got.get(k) == v, f"(got {got.get(k)!r})")
        check("QSettings status NoError", res.returncode == 0)
else:
    print("  skip QSettings cross-check (g++ / Qt 6 headers not found)")

print(f"\n{PASSED[0]} passed, {len(FAILED)} failed")
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if FAILED else 0)
