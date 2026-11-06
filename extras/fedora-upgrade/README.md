# Fedora 43 → 45 upgrade (Galaxy Book 940XGK running Fenestra)

Status: **WIP**. The upgrade path is ready and verified as far as it can be without the
real reboot. The Explorer layer for Nautilus 51 is done (`desktop/nautilus/overlay/51/`).

## User steps

1. `sudo bash extras/fedora-upgrade/prepare-f45.sh` — backup, system-wide Fenestra pieces,
   local repo with the Fedora 45 rebuilds (kit in `~/Downloads/Fenestra/fedora45-kit`),
   COPR fixes, GRUB menu visible, full Fedora 43 update (installs kernel 7.2.15 = the
   Fedora 45 kernel, rebuilds the DKMS drivers for it).
2. Reboot (7.2.15 is the default), log in, `bash extras/fedora-upgrade/check.sh`, and try
   camera (Meet), speakers, mic, Hello, fingerprint, Wi-Fi, Bluetooth, suspend.
   If anything fails: reboot, pick 6.17.1 in GRUB, report.
3. `sudo bash extras/fedora-upgrade/upgrade-f45.sh` — download + offline upgrade.
4. First login on 45: `sudo bash extras/fedora-upgrade/post-upgrade-f45.sh`, then log out/in.

## What was verified

| Area | Result |
|---|---|
| DKMS `ov02c10`, `ipu-bridge-fix`, `max98390-hda` vs kernel 7.2.15 (Fedora kernel-devel in a container) | all compile; the 7.2 kernel still lacks the Samsung quirks, so the DKMS builds stay needed |
| `dnf distro-sync --releasever=45` simulation as user | resolves once howdy/python3-dlib come from the local repo and libfprint is pinned; 2 removals (low-memory-monitor, python3-simpleaudio) |
| howdy + python3-dlib (local builds, hard-wired to Python 3.14) | rebuilt for Fedora 45 / Python 3.15 (`specs/`), import tests pass |
| libfprint for the ETU905A80 (1c7a:05a1) | Fedora 45 ships a different driver (egis_etu905, no SDCP); prepare-f45.sh excludes Fedora's libfprint so the COPR egismoc+SDCP build stays |
| COPRs | claude-desktop has no Fedora 45 chroot (disabled); howdy-beta replaced by the local rebuild |
| GNOME Shell 51 (headless, `f45-lab/`) with the user's extensions | before: windows-tray, lock-clock, spotlight/Hello, rounded-window-corners failed. After the ports in this branch all load; screenshots of taskbar, Start, quick settings, window corners checked |
| Same ports on GNOME 49 (headless) | all load, no regressions |
| Fenestra Settings, Task Manager, OOBE, Notepad on GTK 4.24 / Python 3.15 | start without tracebacks |
| Explorer on Nautilus 51.1 (`overlay/51`, fedora:45 container, GNOME Shell 51 headless) vs Nautilus 49.6 (fedora:43), same overlay build and user | same pixels side by side: tabs in the title bar, command bar, View/Sort/See more menus under their buttons, background and file context menus with icons, address bar (path and edit mode), sidebar with patched icons and pins, Home/This PC/Gallery pages, Details view, new tab. Only environment differences: thumbnails (no thumbnailer in the container), "Open in Terminal" (no terminal extension) |

## GNOME 51 API changes handled

- Nautilus 51 (Blueprint): `nautilus-files-view-context-menus.ui` moved to `/org/gnome/nautilus/menu/`;
  the window wraps its content in `AdwTabOverview` (`tab_overview`, `create_tab_cb`) and connects
  the `tab_view` signals from the template; `nautilus-sidebar-row.ui` lost the `sidebar-row` /
  `sidebarrow-icon` / `sidebar-label` classes (restored in the overlay for Fenestra's CSS);
  details columns now have sorters (arrow hidden, as on 49); widget names became style classes
  (`fenestra-explorer.py` gives them their 49 names back). Overlay/51 = Fenestra's overlay/49
  changes applied to these templates, ids/signals kept.
- GTK 4.24: `-gtk-icon-style: regular` now drops `-symbolic` and picks the icon theme's
  coloured `window-close` (tab close) — symbolic restored where Fenestra needs the glyph.

- `St.BoxLayout` `vertical:` property removed → `orientation: Clutter.Orientation.VERTICAL`.
- `ShellUserVerifier`/`MessageType` moved from `gdm/util.js` to `gdm/userVerifier.js`;
  `_queueMessage(service, message, type)` became `_queueMessage({serviceName, message, messageType, wiggle})`;
  `_onVerificationComplete` left the verifier (fast-unlock tweak is skipped on 51).
- `Shell.GLSLEffect` removed → `rounded-window-corners/effect/glsl_compat.js` (Clutter.ShaderEffect + Cogl.Snippet).
- `addChrome({affectsInputRegion})` removed.
- Every extension declares `"51"`.

## Open work (see the cloud hand-off in the PR)

- Lock screen / GDM on GNOME 51 can only be fully checked on the real machine.
