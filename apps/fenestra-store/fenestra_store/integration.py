"""Make Fenestra Store the only software store people see, without uninstalling anything.

GNOME Software and KDE Discover stay installed (their PackageKit / Flatpak plugins, D-Bus
services and notifiers keep working), but their launchers are overridden by desktop entries
of the same id in a directory that comes first in the XDG search path:

* org.gnome.Software.desktop and org.kde.discover.desktop -> open Fenestra Store, hidden from
  menus and search (NoDisplay), so pins, "Software" links and `gtk-launch org.gnome.Software`
  still work and land in Fenestra Store;
* gnome-software-local-file-{flatpak,packagekit}.desktop -> `fenestra-store --local-filename`,
  so the system's default handlers for .flatpakref / .flatpakrepo / .rpm open Fenestra Store;
* Discover's URL, Flatpak and Snap handlers -> Hidden (removed for this user).

Per user (`fenestra-store --set-default`, run by install.sh for a per-user install): the files
go to ~/.local/share/applications and Fenestra Store becomes the default handler for
appstream:// links, flatpak+https:// links, .flatpakref, .flatpakrepo and .rpm files in
~/.config/mimeapps.list. System-wide (install.sh with PREFIX=/usr, as build-overlay.sh runs
it): the same files in /usr/local/share/applications. `--unset-default` undoes the per-user part.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

MARK = "X-Fenestra-Store-Override=true"
STORE_ID = "org.fenestra.Store.desktop"
MIME_TYPES = ["x-scheme-handler/appstream", "x-scheme-handler/flatpak+https", "application/vnd.flatpak.ref",
              "application/vnd.flatpak.repo", "application/x-rpm", "application/x-redhat-package-manager"]

REDIRECT = {
    # desktop id: (Exec arguments, MimeType or "")
    "org.gnome.Software.desktop": ("%U", "x-scheme-handler/appstream;x-scheme-handler/flatpak+https;"),
    "org.kde.discover.desktop": ("%U", ""),
    "gnome-software-local-file-flatpak.desktop": ("--local-filename %f",
                                                  "application/vnd.flatpak.repo;application/vnd.flatpak.ref;"),
    "gnome-software-local-file-packagekit.desktop": ("--local-filename %f",
                                                     "application/x-rpm;application/x-redhat-package-manager;"),
}
HIDE = ["org.kde.discover.urlhandler.desktop", "org.kde.discover.flatpak.desktop", "org.kde.discover.snap.desktop"]


def entries(exe: str = "fenestra-store") -> dict[str, str]:
    """{desktop id: file content} of every override."""
    out = {}
    for did, (args, mime) in REDIRECT.items():
        lines = ["[Desktop Entry]", "Type=Application", "Name=Fenestra Store", "Name[es]=Fenestra Store",
                 "GenericName=Software center", "GenericName[es]=Centro de software",
                 "Comment=Find, install and update apps from Flathub and Fedora",
                 "Comment[es]=Busca, instala y actualiza aplicaciones de Flathub y Fedora",
                 f"Exec={exe} {args}", "Icon=org.fenestra.Store", "Terminal=false", "StartupNotify=true",
                 "StartupWMClass=org.fenestra.Store", "Categories=GTK;System;PackageManager;", "NoDisplay=true"]
        if mime:
            lines.append(f"MimeType={mime}")
        lines += ["# Fenestra Store replaces this store; the original stays installed.", MARK, ""]
        out[did] = "\n".join(lines)
    for did in HIDE:
        out[did] = "\n".join(["[Desktop Entry]", "Type=Application", "Name=Discover", "Exec=true", "Hidden=true",
                              MARK, ""])
    return out


def write_overrides(directory: str, exe: str = "fenestra-store") -> list[str]:
    os.makedirs(directory, exist_ok=True)
    written = []
    for did, text in entries(exe).items():
        path = os.path.join(directory, did)
        if os.path.exists(path) and not _ours(path):
            continue   # never overwrite someone else's override
        with open(path + ".part", "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(path + ".part", path)
        written.append(path)
    return written


def _ours(path: str) -> bool:
    try:
        with open(path, encoding="utf-8") as f:
            return MARK in f.read()
    except OSError:
        return False


def remove_overrides(directory: str) -> list[str]:
    removed = []
    for did in list(REDIRECT) + HIDE:
        path = os.path.join(directory, did)
        if _ours(path):
            os.remove(path)
            removed.append(path)
    return removed


def _user_apps_dir() -> str:
    from gi.repository import GLib
    return os.path.join(GLib.get_user_data_dir(), "applications")


def _refresh(directory: str):
    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", "-q", directory], check=False)


def _refresh_menus():
    """KService (the Fenestra shell's Start menu, Plasma, Discover) caches desktop entries in
    ksycoca; rebuild it so the hidden launchers disappear now, not at the next login."""
    for tool in ("kbuildsycoca6", "kbuildsycoca5"):
        if shutil.which(tool):
            subprocess.run([tool], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return


def set_defaults(remove=False) -> list[str]:
    """Fenestra Store as this user's handler for MIME_TYPES (~/.config/mimeapps.list)."""
    from gi.repository import Gio, GLib
    done = []
    if remove:
        path = os.path.join(GLib.get_user_config_dir(), "mimeapps.list")
        kf = GLib.KeyFile()
        try:
            kf.load_from_file(path, GLib.KeyFileFlags.KEEP_COMMENTS)
        except GLib.Error:
            return done
        for m in MIME_TYPES:
            try:
                if kf.get_string("Default Applications", m).split(";")[0] == STORE_ID:
                    kf.remove_key("Default Applications", m)
                    done.append(m)
            except GLib.Error:
                pass
        kf.save_to_file(path)
        return done
    info = Gio.DesktopAppInfo.new(STORE_ID)
    if info is None:
        raise RuntimeError(f"{STORE_ID} is not installed")
    for m in MIME_TYPES:
        try:
            info.set_as_default_for_type(m)
            done.append(m)
        except GLib.Error as e:
            print(f"fenestra-store: cannot set the default for {m}: {e.message}", file=sys.stderr)
    return done


def main(remove=False) -> int:
    d = _user_apps_dir()
    exe = shutil.which("fenestra-store") or "fenestra-store"
    if remove:
        files = remove_overrides(d)
        mimes = set_defaults(remove=True)
    else:
        files = write_overrides(d, exe)
        _refresh(d)
        mimes = set_defaults()
    _refresh(d)
    _refresh_menus()
    verb = "removed" if remove else "wrote"
    for f in files:
        print(f"{verb} {f}")
    for m in mimes:
        print(("default handler reset: " if remove else "default handler: Fenestra Store for ") + m)
    return 0


if __name__ == "__main__":
    # python3 -m fenestra_store.integration --system DIR [EXE]: write the overrides into DIR (packaging)
    if len(sys.argv) >= 3 and sys.argv[1] == "--system":
        for p in write_overrides(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "fenestra-store"):
            print(p)
    else:
        sys.exit(main(remove="--remove" in sys.argv))
