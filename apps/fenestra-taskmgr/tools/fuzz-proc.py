#!/usr/bin/env python3
"""Fuzz the /proc sampler: churn hundreds of short-lived dummy processes (odd argv,
zombies, threads, instant exits) while sampling as fast as possible and building the
Processes / Details models.  Only processes this script starts are ever signalled.

    ~/.local/bin/fenestra-test-run python3 tools/fuzz-proc.py [seconds]
"""
import os
import random
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("FENESTRA_TASKMGR_TEST_ALLOW_PIDS", "")

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
from fenestra_taskmgr import procdata  # noqa: E402
from fenestra_taskmgr.pages import processes  # noqa: E402

DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 60
WEIRD = ["x\ny", "tab\tname", "ünïcødé-プロセス", "a" * 3000, "(paren)) name", ")", "", " ",
         "\x1b[31mred", "emoji-🔥", "back\\slash", "-dash", "name with spaces"]
mine = []   # Popen objects: only ever signal our own, still-unreaped children
stop = False


def churn():
    rnd = random.Random(1)
    zombies = []
    while not stop:
        kind = rnd.random()
        try:
            if kind < 0.35:      # instant exit with a weird argv[0] (exec -a)
                p = subprocess.Popen(["bash", "-c", f'exec -a "$0" sleep 0.0{rnd.randint(1, 9)}',
                                      rnd.choice(WEIRD)])
            elif kind < 0.55:    # zombie: exits, parent does not reap for a while
                p = subprocess.Popen(["true"])
                zombies.append(p)
            elif kind < 0.75:    # multi-threaded short-lived python
                p = subprocess.Popen([sys.executable, "-c",
                                      "import threading,time;[threading.Thread(target=time.sleep,args=(0.3,)).start()"
                                      " for _ in range(20)];time.sleep(0.2)", rnd.choice(WEIRD)])
            elif kind < 0.9:     # killed while being read
                p = subprocess.Popen(["sleep", "5"])
                threading.Timer(rnd.random() * 0.2, lambda q=p: q.poll() is None and q.kill()).start()
            else:                # process tree
                p = subprocess.Popen(["bash", "-c", "for i in 1 2 3 4 5; do sleep 0.2 & done; wait"])
            mine.append(p)
        except OSError:
            pass
        if len(zombies) > 40:
            for z in zombies[:20]:
                z.wait()
            del zombies[:20]
        time.sleep(0.02)
    for z in zombies:
        z.wait()


def main():
    global stop
    t = threading.Thread(target=churn, daemon=True)
    t.start()
    col = procdata.Collector()
    n = errors = 0
    worst = 0.0
    maxprocs = 0
    t0 = time.monotonic()
    while time.monotonic() - t0 < DURATION:
        a = time.monotonic()
        try:
            snap = col.sample()
            g = processes.build_entries(snap)
            for e in g["app"] + g["bg"] + g["sys"]:
                e.matches("sleep")
                processes.sort_entries([e], "cpu", True)
            maxprocs = max(maxprocs, len(snap.procs))
        except Exception:  # noqa: BLE001
            errors += 1
            import traceback
            traceback.print_exc()
        worst = max(worst, time.monotonic() - a)
        n += 1
    stop = True
    t.join(5)
    for p in mine:   # only our own children that Popen has not reaped yet
        if p.poll() is None:
            p.kill()
            p.wait()
    print(f"FUZZ samples={n} errors={errors} max_procs={maxprocs} worst_sample={worst * 1000:.0f}ms "
          f"spawned={len(mine)}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
