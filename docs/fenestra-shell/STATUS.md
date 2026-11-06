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
| H8 lock | lock screen done (render test) | kscreenlocker look-and-feel `org.fenestra.desktop`; real PAM / Howdy / fingerprint unlock and the login screen: VM / laptop |
| H9 migrator | backend done | `fenestra-migrate` phases tested in the container; the Settings page comes after the backend split |
| H10 performance | protocol + container numbers | PERF.md; laptop comparison with GNOME pending |
| H11 install | RPM + kickstart | `fenestra-shell` RPM builds; the ISO ships it; GNOME stays the default session until the VM checklist passes |

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
