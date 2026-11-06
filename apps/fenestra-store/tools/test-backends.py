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
            check(len(comps) == 2, f"{tag} two applications, runtime skipped ({len(comps)})")
            t = next((c for c in comps if c.id == "org.fenestra.sample.Telar"), None)
            if t is None:
                continue
            want_sum = "Teje patrones a partir de formas simples" if lang == "es" else "Weave patterns from simple shapes"
            check(t.summary == want_sum, f"{tag} translated summary ({t.summary!r})")
            want_p = "Telar convierte" if lang == "es" else "Telar turns"
            check(bool(t.description) and t.description[0].startswith(want_p), f"{tag} description ({t.description})")
            check(any(p.startswith("• ") for p in t.description), f"{tag} bullet items")
            check(t.developer == "Sample Collective", f"{tag} developer ({t.developer!r})")
            check(t.version == "2.1.0" and t.released.startswith("2026"), f"{tag} newest release ({t.version} {t.released})")
            check(t.icon_path.endswith("128x128/org.fenestra.sample.Telar.png"), f"{tag} cached icon ({t.icon_path})")
            check(t.screenshots and t.screenshots[0][0].endswith("-752.png"), f"{tag} screenshot thumbnail")
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


def backends():
    from gi.repository import GLib  # noqa: F401
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
    check(isinstance(chosen, list), f"choose() without demo -> {chosen}")


print("== AppStream readers")
readers()
print("== Flatpak permissions")
permissions()
print("== real backends (no daemon / network expected)")
backends()
print("BACKENDS", "OK" if not failures else "FAILED", len(failures))
sys.exit(1 if failures else 0)
