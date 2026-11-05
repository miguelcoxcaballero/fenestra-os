"""Background sampling thread + graph history kept on the main thread."""
from __future__ import annotations

import threading
import traceback
from collections import deque

from gi.repository import GLib

HISTORY = 60


class Sampler(threading.Thread):
    def __init__(self, collector, callback, interval=1.0):
        super().__init__(name="taskmgr-sampler", daemon=True)
        self.collector = collector
        self.callback = callback
        self.interval = interval
        self._wake = threading.Event()
        self._quit = False

    def set_interval(self, seconds):
        """seconds == 0 pauses sampling."""
        self.interval = seconds
        self._wake.set()

    def refresh(self):
        self._wake.set()

    def stop(self):
        self._quit = True
        self._wake.set()

    def run(self):
        first = True
        while not self._quit:
            if self.interval > 0 or first:
                try:
                    snap = self.collector.sample()
                    GLib.idle_add(self._deliver, snap, priority=GLib.PRIORITY_DEFAULT_IDLE)
                except Exception:  # noqa: BLE001 - never kill the thread
                    traceback.print_exc()
            # the very first CPU figures need a second sample: take it quickly
            delay = 0.35 if first else (self.interval if self.interval > 0 else None)
            first = False
            self._wake.wait(delay)
            self._wake.clear()

    def _deliver(self, snap):
        self.callback(snap)
        return False


class History:
    """Rolling 60-sample series for every performance graph."""

    def __init__(self):
        self.series: dict[str, deque] = {}
        self.ticks = 0

    def push(self, key, value):
        d = self.series.get(key)
        if d is None:
            d = self.series[key] = deque([None] * HISTORY, maxlen=HISTORY)
        d.append(value)

    def get(self, key):
        d = self.series.get(key)
        return list(d) if d is not None else [None] * HISTORY

    def preload(self, key, values):
        d = self.series[key] = deque([None] * HISTORY, maxlen=HISTORY)
        for v in values[-HISTORY:]:
            d.append(v)

    def add_snapshot(self, s):
        self.ticks += 1
        self.push("cpu", s.cpu_total)
        for i, v in enumerate(s.cpu_cores):
            self.push(f"cpu{i}", v)
        m = s.mem
        if m:
            self.push("mem", m["used"] / max(1, m["total"]) * 100.0)
        for d in s.disks:
            self.push(f"disk:{d['name']}", d["active"])
            self.push(f"diskr:{d['name']}", d["read"])
            self.push(f"diskw:{d['name']}", d["write"])
        for n in s.nets:
            self.push(f"nets:{n['id']}", n["send"])
            self.push(f"netr:{n['id']}", n["recv"])
        for g in s.gpus:
            self.push(f"gpu:{g['index']}", g["busy"])
