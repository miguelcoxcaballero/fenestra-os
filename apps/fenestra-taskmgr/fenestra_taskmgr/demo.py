"""Neutral sample data for screenshots (--demo-data): no real user, host or process info."""
from __future__ import annotations

import math
import random
import time

from .procdata import Proc, Snapshot

GB = 1024 ** 3
MB = 1024 ** 2


class DemoStatic:
    cpu_model = "Intel(R) Core(TM) Ultra 5 125H"
    sockets = 1
    cores = 6
    logical = 6
    base_khz = 3000000
    virtualization = None
    vm = True
    caches = {}
    mem_reserved = int(38.3 * MB)


# (name, icon, mem MB, children, status)
BACKGROUND = [
    ("Accessibility Bus", None, 6.9, 0, ""),
    ("Calendar Reminders", None, 3.5, 0, ""),
    ("Configuration Database", None, 4.3, 0, ""),
    ("Credential Manager (GNOME Keyring)", None, 2.4, 0, ""),
    ("Desktop Portal Service", None, 0.7, 0, ""),
    ("Document Portal", None, 1.6, 0, ""),
    ("Files", "org.gnome.Nautilus", 39.5, 5, ""),
    ("Evolution Data Source Registry", None, 1.0, 0, ""),
    ("File Indexer", None, 18.7, 0, "eff"),
    ("GNOME Shell", "org.gnome.Shell", 20.5, 0, ""),
    ("IBus Input Method Framework", None, 6.4, 3, ""),
    ("Online Accounts Service", None, 1.6, 2, ""),
    ("Permission Store", None, 3.7, 2, ""),
    ("PipeWire Multimedia Service", None, 100.8, 7, ""),
    ("PipeWire PulseAudio Service", None, 3.3, 0, ""),
    ("Settings Daemon (Color)", None, 3.4, 2, ""),
    ("Settings Daemon (Keyboard)", None, 33.2, 2, ""),
    ("Settings Daemon (Media Keys)", None, 1.0, 0, ""),
    ("Settings Daemon (Power)", None, 1.2, 0, ""),
    ("Settings Daemon (Sound)", None, 1.2, 0, ""),
    ("Shell Calendar Service", None, 2.6, 2, ""),
    ("Virtual File System Service", None, 0.9, 0, ""),
    ("WirePlumber Session Manager", None, 2.4, 2, "susp"),
    ("Xwayland", None, 2.2, 0, ""),
    ("Xwayland Video Bridge", None, 1.3, 0, ""),
]

SYSTEM = [
    ("Accounts Service", 140.4, 2), ("Audit Service", 1.5, 2), ("Authorization Manager (polkit)", 4.1, 0),
    ("Bluetooth Support Service", 2.0, 0), ("Color Management Service", 3.0, 0),
    ("D-Bus Message Broker", 2.9, 2), ("Device Manager (udev)", 5.1, 0),
    ("Disk Management Service", 3.6, 0), ("Firewall Service", 31.0, 0),
    ("Firmware Update Service", 22.4, 0), ("GNOME Display Manager", 3.3, 3),
    ("Interrupt Balancer", 1.1, 0), ("Journal Service", 18.0, 0), ("Login Manager", 2.7, 0),
    ("Network Manager", 9.8, 2), ("Network Name Resolution", 4.4, 0),
    ("Out-of-Memory Monitor", 2.0, 0), ("Power Management Service", 3.9, 0),
    ("Power Profiles Service", 2.6, 0), ("Print Spooler (CUPS)", 4.0, 2),
    ("Realtime Policy Service", 0.6, 0), ("Security Audit Service", 1.2, 0),
    ("Sensor Service", 1.0, 0), ("System", 0.1, 0), ("systemd (System and Service Manager)", 9.4, 0),
    ("Task Scheduler (cron)", 1.1, 0), ("Thermal Management Service", 1.4, 0),
    ("Time Synchronization (chrony)", 1.3, 0), ("User Database Service", 1.6, 3),
    ("Wi-Fi Security Service", 2.9, 0),
]

SERVICES = [
    ("accounts-daemon", "Accounts Service", True, "system.slice"),
    ("alsa-state", "Manage Sound Card State (restore and store)", True, "system.slice"),
    ("atd", "Deferred execution scheduler", False, ""),
    ("auditd", "Security Audit Logging Service", True, "system.slice"),
    ("avahi-daemon", "Avahi mDNS/DNS-SD Stack", True, "system.slice"),
    ("bluetooth", "Bluetooth service", True, "system.slice"),
    ("chronyd", "NTP client/server", True, "system.slice"),
    ("colord", "Manage, Install and Generate Color Profiles", True, "system.slice"),
    ("crond", "Command Scheduler", True, "system.slice"),
    ("cups", "CUPS Scheduler", True, "system.slice"),
    ("dbus-broker", "D-Bus System Message Bus", True, "system.slice"),
    ("dnf-makecache", "dnf makecache", False, ""),
    ("firewalld", "firewalld - dynamic firewall daemon", True, "system.slice"),
    ("fwupd", "Firmware update daemon", True, "system.slice"),
    ("gdm", "GNOME Display Manager", True, "system.slice"),
    ("irqbalance", "irqbalance daemon", True, "system.slice"),
    ("ModemManager", "Modem Manager", False, ""),
    ("NetworkManager", "Network Manager", True, "system.slice"),
    ("NetworkManager-dispatcher", "Network Manager Script Dispatcher Service", False, ""),
    ("packagekit", "PackageKit Daemon", False, ""),
    ("plymouth-quit-wait", "Hold until boot process finishes up", False, ""),
    ("polkit", "Authorization Manager", True, "system.slice"),
    ("power-profiles-daemon", "Power Profiles daemon", True, "system.slice"),
    ("rtkit-daemon", "RealtimeKit Scheduling Policy Service", True, "system.slice"),
    ("sshd", "OpenSSH server daemon", False, ""),
    ("switcheroo-control", "Switcheroo Control Proxy service", True, "system.slice"),
    ("systemd-homed", "Home Area Manager", True, "system.slice"),
    ("systemd-journald", "Journal Service", True, "system.slice"),
    ("systemd-logind", "User Login Management", True, "system.slice"),
    ("systemd-oomd", "Userspace Out-Of-Memory (OOM) Killer", True, "system.slice"),
    ("systemd-resolved", "Network Name Resolution", True, "system.slice"),
    ("systemd-udevd", "Rule-based Manager for Device Events and Files", True, "system.slice"),
    ("systemd-userdbd", "User Database Manager", True, "system.slice"),
    ("udisks2", "Disk Manager", True, "system.slice"),
    ("upower", "Daemon for power management", True, "system.slice"),
    ("wpa_supplicant", "WPA supplicant", True, "system.slice"),
]

STARTUP = [
    ("Calendar Reminders", "The GNOME Project", False, "org.gnome.Calendar"),
    ("Files", "", True, "org.gnome.Nautilus"),
    ("Online Accounts", "", True, "goa-panel"),
    ("Security Notifications", "", True, "security-high"),
    ("Terminal", "The GNOME Project", False, "org.gnome.Terminal"),
]

HISTORY_APPS = [
    ("Calculator", "org.gnome.Calculator"), ("Calendar", "org.gnome.Calendar"),
    ("Camera", "org.gnome.Snapshot"), ("Characters", "org.gnome.Characters"),
    ("Clocks", "org.gnome.clocks"), ("Contacts", "org.gnome.Contacts"),
    ("Disks", "org.gnome.DiskUtility"), ("Document Viewer", "org.gnome.Papers"),
    ("Files", "org.gnome.Nautilus"), ("Fonts", "org.gnome.font-viewer"),
    ("GNOME Shell", "org.gnome.Shell"), ("Image Viewer", "org.gnome.Loupe"),
    ("Logs", "org.gnome.Logs"), ("Maps", "org.gnome.Maps"), ("Music", "org.gnome.Music"),
    ("Settings", "org.gnome.Settings"), ("Software", "org.gnome.Software"),
    ("Task Manager", "org.fenestra.TaskManager"), ("Terminal", "org.gnome.Terminal"),
    ("Text Editor", "org.gnome.TextEditor"), ("Videos", "org.gnome.Totem"),
    ("Weather", "org.gnome.Weather"), ("Web", "org.gnome.Epiphany"),
    ("Xwayland", None), ("PipeWire", None), ("Firefox", "firefox"),
    ("Help", "org.gnome.Yelp"), ("Connections", "org.gnome.Connections"),
    ("Boxes", "org.gnome.Boxes"), ("Tour", "org.gnome.Tour"),
]

# 60-sample curves shaped like a lightly loaded machine
CPU_CURVE = [None, None, None, 0, 60, 60, 26, 20, 23, 20, 5, 7, 11, 3, 9, 13, 3, 0, 5, 7, 7, 7, 3, 10,
             3, 35, 62, 50, 13, 5, 4, 44, 27, 10, 11, 6, 7, 2, 2, 2, 0, 2, 7, 7, 28, 25, 8, 23, 27, 27, 9,
             5, 17, 8, 7, 3, 29, 4, 3, 5]


def _curve(seed, n, base, spike):
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        v = base + rnd.random() * base
        if rnd.random() < 0.08:
            v += spike * rnd.random()
        out.append(v)
    return out


class DemoCollector:
    def __init__(self):
        self.static = DemoStatic()
        self.t0 = time.monotonic()
        self.n = 0
        self.services = SERVICES
        self.startup = STARTUP
        self.history_apps = HISTORY_APPS

    def preload(self, hist):
        hist.preload("cpu", CPU_CURVE)
        for i in range(6):
            hist.preload(f"cpu{i}", [None if v is None else min(100, v * (0.6 + 0.15 * i)) for v in CPU_CURVE])
        hist.preload("mem", [41.5 + 0.4 * math.sin(i / 7.0) for i in range(60)])
        hist.preload("disk:sda", [min(100, v) for v in _curve(3, 60, 0.4, 14)])
        hist.preload("diskr:sda", [v * 2000 for v in _curve(4, 60, 1, 400)])
        hist.preload("diskw:sda", [v * 9000 for v in _curve(5, 60, 1, 500)])
        hist.preload("nets:eth0", [0] * 11 + [3000, 30000, 2000, 900, 20000, 3000] + [0] * 43)
        hist.preload("netr:eth0", [0] * 11 + [12000, 40000, 960000, 4000, 170000, 30000, 0] + [0] * 42)

    def sample(self):
        s = Snapshot()
        s.demo = True
        self.n += 1
        s.cpu_total = 5.0
        s.cpu_cores = [4.0, 7.0, 3.0, 6.0, 5.0, 5.0]
        s.freq_khz = 3000000
        total = 6 * GB
        used = int(2.5 * GB)
        s.mem = {"total": total, "avail": int(3.5 * GB), "used": used, "free": int(0.4 * GB),
                 "cached": int(3.4 * GB), "modified": 40 * MB, "committed": int(2.1 * GB),
                 "commit_limit": int(7.6 * GB), "swap_total": int(1.6 * GB), "swap_used": 0,
                 "paged": 256 * MB, "nonpaged": 151 * MB, "compressed": int(33.4 * MB),
                 "zram_orig": 0, "reserved": int(38.3 * MB)}
        s.disks = [{"name": "sda", "index": 0, "model": "QEMU HARDDISK", "type": "HDD (SATA)",
                    "kind": "HDD", "capacity": 64 * GB, "formatted": 64 * GB, "label": "C:",
                    "system": True, "pagefile": True, "active": 1.0, "read": 0.0, "write": 77.0 * 1024,
                    "resp": 2.8}]
        s.nets = [{"id": "eth0", "label": "Ethernet", "kind": "ethernet",
                   "adapter": "Intel(R) 82574L Gigabit Network Connection", "send": 0.0, "recv": 0.0,
                   "up": True, "speed": 1000, "conn": "Ethernet", "ipv4": "10.0.2.15",
                   "ipv6": "fec0::2035:e7:323e:dedd%1"}]
        s.gpus = []
        s.uptime = 14 * 60 + 4 + self.n
        s.boot_time = time.time() - s.uptime
        s.n_threads = 1464
        s.n_handles = 51357
        procs = {}
        pid = [1000]

        def mk(name, kind, mem, unit, cpu=0.0, disk=0.0, app=None, icon=None, user="alex", uid=1000,
               status=""):
            p = Proc()
            pid[0] += 4 + (len(name) * 7) % 23
            p.pid = pid[0]
            p.ppid = 1
            p.comm = p.name = p.desc = name
            p.cmdline = ["/usr/bin/" + name.lower().replace(" ", "-")]
            p.uid, p.user = uid, user
            p.state = "T" if status == "susp" else "S"
            p.threads = 4
            p.ticks = 0
            p.cputime = (len(name) % 5) * 1.0
            p.start = 0
            p.mem = int(mem * MB)
            p.cpu = cpu
            p.disk = disk
            p.nice = 19 if status == "eff" else 0
            p.efficiency = status == "eff"
            p.unit = unit
            p.cgroup = "/" + unit
            p.app_id = app
            p.kind = kind
            p.icon = icon
            procs[p.pid] = p
            return p

        mk("Task Manager", "app", 41.2, "app-gnome-org.fenestra.TaskManager-1.scope", cpu=5.0,
           disk=0.1 * MB, app="org.fenestra.TaskManager")
        s.apps = {"org.fenestra.TaskManager": ("Task Manager", "org.fenestra.TaskManager", True, "")}
        for i, (name, icon, mem, kids, status) in enumerate(BACKGROUND):
            unit = f"bg{i}.service"
            if kids:
                share = mem / kids
                for k in range(kids):
                    mk(name, "bg", share, unit, icon=icon, status=status)
            else:
                mk(name, "bg", mem, unit, icon=icon, status=status)
        for i, (name, mem, kids) in enumerate(SYSTEM):
            unit = f"sys{i}.service"
            for k in range(max(1, kids)):
                mk(name, "sys", mem / max(1, kids), unit, user="root", uid=0)
        s.procs = procs
        s.n_procs = 129
        return s
