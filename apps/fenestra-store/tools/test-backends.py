#!/usr/bin/env python3
"""Checks for the real backends that need no network, daemon or root:
* AppStream catalogue reading (gi AppStream-1.0 reader and the pure-Python XML reader) on
  tools/fixtures/appstream-sample.xml, in English and Spanish;
* Flatpak permission parsing;
* the flatpak / packagekit backends import and load (or report themselves unavailable)
  without raising when their typelibs are installed.
    python3 tools/test-backends.py        # exit 0 when everything passed
"""
import gzip
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from fenestra_store import i18n  # noqa: E402

failures = []


def check(cond, what):
    print(("  ok   " if cond else "  FAIL ") + what, flush=True)
    if not cond:
        failures.append(what)


def readers():
    from fenestra_store.backends import appstream
    tmp = tempfile.mkdtemp()
    src = os.path.join(HERE, "fixtures", "appstream-sample.xml")
    gz = os.path.join(tmp, "appstream.xml.gz")
    with open(src, "rb") as f, gzip.open(gz, "wb") as g:
        g.write(f.read())
    icons = os.path.join(tmp, "icons", "128x128")
    os.makedirs(icons)
    open(os.path.join(icons, "org.fenestra.sample.Telar.png"), "wb").close()
    modes = [("xml", True)] + ([("gi", False)] if appstream.have_gi() else [])
    if not appstream.have_gi():
        print("  (AppStream typelib not installed: only the XML reader is tested)")
    for lang in ("en", "es"):
        i18n.init(lang)
        for mode, no_gi in modes:
            if no_gi:
                os.environ["FENESTRA_STORE_NO_GI_APPSTREAM"] = "1"
            else:
                os.environ.pop("FENESTRA_STORE_NO_GI_APPSTREAM", None)
            comps = appstream.parse_file(gz, os.path.join(tmp, "icons"), "flathub")
            tag = f"[{mode} {lang}]"
            check(appstream.last_reader == mode, f"{tag} parsed by the {mode} reader ({appstream.last_reader})")
            check(len(comps) == 2, f"{tag} two applications, runtime skipped ({len(comps)})")
            t = next((c for c in comps if c.id == "org.fenestra.sample.Telar"), None)
            if t is None:
                continue
            want_sum = "Teje patrones a partir de formas simples" if lang == "es" else "Weave patterns from simple shapes"
            check(t.summary == want_sum, f"{tag} translated summary ({t.summary!r})")
            want_p = "Telar convierte" if lang == "es" else "Telar turns"
            check(bool(t.description) and t.description[0].startswith(want_p), f"{tag} description ({t.description})")
            check(any(p.startswith("• ") for p in t.description), f"{tag} bullet items")
            other = "Telar turns" if lang == "es" else "Telar convierte"
            check(len(t.description) == 2 and not any(p.startswith(other) for p in t.description),
                  f"{tag} only the UI language in the description")
            check(t.developer == "Sample Collective", f"{tag} developer ({t.developer!r})")
            check(t.version == "2.1.0" and t.released.startswith("2026"), f"{tag} newest release ({t.version} {t.released})")
            check(t.icon_path.endswith("128x128/org.fenestra.sample.Telar.png"), f"{tag} cached icon ({t.icon_path})")
            check(t.screenshots and t.screenshots[0][0].endswith("-752.png"), f"{tag} screenshot thumbnail")
            check(t.screenshots and t.screenshots[0][2] == "https://example.org/telar-1.png",
                  f"{tag} large screenshot for banners ({t.screenshots and t.screenshots[0][2]})")
            check(t.branding == {"light": "#bfdbfe", "dark": "#1e3a8a"}, f"{tag} branding colours ({t.branding})")
            check(t.bundle == "app/org.fenestra.sample.Telar/x86_64/stable", f"{tag} flatpak bundle")
            check(t.desktop_id == "org.fenestra.sample.Telar.desktop", f"{tag} launchable")
            check(t.license == "GPL-3.0-or-later" and "Graphics" in t.categories, f"{tag} license and categories")
            g = next(c for c in comps if c.id != t.id)
            check(g.developer == "Sample Games" and g.icon_name == "applications-games" and g.pkgname == "carrusel",
                  f"{tag} legacy developer_name, stock icon, pkgname")
    shutil.rmtree(tmp)
    i18n.init("en")


def permissions():
    try:
        from fenestra_store.backends.flatpak import parse_permissions
    except (ImportError, ValueError):
        print("  (Flatpak typelib not installed: permission parsing skipped)")
        return
    meta = ("[Application]\nname=org.x.Y\n\n[Context]\nshared=network;ipc;\nsockets=x11;wayland;pulseaudio;\n"
            "devices=dri;\nfilesystems=xdg-download;host:ro;!home;\n\n[Session Bus Policy]\nca.desrt.dconf=talk\n")
    p = parse_permissions(meta)
    check(p == ["network", "downloads", "host-ro", "dri", "audio", "x11", "wayland", "settings"],
          f"flatpak permissions parsed ({p})")
    check(parse_permissions("[Application]\nname=a\n") == ["none"], "no permissions -> 'none'")


def local_files():
    try:
        from fenestra_store.backends.flatpak import FlatpakBackend
    except (ImportError, ValueError):
        print("  (Flatpak typelib not installed: .flatpakref parsing skipped)")
        return
    tmp = tempfile.mkdtemp()
    ref = os.path.join(tmp, "org.example.App.flatpakref")
    with open(ref, "w") as f:
        f.write("[Flatpak Ref]\nName=org.example.App\nTitle=Example\nBranch=stable\n"
                "Url=https://dl.flathub.org/repo/\nSuggestRemoteName=flathub\nIsRuntime=false\n")
    repo = os.path.join(tmp, "example.flatpakrepo")
    with open(repo, "w") as f:
        f.write("[Flatpak Repo]\nTitle=Example repo\nUrl=https://example.org/repo/\n")
    b = FlatpakBackend.__new__(FlatpakBackend)
    b.arch = "x86_64"
    a = b.local_app(ref)
    check(a is not None and a.app_id == "org.example.App" and a.name == "Example" and a.local_file == ref
          and a.ref == "app/org.example.App/x86_64/stable" and a.source == "flathub", ".flatpakref -> app")
    r = b.local_app(repo)
    check(isinstance(r, dict) and r["title"] == "Example repo" and r["name"] == "example", ".flatpakrepo -> source")
    check(b.local_app(os.path.join(tmp, "x.rpm")) is None, "flatpak backend ignores .rpm")
    shutil.rmtree(tmp)


def backends():
    for mod, cls in (("flatpak", "FlatpakBackend"), ("packagekit", "PackageKitBackend")):
        try:
            m = __import__(f"fenestra_store.backends.{mod}", fromlist=[cls])
        except (ImportError, ValueError) as e:
            print(f"  ({mod}: typelib not installed: {e})")
            continue
        try:
            b = getattr(m, cls)()
            avail = b.available()
            apps = b.load() if avail else []
            srcs = b.sources() if avail else []
            check(True, f"{mod} backend: available={avail} apps={len(apps)} sources={len(srcs)} {b.why}")
        except Exception as e:  # noqa: BLE001
            check(False, f"{mod} backend raised {e.__class__.__name__}: {e}")
    from fenestra_store.backends import choose
    chosen = [b.id for b in choose(demo=False)]
    check(isinstance(chosen, list) and "webapp" in chosen, f"choose() without demo -> {chosen}")
    # same catalogue as GNOME Software: the system AppStream catalog and every enabled remote
    if "flatpak" in chosen or "packagekit" in chosen:
        from fenestra_store import popular
        from fenestra_store.store import Store
        st = Store(choose(demo=False))
        st.load(sync=True)
        top = [a.name for a in st.popular(games=False)[:5]]
        cur = [a for a in st.catalogue() if a.curated]
        check(len(cur) >= 5, f"curated popular apps found in the real catalogue ({len(cur)}): {top}")
        hero = st.hero()
        check(all(a.curated for a in hero[:4]) and all(a.screenshots for a in hero[:4]),
              f"hero: popular apps with screenshots ({[a.name for a in hero]})")
        check(bool(popular.gnome_picks()) or not os.path.exists(popular.APP_LIST_FILES[0]),
              f"GNOME Software's featured list read ({len(popular.gnome_picks())} apps)")


print("== AppStream readers")
readers()
print("== Flatpak permissions")
permissions()
print("== local files")
local_files()
print("== real backends (no daemon / network expected)")
backends()
print("BACKENDS", "OK" if not failures else "FAILED", len(failures))
sys.exit(1 if failures else 0)
