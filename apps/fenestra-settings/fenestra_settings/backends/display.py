"""Monitor configuration through mutter's org.gnome.Mutter.DisplayConfig (scale, resolution,
refresh rate, orientation). Changes are applied persistently, the UI offers a timed revert."""
from __future__ import annotations

from gi.repository import Gio, GLib

from .. import util

DC = ("org.gnome.Mutter.DisplayConfig", "/org/gnome/Mutter/DisplayConfig", "org.gnome.Mutter.DisplayConfig")
METHOD_PERSISTENT = 2

TRANSFORMS = {"landscape": 0, "portrait": 1, "landscape-flipped": 2, "portrait-flipped": 3}


class Mode:
    def __init__(self, t):
        self.id, self.width, self.height, self.refresh, self.preferred_scale, self.scales, props = t
        self.scales = list(self.scales)
        self.current = bool(props.get("is-current", False))
        self.preferred = bool(props.get("is-preferred", False))


class Monitor:
    def __init__(self, t):
        spec, modes, props = t
        self.spec = tuple(spec)
        self.connector = spec[0]
        self.modes = [Mode(m) for m in modes]
        self.name = props.get("display-name", self.connector)
        self.builtin = bool(props.get("is-builtin", False))

    @property
    def current_mode(self):
        return next((m for m in self.modes if m.current), self.modes[0] if self.modes else None)

    @property
    def preferred_mode(self):
        return next((m for m in self.modes if m.preferred), self.current_mode)


class Logical:
    def __init__(self, t):
        self.x, self.y, self.scale, self.transform, self.primary, specs, _props = t
        self.connectors = [s[0] for s in specs]


class State:
    def __init__(self, res):
        self.serial, mons, logs, props = res
        self.monitors = [Monitor(m) for m in mons]
        self.logical = [Logical(lm) for lm in logs]
        self.props = props

    def monitor(self, connector=None):
        if connector:
            return next((m for m in self.monitors if m.connector == connector), None)
        prim = next((lm for lm in self.logical if lm.primary), self.logical[0] if self.logical else None)
        return self.monitor(prim.connectors[0]) if prim else (self.monitors[0] if self.monitors else None)

    def logical_for(self, connector):
        return next((lm for lm in self.logical if connector in lm.connectors), None)


def _demo_state():
    scales = [1.0, 1.25, 1.5, 1.75, 2.0]
    modes = [("2560x1600@60", 2560, 1600, 60.0, 1.5, scales, {"is-current": True, "is-preferred": True}),
             ("1920x1200@60", 1920, 1200, 60.0, 1.25, scales, {}),
             ("1280x800@60", 1280, 800, 60.0, 1.0, [1.0, 1.25], {})]
    return State((1, [(("eDP-1", "FEN", "0x0001", "0"), modes, {"display-name": "Built-in display",
                                                                  "is-builtin": True})],
                  [(0, 0, 1.5, 0, True, [("eDP-1", "FEN", "0x0001", "0")], {})], {"layout-mode": 1}))


def get_state(callback):
    if util.DEMO:
        GLib.idle_add(lambda: (callback(_demo_state()), False)[1])
        return

    def done(ok, res):
        callback(State(res) if ok and res else None)
    util.dbus_call(Gio.BusType.SESSION, *DC, "GetCurrentState", None, done, mutating=False, interactive=False,
                   reply_type=GLib.VariantType("(ua((ssss)a(siiddada{sv})a{sv})a(iiduba(ssss)a{sv})a{sv})"))


def _config(state, connector, mode_id=None, scale=None, transform=None):
    """Rebuild the full logical monitor configuration, changing only `connector`."""
    out = []
    for lm in state.logical:
        lscale, ltrans = lm.scale, lm.transform
        mons = []
        for c in lm.connectors:
            mon = state.monitor(c)
            mid = mon.current_mode.id if mon and mon.current_mode else None
            if c == connector:
                if mode_id:
                    mid = mode_id
                if scale is not None:
                    lscale = scale
                if transform is not None:
                    ltrans = transform
                mode = next((m for m in mon.modes if m.id == mid), None)
                if mode and mode.scales and not any(abs(s - lscale) < 0.01 for s in mode.scales):
                    lscale = min(mode.scales, key=lambda s: abs(s - lscale))
            if mid:
                mons.append((c, mid, {}))
        out.append((lm.x, lm.y, float(lscale), int(ltrans), bool(lm.primary), mons))
    return out


def apply(state, connector, callback, mode_id=None, scale=None, transform=None):
    cfg = _config(state, connector, mode_id, scale, transform)
    util.dbus_call(Gio.BusType.SESSION, *DC, "ApplyMonitorsConfig",
                   GLib.Variant("(uua(iiduba(ssa{sv}))a{sv})", (state.serial, METHOD_PERSISTENT, cfg, {})),
                   callback)


def restore(old_state, callback):
    """Re-apply a previous configuration (used by "Revert")."""
    def fresh(st):
        if st is None:
            callback(False, None)
            return
        cfg = []
        for lm in old_state.logical:
            mons = []
            for c in lm.connectors:
                mon = old_state.monitor(c)
                if mon and mon.current_mode:
                    mons.append((c, mon.current_mode.id, {}))
            cfg.append((lm.x, lm.y, float(lm.scale), int(lm.transform), bool(lm.primary), mons))
        util.dbus_call(Gio.BusType.SESSION, *DC, "ApplyMonitorsConfig",
                       GLib.Variant("(uua(iiduba(ssa{sv}))a{sv})", (st.serial, METHOD_PERSISTENT, cfg, {})),
                       callback)
    get_state(fresh)


def resolutions(mon):
    """[(key 'WxH', label, best mode id)] largest first, preferring the current refresh rate."""
    cur = mon.current_mode
    best = {}
    for m in mon.modes:
        k = (m.width, m.height)
        prev = best.get(k)
        score = (abs(m.refresh - cur.refresh) if cur else 0, -m.refresh)
        if prev is None or score < prev[0]:
            best[k] = (score, m)
    items = sorted(best.items(), key=lambda kv: -(kv[0][0] * kv[0][1]))
    return [(m.id, f"{w} × {h}", m) for (w, h), (_s, m) in items]


def refresh_rates(mon):
    cur = mon.current_mode
    seen = {}
    for m in mon.modes:
        if cur and (m.width, m.height) == (cur.width, cur.height):
            key = round(m.refresh, 2)
            if key not in seen or ("+vrr" in m.id and m.current):
                seen[key] = m
    return sorted(seen.values(), key=lambda m: -m.refresh)
