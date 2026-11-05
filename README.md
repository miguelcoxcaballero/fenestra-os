<p align="center">
  <img src="assets/generated/branding/fenestra-logo-256.png" width="96" alt="Fenestra logo">
</p>

<h1 align="center">Fenestra</h1>

<p align="center"><b>A Fedora-based Linux distribution that looks and works like Windows 11.</b><br>
Start menu, taskbar, Search, File Explorer, Settings and first-boot setup — rebuilt on GNOME, open source.</p>

---

Fenestra (Latin for *window*) is a **Fedora 43 remix**. It installs Fedora Workstation and then
layers a complete Windows-11-style desktop on top of GNOME 49: no Wine, no theming tricks that break
on update, just GNOME Shell extensions, a patched-in Explorer layer for Files, and two apps written
from scratch — **Fenestra Settings** and the **Fenestra first-boot setup (OOBE)**.

> Fenestra is not affiliated with Microsoft. It contains no Microsoft files; see
> [THIRD-PARTY.md](THIRD-PARTY.md). If you dual-boot, `fenestra-import-windows-assets` can copy *your
> own* Windows fonts and cursors for a pixel-identical look.

## What you get

| Area | Windows 11 behaviour reproduced |
|---|---|
| **Taskbar** | Centered icons, acrylic dark bar, press-shrink animation, live window previews with blur, Show desktop corner, Windows tray layout (overflow ^, language, Wi-Fi/volume/battery, clock + date) |
| **Start** | Pinned grid, Recommended/Recent files, *All* apps by category, account + power flyouts, Windows motion (slides out from behind the taskbar) and a real **luminosity acrylic** effect |
| **Search** | Separate Search flyout: recent searches, filter chips (All · Apps · Documents · Settings · Folders · Photos · Web), *Best match* column and a preview pane with Open/Options/Details |
| **Quick settings / calendar** | Windows-style quick settings tiles, media flyout, calendar flyout with Focus timer |
| **Notifications** | Windows toast banners, Snipping-Tool-style screenshot toast |
| **File Explorer** | Files (Nautilus) with Explorer sidebar (Home, Gallery, This PC…), view modes (Extra large icons … Details/Tiles/Content), **New ▸** context menu with document templates, empty/full folder icons |
| **Desktop** | Desktop icons with the same right-click menu and folder icons |
| **Lock & login** | Windows lock-screen clock, Spotlight-style backgrounds, single-account login screen, face-unlock animation |
| **Consent prompts** | Administrator prompts styled like User Account Control (password always required) |
| **Settings** | New Settings app modelled on Windows 11 Settings (System, Bluetooth & devices, Network, Personalization, Apps, Accounts, Time & language, Accessibility, Privacy, Update) |
| **First boot** | New Windows-11-style OOBE: region, keyboard, network, device name, account, privacy, “Hi… this might take a few minutes” |
| **Look** | Fluent-based dark GTK theme, Win11 icon theme, Bibata Original cursors, Selawik (Segoe UI metrics) and Cascadia fonts, original Fenestra wallpapers |

## Install

1. Download `Fenestra-43-netinst-x86_64.iso` from the [Releases](../../releases) (or build it, below).
2. Write it to a USB stick (`dd`, Fedora Media Writer, Ventoy…) and boot it.
3. Pick the disk in the installer; everything else is preconfigured. Packages are downloaded from
   the Fedora mirrors, so an internet connection is required.
4. After the reboot, the Windows-style setup asks for region, keyboard, network, device name and
   your account.

Dual boot with Windows? After the first login, run `fenestra-import-windows-assets` (or accept the
offer in the setup) to use your own Segoe UI fonts, cursors, battery glyphs and folder icons.

## Build it yourself

Requirements: Fedora (any recent version), `podman`, `python3-pillow`, `python3-numpy`, ImageMagick, `git`, `curl`. No root.

```bash
git clone https://github.com/miguelcoxcaballero/fenestra-os && cd fenestra-os
curl -LO --output-dir ~/.local/share/fenestra-vm \
  https://dl.fedoraproject.org/pub/fedora/linux/releases/43/Everything/x86_64/iso/Fedora-Everything-netinst-x86_64-43-1.6.iso
python3 tools/generate-assets.py      # open replacement assets (already committed)
bash build/build-iso.sh               # -> build/out/Fenestra-43-netinst-x86_64.iso
```

`build/build-iso.sh --test` produces an unattended ISO that **wipes the disk** — only for VMs.
Rootless builds cannot rebuild the EFI boot image, so they boot the kickstart in BIOS mode; the CI
build (`.github/workflows/build-iso.yml`, runs as root) produces a UEFI-ready ISO.

## Test in a virtual machine

```bash
bash build/build-iso.sh --test
bash tests/vm/vm.sh install build/out/Fenestra-43-test-x86_64.iso   # unattended install, powers off
bash tests/vm/vm.sh boot                                             # first boot -> OOBE
bash tests/vm/vm.sh shot oobe-1                                      # screenshot (QMP) -> tests/vm/shots/
```

`tests/vm/vm.sh` also sends keys, text and clicks so the whole first-boot flow can be scripted.

## Repository layout

```
apps/fenestra-settings/   Windows-11-style Settings app (Python + GTK 4)
apps/fenestra-oobe/       Windows-11-style first-boot setup (replaces GNOME Initial Setup)
desktop/extensions/       GNOME Shell extensions (Fenestra's own + modified ArcMenu/DING + upstream ones)
desktop/nautilus/         Explorer layer for Files: nautilus-python extensions + UI overlay
desktop/dconf/            System-wide defaults (/etc/dconf/db/local.d, gdm.d)
desktop/themes/           Fenestra-Dark GTK theme
desktop/skel/             New-user files (GTK overrides, "New" templates)
desktop/libexec, systemd  Files patcher/launcher and its boot service
assets/generated/         Open assets: battery, power, menu icons, folders, Hello animation, wallpapers, logo
kickstart/                Anaconda kickstarts (installer + unattended test)
build/                    build-overlay.sh (root filesystem overlay), build-iso.sh (mkksiso)
tools/                    Asset generator, icon theme builder, dconf exporter, Windows asset importer
tests/vm/                 QEMU/KVM harness with QMP screenshots and input
docs/                     Architecture notes, images and test reports
extras/                   Optional hardware-specific bits (not installed by default)
```

## How it fits together

* **Shell**: Dash to Panel (taskbar) + ArcMenu (Start and Search) + `fenestra-tray` (tray, quick
  settings, calendar, previews, press animation, toasts) + Blur my Shell, Rounded Window Corners,
  Tiling Assistant (Snap layouts), DING (desktop).
* **Assets** are looked up in `~/.local/share/fenestra/assets` first (imported originals) and then
  in `/usr/share/fenestra/assets` (open defaults), so importing never touches system files.
* **Files** keeps the stock Nautilus package: `fenestra-patch-nautilus` derives a copy with
  Explorer sidebar icon names at boot, and `fenestra-nautilus` only uses it (plus the UI overlay)
  when it matches the installed major version — otherwise stock Nautilus runs.
* **Defaults** live in dconf system databases; users can change everything.

## Status

Fenestra is an early, community project. See [docs/TESTING.md](docs/TESTING.md) for the latest VM
test report and known issues.

## Licence

GPL-3.0-or-later for Fenestra's code; bundled components keep their own licences
([THIRD-PARTY.md](THIRD-PARTY.md)).

---

### En español

Fenestra es una distribución basada en **Fedora 43** que reproduce Windows 11: barra de tareas,
menú Inicio, Búsqueda, Explorador de archivos, Configuración y la instalación inicial (OOBE), todo
sobre GNOME y sin archivos de Microsoft. Si tienes Windows en el mismo equipo,
`fenestra-import-windows-assets` copia tus propias fuentes Segoe UI y cursores para que se vea
idéntico.
