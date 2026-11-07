# Feasibility: Fenestra Shell on KWin

Every result below was run on Fedora 45 (KWin 6.8.2, Qt 6.11.2, KF 6.31, LayerShellQt 6.8.2,
plasma-wayland-protocols 1.23), in the container of `tests/shell-kwin/Containerfile`. Where a
statement has not been run, it says **not tested** and where it must be checked (VM or laptop).

| Question | Result | Evidence |
|---|---|---|
| KWin as the compositor of its own session, without Plasma | **Yes.** `kwin_wayland` runs without plasmashell, plasma-workspace or any Plasma QML. `--xwayland` starts a rootless Xwayland on demand. | `tests/shell-kwin/session.sh`, check `kwin-start` |
| A Qt 6 client draws the shell with layer-shell surfaces | **Yes.** LayerShellQt from QML (`org.kde.layershell`): wallpaper in `BACKGROUND`, taskbar in `TOP` with a 48 px exclusive zone, flyouts in `TOP` with `margins` and keyboard focus on demand. | checks `shell-ready`, `B11` screenshots |
| Window list and control from a client that is not plasmashell | **Yes, with `org_kde_plasma_window_management`** (protocol version 16 is used; KWin offers 21). KWin only offers it to clients whose `.desktop` lists it in `X-KDE-Wayland-Interfaces` (`shell/data/org.fenestra.Shell.desktop`). Activate, minimize, close and show desktop all work. | checks `window-management`, `B02-*` |
| LibTaskManager instead of the protocol | **Not used.** The C++ library is in `plasma-workspace-libs`, but its QML module only ships with the full `plasma-workspace` (the Plasma session). Using the protocol directly costs about 250 lines (`shell/src/services/windowsmodel.cpp`) and keeps Plasma off the system. | package query (`dnf repoquery`) |
| A KWin script + D-Bus for the window list | **Not needed** (the protocol covers it). Kept as the plan for Snap Layouts and Task View (H6). | — |
| X11 apps | **Yes.** A GTK 3 window under `GDK_BACKEND=x11` appears in the window list and the taskbar. | check `B02-unpinned-app-button` |
| A crash of the shell | **KWin and every window survive.** A new shell process lists the open windows again. `fenestra-shell.service` relaunches it, and after 3 crashes in 2 minutes `fenestra-shell-failed` offers *Try again*, *Sign out* and *Use GNOME next time*. | checks `kwin-survives-shell-crash`, `windows-after-restart`; `systemd-analyze --user verify` on the units |
| Launching apps with focus | **KIO `ApplicationLauncherJob`**, which requests an xdg-activation token so KWin focuses the new window. App database: KService (KSycoca; changes come by inotify). | check `B02-launch-from-pinned` |
| Taskbar weather without GNOME Shell | **Yes, with libgweather 4** and the location saved by the Weather app (`org.gnome.Weather locations`), as GNOME Shell's WeatherClient did. **Not tested with real data**: the container has no network location. Check in the VM. | `shell/src/services/weather.cpp` |
| Live window thumbnails (B03) | **Yes.** The shell asks KWin for a window screencast (`zkde_screencast_unstable_v1.stream_window` by the window's uuid, listed in `X-KDE-Wayland-Interfaces`) and draws the PipeWire stream with KPipeWire's `PipeWireSourceItem` (`shell/src/services/screencast.*`, `shell/qml/taskbar/LiveThumbnail.qml`), as Plasma's task manager does. Needs KWin's OpenGL compositing and a PipeWire daemon (and wireplumber to link the stream); without them the preview shows KWin's still pictures (`ScreenShot2.CaptureWindow`), refreshed every second. | `tests/shell-kwin/popups-gl.sh` with `IMAGE` carrying pipewire |
| Screen lock | **Not tested.** Options: kscreenlocker with a Fenestra greeter theme, or our own `ext-session-lock-v1` client. kscreenlocker is the safer default because it keeps the screen locked if the shell crashes and is maintained by KDE. To decide in H8. | — |
| Notifications server | **Not tested.** Planned: `org.freedesktop.Notifications` inside the shell (H4). | — |
| Global shortcuts, OSD | **Not tested.** kglobalaccel is installed with KWin. KWin binds Ctrl+Alt+Del to log out by default, so the shipped `kglobalshortcutsrc` must free it for the security screen. | INVENTORY.md §7 |
| Power | Fedora 45 ships **power-profiles-daemon**, plus UPower and logind. powerdevil is not needed and would duplicate them. **Not tested**: idle → dim → lock → suspend via `ext-idle-notify-v1`. | `rpm -q` |
| Portals | **Not settled.** For `XDG_CURRENT_DESKTOP=Fenestra` there is no portals config yet. Plan: `fenestra-portals.conf` with `gtk` for the file chooser (GTK apps keep their look) and `kde` for screenshots, screencast and inhibit (they need KWin). To test in H7. | APPS.md, integration points |
| polkit agent | **Needed:** GNOME Shell was the agent. Without one, every `pkexec` and every interactive D-Bus authorization from Settings fails. Use `polkit-kde-agent-1` first, then a Fenestra-styled one (Q06). | APPS.md, biggest risks |
| Login manager | **GDM stays.** It lists `/usr/share/wayland-sessions/fenestra.desktop` next to GNOME. SDDM is not installed. | `session/` |

## KWin problems found (upstream bugs, to report)

Both happen only when KWin has **no render device**, so it falls back to QPainter compositing.
Containers and CI hit this; a VM or a machine without a GPU still has llvmpipe through DRM, so
KWin keeps OpenGL and its effects there.

1. `ScreenShot2.CaptureScreen` crashes in `KWin::RenderDevice::eglContext()`. The bench
   therefore composes the shell's own surfaces (`tests/shell-kwin/compose.py`, test probe `Grab`)
   instead of taking a screenshot.
2. Committing an xdg-activation token crashes in `KWin::EffectsHandler::startupAdded()`: there is
   no effects handler. In the bench only, the shell launches apps with `gio launch`, which sends
   no token (`FENESTRA_SHELL_NO_ACTIVATION=1`, test mode only).

Both backtraces were taken with gdb in the lab image (KWin 6.8.2-3.fc45).

## What the container cannot test

These need a VM with KVM or the laptop:
- OpenGL effects: blur and acrylic, rounded corners, live thumbnails.
- Real screenshots (spectacle).
- Real input devices and multi-monitor hardware.
- Suspend.
- Battery, cameras and the fingerprint reader.
