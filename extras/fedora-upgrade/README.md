# Fedora 43 → 45 upgrade (Galaxy Book 940XGK running Fenestra)

Status: **WIP**. The upgrade path is ready and verified as far as it can be without the
real reboot; the Explorer port to Nautilus 51 is unfinished (Files falls back to stock
Nautilus on Fedora 45 until it is done).

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

## GNOME 51 API changes handled

- `St.BoxLayout` `vertical:` property removed → `orientation: Clutter.Orientation.VERTICAL`.
- `ShellUserVerifier`/`MessageType` moved from `gdm/util.js` to `gdm/userVerifier.js`;
  `_queueMessage(service, message, type)` became `_queueMessage({serviceName, message, messageType, wiggle})`;
  `_onVerificationComplete` left the verifier (fast-unlock tweak is skipped on 51).
- `Shell.GLSLEffect` removed → `rounded-window-corners/effect/glsl_compat.js` (Clutter.ShaderEffect + Cogl.Snippet).
- `addChrome({affectsInputRegion})` removed.
- Every extension declares `"51"`.

## Open work (see the cloud hand-off in the PR)

- Nautilus 51 Explorer overlay: `desktop/nautilus/overlay/51-wip/` is an unverified port;
  rename to `51/` only after it renders like 49 (the launchers pick `overlay/<major>/`).
- `fenestra-explorer.py` and the other nautilus-python extensions on Nautilus 51.
- Lock screen / GDM on GNOME 51 can only be fully checked on the real machine.
