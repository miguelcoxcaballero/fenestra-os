<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/wordmark-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="docs/images/wordmark-light.png">
    <img src="docs/images/wordmark-light.png" width="420" alt="Fenestra OS">
  </picture>
</p>

<p align="center"><b>A Fedora-based Linux distribution that looks and works like Windows 11.</b><br>
Taskbar, Start, Search, File Explorer, Settings, Task Manager and first-boot setup — rebuilt on GNOME, open source.</p>

<p align="center">
  <img src="docs/images/desktop.png" width="900" alt="Fenestra desktop: centred taskbar with Start, Search and File Explorer">
</p>

---

Fenestra is a **Fedora 43 remix**. It installs Fedora Workstation and layers a complete
Windows-11-style desktop on top of GNOME 49. There is no Wine and no theming trick that breaks on
update: just GNOME Shell extensions, an Explorer layer for Files, and apps written from scratch:
**Fenestra Settings**, **Fenestra Task Manager** and the **Fenestra first-boot setup (OOBE)**.

> Fenestra is not affiliated with Microsoft and contains no Microsoft files (see
> [THIRD-PARTY.md](THIRD-PARTY.md)). If you dual-boot, `fenestra-import-windows-assets` can copy
> *your own* Windows fonts and cursors into your home folder for a pixel-identical look.

## Gallery

| Start | Search |
|---|---|
| ![Start: Pinned, Recommended and All apps](docs/images/theme-dark-start.png) | ![Search flyout](docs/images/theme-dark-search.png) |

| File Explorer: Home | File Explorer: This PC |
|---|---|
| ![Explorer Home with Quick access and Recent files](docs/images/explorer-home.png) | ![Explorer This PC with drive usage bars](docs/images/explorer-thispc.png) |

**Taskbar: weather and the four Search options** (*Settings › Personalization › Taskbar*)

![Taskbar with the weather on the left and each Search option](docs/images/taskbar-weather-search.png)

| Quick settings | Notifications and calendar | Volume flyout |
|---|---|---|
| ![Quick settings](docs/images/theme-dark-quick.png) | ![Notification centre and calendar cards](docs/images/notifications-calendar-empty.png) | ![Volume flyout](docs/images/osd-volume.png) |

| Settings | Task Manager |
|---|---|
| ![Fenestra Settings, Home page](apps/fenestra-settings/screenshots/home-dark.png) | ![Fenestra Task Manager, Performance](apps/fenestra-taskmgr/screenshots/performance-cpu.png) |

| Notepad | Paint |
|---|---|
| ![Fenestra Notepad with tabs, dark mode](apps/fenestra-notepad/screenshots/tabs-dark.png) | ![Fenestra Paint with a drawing, light mode](apps/fenestra-paint/screenshots/demo-light.png) |
| ![Fenestra Notepad Find and Replace, light mode](apps/fenestra-notepad/screenshots/replace-light.png) | ![Fenestra Paint View menu, dark mode](apps/fenestra-paint/screenshots/menu-view-dark.png) |

| Ctrl+Alt+Del | Sign-in options (Fenestra Hello) |
|---|---|
| ![Ctrl+Alt+Del security screen](docs/images/ctrl-alt-del.png) | ![Face sign-in setup](apps/fenestra-settings/screenshots/hello-face-2-dark.png) |

**Light and dark mode, any accent colour.** *Settings › Personalization › Colors* offers the
familiar 48-colour accent palette (plus a custom colour), and the whole desktop follows it live.

| Light | Dark | Accent palette |
|---|---|---|
| ![Start in light mode](docs/images/theme-light-start.png) | ![Start in dark mode](docs/images/theme-dark-start.png) | ![Accent colour grid](docs/images/accent-settings-colors-dark.png) |

**First-boot setup (OOBE)**

| Region | Account | Privacy | Finale |
|---|---|---|---|
| ![OOBE region page](apps/fenestra-oobe/screenshots/region.png) | ![OOBE account page](apps/fenestra-oobe/screenshots/account-name.png) | ![OOBE privacy page](apps/fenestra-oobe/screenshots/privacy.png) | ![OOBE finale](apps/fenestra-oobe/screenshots/finale-1.png) |

Screenshots use demo data only (user "Alex Morgan", device "FENESTRA-PC").

## What you get

| Area | Windows 11 behaviour reproduced |
|---|---|
| **Taskbar** | Centred icons, weather at the left end, Search as icon, icon and label, or search box (or hidden), acrylic bar, press-shrink animation, live window previews, Show desktop corner, Windows tray layout (overflow ^, language, Wi‑Fi/volume/battery, clock + date) |
| **Start** | Search box, Pinned, Recommended, *All* apps by category / grid / list, account and power flyouts, Windows motion and a luminosity acrylic effect |
| **Search** | Separate Search flyout: recent searches, Top apps, filter chips (All · Web · Apps · Documents · Settings · Folders · Photos), *Best match* and a preview pane |
| **Quick settings, OSD** | Windows quick settings tiles, media flyout, volume/brightness flyout |
| **Notifications and calendar** | Two independent cards: notification centre with Clear all and Do not disturb, calendar with Focus timer; Windows toast banners |
| **Ctrl+Alt+Del** | Security screen with Lock, Switch user, Sign out, Change a password, Task Manager and power menu |
| **File Explorer** | Files (Nautilus) with Explorer Home (Quick access, Recent/Favorites/Shared), Gallery, This PC with drive bars, sidebar with pins, command bar (New, Sort, View, Filter, Details), per-folder views, Windows context menus, **New ▸** templates |
| **Window buttons** | Minimize, maximize/restore and close on every window, Windows 11 metrics and glyphs: GTK 3/4 and libadwaita apps, X11 apps (also Spotify), Qt apps (via XWayland), Flatpak apps |
| **Desktop** | Desktop icons with the same right-click menu and folder icons |
| **Lock and sign-in** | Windows lock-screen clock, Spotlight-style backgrounds, single-account sign-in screen, Fenestra Hello (face/fingerprint) |
| **Consent prompts** | Administrator prompts styled like User Account Control (password always required) |
| **Settings** | Fenestra Settings replaces GNOME Settings (also for `gnome-control-center <panel>`): System, Bluetooth & devices, Network, Personalization, Apps, Accounts, Time & language, Gaming, Accessibility, Privacy, Update, plus a *Fenestra* section for GNOME-specific options. *System › Recovery › Reset this PC* resets Fenestra without reinstalling (*Keep my files* or *Remove everything*; it runs at the next boot, before the sign-in screen). *Fenestra Update* lists Fedora's updates and, from GitHub, every newer Fenestra build with its changes; installing one rebuilds and installs Fenestra in place |
| **Task Manager** | Fenestra Task Manager (Ctrl+Shift+Esc): Processes, Performance, App history, Startup apps, Users, Details, Services |
| **Notepad** | Fenestra Notepad: tabs in the title bar, File / Edit / View menus, Find and Replace, Go to line, zoom, line endings and encodings in the status bar, Markdown preview, sessions that keep unsaved tabs, light and dark |
| **Paint** | Fenestra Paint: the familiar toolbar (selection, image, tools, brushes, shapes, colours), layers, text tool, resize and skew, rotate and flip, zoom, light and dark |
| **First boot** | Windows-style OOBE: region, keyboard, network, device name, account, automatic sign-in, privacy, “Hi… this might take a few minutes” |
| **Installer** | Anaconda with the Fenestra name, artwork and boot menu (no Fedora logos); account screens hidden because the OOBE creates the user |
| **Look** | Fenestra-Light / Fenestra-Dark GTK themes, Win11 icon theme, Bibata Original cursors, Selawik (Segoe UI metrics) and Cascadia fonts, original wallpapers |

## Install

1. Download `Fenestra-43-netinst-x86_64.iso` from the [Releases](../../releases), or the
   `Fenestra-43-netinst-x86_64` artifact of the latest successful [CI run](../../actions), or
   build it (below).
2. Write it to a USB stick (Fedora Media Writer, Ventoy, `dd` …) and boot it (UEFI or BIOS).
3. Pick the disk in the installer; everything else is preconfigured. Packages come from the Fedora
   mirrors, so an internet connection is required.
4. After the reboot the Windows-style setup asks for region, keyboard, network, device name and
   your account, then signs you in.

## Build it yourself

Requirements: Fedora (any recent version), `podman`, `python3-pillow`, `python3-numpy`,
ImageMagick, `librsvg2-tools`, `cpio`, `git`, `curl`. No root needed.

```bash
git clone https://github.com/miguelcoxcaballero/fenestra-os && cd fenestra-os
```

```bash
curl -L --create-dirs -o ~/.local/share/fenestra-vm/Fedora-Everything-netinst-x86_64-43-1.6.iso \
  https://dl.fedoraproject.org/pub/fedora/linux/releases/43/Everything/x86_64/iso/Fedora-Everything-netinst-x86_64-43-1.6.iso
```

```bash
bash build/build-iso.sh
```

The ISO is written to `build/out/Fenestra-43-netinst-x86_64.iso`.

- `bash build/build-overlay.sh` builds only the file tree Fenestra adds on top of Fedora.
- `python3 tools/generate-assets.py` and `python3 tools/build-gtk-themes.py` regenerate the open
  assets and the GTK themes (both outputs are committed).
- Rootless builds cannot rebuild the EFI boot image, so they boot in BIOS mode only. The CI build
  (`.github/workflows/build-iso.yml`, runs as root) produces a UEFI-ready ISO.

## Test it

**Virtual machine.** `--test` builds an unattended ISO that **wipes the disk** (VMs only) and
allows root SSH with `~/.local/share/fenestra-vm/test_key`:

```bash
bash build/build-iso.sh --test
```

```bash
bash tests/vm/vm.sh install build/out/Fenestra-43-test-x86_64.iso
```

```bash
bash tests/vm/vm.sh boot
```

`tests/vm/vm.sh shot NAME`, `key`, `type`, `click X Y` and `ssh CMD` drive the VM; QMP screenshots
go to `tests/vm/shots/`. It uses KVM when available and falls back to (slow) TCG.
`FENESTRA_MIRROR=http://mirrors.kernel.org/fedora` pins one HTTP mirror for networks that
intercept TLS. `tests/vm/win11.sh` runs a Windows 11 Enterprise Evaluation VM for reference shots.

**Headless shell (no VM).** In a Fedora 43 container with the overlay copied to `/`,
`tests/shell/shell.sh start | shot | click | key | eval | run` runs GNOME Shell headless with every
Fenestra extension, for quick screenshots and JS error checks. The apps have their own headless
screenshot modes (see each app's README).

## Repository layout

```
apps/fenestra-settings/   Windows-11-style Settings app (Python + GTK 4)
apps/fenestra-taskmgr/    Windows-11-style Task Manager (Python + GTK 4)
apps/fenestra-oobe/       Windows-11-style first-boot setup (replaces GNOME Initial Setup)
apps/fenestra-notepad/    Notepad (Python + GTK 4 + GtkSourceView)
apps/fenestra-paint/      Paint (Python + GTK 4 + cairo)
desktop/extensions/       GNOME Shell extensions (Fenestra's own + modified ArcMenu/DING + upstream ones)
desktop/nautilus/         Explorer layer for Files: nautilus-python extensions + UI overlay
desktop/dconf/            System-wide defaults (/etc/dconf/db/local.d, gdm.d)
desktop/themes/           Fenestra-Light and Fenestra-Dark GTK themes
desktop/skel/, systemd/   New-user files; systemd units and drop-ins
assets/generated/         Open assets: battery, power, menu icons, folders, wallpapers, logo
kickstart/                Anaconda kickstarts (installer + unattended test)
build/                    build-overlay.sh, build-iso.sh, installer branding
tools/                    Asset and theme generators, icon theme builder, Windows asset importer
tests/vm/, tests/shell/   QEMU harness (QMP screenshots/input) and headless GNOME Shell harness
docs/                     Images and the test report
```

## How it fits together

* **Shell**: Dash to Panel (taskbar) + ArcMenu (Start and Search) + `fenestra-tray` (tray, quick
  settings, calendar, OSD, Ctrl+Alt+Del, appearance and accent, toasts) + Blur my Shell, Rounded
  Window Corners, Tiling Assistant (Snap layouts), DING (desktop).
* **First boot**: GDM starts its initial-setup session when no user exists; Fenestra's systemd
  drop-ins run `fenestra-oobe` instead of GNOME Initial Setup, which creates the account and signs
  in automatically.
* **Appearance**: `org.fenestra.desktop` holds the exact accent colour; `fenestra-tray` applies the
  mode and accent to the shell, GTK themes, Dash to Panel and ArcMenu.
* **Assets** are looked up in `~/.local/share/fenestra/assets` first (imported originals) and then
  in `/usr/share/fenestra/assets` (open defaults), so importing never touches system files.
* **Files** keeps the stock Nautilus package: `fenestra-patch-nautilus` derives a copy with
  Explorer sidebar icon names at boot, and `fenestra-nautilus` only uses it (plus the UI overlay)
  when it matches the installed major version; otherwise stock Nautilus runs.
* **Defaults** live in dconf system databases; users can change everything.

## Status

Fenestra is an early community project. The latest test report, with what was verified, how and
the known issues, is in [docs/TESTING.md](docs/TESTING.md).

## Licence

GPL-3.0-or-later for Fenestra's code; bundled components keep their own licences
([THIRD-PARTY.md](THIRD-PARTY.md)).

---

### En español

Fenestra OS es una distribución basada en **Fedora 43** que reproduce Windows 11: barra de tareas
centrada, Inicio, Búsqueda, Explorador de archivos, Configuración, Administrador de tareas,
Ctrl+Alt+Supr y la instalación inicial (OOBE), en modo claro u oscuro y con cualquier color de
acento, todo sobre GNOME 49 y sin archivos de Microsoft. Descarga la ISO, arráncala, elige el disco
y, tras reiniciar, el asistente te pide región, teclado, red, nombre del equipo y tu cuenta. Para
compilarla: `bash build/build-iso.sh` (instrucciones arriba). Si tienes Windows en el mismo equipo,
`fenestra-import-windows-assets` copia tus propias fuentes y cursores para que se vea idéntico.
El estado de las pruebas está en [docs/TESTING.md](docs/TESTING.md).
