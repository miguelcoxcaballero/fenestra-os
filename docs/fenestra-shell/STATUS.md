# Fenestra Shell: status

Branch `feature/fenestra-shell-kwin`. Tested only in the headless KWin bench
(`tests/shell-kwin/build.sh`, Fedora 45, KWin 6.8.2, Qt 6.11.2), with one and two outputs.
**Not tested yet in a VM or on the laptop.** The per-feature state is in [CHECKLIST.md](CHECKLIST.md).

| Milestone | State | How it was tested |
|---|---|---|
| Phase 0: merge, inventories, feasibility | done: INVENTORY.md, APPS.md, FEASIBILITY.md, CHECKLIST.md | greeter bench 9/9, Notepad/Paint/Task Manager smoke tests, linter, after the merge |
| H1 minimal session | done in the container | KWin + shell + GTK 4 and X11 clients; shell crash → windows survive, relaunch; session units verified with `systemd-analyze --user verify` |
| H2 taskbar | mostly done | grouping, pins, launch, unpinned apps, preview list, menus, alignment, search modes, light mode, tray (StatusNotifierItem + menus), keyboard layout, two outputs. **Missing:** live thumbnails and acrylic (need OpenGL), real Wi-Fi/volume/battery (VM), privacy glyphs (H4) |
| H3 Start and Search | done in the container | Start (pins, Recommended, All apps ×3 views, power and account menus, Super via D-Bus), Search (home, history, chips, apps, Settings pages, documents/folders/photos, preview, opening). **Missing:** acrylic blur (VM), localsearch for file contents |
| H4 tray panels | mostly done in the container | notifications server + centre + banners, calendar with Focus, quick settings + media, OSD, Ctrl+Alt+Del, image toast, snipping overlay (Super+Shift+S / Print; frozen screen from a test picture in the bench). **Missing:** ScreenShot2 capture and clipboard (VM), real devices, polkit and media keys (VM), camera privacy glyph |
| H5 desktop | done in the container | icons, selection, rename, new folder / from template, move, trash, menus, solid colour and Spotlight wallpapers |
| Visual tuning | waiting for reference measurements | `design/tokens.json` holds placeholders; `tools/apply-measurements.py` merges the measured values |
| H6 windows | mostly done in the container | Fenestra decoration (Aurorae, loaded by KWin), Alt+Tab theme, Snap Layouts (window placed exactly), Task View (KWin Overview), first-login curtain. **Missing:** rounded window corners (needs a KWin effect; GL), Snap Layouts on hovering maximize |
| H7 apps | in progress | session integration done (portals, autostart, mimeapps, search launcher); Fenestra Settings backends being split for the KWin session |
| H8 lock | Windows 11 lock screen (measured), real kscreenlocker + PAM bench | kscreenlocker shell package `shells/org.fenestra.desktop`; Howdy needs `fenestra-lock-hello enable` (root); login screen (GDM): not this package |
| H9 migrator | backend + delivery done in the container | `fenestra-migrate` ships in the Fenestra overlay (so Settings › Fenestra Update shows «Migrar a KDE» on a GNOME install); it downloads `fenestra-shell` from the rolling release `fenestra-shell-latest` (`.github/workflows/shell-rpm.yml`, one build per commit of `main`, `index.json` + `SHA256SUMS`), verifies it and installs it with dnf. check / dry run / run / boot test / update-shell / rollback tested in a Fedora 45 GNOME container against a local copy of the release. **Missing:** first published release (after the merge to main), the run on a real PC through pkexec |
| H10 performance | protocol + container numbers | PERF.md; laptop comparison with GNOME pending |
| H11 install | RPM + kickstart + CI release | `fenestra-shell` RPM builds (Release `<commit date>.git<id>`); the ISO ships it; CI publishes it for every commit of `main`; GNOME stays the default session until the VM checklist passes |

## How to run the bench

```bash
docker build -f tests/shell-kwin/Containerfile -t fenestra-kwinlab .
tests/shell-kwin/build.sh                 # one 1920×1080 output
OUTPUTS=2 tests/shell-kwin/build.sh       # two outputs
```

The bench prints `CHECK <id> PASS|FAIL` lines and `QA_RESULT`. Its screenshots are made from the
shell's own surfaces (the app windows are not in them), because KWin cannot take screenshots
without OpenGL (FEASIBILITY.md).

## Known differences from the GNOME session

- Acrylic: KWin blur plus a tint, instead of the GNOME layer's luminosity remap.
- Live window thumbnails: not yet (window list with close buttons instead).

## How «Migrar a KDE» gets the Fenestra session

1. `.github/workflows/shell-rpm.yml` builds `packaging/fenestra-shell.spec` in a Fedora 45 container
   for every push to `main` and uploads the RPM, `index.json` and `SHA256SUMS`
   (`packaging/rpm-index.py`, newest 10 builds) to the pre-release `fenestra-shell-latest`.
   Pull requests and other branches only build it (workflow artifact).
2. Settings › Fenestra Update › «Migrar a KDE» runs `pkexec /usr/libexec/fenestra/fenestra-migrate`
   (installed by `build/build-overlay.sh`, i.e. by every Fenestra install and update — not by the RPM,
   so removing the RPM keeps it). `check` reads `index.json` and picks the build of the installed
   commit (`/usr/share/fenestra/release.json`), else the newest one for the same Fedora version;
   `download` fetches it to `/var/cache/fenestra/migrate`, compares its SHA-256 with `index.json`
   and `SHA256SUMS` and its RPM header; `simulate`/`install` run dnf on the Fedora runtime packages
   plus that local file. Errors (no build published, 404, no network, checksum) end in the state
   file's `error`, shown by Settings; `rollback --remove-packages` removes what was installed and the cache.
3. Later Fenestra updates (`fenestra-update`) run `fenestra-migrate update-shell` when
   `fenestra-shell` is installed: the build of the new commit, boot-tested, and the previous build
   put back with `dnf downgrade` if the test fails.

Container test (no pkexec, so the source can be overridden): `FENESTRA_SHELL_RPM_BASE=http://127.0.0.1:8000/`
(or `file:///dir/`) points to a directory with the same three kinds of files.
