"""Things Task Manager does to the system.  Everything is refused in read-only/demo mode."""
from __future__ import annotations

import os
import shlex
import shutil
import signal
import subprocess

from gi.repository import Gio, GLib

from . import util


def _allowed():
    return not (util.DEMO or util.READ_ONLY)


def _pids_alive(pids):
    alive = []
    for p in pids:
        try:
            os.kill(p, 0)
            alive.append(p)
        except ProcessLookupError:
            pass
        except PermissionError:
            alive.append(p)
    return alive


def _pkexec(argv):
    if shutil.which("pkexec"):
        try:
            subprocess.Popen(["pkexec"] + argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except OSError:
            pass
    return False


def end_task(pids, cgroup=None, on_error=None):
    """SIGTERM, then SIGKILL after 3 s for whatever is still alive.  Uses the cgroup's
    cgroup.kill / systemd scope stop for whole apps when possible."""
    if not _allowed() or not pids:
        return False
    denied = []
    for p in pids:
        try:
            os.kill(p, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError:
            denied.append(p)
    if denied:
        _pkexec(["kill", "-TERM"] + [str(p) for p in denied])

    def finish():
        left = _pids_alive(pids)
        if not left:
            return False
        if cgroup and cgroup.endswith(".scope"):
            path = "/sys/fs/cgroup" + cgroup + "/cgroup.kill"
            try:
                with open(path, "w") as f:
                    f.write("1")
                return False
            except OSError:
                pass
        mine, theirs = [], []
        for p in left:
            try:
                os.kill(p, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except PermissionError:
                theirs.append(p)
        if theirs:
            _pkexec(["kill", "-KILL"] + [str(p) for p in theirs])
        return False
    GLib.timeout_add(3000, finish)
    return True


def set_efficiency(pids, on):
    """Efficiency mode: nice +10 and idle I/O class (back to normal when turned off)."""
    if not _allowed():
        return False
    need_root = []
    for p in pids:
        try:
            os.setpriority(os.PRIO_PROCESS, p, 10 if on else 0)
        except PermissionError:
            need_root.append(p)
        except ProcessLookupError:
            continue
        if shutil.which("ionice"):
            subprocess.Popen(["ionice", "-c", "3" if on else "2", "-p", str(p)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if need_root:
        _pkexec(["renice", "-n", "10" if on else "0", "-p"] + [str(p) for p in need_root])
    return True


def open_file_location(pid):
    if not _allowed():
        return
    try:
        exe = os.readlink(f"/proc/{pid}/exe")
    except OSError:
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                exe = f.read().split(b"\0")[0].decode()
            exe = shutil.which(exe) or exe
        except OSError:
            return
    exe = exe.replace(" (deleted)", "")
    uri = Gio.File.new_for_path(exe).get_uri()
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call("org.freedesktop.FileManager1", "/org/freedesktop/FileManager1",
                 "org.freedesktop.FileManager1", "ShowItems",
                 GLib.Variant("(ass)", ([uri], "")), None, Gio.DBusCallFlags.NONE, 2000, None, None)
    except GLib.Error:
        Gio.AppInfo.launch_default_for_uri(Gio.File.new_for_path(os.path.dirname(exe)).get_uri(), None)


def search_online(name):
    if _allowed():
        Gio.AppInfo.launch_default_for_uri(
            "https://duckduckgo.com/?q=" + GLib.uri_escape_string(name + " linux process", None, False), None)


def run_task(text, admin=False):
    """Run new task: a command line, a path or a URI."""
    if not _allowed():
        return True
    text = text.strip()
    if not text:
        return False
    try:
        if "://" in text and " " not in text:
            Gio.AppInfo.launch_default_for_uri(text, None)
            return True
        path = os.path.expanduser(text)
        if os.path.exists(path) and not os.access(path, os.X_OK) or os.path.isdir(path):
            Gio.AppInfo.launch_default_for_uri(Gio.File.new_for_path(path).get_uri(), None)
            return True
        argv = shlex.split(text)
        if not argv or not shutil.which(os.path.expanduser(argv[0])):
            return False
        if admin:
            argv = ["pkexec", "env", f"DISPLAY={os.environ.get('DISPLAY', '')}",
                    f"WAYLAND_DISPLAY={os.environ.get('WAYLAND_DISPLAY', '')}",
                    f"XDG_RUNTIME_DIR={os.environ.get('XDG_RUNTIME_DIR', '')}"] + argv
        subprocess.Popen(argv, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (OSError, ValueError, GLib.Error):
        return False


def service_action(action, unit, user=False, done=None):
    """systemctl start/stop/restart (system units authenticate through polkit)."""
    if not _allowed():
        return
    argv = ["systemctl"] + (["--user"] if user else []) + [action, unit]
    try:
        proc = Gio.Subprocess.new(argv, Gio.SubprocessFlags.STDERR_PIPE)
    except GLib.Error:
        return

    def fin(p, res):
        try:
            p.communicate_utf8_finish(res)
        except GLib.Error:
            pass
        if done:
            done()
    proc.communicate_utf8_async(None, None, fin)


def open_users_settings():
    if not _allowed():
        return
    for argv in (["fenestra-settings", "--page", "accounts"], ["gnome-control-center", "users"]):
        if shutil.which(argv[0]):
            subprocess.Popen(argv, start_new_session=True)
            return


def open_services_tool():
    for argv in (["systemd-manager"], ["cockpit-desktop", "services"], ["gnome-logs"]):
        if shutil.which(argv[0]):
            if _allowed():
                subprocess.Popen(argv, start_new_session=True)
            return True
    return False


def has_services_tool():
    return any(shutil.which(a) for a in ("systemd-manager", "cockpit-desktop", "gnome-logs"))
