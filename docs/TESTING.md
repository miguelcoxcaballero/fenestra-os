# Fenestra test report

Date: 2026-11-05 · Branch: `claude/fenestra-os-polish-validation-qo5cej`

## Environment

- Build host: an Ubuntu 24.04 container with **no `/dev/kvm`**. Fedora 43 tools (lorax/mkksiso,
  GNOME Shell 49.10, mutter 49.8, GTK 4.20, Nautilus 49.6) ran in a privileged
  `registry.fedoraproject.org/fedora:43` container.
- VM: `tests/vm/vm.sh` with QEMU under multi-threaded **TCG** (4 vCPUs, 6 GiB). The VM's
  HTTPS goes through a TLS-intercepting proxy, so the test ISO uses one plain-HTTP mirror
  (`FENESTRA_MIRROR=http://mirrors.kernel.org/fedora`).
- The Windows 11 reference VM (`tests/vm/win11.sh`) was **not** run in this session: without
  KVM a Windows 11 install and OOBE take many hours, and the 7 GB ISO plus its disk don't fit the
  disk quota next to the Fedora VM. The OOBE comparisons use the reference captures already in
  `apps/fenestra-oobe/screenshots/compare-*.png`.

## How to reproduce

```bash
FENESTRA_MIRROR=http://mirrors.kernel.org/fedora bash build/build-iso.sh --test
```

```bash
bash tests/vm/vm.sh install build/out/Fenestra-43-test-x86_64.iso
```

```bash
bash tests/vm/vm.sh boot
```

Headless desktop checks (in a Fedora 43 container with `build/out/rootfs` copied to `/`, `dconf
update`, a user `alex` and `/run/systemd/seats` absent so GNOME Shell uses its logind stub):

```bash
tests/shell/shell.sh start
```

```bash
tests/shell/shell.sh click 915 1056 && tests/shell/shell.sh shot start.png
```

## Results

<!-- VM-RESULTS -->

### Headless GNOME Shell (all Fenestra extensions enabled)

| Check | Result |
|---|---|
| Desktop, centred taskbar (Start, Search, Files), tray, clock | OK |
| Start opens | **Fixed**: failed on every new account (see below) |
| Start layout: Pinned, Recommended, All (Category) | OK; "Recent" renamed "Recommended"; the strip/band above the search box was removed |
| Search: recent searches, chips, Best match, preview pane | OK; selected chip used a green accent → blue; added "Top apps" to the empty home |
| Quick settings | OK (Wi‑Fi/volume tiles need NetworkManager/PipeWire, absent in the container) |
| Notification centre + calendar + Focus | OK; strings were hard-coded Spanish → English (Spanish kept as translation) |
| Files: Explorer sidebar, command bar, tabs | **Fixed**: Spanish labels, 5 missing icons, red tab close, sidebar missing Gallery/Desktop |
| Settings (`--demo-data`), dark and light | OK |
| OOBE unit tests + demo flow (`tests.test_backends`, `tests.test_flow_demo`) | OK (17 tests) after fixing the flow test |

## Bugs fixed in this round

1. **OOBE never started on first boot.** The kickstart had `firstboot --disable`. Anaconda then
   writes `post_install_tools_disabled = 1` to `/etc/sysconfig/anaconda`, and GDM skips its
   initial-setup session when that key is set, so GDM showed the plain "Username" login. The
   directive was removed, Anaconda's own `initial-setup` is excluded, and `%post` resets the key.
   `%post` also runs `restorecon` over the unpacked overlay so the confined session can execute
   `/usr/libexec/fenestra-oobe`.
2. **Start never opened on a new account.** `recentFilesManager.js` called
   `GLib.Error.matches()` with one argument when `recently-used.xbel` did not exist yet. The
   `TypeError` broke the Start layout, so clicking Start did nothing until a file had been opened.
3. **Personal accent colour.** The tray, lock screen, UAC dialog, Search, Dash to Panel and the
   GTK theme hard-coded a sage-green accent taken from one person's Windows setup. They now use the
   default Windows 11 blue (shell `#4cc2ff` with black text on it; GTK `#0078d4` family).
4. **Spanish strings in an English session**: the notification centre and the Files command bar,
   search box and tooltips.
5. **Files icons**: `win11-explorer-*` icons were referenced but never generated; the tab close
   button rendered as a red circle.
6. **ArcMenu dependency**: `gnome-menus` (GMenu typelib) is now in the package list.
7. **Installer branding**: an Anaconda updates image sets the product name to Fenestra, replaces
   the Fedora sidebar/top-bar logos with Fenestra artwork and hides the user/root spokes.

## Known issues

- The Windows 11 reference VM was not re-run here (see Environment), so desktop and Settings
  were checked against Windows 11 25H2 behaviour, not against fresh side-by-side captures.
- Anaconda's boot splash and some text in the installer environment still come from Fedora's
  installer image. Rebranding it fully needs a rebuilt `install.img` (lorax), not just
  `mkksiso`.
- Rootless ISO builds are BIOS-only (no `mkefiboot`); the CI build is UEFI.
- The Files "Home" page is a folder listing, not Explorer's Quick access/Favorites/Recent view.
- "This PC" has no sidebar entry (Nautilus 49 has no `computer:///`).
