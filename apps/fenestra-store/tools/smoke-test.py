#!/usr/bin/env python3
"""Smoke test for Fenestra Store.

Part 1 (always, no display needed): drives the demo backend through the Store end to end:
catalogue loads, search finds apps (accent-insensitive), install / uninstall / update change
state with progress callbacks, Library lists installed apps and updates, Update all, sources.

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
        for _ in range(4):
            yield
        check(w.current == "search" and bool(w.pages["search"].results), "live search shows results")
        w.search.set_text("")
        yield
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
if args.ui:
    ui_test()
ok = not failures and not errors
print("SMOKE", "OK" if ok else "FAILED", f"failures={len(failures)} tracebacks={len(errors)}")
sys.exit(0 if ok else 1)
