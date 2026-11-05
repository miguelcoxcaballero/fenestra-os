# Fenestra test report

Last update: 2026-11-05 (cloud session, branch `claude/fenestra-os-polish-validation-qo5cej`,
based on `main` at `d93a50d`). The OOBE first-boot flow and the Explorer pages are being tested
in parallel by the local session on a KVM VM; their results are reported there.

## Environments

| Environment | What it is good for | Limits |
|---|---|---|
| **Fresh install in a VM** (`tests/vm/vm.sh`, QEMU **TCG**, no `/dev/kvm`, 4 vCPUs) | Kickstart, `%post`, SELinux labels, GDM → initial-setup session, journal | Very slow (the install takes ~2 h); mutter stops presenting frames under TCG (see below), so the desktop cannot be screenshotted there |
| **Headless GNOME Shell** (`tests/shell/shell.sh`) in a Fedora 43 container with `build/out/rootfs` copied to `/` | Every Fenestra extension running in GNOME Shell 49.10, JS errors, screenshots and input | No logind (so no lock screen), no NetworkManager/PipeWire/polkit |
| **App screenshot modes** (Settings `--screenshot --demo-data`, OOBE `--demo --screenshot`, Task Manager demo) in headless mutter | Page layout, light/dark, demo data only | Writes are mocked |
| **CI** (`.github/workflows/build-iso.yml`) | Python syntax, kickstart validation, no-Microsoft-assets check, full UEFI ISO build | Doesn't boot the ISO |

The Windows 11 reference VM (`tests/vm/win11.sh`) was not run in the cloud session (without
KVM a Windows install and OOBE take many hours, and the disk quota doesn't fit both VMs). The
comparisons in the README use the reference captures already in the repository.

## Reproducing

```bash
FENESTRA_MIRROR=http://mirrors.kernel.org/fedora bash build/build-iso.sh --test
```

```bash
bash tests/vm/vm.sh install build/out/Fenestra-43-test-x86_64.iso
```

```bash
bash tests/vm/vm.sh boot
```

```bash
bash tests/vm/vm.sh ssh 'journalctl -b | grep -iE "fenestra|initial-setup|avc"'
```

`FENESTRA_MIRROR` is only needed behind a TLS-intercepting proxy (the installer doesn't trust its
CA); `FENESTRA_SKIP_MKEFIBOOT=1` builds in containers where loop mounts fail.

Headless shell (inside the Fedora container, after `bash build/build-overlay.sh`, copying
`build/out/rootfs` to `/`, `dconf update`, creating a user `alex` and removing
`/run/systemd/seats` so GNOME Shell uses its logind stub):

```bash
tests/shell/shell.sh start
```

```bash
tests/shell/shell.sh click 915 1056 && tests/shell/shell.sh shot start.png
```

## Results

### Fresh install (VM, test ISO)

| Check | Result |
|---|---|
| Unattended install from the test ISO, packages over plain HTTP | **OK** (Anaconda reports "anaconda 43.44 for **Fenestra** 43", so the updates image is applied) |
| `/etc/sysconfig/anaconda` | **OK**: `post_install_tools_disabled = 0` (was `1` with `firstboot --disable`; the kickstart now says `firstboot --enable`, the same fix as on `main`) |
| GDM starts the `gnome-initial-setup` session on first boot | **OK** (session `c1`, class `greeter`) |
| `gnome-initial-setup.service` runs Fenestra's drop-in | **OK**: Main PID is `/usr/libexec/fenestra-oobe` |
| SELinux label of `/usr/libexec/fenestra-oobe` | **OK**: `bin_t` (after the `%post` `restorecon`); no AVC denials for the OOBE |
| OOBE UI icons | **Fixed**: `accessibility.svg`/`back.svg` were not installed |
| OOBE page visible | **Not verified under TCG**: the window maps (full-screen background colour) but never shows its content, and neither does a second, demo, OOBE window started on the same display. GNOME Shell logs `Invalid sequence for VSYNC frame info` and stops presenting new frames; both processes sit idle. The same OOBE page renders correctly off-screen inside the VM (`--demo --screenshot`, cairo renderer: 35 s at 1920×1080). With `GDK_DEBUG=frames` the OOBE paints exactly three frames (6–12 s each on TCG, cairo renderer) and is then never asked for another; the same happens with `FENESTRA_VM_GPU=VGA` (bochs-drm). The identical live, full-screen OOBE renders correctly in GNOME Shell 49 in the headless harness, so this is the TCG VM, not Fenestra; a KVM VM is needed for the visual first-boot walk-through. |
| OOBE CPU use without a GPU | **Fixed**: the animated background redrew full-screen gradients every frame (300 % CPU on llvmpipe). It now stops after slow frames, and software GL selects the cairo renderer (35 s vs 157 s for a first-page screenshot in the VM) |
| Boot entry title | **Fixed**: GRUB said "Fedora Linux (…) 43 (Workstation Edition)" |

### Headless GNOME Shell

| Check | Result |
|---|---|
| Desktop, centred taskbar, tray, clock | OK |
| Start opens on a new account | **Fixed** (also fixed independently on `main`): with no `recently-used.xbel`, a one-argument `GLib.Error.matches()` threw and the Start layout was never built |
| Start: band above/behind the search box | **Fixed**: removed (top padding and tinted header); section renamed "Recommended" |
| Search home on a new account | **Fixed**: added "Top apps" (was empty apart from "Your recent searches will appear here") |
| Search results with preview pane, filter chips | OK |
| Quick settings, notification centre, calendar | OK (Wi‑Fi/volume tiles need NetworkManager/PipeWire) |
| Taskbar weather (`org.fenestra.desktop taskbar-widgets`) | OK with a city set in `org.gnome.shell.weather locations` (GWeather/met.no): icon, "9°C", "Clear sky"; symbolic icon in light mode. Hiding it without a location or with a left-aligned taskbar is implemented but not tested |
| Taskbar Search (`taskbar-search`: hide / icon / icon-label / box) | OK, all four modes switch live, dark and light |
| Extension errors in the journal | ArcMenu needed `gnome-menus` (now in the package list); `fenestra-spotlight` assumed a screen shield (now optional) |

### Apps (headless mutter)

| Check | Result |
|---|---|
| OOBE unit tests (`tests.test_backends`) | OK |
| OOBE demo flow (`tests.test_flow_demo`) | OK, except where the host has a real user called `alex`: the username derivation then (correctly) proposes `alexrivera` |
| Settings pages in dark and light (`--demo-data`) | OK |
| *System › Recovery › Reset this PC* (`fenestra-reset run`, both modes, on throw-away users in the Fedora 43 container) | OK: *Keep my files* leaves `~/Documents` and restores `~/.config` from `/etc/skel`; *Remove everything* deletes the users and their homes; the request file is consumed first, so it never runs twice. Not yet run on a real boot (polkit, `fenestra-reset.service` before GDM) |
| *Fenestra Update* from GitHub: check | OK against the live repository: an older build lists the commits since it (merge commits left out), a build without a commit id offers the newest one, the newest build reports nothing to install |
| *Fenestra Update* from GitHub: install (`fenestra-update apply`, Fedora 43 container, source tarball of the working tree) | OK: the overlay is rebuilt (`build/build-overlay.sh`) and installed; files dropped since the last update are removed (`/usr` only), `/var` state is kept, running programs keep their open files (new inodes), `fenestra-post-install` runs. Not yet run with pkexec on an installed system |

### Build and packaging

| Check | Result |
|---|---|
| `build/build-overlay.sh` installs Settings, OOBE and Task Manager | OK (`/usr/bin/fenestra-settings`, `/usr/bin/fenestra-taskmgr`, `/usr/libexec/fenestra-oobe`) |
| `gnome-control-center` wrapper and `org.gnome.Settings.desktop` override | OK (installed by `install.sh`, copied to `/usr/local` by the kickstart) |
| `org.fenestra.desktop` schema | OK (`/usr/share/glib-2.0/schemas`, compiled in `%post`) |
| Fenestra-Light / Fenestra-Dark themes | OK (generated by `tools/build-gtk-themes.py`, committed, copied by the overlay) |
| GNOME Shell priority drop-in | OK (`/usr/lib/systemd/user/org.gnome.Shell@wayland.service.d/fenestra-priority.conf`) |
| Ctrl+Shift+Esc → Task Manager | OK (custom keybinding in `10-fenestra-theme`, verified with `gsettings`) |
| Python dependencies of the apps | All in Fedora Workstation (PyGObject, GTK 4, Gst, Rsvg, cairo, Gdm typelib) |
| CI lint (py_compile, ksvalidator, no Microsoft assets) | OK locally |

### Caption buttons (minimize, maximize, close)

Tested in the headless GNOME Shell (with Xwayland) by opening one app of each kind and measuring the title bar:

| App kind | Example | Result |
|---|---|---|
| GTK 4 / libadwaita | Text Editor, Calculator | Three buttons, 46 px wide, full title-bar height, flush with the corner, white 10 px glyphs, 6 % hover, red close with rounded corner |
| Fenestra apps | Settings | Same |
| GTK 3 | gedit | Same (GtkHeaderBar's 6 px spacing cancelled) |
| X11 apps (mutter frames) | xterm | Same glyphs and spacing, 12 px regular title. Spotify uses this path. |
| Qt 6 | PyQt6 window | Through XWayland (`QT_QPA_PLATFORM=xcb;wayland`) the mutter frame gives the same buttons; Qt's own Wayland decoration would draw round Adwaita buttons |
| Firefox | Firefox 145 | Fenestra glyphs, but Firefox spaces the buttons 37 px apart instead of 46 |
| Files (Explorer layer) | Nautilus | Correct buttons, but in narrow windows the close button is pushed past the right edge by the tab strip's minimum width (`.tab-title { min-width: 1024px }`); fine at 1400 px |

Flatpak apps get the same CSS (per-user copy plus a system `flatpak override` for `xdg-config/gtk-*`); not tested.

## Installer branding (legal notes)

Fenestra is a Fedora *remix*: it may say "based on Fedora" but must not use the Fedora logos.

- Installed system: `generic-logos` instead of `fedora-logos`, own `os-release` (`NAME=Fenestra`,
  `ID=fenestra`, `ID_LIKE=fedora`), boot entries retitled.
- Installer: an Anaconda updates image (`build/installer/`) sets the product name in
  `.buildstamp`, replaces the sidebar/top-bar artwork with Fenestra's own and hides the user and
  root spokes. The ISO volume label becomes `Fenestra-43-x86_64` when the EFI image is rebuilt
  (CI); boot menu entries say Fenestra.
- Still Fedora's: the installer's own boot splash and fonts inside `install.img`, and
  `Fedora-Legal-README.txt` (Fedora's licence text, kept on purpose). Replacing the splash
  needs a full lorax build of the installer image with `generic-logos`.

## Known issues

- Not verified end to end in a VM here: the OOBE pages after region, automatic sign-in, the
  first-login privacy step, the desktop after sign-in, lock screen, UAC prompt and the Settings
  actions that change the system (Wi‑Fi, Bluetooth, uninstall, update, rename, time zone). The
  local session's KVM VM covers the OOBE.
- `docs/images/notifications-calendar.png` shows example notifications that name another
  vendor's products; the README uses `notifications-calendar-empty.png` instead.
- `docs/images/theme-dark-explorer.png` shows a scratchpad path in the address bar and a
  Spanish "Galeria" label; the README uses `explorer-home.png` instead.
- Rootless ISO builds are BIOS-only (no `mkefiboot`).
