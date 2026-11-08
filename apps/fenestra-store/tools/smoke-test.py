#!/usr/bin/env python3
"""Smoke test for Fenestra Store.

Part 1 (always, no display needed): drives the demo backend through the Store end to end:
catalogue loads, search finds apps (accent-insensitive), install / uninstall / update change
state with progress callbacks, Library lists installed apps and updates, Update all, sources.

Part 1b (no display): the curated popular list and how it ranks a catalogue, the hero choice,
the banner/icon loader (one download per image, scaled cache, dominant colour), web apps
(install = a launcher file, uninstall), the GNOME Software / Discover launcher overrides and
the GNOME Software compatible command line (local files, appstream:// links).

Part 2 (--ui, needs a Wayland/X display): opens the window in demo mode and builds every page,
the app page of every catalogue entry and the search results, failing on any traceback.

    python3 tools/smoke-test.py                 # store only
    WAYLAND_DISPLAY=w0 python3 tools/smoke-test.py --ui --lang es
Exit status 0 when everything passed.
"""
import argparse
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("FENESTRA_STORE_DEMO_SPEED", "0.05")
import tempfile  # noqa: E402
import warnings  # noqa: E402

warnings.filterwarnings("ignore", message=".*DesktopAppInfo is deprecated.*")

TMP = tempfile.mkdtemp(prefix="fenestra-store-smoke-")
os.environ["XDG_CACHE_HOME"] = os.path.join(TMP, "cache")   # never touch the user's caches

ap = argparse.ArgumentParser()
ap.add_argument("--ui", action="store_true", help="also build every page in a window")
ap.add_argument("--lang", default="en")
args = ap.parse_args()

from fenestra_store import i18n, util  # noqa: E402

i18n.init(args.lang)
util.DEMO = True
util.DEMO_SPEED = float(os.environ["FENESTRA_STORE_DEMO_SPEED"])

from gi.repository import GLib  # noqa: E402

from fenestra_store.backends import choose  # noqa: E402
from fenestra_store.store import Store  # noqa: E402

failures = []
errors = []
sys.excepthook = lambda *a: (errors.append(a), traceback.print_exception(*a))


def check(cond, what):
    print(("  ok   " if cond else "  FAIL ") + what, flush=True)
    if not cond:
        failures.append(what)


def wait(pred, timeout=20.0):
    ctx = GLib.MainContext.default()
    end = time.monotonic() + timeout
    while not pred() and time.monotonic() < end:
        ctx.iteration(False)
        time.sleep(0.002)
    while ctx.pending():
        ctx.iteration(False)
    return pred()


def store_test():
    print("== store / demo backend")
    backends = choose(demo=True)
    check([b.id for b in backends] == ["demo"], "demo backend chosen")
    st = Store(backends)
    events = {"progress": [], "done": [], "updates": 0, "changed": 0}
    st.connect("progress", lambda _s, uid, f, t: events["progress"].append((uid, f, t)))
    st.connect("job-done", lambda _s, uid, op, ok, msg: events["done"].append((uid, op, ok, msg)))
    st.connect("updates-changed", lambda *_: events.__setitem__("updates", events["updates"] + 1))
    st.connect("app-changed", lambda *_: events.__setitem__("changed", events["changed"] + 1))
    st.load()
    check(wait(lambda: st.loaded), "catalogue loads")
    cat = st.catalogue()
    check(20 <= len(cat) <= 30, f"20-30 apps in the catalogue ({len(cat)})")
    check(len(st.apps) == len(cat) + 1, "one app has an alternative source (folded into one entry)")
    check(len(st.featured()) >= 3, f"featured apps ({len(st.featured())})")
    check(all(a.is_game for a in st.popular(games=True)) and st.popular(games=True), "games list")
    check(not any(a.is_game for a in st.popular(games=False)), "apps list has no games")
    check(st.new_and_updated(limit=3)[0].released >= st.new_and_updated()[-1].released, "new and updated sorted")
    for key in ("productivity", "creativity", "utilities", "games", "education", "development"):
        check(bool(st.by_category(key)), f"category {key} has apps")
    incomplete = [a.name for a in cat if not (a.name and a.summary and a.description and a.developer and a.art
                                              and a.version and a.license and a.screenshots)]
    check(not incomplete, f"every entry has name, summary, description, developer, art ({incomplete})")

    # search
    r = st.search("rapidas")
    check(bool(r) and r[0].name == "Notas rápidas", "search 'rapidas' finds Notas rápidas (accents folded)")
    check(st.search("Ola")[0].name == "Reproductor Ola", "search 'Ola' ranks Reproductor Ola first")
    check(all(a.is_game for a in st.search("a", kind="games")), "search filtered to games")
    check(st.search("zzqqxx") == [], "search without matches is empty")
    check(bool(st.search("Faro")), "search by developer")

    lienzo = next(a for a in cat if a.name == "Lienzo")
    check(lienzo.source == "flathub" and len(st.alternatives(lienzo)) == 1, "Lienzo: Flathub + Fedora alternative")
    check(len(st.by_developer(lienzo)) >= 2, "other apps by the same developer")
    check(lienzo.permissions is not None and st.alternatives(lienzo)[0].permissions is None,
          "permissions only for Flatpak apps")

    # library
    inst = st.installed()
    ups = st.updates()
    check(len(inst) >= 5, f"library lists installed apps ({len(inst)})")
    check(len(ups) >= 2, f"library lists updates ({len(ups)})")
    check({a.source for a in inst} == {"flathub", "fedora"}, "installed apps from both sources")
    check(st.last_checked is not None, "last checked time")

    # install
    target = next(a for a in cat if not a.installed and not a.is_game)
    events["progress"].clear()
    st.install(target.uid)
    check(target.state == "queued", "install queued")
    check(wait(lambda: any(d[0] == target.uid for d in events["done"])), "install finished")
    prog = [p for p in events["progress"] if p[0] == target.uid]
    check(len(prog) >= 3, f"install progress callbacks ({len(prog)})")
    check(all(prog[i][1] <= prog[i + 1][1] for i in range(len(prog) - 1)), "progress increases")
    check(target.installed and target.state == "installed", "installed after install")
    check(target in st.installed(), "library lists the new app")

    # uninstall
    events["done"].clear()
    st.remove(target.uid)
    check(wait(lambda: events["done"]), "uninstall finished")
    check(events["done"][0][2] and not target.installed and target.state == "available", "removed")

    # update one
    up = ups[0]
    new_version = up.update_version
    events["done"].clear()
    events["progress"].clear()
    st.update(up.uid)
    check(wait(lambda: events["done"]), "update finished")
    check(up.version == new_version and not up.has_update, f"updated to {new_version}")
    check(bool(events["progress"]), "update progress callbacks")
    check(len(st.updates()) == len(ups) - 1, "one update fewer")

    # update all
    events["done"].clear()
    n = len(st.updates())
    st.update_all()
    check(wait(lambda: len(events["done"]) >= n), f"update all finished ({n} apps)")
    check(st.updates() == [], "no updates left")

    # check updates again (demo: nothing new)
    before = st.last_checked
    st.check_updates()
    check(wait(lambda: not st.checking), "check for updates")
    check(st.last_checked and st.last_checked >= before, "last checked advanced")

    # sources: switching Flathub off hides Flathub apps that are not installed
    flathub = next(s for s in st.sources() if s.id == "flathub")
    done = []
    st.set_source_enabled(flathub, False, lambda ok, msg: done.append(ok))
    check(wait(lambda: done) and done[0], "Flathub disabled")
    vis = st.catalogue()
    check(all(a.source != "flathub" or a.installed for a in vis), "only installed Flathub apps remain")
    check(next(a for a in vis if a.app_id == lienzo.app_id).source == "fedora", "Lienzo falls back to Fedora")
    done.clear()
    st.set_source_enabled(flathub, True, lambda ok, msg: done.append(ok))
    check(wait(lambda: done) and len(st.catalogue()) == len(cat), "Flathub enabled again")
    check(not st.busy_apps(), "no operation left running")
    return st


def popular_test():
    print("== popular list, hero, banner loader")
    from fenestra_store import popular
    from fenestra_store.model import App, Screenshot

    def mk(aid, name, shots=1, game=False, pkg=""):
        return App(uid=f"t:{aid}", app_id=aid, backend="t", source="flathub", name=name, summary=name,
                   categories=["games" if game else "utilities"], kind="game" if game else "app", pkgname=pkg,
                   screenshots=[Screenshot(url=f"https://example.org/{aid}.png") for _i in range(shots)])
    apps = [mk("org.example.Zeta", "Zeta"), mk("com.spotify.Client", "Spotify"), mk("web.youtube", "YouTube", 0),
            mk("com.google.Chrome", "Google Chrome"), mk("org.example.Gnome", "Gnome pick"),
            mk("com.valvesoftware.Steam", "Steam", 1, True), mk("x.firefox", "Firefox", 1, False, "firefox"),
            mk("org.telegram.desktop", "Telegram")]
    for a in apps:
        a.popularity = 3
    n = popular.apply(apps, gnome={"org.example.Gnome": popular.GNOME_POPULAR})
    check(n == 6, f"curated entries found ({n})")
    order = [a.name for a in sorted(apps, key=lambda a: -a.popularity)]
    check(order[:3] == ["Google Chrome", "YouTube", "Spotify"], f"Chrome, YouTube, Spotify first ({order[:3]})")
    check(order.index("Gnome pick") < order.index("Zeta"), "GNOME Software's picks before other apps")
    check(next(a for a in apps if a.name == "Firefox").curated, "curated entries match package names too")
    ids = [i for entry in popular.POPULAR_APPS for i in entry]
    for want in ("com.google.Chrome", "web.youtube", "com.spotify.Client", "com.brave.Browser",
                 "com.discordapp.Discord", "web.whatsapp", "org.telegram.desktop", "org.videolan.VLC", "us.zoom.Zoom",
                 "org.mozilla.firefox", "com.microsoft.Edge", "com.obsproject.Studio", "org.gimp.GIMP",
                 "com.visualstudio.code", "com.slack.Slack", "web.netflix", "web.primevideo", "web.disneyplus"):
        check(want in ids, f"popular list has {want}")
    check(ids.index("com.google.Chrome") < ids.index("web.youtube") < ids.index("com.spotify.Client")
          < ids.index("com.brave.Browser"), "popular list order: Chrome, YouTube, Spotify, Brave")
    from fenestra_store.backends import webapps
    web_ids = {w[0] for w in webapps.WEB_APPS}
    check({"web.youtube", "web.whatsapp", "web.netflix", "web.primevideo", "web.disneyplus"} <= web_ids,
          "web apps for the services without a Linux app")
    gp = os.path.join(TMP, "applist.xml")
    with open(gp, "w") as f:
        f.write('<components><component merge="append"><id>a.b.C</id><custom><value key="GnomeSoftware::FeatureTile">'
                'True</value></custom><kudos><kudo>GnomeSoftware::popular</kudo></kudos></component>'
                '<component><id>d.e.F</id></component></components>')
    picks = popular.gnome_picks([gp])
    check(picks == {"a.b.C": popular.GNOME_POPULAR + popular.GNOME_FEATURED}, f"GNOME Software app list read ({picks})")

    # the Store: curated first, hero = popular apps with screenshots
    from fenestra_store.backends import Backend

    class Fake(Backend):
        id = "t"
        label = "test"

        def load(self):
            return [mk(a.app_id, a.name, len(a.screenshots), a.is_game, a.pkgname) for a in apps]
    st = Store([Fake()])
    st.load(sync=True)
    check(st.has_popularity, "a catalogue with curated apps says 'Popular'")
    names = [a.name for a in st.popular(games=False)]
    check(names[:3] == ["Google Chrome", "YouTube", "Spotify"], f"Popular apps start with the curated list ({names[:4]})")
    hero = [a.name for a in st.hero()]
    check(hero[0] == "Google Chrome" and "Zeta" not in hero[:6], f"hero = popular apps ({hero})")
    check(all(a.screenshots for a in st.hero()), "the hero shows apps that have screenshots")
    check([a.name for a in st.hero(games=True)][:1] == ["Steam"], "games hero starts with Steam")

    # banner / icon loader
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    from fenestra_store import media
    src = os.path.join(TMP, "shot.png")
    pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 2000, 1000)
    pb.fill(0xd02020ff)
    pb.savev(src, "png", [], [])
    calls = []
    ld = media.Loader(workers=2)
    got = []

    def job():
        calls.append(1)
        return media.banner_texture(src, 640)
    ld.get("k", job, got.append)
    ld.get("k", job, got.append)
    check(wait(lambda: len(got) == 2), "two widgets asking for one banner both get it")
    check(len(calls) == 1, f"one download/decode per banner ({len(calls)})")
    check(got[0] is not None and got[0].get_width() == 640 and got[0].get_height() == 320,
          f"banner scaled down to the tile width ({got[0] and (got[0].get_width(), got[0].get_height())})")
    sync = []
    ld.get("k", job, sync.append)
    check(len(sync) == 1 and len(calls) == 1, "cached banner returned at once, without a new job")
    scaled = media.scaled_file(src, 640, src)
    check(bool(scaled) and scaled.startswith(os.path.join(TMP, "cache")) and os.path.isfile(scaled),
          "scaled banner cached under ~/.cache/fenestra-store/banners")
    check(media.scaled_file(src, 640, src) == scaled, "scaled banner reused")
    col = media.dominant_color(src)
    check(col.startswith("#") and int(col[1:3], 16) > 150 > int(col[3:5], 16), f"dominant colour of a red image ({col})")
    a = apps[0]
    a.brand_dark = "#123456"
    check(media.banner_colour(a, True) == "#123456", "banner uses the branding colour")
    a.brand_dark = a.brand_light = ""
    check(media.banner_colour(a, True, "#ff0000").startswith("#") and media.banner_colour(a, True) == "#2b2b2b",
          "banner falls back to the icon colour, then neutral grey")


def webapps_test():
    print("== web apps")
    from fenestra_store.backends import webapps
    apps_dir, data_dir = os.path.join(TMP, "applications"), os.path.join(TMP, "webapps")
    pwa = os.path.join(TMP, "gnome-pwa-list-test.xml")
    with open(pwa, "w") as f:
        f.write('<components><component type="web-application"><id>x.desktop</id><name>Pad</name>'
                '<summary>Notes</summary><launchable type="url">https://pad.example.org/</launchable>'
                '<icon type="remote" width="512" height="512">https://pad.example.org/i.png</icon>'
                '<categories><category>Office</category></categories></component></components>')
    be = webapps.WebAppBackend(apps_dir, data_dir, [pwa])
    apps = {a.app_id: a for a in be.load()}
    check({"web.youtube", "web.whatsapp", "web.netflix"} <= set(apps), "curated web apps listed")
    check("web.pad_example_org" in apps and apps["web.pad_example_org"].icon_url.endswith("/i.png"),
          "GNOME Software's web app list read")
    yt = apps["web.youtube"]
    check(yt.packaging == "web" and yt.source == "web" and not yt.installed and yt.brand_dark,
          "YouTube: web app, not installed, branding colour")
    q = webapps.exec_quote(["/usr/bin/brave", "--app=https://x.org/?a=1&b=2"])
    check(q == '/usr/bin/brave "--app=https://x.org/?a=1&b=2"', f"Exec quoting ({q})")
    check(webapps.wm_class("https://www.youtube.com/", "brave") == "brave-www.youtube.com__-Default", "window class")
    m = webapps.manifest_icon("https://s.org/m.json", '{"icons": [{"src": "a16.png", "sizes": "16x16"}, '
                              '{"src": "m.png", "sizes": "512x512", "purpose": "maskable"}, '
                              '{"src": "/a192.png", "sizes": "192x192"}]}')
    check(m == "https://s.org/a192.png", f"manifest icon: largest full-colour one ({m})")
    man, best = webapps.page_icon("https://s.org/x/", '<link rel="manifest" href="/m.json"><link rel="icon" '
                                  'href="f.ico"><link rel="apple-touch-icon" sizes="180x180" href="/t.png">')
    check(man == "https://s.org/m.json" and best == "https://s.org/t.png", f"page icon links ({man}, {best})")
    events = []
    be.install(yt, lambda f, t: events.append(f))
    path = be.desktop_path(yt)
    check(os.path.isfile(path), "install writes a launcher")
    text = open(path).read()
    check(f"{webapps.MARK}=web.youtube" in text and "https://www.youtube.com/" in text, "launcher opens the site")
    from gi.repository import Gio
    info = Gio.DesktopAppInfo.new_from_filename(path)
    check(info is not None and info.get_name() == "YouTube", "launcher is a valid desktop entry")
    check(webapps.WebAppBackend(apps_dir, data_dir, []).load()[0].installed, "installed after a reload")
    be.remove(yt, lambda f, t: None)
    check(not os.path.exists(path), "uninstall removes the launcher")


def integration_test():
    print("== one store: launcher overrides, command line")
    from fenestra_store import integration
    d = os.path.join(TMP, "overrides")
    os.makedirs(d)
    foreign = os.path.join(d, "org.kde.discover.snap.desktop")
    with open(foreign, "w") as f:
        f.write("[Desktop Entry]\nName=Mine\n")
    exe = os.path.join(TMP, "bin", "fenestra-store")   # GLib only loads entries whose Exec exists
    os.makedirs(os.path.dirname(exe))
    with open(exe, "w") as f:
        f.write("#!/bin/sh\n")
    os.chmod(exe, 0o755)
    written = integration.write_overrides(d, exe)
    names = {os.path.basename(p) for p in written}
    check({"org.gnome.Software.desktop", "org.kde.discover.desktop", "gnome-software-local-file-flatpak.desktop",
           "gnome-software-local-file-packagekit.desktop", "org.kde.discover.urlhandler.desktop"} <= names,
          "GNOME Software and Discover launchers overridden")
    check(open(foreign).read().startswith("[Desktop Entry]\nName=Mine"), "a foreign override is left alone")
    from gi.repository import Gio
    gs = Gio.DesktopAppInfo.new_from_filename(os.path.join(d, "org.gnome.Software.desktop"))
    check(gs is not None and gs.get_nodisplay() and gs.get_name() == "Fenestra Store"
          and gs.get_commandline().startswith(exe), "org.gnome.Software opens Fenestra Store, hidden")
    check("DBusActivatable" not in open(os.path.join(d, "org.gnome.Software.desktop")).read(),
          "no D-Bus activation of GNOME Software")
    url = open(os.path.join(d, "org.kde.discover.urlhandler.desktop")).read()
    check("Hidden=true" in url, "Discover's link handler hidden")
    lf = Gio.DesktopAppInfo.new_from_filename(os.path.join(d, "gnome-software-local-file-flatpak.desktop"))
    check(lf is not None and "--local-filename" in lf.get_commandline() and
          "application/vnd.flatpak.ref" in lf.get_supported_types(), ".flatpakref handler opens Fenestra Store")
    removed = integration.remove_overrides(d)
    check(len(removed) == len(written) and os.path.exists(foreign), "overrides removed, foreign file kept")

    from fenestra_store import app as appmod
    o = appmod.parse_args(["x", "--local-filename", "pkg.flatpakref"])
    check(appmod.start_target(o) == ("file", os.path.abspath("pkg.flatpakref")), "--local-filename")
    o = appmod.parse_args(["x", "/tmp/a.rpm"])
    check(appmod.start_target(o) == ("file", "/tmp/a.rpm"), ".rpm as an argument")
    o = appmod.parse_args(["x", "flatpak+https://dl.flathub.org/repo/appstream/org.x.Y.flatpakref"])
    check(appmod.start_target(o)[0] == "file", "flatpak+https:// link")
    o = appmod.parse_args(["x", "appstream://org.gnome.Maps.desktop"])
    check(appmod.start_target(o) == ("app", "org.gnome.Maps.desktop"), "appstream:// link")
    o = appmod.parse_args(["x", "--install=org.x.Y", "--interaction=full"])
    check(appmod.start_target(o) == ("app", "org.x.Y"), "GNOME Software's --install opens the app page")
    o = appmod.parse_args(["x", "--mode=updates"])
    check(appmod.start_target(o) == ("updates", None), "--mode=updates")


def ui_test():
    print(f"== UI pages (--lang {args.lang})")
    from fenestra_store import app as appmod
    opts = appmod.parse_args(["x", "--demo-data", "--lang", args.lang])
    a = appmod.App(opts)
    state = {"it": None}

    def steps():
        w = a.win
        while not w.store.loaded:
            yield
        for pid in ("home", "apps", "games", "library", "updates", "sources", "home"):
            w.navigate(pid)
            yield
        check(True, "every page built")
        hero = w.pages["home"].banner
        check(hero is not None and len(hero.big_apps) >= 1 and len(hero.tiles) == 3, "home hero: banner and 3 tiles")
        for _ in range(20):
            if not hero.big.art.loading and not any(t.art.loading for t in hero.tiles):
                break
            yield
        check(hero.big.art.shot is not None and all(t.art.shot is not None for t in hero.tiles),
              "hero tiles show screenshots (generated ones in demo mode)")
        check(hero.big.content[0].get_opacity() == 1.0, "hero text shown once the picture is ready")
        w.pages["home"].banner.next()
        w.pages["home"].banner.prev()
        yield
        for cat in ("productivity", "games"):
            w.navigate("category", arg=cat)
            yield
        for app in w.store.catalogue():
            w.show_app(app.uid)
            yield
        check(True, "every app page built")
        for alt in w.store.alternatives(w.store.catalogue()[0]) or []:
            w.show_app(alt.uid)
        w.search.set_text("notas")
        for _ in range(40):
            if w.current == "search":
                break
            yield
        check(w.current == "search" and bool(w.pages["search"].results), "live search shows results")
        w.search.set_text("")
        for _ in range(40):
            if w.current != "search":
                break
            yield
        check(w.current != "search", "clearing the search returns to the previous page")
        app = next(x for x in w.store.catalogue() if not x.installed)
        w.show_app(app.uid)
        w.pages["details"].action.clicked()
        while app.busy:
            yield
        check(app.installed, "install from the app page")
        w.pages["details"].remove_btn.emit("clicked")
        yield
        if w.dialog is not None:
            w.dialog.confirm()
        while app.busy:
            yield
        check(not app.installed, "uninstall from the app page")
        w.navigate("updates")
        yield
        w.pages["library"].update_all_btn.emit("clicked")
        while w.store.busy_apps():
            yield
        check(not w.store.updates(), "Update all from the Library")
        w.go_back()
        yield
        w.set_compact(True)
        yield
        w.set_compact(False)
        yield

    def tick():
        if a.win is None:
            return True
        if state["it"] is None:
            state["it"] = steps()
        try:
            next(state["it"])
            return True
        except StopIteration:
            a.quit()
            return False
        except Exception:  # noqa: BLE001
            errors.append(sys.exc_info())
            traceback.print_exc()
            a.quit()
            return False

    GLib.timeout_add(60, tick)
    GLib.timeout_add(90000, lambda: (errors.append("timeout"), a.quit()))
    a.run(["x"])


store_test()
popular_test()
webapps_test()
integration_test()
if args.ui:
    ui_test()
ok = not failures and not errors
print("SMOKE", "OK" if ok else "FAILED", f"failures={len(failures)} tracebacks={len(errors)}")
import shutil  # noqa: E402

shutil.rmtree(TMP, ignore_errors=True)
sys.exit(0 if ok else 1)
