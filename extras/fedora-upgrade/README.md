# Fedora 43 → 45 upgrade (Galaxy Book 940XGK running Fenestra)

Status: **WIP**. The upgrade path is ready and verified as far as it can be without the
real reboot. The Explorer layer for Nautilus 51 is done (`desktop/nautilus/overlay/51/`).

## How the upgrade runs (Settings › Fenestra Update › Upgrade)

`desktop/libexec/fenestra-release-upgrade` does everything; the scripts in this folder are the
manual equivalent and stay for recovery.

1. Settings asks `fenestra-release-upgrade available` (fedoraproject.org/releases.json) and
   shows "Fedora N is available" for the newest release at most two ahead.
2. **Upgrade** → `pkexec fenestra-release-upgrade start N --kit … --user …`: the helper copies
   itself to `/usr/local/libexec/fenestra/` (or uses `/usr/libexec/fenestra/` on the ISO),
   installs `fenestra-post-upgrade.service` and runs as the transient unit
   `fenestra-release-upgrade.service` (closing Settings does not stop it). Progress goes to
   `/var/log/fenestra-release-upgrade.log` and `/var/lib/fenestra/release-upgrade.json`, which
   the page polls.
3. Run: backup → COPRs without a chroot for N disabled → Fenestra system pieces (lock screen,
   Hello assets) → local repo with rebuilds of local packages (prebuilt from the kit
   `~/.local/share/fenestra/upgrade-kit/rpms`, else rebuilt from `srpms/` in a fedora:N
   container) → pinned drivers (egismoc libfprint) → dry run (stops if anything important
   would be removed) → full update of the current release + DKMS check for the new kernel →
   `dnf system-upgrade download` → Windows-style Plymouth theme (`fenestra-plymouth-theme`,
   black screen, dot spinner, "Working on updates · NN% complete · Don't turn off your
   computer") + initramfs → "Restart now".
4. Restart → offline upgrade with that screen → `fenestra-post-upgrade.service` (before the
   login screen): DKMS/akmods for the new kernel, local rebuilds for the new Python, system
   pieces; if the camera/speaker drivers do not build, the previous kernel becomes the default.
5. Login → `fenestra-release-upgrade-user` (autostart): extensions on, Explorer layer for the
   new Nautilus, `check.sh`, notification with the result. The page shows the outcome.

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
| Plymouth theme `fenestra` (Plymouth 26, Fedora 45 kernel 7.2.15 + dracut initramfs, QEMU **TCG** + OVMF, bochs-drm; `tests/plymouth/`) | boot (firmware-logo stand-in + spinner), live switch to the offline-upgrade screen (`change-mode --system-upgrade`, what `dnf5 offline` does), progress 0/42/87 %, `--updates` mode, Restarting, Shutting down; English and Spanish; 1280×800, 1920×1080 and 2560×1600 (2× assets). Text uses Selawik Semilight through the `99fenestra-plymouth` dracut module (Plymouth only reads `/usr/share/fonts/Plymouth.ttf`). Not covered without KVM/real hardware: the firmware's own BGRT logo hand-off and a full `dnf5 offline` run |
| Release upgrade for later releases (os-release logic, rebrand, GNOME version check), fedora:45 container | version from `/usr/lib/os-release`; a stale "Fenestra 43" `/etc/os-release` and boot entry become "Fenestra 45"; with a simulated GNOME 53 the login step keeps the desktop extensions on and reports them |
| Lock screen and greeter on GNOME 51.1 vs 49 (headless shells; logind/GDM stubs and accounts-daemon in `f45-lab/fakelogind.py`) | lock-clock, direct-unlock, user-lock-prompt, spotlight enable and lock the screen on both; the Fenestra lock background and account prompt render on both; fenestra-login + spotlight enable in `--mode=gdm` and draw the greeter background. Fast unlock on 51 (simulated verifier): after a Hello success the fingerprint/face hints are dropped and only the short success message stays. Not verifiable without a real GDM/PAM: typing the password, Howdy/fingerprint unlock timing (51's verifier needs GDM's reauthentication service) |

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
  `_onVerificationComplete` left the verifier: fast unlock now hooks `AuthServices._onVerificationComplete`
  (which service succeeded) and `ShellUserVerifier.handlePendingMessages()` (what AuthPrompt waits for).
- Mutter 51 removed `Meta.Background.set_file` (backgrounds load through a private glycin cache):
  the lock screen, greeter and startup cover use an St background (cover) there — before this,
  `Main.screenShield.lock()` threw and **the screen never locked** on 51.
- `Shell.GLSLEffect` removed → `rounded-window-corners/effect/glsl_compat.js` (Clutter.ShaderEffect + Cogl.Snippet).
- `addChrome({affectsInputRegion})` removed.
- Every extension declares `"51"`.

## Open work (see the cloud hand-off in the PR)

- Lock screen / GDM on GNOME 51: the unlock itself (password, Hello, fingerprint and the fast-unlock
  timing) can only be checked on the real machine.

## Login screen after the upgrade

See `docs/login-safety.md`: why Fedora 45 showed a black screen, how to restore the
Fenestra login (`restore-login-extensions.sh`, `fix-local-services.sh`) and the safety net
(compatibility matrix, linter, greeter bench, Fenestra Update gate, greeter guard).
