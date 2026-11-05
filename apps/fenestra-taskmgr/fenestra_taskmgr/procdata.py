"""System and process sampling straight from /proc and /sys (psutil is not required).

Everything here runs in a background thread (see sampler.py); the results are
plain Python objects handed to the GTK main loop.
"""
from __future__ import annotations

import json
import os
import pwd
import subprocess
import time

from . import apps

CLK_TCK = os.sysconf("SC_CLK_TCK")
PAGE = os.sysconf("SC_PAGE_SIZE")
NCPU = os.cpu_count() or 1
PF_KTHREAD = 0x00200000
MY_UID = os.getuid()


class Proc:
    __slots__ = ("pid", "ppid", "comm", "name", "cmdline", "exe", "uid", "user", "state",
                 "threads", "ticks", "start", "mem", "cpu", "disk", "nice", "unit", "cgroup",
                 "app_id", "kind", "desc", "icon", "arch", "cputime", "fds", "efficiency")

    def __init__(self):
        self.cpu = 0.0
        self.disk = 0.0
        self.mem = 0
        self.icon = None
        self.app_id = None
        self.arch = "64 bit"
        self.fds = 0
        self.efficiency = False


class Snapshot:
    def __init__(self):
        self.t = time.monotonic()
        self.procs: dict[int, Proc] = {}
        self.apps: dict[str, tuple] = {}
        self.cpu_total = 0.0
        self.cpu_cores: list[float] = []
        self.freq_khz = 0.0
        self.mem: dict = {}
        self.disks: list[dict] = []
        self.nets: list[dict] = []
        self.gpus: list[dict] = []
        self.n_procs = 0
        self.n_threads = 0
        self.n_handles = 0
        self.uptime = 0.0
        self.boot_time = 0.0
        self.demo = False


def _read(path, mode="r"):
    try:
        with open(path, mode) as f:
            return f.read()
    except OSError:
        return None


def _user(uid, _cache={}):
    n = _cache.get(uid)
    if n is None:
        try:
            n = pwd.getpwuid(uid).pw_name
        except KeyError:
            n = str(uid)
        _cache[uid] = n
    return n


_INTERPRETERS = {"python", "python3", "perl", "node", "gjs", "java", "ruby", "bash", "sh",
                 "python3.13", "python3.14", "python3.12", "dash", "zsh", "env"}


def _proc_name(comm, argv):
    if argv:
        a0 = os.path.basename(argv[0].split(" ")[0]) if argv[0] else ""
        if a0 in _INTERPRETERS and len(argv) > 1:
            for a in argv[1:]:
                if a and not a.startswith("-"):
                    return os.path.basename(a)
            return a0
        if a0 and (comm.startswith(a0[:15]) or len(comm) >= 15):
            return a0
    return comm


class StaticInfo:
    """Hardware facts that do not change between samples."""

    def __init__(self):
        self.cpu_model = ""
        self.sockets = 1
        self.cores = NCPU
        self.logical = NCPU
        self.base_khz = 0
        self.virtualization = None
        self.vm = False
        self.caches = {}
        self.mem_reserved = 0
        self._cpu()
        self._caches()
        self._memory()

    def _cpu(self):
        txt = _read("/proc/cpuinfo") or ""
        phys, cores = set(), set()
        flags = ""
        pid = "0"
        for line in txt.splitlines():
            k, _, v = line.partition(":")
            k, v = k.strip(), v.strip()
            if k == "model name" and not self.cpu_model:
                self.cpu_model = " ".join(v.split())
            elif k == "physical id":
                pid = v
                phys.add(v)
            elif k == "core id":
                cores.add((pid, v))
            elif k == "flags" and not flags:
                flags = v
        if not self.cpu_model:
            self.cpu_model = os.uname().machine
        self.sockets = max(1, len(phys))
        self.cores = len(cores) or NCPU
        fl = flags.split()
        self.vm = "hypervisor" in fl
        self.virtualization = "vmx" in fl or "svm" in fl
        for f in ("base_frequency", "cpuinfo_max_freq"):
            v = _read(f"/sys/devices/system/cpu/cpu0/cpufreq/{f}")
            if v and v.strip().isdigit():
                self.base_khz = int(v)
                break

    def _caches(self):
        seen = set()
        tot = {}
        base = "/sys/devices/system/cpu"
        try:
            cpus = [d for d in os.listdir(base) if d.startswith("cpu") and d[3:].isdigit()]
        except OSError:
            cpus = []
        for c in cpus:
            cd = f"{base}/{c}/cache"
            try:
                idx = os.listdir(cd)
            except OSError:
                continue
            for i in idx:
                if not i.startswith("index"):
                    continue
                lvl = (_read(f"{cd}/{i}/level") or "").strip()
                typ = (_read(f"{cd}/{i}/type") or "").strip()
                size = (_read(f"{cd}/{i}/size") or "").strip()
                shared = (_read(f"{cd}/{i}/shared_cpu_list") or c).strip()
                key = (lvl, typ, shared)
                if key in seen or not size:
                    continue
                seen.add(key)
                mult = 1024 * 1024 if size.endswith("M") else 1024 if size.endswith("K") else 1
                try:
                    n = int(size.rstrip("KM")) * mult
                except ValueError:
                    continue
                tot[lvl] = tot.get(lvl, 0) + n
        self.caches = tot

    def _memory(self):
        try:
            bs = int(_read("/sys/devices/system/memory/block_size_bytes").strip(), 16)
            n = 0
            for d in os.listdir("/sys/devices/system/memory"):
                if d.startswith("memory") and (_read(f"/sys/devices/system/memory/{d}/online") or "1").strip() == "1":
                    n += 1
            phys = n * bs
            mi = _read("/proc/meminfo") or ""
            total = int(mi.split("MemTotal:")[1].split()[0]) * 1024
            self.mem_reserved = max(0, phys - total)
        except (AttributeError, ValueError, OSError, IndexError):
            self.mem_reserved = 0


def _disk_kind(name):
    rot = (_read(f"/sys/block/{name}/queue/rotational") or "0").strip() == "1"
    real = os.path.realpath(f"/sys/block/{name}")
    if name.startswith("nvme"):
        bus = "NVMe"
    elif "/usb" in real:
        bus = "USB"
    elif name.startswith("mmcblk"):
        bus = "SD"
    elif name.startswith("vd") or "/virtio" in real:
        bus = "Virtual"
    elif "/ata" in real:
        bus = "SATA"
    else:
        bus = "SCSI"
    if (_read(f"/sys/block/{name}/removable") or "0").strip() == "1" or bus in ("USB", "SD"):
        kind = "Removable"
    else:
        kind = "HDD" if rot else "SSD"
    return f"{kind} ({bus})", kind


def _devnum_to_disk():
    """major:minor of every block device -> top-level disk name (resolves partitions and dm)."""
    out = {}

    def top(name, depth=0):
        if depth > 6:
            return name
        if os.path.exists(f"/sys/block/{name}"):
            slaves = []
            try:
                slaves = os.listdir(f"/sys/block/{name}/slaves")
            except OSError:
                pass
            if slaves:
                return top(slaves[0], depth + 1)
            return name
        # partition -> parent directory under /sys/class/block
        real = os.path.realpath(f"/sys/class/block/{name}")
        parent = os.path.basename(os.path.dirname(real))
        if parent and os.path.exists(f"/sys/block/{parent}"):
            return top(parent, depth + 1)
        return name

    try:
        for name in os.listdir("/sys/class/block"):
            dev = (_read(f"/sys/class/block/{name}/dev") or "").strip()
            if dev:
                out[dev] = top(name)
    except OSError:
        pass
    return out


PHYS_DISK_PREFIX = ("nvme", "sd", "vd", "hd", "xvd", "mmcblk")


def disk_static():
    disks = []
    devmap = _devnum_to_disk()
    roots, swaps, mounted = set(), set(), {}
    mi = _read("/proc/self/mountinfo") or ""
    for line in mi.splitlines():
        p = line.split()
        if len(p) < 5:
            continue
        d = devmap.get(p[2])
        if not d and " - " in line:
            src = line.split(" - ", 1)[1].split()
            if len(src) >= 2 and src[1].startswith("/dev/"):
                nm = os.path.basename(os.path.realpath(src[1]))
                d = devmap.get((_read(f"/sys/class/block/{nm}/dev") or "").strip())
        if not d:
            continue
        mounted.setdefault(d, []).append(p[4])
        if p[4] == "/":
            roots.add(d)
    for line in (_read("/proc/swaps") or "").splitlines()[1:]:
        dev = line.split()[0] if line.split() else ""
        name = os.path.basename(os.path.realpath(dev))
        dn = (_read(f"/sys/class/block/{name}/dev") or "").strip()
        if dn in devmap:
            swaps.add(devmap[dn])
    try:
        names = sorted(os.listdir("/sys/block"))
    except OSError:
        names = []
    letter = ord("D")
    idx = 0
    for name in names:
        if not name.startswith(PHYS_DISK_PREFIX):
            continue
        if name.startswith("nvme") and "c" in name[4:].split("n")[0]:
            continue  # multipath controller node
        size = int((_read(f"/sys/block/{name}/size") or "0").strip() or 0) * 512
        if size == 0:
            continue
        model = " ".join(((_read(f"/sys/block/{name}/device/model") or "") + "").split()) or name
        typ, kind = _disk_kind(name)
        formatted = 0
        try:
            for part in os.listdir(f"/sys/block/{name}"):
                if part.startswith(name) and os.path.exists(f"/sys/block/{name}/{part}/partition"):
                    formatted += int((_read(f"/sys/block/{name}/{part}/size") or "0").strip() or 0) * 512
        except OSError:
            pass
        if name in roots:
            label = "C:"
        elif name in mounted:
            label = chr(letter) + ":"
            letter += 1
        else:
            label = ""
        disks.append({"name": name, "index": idx, "model": model, "type": typ, "kind": kind,
                      "capacity": size, "formatted": formatted or size, "label": label,
                      "system": name in roots, "pagefile": name in swaps})
        idx += 1
    # system disk first (Windows: Disk 0 is usually C:)
    disks.sort(key=lambda d: (not d["system"], d["index"]))
    for i, d in enumerate(disks):
        d["index"] = i
    return disks


def _udev_model(syspath):
    try:
        out = subprocess.run(["udevadm", "info", "-q", "property", "-p", syspath],
                             capture_output=True, text=True, timeout=2).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    props = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    model = props.get("ID_MODEL_FROM_DATABASE") or props.get("ID_MODEL", "")
    vendor = props.get("ID_VENDOR_FROM_DATABASE", "")
    if model and vendor and not model.startswith(vendor.split()[0]):
        return f"{vendor.split(' ')[0]} {model}"
    return model


def net_static():
    nets = []
    try:
        names = sorted(os.listdir("/sys/class/net"))
    except OSError:
        names = []
    n_eth = n_wifi = 0
    for name in names:
        base = f"/sys/class/net/{name}"
        if name == "lo" or not os.path.exists(f"{base}/device"):
            continue
        wifi = os.path.exists(f"{base}/wireless") or os.path.exists(f"{base}/phy80211")
        if wifi:
            n_wifi += 1
            label = "Wi-Fi" if n_wifi == 1 else f"Wi-Fi {n_wifi}"
        else:
            n_eth += 1
            label = "Ethernet" if n_eth == 1 else f"Ethernet {n_eth}"
        nets.append({"id": name, "label": label, "kind": "wifi" if wifi else "ethernet",
                     "adapter": _udev_model(base) or name})
    return nets


def _nm_state():
    """device -> (connection name, ssid) via nmcli (best effort)."""
    out = {}
    try:
        r = subprocess.run(["nmcli", "-t", "-f", "DEVICE,STATE,CONNECTION", "device"],
                           capture_output=True, text=True, timeout=2)
        for line in r.stdout.splitlines():
            parts = line.replace("\\:", "\x00").split(":")
            if len(parts) >= 3:
                out[parts[0]] = (parts[1], parts[2].replace("\x00", ":"))
    except (OSError, subprocess.SubprocessError):
        pass
    return out


def _ip_addrs():
    out = {}
    try:
        r = subprocess.run(["ip", "-j", "addr"], capture_output=True, text=True, timeout=2)
        for itf in json.loads(r.stdout or "[]"):
            v4 = [a["local"] for a in itf.get("addr_info", []) if a.get("family") == "inet"]
            v6 = [a["local"] + ("%" + str(itf.get("ifindex")) if a.get("scope") == "link" else "")
                  for a in itf.get("addr_info", []) if a.get("family") == "inet6"]
            out[itf.get("ifname")] = (v4[0] if v4 else "", v6[0] if v6 else "")
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return out


class Collector:
    def __init__(self):
        self.static = StaticInfo()
        self.disk_info = disk_static()
        self.net_info = net_static()
        self.gpu_paths = []
        try:
            for c in sorted(os.listdir("/sys/class/drm")):
                p = f"/sys/class/drm/{c}/device/gpu_busy_percent"
                if c.startswith("card") and "-" not in c and os.path.exists(p):
                    self.gpu_paths.append((c, p, _udev_model(f"/sys/class/drm/{c}/device") or c))
        except OSError:
            pass
        self.prev_cpu = None
        self.prev_t = None
        self.prev_ticks: dict[int, tuple] = {}
        self.prev_io: dict[int, int] = {}
        self.prev_disk: dict[str, tuple] = {}
        self.prev_net: dict[str, tuple] = {}
        self.cache: dict[int, dict] = {}
        self.cycle = 0
        self.nm = {}
        self.ips = {}
        self.boot = time.time() - float((_read("/proc/uptime") or "0 0").split()[0])

    # ----------------------------------------------------------------- processes
    def _static_proc(self, pid, start):
        c = self.cache.get(pid)
        if c is not None and c["start"] == start:
            return c
        c = {"start": start, "uid": 0, "cmdline": [], "unit": "", "cgroup": "", "app": None,
             "io": True, "pss": None, "smaps": True, "arch": "64 bit"}
        try:
            c["uid"] = os.stat(f"/proc/{pid}").st_uid
        except OSError:
            pass
        raw = _read(f"/proc/{pid}/cmdline", "rb") or b""
        c["cmdline"] = [a.decode(errors="replace") for a in raw.split(b"\0") if a]
        cg = _read(f"/proc/{pid}/cgroup") or ""
        path = ""
        for line in cg.splitlines():
            if line.startswith("0::"):
                path = line[3:]
        c["cgroup"] = path
        unit = path.rstrip("/").rsplit("/", 1)[-1] if path else ""
        c["unit"] = unit
        did = apps.desktop_id_from_unit(unit)
        if did is None and c["uid"] == MY_UID:
            env = _read(f"/proc/{pid}/environ", "rb")
            if env:
                for kv in env.split(b"\0"):
                    if kv.startswith(b"GIO_LAUNCHED_DESKTOP_FILE="):
                        p = kv.split(b"=", 1)[1].decode(errors="replace")
                        did = os.path.basename(p)[:-8] if p.endswith(".desktop") else None
                        break
        if did:
            info = apps.app_info(did)
            if info and info[2]:
                c["app"] = did
        try:
            with open(f"/proc/{pid}/exe", "rb") as f:
                hdr = f.read(5)
            if hdr[:4] == b"\x7fELF":
                c["arch"] = "32 bit" if hdr[4] == 1 else "64 bit"
        except OSError:
            pass
        self.cache[pid] = c
        return c

    def _procs(self, snap, dt):
        procs = {}
        threads = 0
        ticks_now = {}
        io_now = {}
        self.cycle += 1
        try:
            pids = [int(p) for p in os.listdir("/proc") if p.isdigit()]
        except OSError:
            pids = []
        for pid in pids:
            data = _read(f"/proc/{pid}/stat", "rb")
            if not data:
                continue
            r = data.rfind(b")")
            comm = data[data.find(b"(") + 1:r].decode(errors="replace")
            f = data[r + 2:].split()
            try:
                state = f[0].decode()
                ppid = int(f[1])
                flags = int(f[6])
                ticks = int(f[11]) + int(f[12])
                nice = int(f[16])
                nthreads = int(f[17])
                start = int(f[19])
                rss_pages = int(f[21])
            except (IndexError, ValueError):
                continue
            p = Proc()
            p.pid, p.ppid, p.comm, p.state, p.nice, p.threads, p.start = pid, ppid, comm, state, nice, nthreads, start
            p.ticks = ticks
            p.cputime = ticks / CLK_TCK
            threads += nthreads
            kthread = bool(flags & PF_KTHREAD) or pid == 2 or ppid == 2
            prev = self.prev_ticks.get(pid)
            if prev and prev[1] == start and dt > 0:
                p.cpu = max(0.0, (ticks - prev[0]) / CLK_TCK / dt / NCPU * 100.0)
            ticks_now[pid] = (ticks, start)
            if kthread:
                p.kind = "kernel"
                p.uid, p.user, p.cmdline, p.unit, p.cgroup = 0, "root", [], "", ""
                p.name = comm
                p.desc = comm
                p.mem = 0
                p.efficiency = False
                procs[pid] = p
                continue
            c = self._static_proc(pid, start)
            p.uid = c["uid"]
            p.user = _user(p.uid)
            p.cmdline = c["cmdline"]
            p.unit = c["unit"]
            p.cgroup = c["cgroup"]
            p.app_id = c["app"]
            p.arch = c["arch"]
            p.name = _proc_name(comm, p.cmdline)
            p.efficiency = nice >= 10
            # memory: PSS (smaps_rollup, refreshed round-robin) or private anonymous RSS
            if c["smaps"] and (c["pss"] is None or (pid + self.cycle) % 3 == 0):
                sm = _read(f"/proc/{pid}/smaps_rollup")
                if sm:
                    i = sm.find("\nPss:")
                    if i >= 0:
                        try:
                            c["pss"] = int(sm[i + 5:sm.index("kB", i)].strip()) * 1024
                        except ValueError:
                            c["smaps"] = False
                else:
                    c["smaps"] = False
            if c["pss"] is not None:
                p.mem = c["pss"]
            else:
                sm = _read(f"/proc/{pid}/statm")
                try:
                    parts = sm.split()
                    p.mem = max(0, int(parts[1]) - int(parts[2])) * PAGE
                except (AttributeError, IndexError, ValueError):
                    p.mem = rss_pages * PAGE
            if c["io"]:
                io = _read(f"/proc/{pid}/io")
                if io is None:
                    c["io"] = False
                else:
                    tot = 0
                    for line in io.splitlines():
                        if line.startswith(("read_bytes", "write_bytes")):
                            tot += int(line.split()[1])
                    io_now[pid] = tot
                    pv = self.prev_io.get(pid)
                    if pv is not None and dt > 0:
                        p.disk = max(0.0, (tot - pv) / dt)
            if p.app_id:
                p.kind = "app"
            elif p.uid >= 1000 and p.uid != 65534:
                p.kind = "bg"
            else:
                p.kind = "sys"
            procs[pid] = p
        # forget dead pids
        for pid in list(self.cache):
            if pid not in procs:
                del self.cache[pid]
        self.prev_ticks = ticks_now
        self.prev_io = io_now
        snap.procs = procs
        snap.n_procs = sum(1 for p in procs.values() if p.kind != "kernel") + 1
        snap.n_threads = threads
        app_ids = {p.app_id for p in procs.values() if p.app_id}
        snap.apps = {a: apps.app_info(a) for a in app_ids}

    # ----------------------------------------------------------------- system
    def _cpu(self, snap):
        txt = _read("/proc/stat") or ""
        cur = {}
        for line in txt.splitlines():
            if line.startswith("cpu"):
                p = line.split()
                vals = [int(x) for x in p[1:9]]
                idle = vals[3] + vals[4]
                cur[p[0]] = (sum(vals), idle)
        if self.prev_cpu:
            def pct(k):
                a, b = cur.get(k), self.prev_cpu.get(k)
                if not a or not b or a[0] == b[0]:
                    return 0.0
                return max(0.0, min(100.0, 100.0 * (1 - (a[1] - b[1]) / (a[0] - b[0]))))
            snap.cpu_total = pct("cpu")
            snap.cpu_cores = [pct(f"cpu{i}") for i in range(NCPU)]
        else:
            snap.cpu_cores = [0.0] * NCPU
        self.prev_cpu = cur
        tot = n = 0
        for i in range(NCPU):
            v = _read(f"/sys/devices/system/cpu/cpu{i}/cpufreq/scaling_cur_freq")
            if v:
                try:
                    tot += int(v)
                    n += 1
                except ValueError:
                    pass
        if n:
            snap.freq_khz = tot / n
        else:
            for line in (_read("/proc/cpuinfo") or "").splitlines():
                if line.startswith("cpu MHz"):
                    snap.freq_khz = float(line.split(":")[1]) * 1000
                    break

    def _mem(self, snap):
        m = {}
        for line in (_read("/proc/meminfo") or "").splitlines():
            k, _, v = line.partition(":")
            try:
                m[k] = int(v.split()[0]) * 1024
            except (IndexError, ValueError):
                pass
        total = m.get("MemTotal", 1)
        avail = m.get("MemAvailable", m.get("MemFree", 0))
        compressed = 0
        zram_orig = 0
        try:
            for z in os.listdir("/sys/block"):
                if z.startswith("zram"):
                    st = (_read(f"/sys/block/{z}/mm_stat") or "").split()
                    if len(st) >= 3:
                        zram_orig += int(st[0])
                        compressed += int(st[2])
        except OSError:
            pass
        snap.mem = {
            "total": total, "avail": avail, "used": total - avail, "free": m.get("MemFree", 0),
            "cached": m.get("Cached", 0) + m.get("Buffers", 0) + m.get("SReclaimable", 0),
            "modified": m.get("Dirty", 0) + m.get("Writeback", 0),
            "committed": m.get("Committed_AS", 0), "commit_limit": m.get("CommitLimit", 0) or total,
            "swap_total": m.get("SwapTotal", 0), "swap_used": m.get("SwapTotal", 0) - m.get("SwapFree", 0),
            "paged": m.get("SReclaimable", 0), "nonpaged": m.get("SUnreclaim", 0) + m.get("KernelStack", 0),
            "compressed": compressed, "zram_orig": zram_orig,
            "reserved": self.static.mem_reserved,
        }

    def _disks(self, snap, dt):
        stats = {}
        for line in (_read("/proc/diskstats") or "").splitlines():
            p = line.split()
            if len(p) >= 14:
                stats[p[2]] = (int(p[3]), int(p[5]), int(p[6]), int(p[7]), int(p[9]), int(p[10]), int(p[12]))
        out = []
        for d in self.disk_info:
            s = stats.get(d["name"])
            e = dict(d)
            e.update(active=0.0, read=0.0, write=0.0, resp=0.0)
            pv = self.prev_disk.get(d["name"])
            if s and pv and dt > 0:
                e["active"] = max(0.0, min(100.0, (s[6] - pv[6]) / (dt * 1000.0) * 100.0))
                e["read"] = (s[1] - pv[1]) * 512 / dt
                e["write"] = (s[4] - pv[4]) * 512 / dt
                ios = (s[0] - pv[0]) + (s[3] - pv[3])
                if ios > 0:
                    e["resp"] = ((s[2] - pv[2]) + (s[5] - pv[5])) / ios
            if s:
                self.prev_disk[d["name"]] = s
            out.append(e)
        snap.disks = out

    def _nets(self, snap, dt):
        if self.cycle % 10 == 1:
            self.nm = _nm_state()
            self.ips = _ip_addrs()
        stats = {}
        for line in (_read("/proc/net/dev") or "").splitlines()[2:]:
            name, _, rest = line.partition(":")
            p = rest.split()
            if len(p) >= 9:
                stats[name.strip()] = (int(p[0]), int(p[8]))
        out = []
        for n in self.net_info:
            s = stats.get(n["id"])
            e = dict(n)
            e.update(send=0.0, recv=0.0)
            pv = self.prev_net.get(n["id"])
            if s and pv and dt > 0:
                e["recv"] = max(0, s[0] - pv[0]) * 8 / dt
                e["send"] = max(0, s[1] - pv[1]) * 8 / dt
            if s:
                self.prev_net[n["id"]] = s
            oper = (_read(f"/sys/class/net/{n['id']}/operstate") or "").strip()
            e["up"] = oper == "up"
            try:
                e["speed"] = int((_read(f"/sys/class/net/{n['id']}/speed") or "-1").strip())
            except ValueError:
                e["speed"] = -1
            st = self.nm.get(n["id"])
            e["conn"] = st[1] if st and st[1] and st[1] != "--" else ""
            e["ipv4"], e["ipv6"] = self.ips.get(n["id"], ("", ""))
            out.append(e)
        snap.nets = out

    def _gpus(self, snap):
        out = []
        for i, (card, path, name) in enumerate(self.gpu_paths):
            try:
                busy = float((_read(path) or "0").strip())
            except ValueError:
                busy = 0.0
            out.append({"index": i, "name": name, "busy": busy})
        snap.gpus = out

    def sample(self) -> Snapshot:
        snap = Snapshot()
        now = snap.t
        dt = (now - self.prev_t) if self.prev_t else 0.0
        self.prev_t = now
        self._cpu(snap)
        self._mem(snap)
        self._procs(snap, dt)
        self._disks(snap, dt)
        self._nets(snap, dt)
        self._gpus(snap)
        try:
            snap.n_handles = int((_read("/proc/sys/fs/file-nr") or "0").split()[0])
        except (ValueError, IndexError):
            snap.n_handles = 0
        snap.uptime = float((_read("/proc/uptime") or "0 0").split()[0])
        snap.boot_time = self.boot
        if self.cycle % 30 == 0:
            self.disk_info = disk_static()
        return snap
