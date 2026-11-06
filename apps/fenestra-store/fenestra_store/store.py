"""The Store: merges the backends' catalogues, runs operations in a worker thread and tells
the UI about changes through GObject signals (always emitted on the main thread).

No GTK here, so tools/smoke-test.py can drive it with a plain GLib main loop.
"""
from __future__ import annotations

import os
import queue
import threading
import time

from gi.repository import GLib, GObject

from . import util
from .model import (AVAILABLE, INSTALLED, INSTALLING, QUEUED, REMOVING, UPDATING, App, Source,
                    StoreError)

OPS = {"install": INSTALLING, "remove": REMOVING, "update": UPDATING}


class Store(GObject.Object):
    __gsignals__ = {
        "loaded": (GObject.SignalFlags.RUN_FIRST, None, ()),
        # uid
        "app-changed": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        # uid, fraction (-1 = unknown), status text (English key, translate in the UI)
        "progress": (GObject.SignalFlags.RUN_FIRST, None, (str, float, str)),
        # uid, operation, ok, message
        "job-done": (GObject.SignalFlags.RUN_FIRST, None, (str, str, bool, str)),
        "updates-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "sources-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, backends):
        super().__init__()
        self.backends = {b.id: b for b in backends}
        self.apps: dict[str, App] = {}
        self.loaded = False
        self.loading = False
        self.load_errors: list[str] = []
        self.has_popularity = False
        self._hay: dict = {}
        self.checking = False
        self.last_checked: float | None = None
        self._sources: list[Source] = []
        self._jobs: queue.Queue = queue.Queue()
        self._worker = None
        self._state = GLib.KeyFile()
        if not util.DEMO:
            try:
                self._state.load_from_file(util.state_file(), GLib.KeyFileFlags.NONE)
                self.last_checked = self._state.get_double("updates", "last-checked")
            except GLib.Error:
                pass

    # ------------------------------------------------------------------ loading
    def load(self, sync=False):
        """Load every backend's catalogue in a worker thread (or right away with sync=True,
        used by screenshot mode so the first frame already shows the page); emits 'loaded'."""
        if self.loading:
            return
        self.loading = True

        def work():
            apps, sources, errors = [], [], []
            for b in self.backends.values():
                try:
                    apps += b.load()
                    sources += b.sources()
                except Exception as e:  # noqa: BLE001 - one broken backend must not hide the others
                    errors.append(f"{b.label}: {e}")
                    util.log("load failed", b.id, e)
            return apps, sources, errors
        if sync:
            self._loaded(work())
        else:
            util.in_thread(work, on_done=self._loaded)

    def _loaded(self, res):
        apps, sources, errors = res
        self.apps = {a.uid: a for a in apps}
        self._hay = {}
        # Real catalogues carry no download counts: rank by how complete the listing is instead,
        # and say "Recommended" rather than "Popular" (has_popularity).
        self.has_popularity = any(a.popularity for a in apps)
        if not self.has_popularity:
            for a in apps:
                a.popularity = self._quality(a)
        self._sources = sources
        self.load_errors = errors
        self.loaded = True
        self.loading = False
        if util.DEMO and self.last_checked is None:
            self.last_checked = time.time() - 25 * 60
        self.emit("loaded")
        self.emit("updates-changed")

    # ------------------------------------------------------------------ queries
    def get(self, uid) -> App | None:
        return self.apps.get(uid)

    def _source_enabled(self, kind):
        srcs = [s for s in self._sources if s.kind == kind]
        return not srcs or any(s.enabled for s in srcs)

    def visible(self, app: App) -> bool:
        return app.installed or self._source_enabled(app.source)

    def catalogue(self) -> list[App]:
        """One entry per application (alternative sources folded in), visible sources only."""
        best: dict[str, App] = {}
        for a in self.apps.values():
            if not self.visible(a):
                continue
            cur = best.get(a.app_id)
            if cur is None or self._rank(a) < self._rank(cur):
                best[a.app_id] = a
        return sorted(best.values(), key=lambda a: util.fold(a.name))

    @staticmethod
    def _quality(a: App) -> int:
        score = min(len(a.screenshots), 3) * 3 + (2 if a.developer else 0) + (2 if len(a.description) >= 2 else 0)
        score += 2 if a.icon_path or a.icon_name else 0
        score += 3 if a.released >= time.strftime("%Y-%m-%d", time.gmtime(time.time() - 180 * 86400)) else 0
        score += 1 if a.installed else 0
        return score

    @staticmethod
    def _rank(a: App):
        return (0 if a.installed else 1, 0 if a.source == "flathub" else 1)

    def alternatives(self, app: App) -> list[App]:
        return [a for a in self.apps.values() if a.app_id == app.app_id and a.uid != app.uid and self.visible(a)]

    def featured(self) -> list[App]:
        f = [a for a in self.catalogue() if a.featured]
        if f:
            return sorted(f, key=lambda a: (-a.popularity, a.name))
        # Real catalogues: five complete, recently released listings, a different set each day.
        pool = sorted((a for a in self.catalogue() if len(a.screenshots) >= 2 and a.description and not a.installed),
                      key=lambda a: (a.popularity, a.released), reverse=True)[:40]
        if not pool:
            return []
        day = int(time.time() // 86400)
        return [pool[(day * 7 + i * 8) % len(pool)] for i in range(min(5, len(pool)))]

    def popular(self, games=None, limit=None) -> list[App]:
        r = [a for a in self.catalogue() if games is None or a.is_game == games]
        r.sort(key=lambda a: (-a.popularity, util.fold(a.name)))
        return r[:limit] if limit else r

    def new_and_updated(self, games=None, limit=None) -> list[App]:
        r = [a for a in self.catalogue() if a.released and (games is None or a.is_game == games)]
        r.sort(key=lambda a: (a.released, a.popularity), reverse=True)
        return r[:limit] if limit else r

    def by_category(self, key, limit=None) -> list[App]:
        r = [a for a in self.catalogue() if key in a.categories]
        r.sort(key=lambda a: (-a.popularity, util.fold(a.name)))
        return r[:limit] if limit else r

    def by_developer(self, app: App) -> list[App]:
        if not app.developer:
            return []
        return [a for a in self.popular() if a.developer == app.developer and a.app_id != app.app_id]

    def installed(self) -> list[App]:
        return sorted((a for a in self.apps.values() if a.installed), key=lambda a: util.fold(a.name))

    def updates(self) -> list[App]:
        return [a for a in self.installed() if a.has_update]

    def search(self, text, kind=None) -> list[App]:
        """Ranked matches for text over name, keywords, summary, developer and description."""
        words = [w for w in util.fold(text).split() if w]
        if not words:
            return []
        scored = []
        for a in self.catalogue():
            if kind == "games" and not a.is_game or kind == "apps" and a.is_game:
                continue
            name, fields = self._haystack(a)
            total = 0
            for w in words:
                if name.startswith(w) or f" {w}" in f" {name}":
                    s = 20 if name.startswith(w) else 14
                elif w in name:
                    s = 10
                else:
                    s = next((weight for hay, weight in fields if w in hay), 0)
                if s == 0:
                    total = 0
                    break
                total += s
            if total:
                scored.append((total, a.popularity, a))
        scored.sort(key=lambda t: (-t[0], -t[1], util.fold(t[2].name)))
        return [t[2] for t in scored]

    def _haystack(self, a: App):
        """Folded search text of an app, computed once per catalogue load."""
        h = self._hay.get(a.uid)
        if h is None:
            h = self._hay[a.uid] = (util.fold(a.name), [
                (util.fold(" ".join(a.keywords)), 6), (util.fold(a.summary), 4), (util.fold(a.developer), 3),
                (util.fold(a.app_id), 2), (util.fold(" ".join(a.description)), 1)])
        return h

    def sources(self) -> list[Source]:
        return list(self._sources)

    # ------------------------------------------------------------------ details
    def load_details(self, uid):
        app = self.apps.get(uid)
        if app is None or app.details_loaded:
            return
        app.details_loaded = True
        be = self.backends[app.backend]
        util.in_thread(be.details, app, on_done=lambda _r: self.emit("app-changed", uid),
                       on_error=lambda _e: self.emit("app-changed", uid))

    # ------------------------------------------------------------------ operations
    def install(self, uid):
        self._queue("install", uid)

    def remove(self, uid):
        self._queue("remove", uid)

    def update(self, uid):
        self._queue("update", uid)

    def update_all(self):
        for a in self.updates():
            if not a.busy:
                self._queue("update", a.uid)

    def busy_apps(self) -> list[App]:
        return [a for a in self.apps.values() if a.busy]

    def _queue(self, op, uid):
        app = self.apps.get(uid)
        if app is None or app.busy:
            return False
        if util.READ_ONLY and not util.DEMO:
            self.emit("job-done", uid, op, False, "read-only")
            return False
        app.state = QUEUED
        app.progress = 0.0
        app.status_text = "Queued"
        self.emit("app-changed", uid)
        self._jobs.put((op, uid))
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._run_jobs, name="fenestra-store-jobs", daemon=True)
            self._worker.start()
        return True

    def _run_jobs(self):
        # One operation at a time: package managers hold a lock anyway, and progress stays readable.
        while True:
            try:
                op, uid = self._jobs.get(timeout=1.0)
            except queue.Empty:
                return
            app = self.apps[uid]
            be = self.backends[app.backend]
            GLib.idle_add(self._start, uid, op)

            last = [0.0]

            def progress(frac, text, uid=uid):
                now = time.monotonic()
                if frac is not None and frac < 1.0 and now - last[0] < 0.05:
                    return  # keep the main loop free: at most ~20 updates per second
                last[0] = now
                GLib.idle_add(self._progress, uid, -1.0 if frac is None else float(frac), text or "")
            try:
                getattr(be, op)(app, progress)
                ok, msg = True, ""
            except StoreError as e:
                ok, msg = False, str(e)
            except Exception as e:  # noqa: BLE001 - backend failures are reported, never crash
                util.log("operation failed", op, uid, e)
                ok, msg = False, str(e) or e.__class__.__name__
            GLib.idle_add(self._finish, uid, op, ok, msg)

    def _start(self, uid, op):
        app = self.apps[uid]
        app.state = OPS[op]
        app.status_text = "Preparing"
        self.emit("app-changed", uid)
        return False

    def _progress(self, uid, frac, text):
        app = self.apps[uid]
        if frac >= 0:
            app.progress = frac
        app.status_text = text
        self.emit("progress", uid, frac, text)
        return False

    def _finish(self, uid, op, ok, msg):
        app = self.apps[uid]
        if ok:
            if op == "install":
                app.installed = True
                app.update_version = ""
            elif op == "remove":
                app.installed = False
                app.update_version = ""
            elif op == "update":
                app.version = app.update_version or app.version
                app.update_version = ""
        app.state = INSTALLED if app.installed else AVAILABLE
        app.progress = 0.0
        app.status_text = ""
        self.emit("app-changed", uid)
        self.emit("job-done", uid, op, ok, msg)
        if op in ("install", "remove", "update"):
            self.emit("updates-changed")
        return False

    # ------------------------------------------------------------------ updates
    def check_updates(self):
        if self.checking:
            return
        self.checking = True
        self.emit("updates-changed")
        apps = list(self.apps.values())

        def work():
            found = {}
            for b in self.backends.values():
                try:
                    found.update(b.refresh_updates([a for a in apps if a.backend == b.id and a.installed]))
                except Exception as e:  # noqa: BLE001
                    util.log("update check failed", b.id, e)
            return found
        util.in_thread(work, on_done=self._checked, on_error=lambda _e: self._checked({}))

    def _checked(self, found):
        for a in self.apps.values():
            if a.installed and not a.busy:
                a.update_version = found.get(a.uid, "")
        self.checking = False
        self.last_checked = time.time()
        if not util.DEMO:
            try:
                self._state.set_double("updates", "last-checked", self.last_checked)
                os.makedirs(os.path.dirname(util.state_file()), exist_ok=True)
                self._state.save_to_file(util.state_file())
            except GLib.Error:
                pass
        self.emit("updates-changed")

    # ------------------------------------------------------------------ launch / sources
    def launch(self, uid) -> bool:
        app = self.apps.get(uid)
        if app is None or not app.installed:
            return False
        if util.READ_ONLY and not util.DEMO:
            return False
        return self.backends[app.backend].launch(app)

    def set_source_enabled(self, source: Source, enabled: bool, on_done=None):
        if util.READ_ONLY and not util.DEMO:
            if on_done:
                on_done(False, "read-only")
            return
        be = self.backends.get(source.backend)

        def done(_r):
            source.enabled = enabled
            self.emit("sources-changed")
            if on_done:
                on_done(True, "")

        def failed(e):
            self.emit("sources-changed")
            if on_done:
                on_done(False, str(e))
        util.in_thread(be.set_source_enabled, source, enabled, on_done=done, on_error=failed)
