# Fenestra apps in the KWin session

Status: audit for the `feature/fenestra-shell-kwin` branch. Fenestra Settings items 1, 4, 5 and 6
of the backend split (§9) are implemented; see "Implementation status" at the end of §9. Nothing
else here is implemented yet.

In the new session (`session/libexec/fenestra-session:6` exports
`XDG_CURRENT_DESKTOP=Fenestra`), KWin 6.8 is the compositor and Fenestra Shell (Qt,
`shell/`) draws the taskbar, Start, notifications, quick settings and desktop. GNOME Shell,
Mutter, gnome-session and gnome-settings-daemon (gsd-*) **do not run**. GTK apps,
NetworkManager, BlueZ, PipeWire, UPower, power-profiles-daemon, logind, AccountsService,
polkit and xdg-desktop-portal stay.

gsettings/dconf still work as a store, but **no running GNOME component reads
`org.gnome.*` keys any more**. A few keys are still read by GTK/GLib or by an app itself;
those are listed as "still read by ..." below. Every other GNOME key becomes a control that
saves a value and has no effect. Under KWin those controls must be **hidden** (or moved to a
Fenestra backend), not left visible.

Conventions:

* `file:line` paths are relative to the repository root. The Settings package is
  `apps/fenestra-settings/fenestra_settings/`, shortened to `fs/` in this document.
* **(verify)** marks an equivalent that has not been tested on KWin 6.8 / Fedora 43 yet.
* "shell.conf" means `~/.config/fenestra/shell.conf`. While this audit was being written,
  uncommitted shell work added `shell/src/core/shellsettings.{h,cpp}`. It reads
  `Taskbar/Alignment`, `Taskbar/SearchMode`, `Taskbar/Weather`, `Taskbar/Pinned`,
  `Appearance/ColorScheme`, `Appearance/Accent` and `Appearance/Wallpaper`
  (`shellsettings.cpp:55-66`) and reloads when the file changes (`QFileSystemWatcher`,
  `shellsettings.cpp:37-50`). Settings can therefore write the file atomically and needs no
  D-Bus call for these keys. Every other shell.conf key named below is a **proposal** that
  the shell does not read yet. Check these line numbers again once that work is committed.

How Settings builds its controls matters here. `gsetting_toggle()` and
`gsetting_dropdown()` (`fs/pages/common.py:239-266`) return `None` only when the **schema
or key is missing**. Under KWin the GNOME schemas are still installed (gsettings-desktop-schemas,
gnome-settings-daemon, mutter and gnome-shell schemas stay on disk), so **every GNOME
control still shows up and still writes values**. The existing "hide when unavailable"
logic does not protect us. Hiding has to be decided by the session (see the backend split
at the end).

---

## 1. Fenestra Settings (`apps/fenestra-settings`)

A GTK 4 Fluent-style settings app (Python, no libadwaita). It replaces GNOME Settings:
`fs/util.py:122-150` sends `gnome-control-center` launches to the real binary, and
`apps/fenestra-settings/bin/gnome-control-center` redirects panel names to Fenestra pages.

### 1.1 Pages and subpages

Registry: `fs/pages/base.py:10-19` (`PAGES`, `NAV_ORDER`). Page ids with their files:

| Top level (NAV_ORDER) | File | Subpages (`parent=`) |
|---|---|---|
| `home` | `pages/home.py:18` | none |
| `system` | `pages/system.py:11` | `display` (`display.py:22`), `sound` (`sound.py:18`), `notifications` and `focus` (`notifications.py:26,94`), `power` (`power.py:34`), `storage` (`storage.py:19`), `nearby`, `multitasking`, `troubleshoot`, `recovery`, `projecting`, `clipboard` (`system_misc.py:23,48,103,133,211,230`), `about` (`about.py:40`) |
| `devices` | `pages/devices.py:90` | `bt-devices` (156), `mouse` (204), `touchpad` (246), `cameras` (291), `autoplay` (315) |
| `network` | `pages/network.py:26` | `wifi` (120), `ethernet` (230), `proxy` (267) |
| `personalization` | `pages/personalization.py:94` | `background` (135), `colors` (244), `themes` (363), `lockscreen` (409), `start` (488), `taskbar` (612), `fonts` (713) |
| `apps` | `pages/apps.py:22` | `installed` (45), `defaultapps` (182), `startup` (232) |
| `accounts` | `pages/accounts.py:15` | `yourinfo` (48), `signin` (139), `otherusers` (296) |
| `time` | `pages/time_language.py:21` | `datetime` (68), `language` (150), `typing` (205) |
| `gaming` | `pages/gaming.py:13` | none |
| `accessibility` | `pages/accessibility.py:23` | `textsize` (54), `visualeffects` (93), `pointer` (120), `magnifier` (149), `contrast` (172), `narrator` (190), `a11y-audio` (211), `a11y-keyboard` (231) |
| `privacy` | `pages/privacy.py:18` | `general` (67), `location` (117), `camera` (131), `microphone` (144), `diagnostics` (157), `screenlock` (197) |
| `update` | `pages/update.py:28` | `update-advanced` (362), `update-history` (388) |
| `fenestra` | `pages/fenestra.py:35` | `fx-workspaces` (71), `fx-windows` (102), `fx-desktop-icons` (150), `fx-extensions` (181), `fx-search` (226), `fx-online-accounts` (291), `fx-sharing` (334), `fx-shortcuts` (415), `fx-hardware` (493) |

Other page files: `pages/common.py` (gsetting widgets, thumbnails), `pages/base.py`
(registry, `nav_row`, `ext_row`), `pages/__init__.py` (imports all pages).

Backends in `fs/backends/`: `accounts.py` (AccountsService), `apps.py` (installed apps,
default handlers, autostart), `audio.py` (wpctl), `bluetooth.py` (BlueZ / bluetoothctl),
`demo.py` (sample data), `display.py` (**Mutter DisplayConfig**), `fenestra_update.py`,
`hello.py` (fprintd, howdy), `linux.py` (**Shell extensions, GOA, gnome-remote-desktop,
gnome-user-share, search providers**, printers, tablets, colord), `network.py` (nmcli +
**gsd-rfkill**), `packages.py` (PackageKit/dnf/flatpak), `power.py` (UPower, PPD,
**gsd-power / Mutter backlight**), `release.py`, `storage.py`, `system_info.py`
(hostnamed + **background key**), `timedate.py` (timedated, localed).

Other modules: `app.py` (CLI, `ALIASES` for gnome-control-center panel names at
`app.py:21-35`), `theme.py`, `search.py` (indexes **every** page in `PAGES`,
`search.py:41`), `nav.py`, `window.py`, `widgets.py`, `hello_wizard.py`, `util.py`.

### 1.2 GSettings keys used, with their KWin-session equivalent

Legend for the "Under KWin" column:
**read** = still read by GTK/GLib or by the app itself, keep the key (it may need a mirror);
**dead** = nobody reads it, so hide the control or move it to a Fenestra backend.

#### org.gnome.desktop.interface (`IFACE`)

| Key | Where | Under KWin | Equivalent |
|---|---|---|---|
| `color-scheme` | `theme.py:176,190`; `home.py:103,110`; `personalization.py:121,256-259` | read (GTK/libadwaita through the Settings portal, our own apps) | Fenestra Shell setting (shell.conf `Appearance/ColorScheme` (already read)) **plus** a mirror to this key, so GTK apps keep following it. The Settings portal backend must be `gtk` or `gnome` (see §8.5). GTK 4.20 apps also take `gtk-interface-color-scheme` from that portal. |
| `accent-color` | `theme.py:177,196`; `personalization.py:264,318` | read (libadwaita through the portal; our apps) | shell.conf `Appearance/Accent` (already read) + mirror. Whether `xdg-desktop-portal-gtk` exports `accent-color` needs checking **(verify)**. |
| `gtk-theme`, `icon-theme`, `cursor-theme` | `personalization.py:377-393` | read by GTK | Mirror. The cursor must also go to `kcminputrc [Mouse] cursorTheme`, because KWin draws the cursor. Qt shell icons come from `kdeglobals [Icons] Theme` or shell.conf **(verify)**. The `gtk-theme` value is the generated `*-AccentA/B` wrapper written by `fenestra-tray` (see §1.4). |
| `cursor-size` | `accessibility.py:131-136` | read by GTK | Also `kcminputrc [Mouse] cursorSize`. |
| `text-scaling-factor` | `accessibility.py:72-75` | read by GTK | Fenestra Shell font scale (shell.conf). For Qt/KWin decorations: `kdeglobals` font DPI **(verify)**. |
| `font-name`, `document-font-name`, `monospace-font-name` | `personalization.py:722-735` | read by GTK | Shell font in shell.conf. KWin title bar font is `kdeglobals [WM] activeFont` (only for server-side decorations). |
| `font-antialiasing`, `font-hinting` | `personalization.py:739-749` | read by GTK | none needed for KWin |
| `overlay-scrolling`, `enable-animations` | `accessibility.py:102,107` | read by GTK | Animations also go to KWin: `kdeglobals [KDE] AnimationDurationFactor=0` **(verify)**. |
| `locate-pointer` | `accessibility.py:139` | **dead** (Mutter feature) | KWin "Track Mouse" effect (`kwinrc [Plugins] trackmouseEnabled`), but it is not the same Ctrl gesture **(verify)**, or hide. |
| `enable-hot-corners` | `system_misc.py:68`; `fenestra.py:83` | **dead** (GNOME overview) | `kwinrc [ElectricBorders] TopLeft=` / the shell. The Fenestra default is off (`desktop/dconf/local.d/10-fenestra-theme:14`), so hide it. |
| `clock-format` | `personalization.py:706`; `time_language.py:60,107,121` | read by the GTK file chooser; **dead** for the panel clock | shell.conf `[Clock]` + mirror |
| `clock-show-weekday/-date/-seconds` | `personalization.py:698-701` | **dead** (GNOME top bar / Dash to Panel clock) | shell.conf `[Clock]` |
| `show-battery-percentage` | `power.py:127` | **dead** | shell.conf `[Tray] BatteryPercentage` |

#### org.gnome.desktop.background / .screensaver

| Key | Where | Under KWin | Equivalent |
|---|---|---|---|
| `background picture-uri`, `picture-uri-dark` | `personalization.py:57-58,238`; `system_info.py:224-225` | **dead** | shell.conf `Appearance/Wallpaper` (already read; a separate dark-mode image would be a new key). |
| `background picture-options` | `personalization.py:155-157,187` | **dead** | proposed shell.conf `Appearance/WallpaperFill` (zoom/scaled/stretched/wallpaper/centered/spanned/none). "Solid color" needs a colour key. |
| `screensaver picture-uri` | `personalization.py:419,436,466` | **dead** | Lock screen picture: kscreenlocker greeter wallpaper (`kscreenlockerrc [Greeter][Wallpaper][org.kde.image][General] Image`), or the shell's own lock screen **(verify)** |
| `screensaver lock-enabled` | `privacy.py:206` | **dead** | `kscreenlockerrc [Daemon] Autolock` |
| `screensaver lock-delay` | `privacy.py:212-219` | **dead** | `kscreenlockerrc [Daemon] LockGrace` (seconds) |

#### org.gnome.desktop.session / .settings-daemon.plugins.power

| Key | Where | Under KWin | Equivalent |
|---|---|---|---|
| `session idle-delay` | `power.py:81-87` | **dead** (gsd-power/Mutter blank the screen) | Fenestra Shell idle handling: `ext-idle-notify-v1`, then DPMS off through KWin. Also `kscreenlockerrc [Daemon] Timeout` (minutes) for auto-lock. PowerDevil is not part of the session. |
| `sleep-inactive-ac/battery-timeout` and `-type` | `power.py:88-109` | **dead** (gsd-power) | Shell idle timer → `org.freedesktop.login1.Manager.Suspend` |
| `power-button-action` | `power.py:140-148` | **dead** (gsd-power holds the logind inhibitor) | The shell takes a `handle-power-key` inhibitor and acts itself, or set `HandlePowerKey=` in `logind.conf` (system-wide, root) |
| `power-saver-profile-on-low-battery` | `power.py:133-138` | **dead** (gsd-power) | The shell watches UPower `Percentage` and sets PPD `ActiveProfile=power-saver` |

#### org.gnome.settings-daemon.plugins.color (night light)

`night-light-enabled`, `-temperature`, `-schedule-automatic`, `-schedule-from`, `-schedule-to`
(`display.py:44-70`): **dead** (gsd-color). Equivalent: `kwinrc [NightColor] Active`,
`NightTemperature`, `Mode` (Automatic/Location/Times/Constant), `EveningBeginFixed`,
`MorningBeginFixed`, applied with `org.kde.KWin /KWin reconfigure`. Live state comes from
`org.kde.KWin.NightLight` on `/org/kde/KWin/NightLight` (`available`, `enabled`, `running`,
`currentTemperature`). "Sunset to sunrise" needs a location, which Plasma normally feeds
to KWin and nothing feeds here **(verify)**. Offer "Set hours" only until the shell supplies one.

#### org.gnome.desktop.peripherals.mouse / .touchpad

| Key | Where | KWin `org.kde.KWin.InputDevice` property (per device, `/org/kde/KWin/InputDevice/eventN`) |
|---|---|---|
| mouse `left-handed` | `devices.py:217-221` | `leftHanded` |
| mouse/touchpad `speed` | `devices.py:224,266` | `pointerAcceleration` (-1..1) |
| mouse `accel-profile` | `devices.py:228-230` | `pointerAccelerationProfileFlat` / `...Adaptive` |
| `natural-scroll` | `devices.py:234,282` | `naturalScroll` |
| touchpad `send-events` | `devices.py:260-264` | `enabled` |
| `tap-to-click` | `devices.py:270` | `tapToClick` |
| `disable-while-typing` | `devices.py:274` | `disableWhileTyping` |
| `two-finger-scrolling-enabled` | `devices.py:278` | `scrollTwoFinger` |

All of these are **dead** under KWin. Devices are listed with
`org.kde.KWin.InputDeviceManager.devicesSysNames` on `/org/kde/KWin/InputDevice`.
Values are saved by KWin in `[Libinput][vendor][product][name]` groups. In KWin 6 that is
`kcminputrc`, not `kwinrc` **(verify on 6.8)**. The Fenestra defaults in
`desktop/dconf/local.d/00-fenestra:422-433` (mouse, pointingstick, touchpad) need a KWin
copy as well.

#### org.gnome.desktop.media-handling

`autorun-never` (`devices.py:322`), `automount-open` (`devices.py:328`): **dead**. GNOME
Shell's autorun manager handled both. Equivalent: the shell (UDisks2 signals plus a
notification), or hide the AutoPlay page.

#### org.gnome.desktop.notifications (+ `.application`)

| Key | Where | Under KWin |
|---|---|---|
| `show-banners` (DND) | `notifications.py:39-44,120,135-151` | **dead**. Fenestra Shell `org.freedesktop.Notifications` server, DND state in shell.conf or on the shell's D-Bus |
| `show-in-lock-screen` | `notifications.py:50`; `personalization.py:440` | **dead**. Shell option |
| `application-children` + per-app `org.gnome.desktop.notifications.application` (`enable`, `show-banners`) | `notifications.py:16-21,62-89` | **dead**. GNOME Shell filled `application-children` whenever an app notified. Fenestra's server must keep its own per-app list. The schema can stay the store if the shell reads and writes it. |

#### org.gnome.desktop.privacy / org.gnome.system.location

| Key | Where | Under KWin |
|---|---|---|
| `remember-recent-files`, `recent-files-max-age` | `privacy.py:77-97`; `personalization.py:516` | read by GTK (recent manager). Keep. The shell's Start "recommended" list should honour it too. |
| `remove-old-trash-files`, `remove-old-temp-files`, `old-files-age` | `privacy.py:80-83`; `storage.py:70-80` | **dead** (gsd-housekeeping). Alternative: a user systemd timer, or the shell. Until then hide "Storage Sense". |
| `show-full-name-in-top-bar` | `privacy.py:84-86` | **dead** (GNOME top bar). Shell option or hide. |
| `report-technical-problems` | `privacy.py:166` | read by ABRT's GNOME integration **(verify)**. `abrt-auto-reporting` (`privacy.py` diagnostics page) does not depend on GNOME. |
| `disable-camera`, `disable-microphone` | `privacy.py:131-153` | only read through the portal `Lockdown` backend (`xdg-desktop-portal-gtk`/`-gnome`), so they only affect portal clients. Keep if `Lockdown=gtk` in the portals config **(verify)**. |
| `org.gnome.system.location enabled` | `privacy.py:117-127` | **dead in practice**. GNOME Shell was the GeoClue agent. Without an agent, GeoClue denies apps that are not allow-listed. The shell has to implement `org.freedesktop.GeoClue2.Agent` (or run the GeoClue demo agent) and honour this key. |

#### org.gnome.desktop.a11y.*

| Key | Where | Under KWin |
|---|---|---|
| `a11y.applications screen-magnifier-enabled`, `a11y.magnifier mag-factor` | `accessibility.py:157-166` | **dead**. KWin Zoom effect (`kwinrc [Plugins] zoomEnabled`, `[Effect-zoom]`, effect loaded through `org.kde.KWin /Effects`) **(verify)** |
| `a11y.interface high-contrast` | `accessibility.py:180` | read through the Settings portal (`org.freedesktop.appearance contrast`) by GTK 4/libadwaita **(verify for portal-gtk)**. The shell needs its own high-contrast palette. |
| `a11y.interface show-status-shapes` | `accessibility.py:112` | read by GTK only if the GTK version supports it **(verify)** |
| `a11y.applications screen-reader-enabled` | `accessibility.py:198` | **dead**. GNOME Shell started Orca. The shell must start and stop `orca` when the key changes, and toolkit a11y (`toolkit-accessibility`, AT-SPI) must be on. |
| `a11y.applications screen-keyboard-enabled` | `accessibility.py:241-249` | **dead** (GNOME Shell's keyboard). KWin input method: `kwinrc [Wayland] InputMethod=<maliit .desktop>` plus `org.kde.kwin.VirtualKeyboard` `enabled` **(verify)** |
| `a11y.keyboard stickykeys-enable`, `slowkeys-enable`, `togglekeys-enable` | `accessibility.py:243-249` | **dead** (Mutter/gsd). `kaccessrc [Keyboard] StickyKeys`, `SlowKeys`, `ToggleKeys` (read by KWin 6) **(verify each)** |
| `wm.preferences visual-bell` | `accessibility.py:219` | **dead**. `kaccessrc [Bell] VisibleBell` (KWin system-bell effect) **(verify)** |

#### Window manager, workspaces, Alt+Tab (`org.gnome.mutter`, `.desktop.wm.preferences`, `.shell.app-switcher`)

| Key | Where | KWin equivalent (`kwinrc`, then `org.kde.KWin /KWin reconfigure`) |
|---|---|---|
| `mutter dynamic-workspaces` | `system_misc.py:78`; `fenestra.py:79` | no equivalent (KWin keeps a fixed number of desktops). Hide. |
| `mutter workspaces-only-on-primary` | `system_misc.py:88`; `fenestra.py:81` | no equivalent (KWin desktops cover all outputs). Hide. |
| `mutter edge-tiling` | `system_misc.py:62`; `fenestra.py:85` | `[Windows] ElectricBorderMaximize`, `ElectricBorderTiling` |
| `wm.preferences num-workspaces` | `system_misc.py:84-85`; `fenestra.py:90` | `[Desktops] Number`, or `org.kde.KWin.VirtualDesktopManager` createDesktop/removeDesktop |
| `shell.app-switcher current-workspace-only` | `system_misc.py:92-93`; `fenestra.py:94` | `[TabBox] DesktopMode` (1 = current desktop, 0 = all) |
| `wm.preferences focus-mode` | `fenestra.py:117` | `[Windows] FocusPolicy` (ClickToFocus / FocusFollowsMouse / FocusUnderMouse) |
| `wm.preferences auto-raise` | `fenestra.py:121` | `[Windows] AutoRaise` |
| `action-double/middle/right-click-titlebar` | `fenestra.py:126-131` | `[Windows] TitlebarDoubleClickCommand`, `[MouseBindings] CommandActiveTitlebar2/3`. These only apply to server-side decorations. GTK CSD windows read the GNOME keys themselves through the portal **(verify)**. |
| `wm.preferences button-layout` | `fenestra.py:132` | read by GTK (CSD buttons). For SSD: `[org.kde.kdecoration2] ButtonsOnLeft/ButtonsOnRight` |
| `mutter center-new-windows` | `fenestra.py:136` | `[Windows] Placement=Centered` |
| `mutter attach-modal-dialogs` | `fenestra.py:137` | closest is the KWin "Dialog Parent" effect, which only dims. No real equivalent, so hide. |
| `wm.preferences resize-with-right-button` | `fenestra.py:138` | `[MouseBindings] CommandAll3=Resize` |
| `wm.preferences mouse-button-modifier` | `fenestra.py:142` | `[MouseBindings] CommandAllKey=Meta` / `Alt` |

#### Keyboard shortcuts (`fenestra.py:377-399`, page `fx-shortcuts`)

Schemas `org.gnome.desktop.wm.keybindings`, `org.gnome.shell.keybindings`,
`org.gnome.mutter.keybindings`, `org.gnome.settings-daemon.plugins.media-keys`. All are
**dead**. Equivalent: **kglobalaccel**. In Plasma 6 it runs inside `kwin_wayland`
**(verify that the in-process kglobalaccel is active without Plasma)**. The D-Bus API is
`org.kde.kglobalaccel` `/kglobalaccel`, with components such as `/component/kwin`.

| GNOME key | kglobalaccel action |
|---|---|
| `close`, `minimize`, `toggle-maximized`, `toggle-fullscreen`, `show-desktop` | kwin: `Window Close`, `Window Minimize`, `Window Maximize`, `Window Fullscreen`, `Show Desktop` |
| `switch-applications` / `switch-windows` | kwin: `Walk Through Windows` / `Walk Through Windows of Current Application` (approximate) |
| mutter `toggle-tiled-left/right` | kwin: `Window Quick Tile Left/Right` |
| `switch-to-workspace-left/right`, `move-to-workspace-left/right` | kwin: `Switch One Desktop to the Left/Right`, `Window One Desktop to the Left/Right` |
| shell `toggle-overview` | kwin: `Overview` |
| shell `toggle-message-tray`, `toggle-quick-settings`, `show-screenshot-ui`; wm `panel-run-dialog`; media-keys `home`, `control-center` | Fenestra Shell's own kglobalaccel component (to be created) |
| media-keys `screensaver`, `logout` | ksmserver owns these in Plasma, and ksmserver does not run here. Fenestra Shell registers them and calls `loginctl lock-session` / its logout flow. |
| wm `switch-input-source` | KWin keyboard layout component `Switch to Next Keyboard Layout` **(verify)** |

The Fenestra defaults also bind Ctrl+Shift+Esc to `fenestra-taskmgr` through a gsd custom
keybinding (`desktop/dconf/local.d/10-fenestra-theme:47-54`) and free Ctrl+Alt+Del for the
`fenestra-tray` security screen (`10-fenestra-theme:36-39`). Both have to become kglobalaccel or
shell bindings.

#### Input sources, date and time

| Key | Where | Under KWin |
|---|---|---|
| `input-sources sources`, `per-window` | `time_language.py:221-275` | **dead** (Mutter/gnome-shell applied them). Use `kxkbrc [Layout] LayoutList`, `VariantList`, `Use=true`, `SwitchMode=Window\|Global`, then the D-Bus signal `/Layouts org.kde.keyboard.reloadConfig`. Keep calling localed `SetX11Keyboard` for the login screen. |
| `datetime automatic-timezone` | `time_language.py:95` | **dead** (gsd-datetime). No equivalent: hide, or have the shell do it with GeoClue and timedated `SetTimezone` |
| `calendar show-weekdate` | `time_language.py:115-117` | **dead** (GNOME Shell calendar). Shell option (Fenestra calendar flyout) |

#### Shell extensions (Dash to Panel, ArcMenu, DING) and `org.gnome.shell`

All of these are **dead** because the extensions do not exist under KWin. Each control
becomes a Fenestra Shell option in shell.conf.

| Schema / key | Where | shell.conf option |
|---|---|---|
| `org.gnome.shell disable-user-extensions` | `fenestra.py:188` | none. Hide the whole `fx-extensions` page. |
| `org.gnome.shell.extensions.dash-to-panel` `panel-element-positions` (alignment, show-desktop corner), `panel-positions`, `panel-sizes`, `intellihide`, `group-apps`, `trans-use-custom-opacity`, `trans-panel-opacity` | `personalization.py:544-696` | `Taskbar/Alignment` (already read), proposed `Position`, `Size`, `AutoHide`, `Combine`, `ShowDesktopCorner`, `Transparency`, `Opacity` |
| `org.gnome.shell.extensions.arcmenu` `menu-layout`, `eleven-show-frequent-apps`, `show-recently-installed-apps`, `show-user-avatar`, `pinned-apps` | `personalization.py:498-541` | proposed `[Start] Layout` (most ArcMenu layouts in `personalization.py:481-483` have no shell counterpart, so offer only the Fenestra ones), `ShowFrequent`, `ShowRecentlyInstalled`, `ShowAvatar`, `Pinned` + reset |
| `org.gnome.shell.extensions.ding` `show-home`, `show-trash`, `show-volumes`, `show-network-volumes`, `keep-arranged`, `icon-size`, `start-corner` | `fenestra.py:160-176` | proposed `[Desktop] Show*`, `IconSize`, `StartCorner` (the shell draws the desktop) |
| `org.fenestra.desktop taskbar-search`, `taskbar-widgets` | `personalization.py:627-639` | `Taskbar/SearchMode`, `Taskbar/Weather` (already read). The schema is installed from the `fenestra-tray` extension folder (`build/build-overlay.sh:30-31`), so it must keep being installed after the extensions are dropped. |
| `org.fenestra.desktop accent-color-custom` | `personalization.py:317`; `fs/theme.py:178,201` | shell.conf accent + keep the key (Notepad, Paint and Settings read it) |
| `org.gnome.desktop.search-providers` `disable-external`, `disabled`, `enabled`, `sort-order` | `fenestra.py:233-286` (providers from `gnome-shell/search-providers/*.ini`, `backends/linux.py:167-190`) | still valid **if** Fenestra Shell's Start search uses the same `org.gnome.Shell.SearchProvider2` providers and reads these keys. Otherwise hide the page. |

`fs/util.py:181-201` looks up extension schemas in `gnome-shell/extensions/*/schemas`.
As long as those folders stay installed (`build/build-overlay.sh:23-28` copies them), the
Taskbar, Start and Desktop icons pages show live-looking but dead controls under KWin.

#### Other GSettings

| Key | Where | Under KWin |
|---|---|---|
| `org.gnome.desktop.sound event-sounds` | `sound.py:59` | read by GTK/libcanberra. Keep. |
| `org.gnome.desktop.sound allow-volume-above-100-percent` | `sound.py:65` | **dead** (GNOME Shell volume slider). Shell option. |
| `org.gnome.system.proxy mode` (+ sub-schemas) | `network.py:262-298` | **dead for most apps**. GLib's GNOME proxy resolver and libproxy's GNOME module are only used when the desktop is GNOME **(verify both)**. Alternative: `environment.d` variables (`http_proxy`, ...) and/or a libproxy config. |
| `org.gnome.software download-updates`, `download-updates-notify`, `allow-updates` | `update.py:70,197,374-378` | read by GNOME Software, but only while its background service runs. Its autostart entry may be limited to GNOME **(verify `OnlyShowIn`)**. |

### 1.3 D-Bus interfaces and GNOME binaries

| Dependency | Where | Under KWin | Equivalent |
|---|---|---|---|
| `org.gnome.Mutter.DisplayConfig` `GetCurrentState`, `ApplyMonitorsConfig` | `backends/display.py:9,81-133`; used by `display.py:105-208` | **gone** | KScreen: `kscreen-doctor -j` for the state, `kscreen-doctor output.<n>.mode.<id>` / `.scale.<f>` / `.rotation.<r>` / `.primary` / `.vrrpolicy` / `.hdr.enable` for changes (it talks to KWin's `kde_output_management_v2`). The `org.kde.KScreen` kded module is not running without Plasma's kded, so use the CLI or libkscreen directly **(verify)**. Keep our own 15 s revert dialog: KWin saves the config itself (`~/.config/kwinoutputconfig.json`). |
| `org.gnome.Mutter.DisplayConfig` `Backlight` / `SetBacklight` | `backends/power.py:92-139` | **gone** | KWin output brightness through `kscreen-doctor output.<n>.brightness.<0-100>` (KWin/KScreen 6.2 or later) **(verify)**. Fallback: `org.freedesktop.login1.Session.SetBrightness` on `/sys/class/backlight/*` (no polkit prompt for the active session). |
| `org.gnome.SettingsDaemon.Power.Screen` `Brightness` | `backends/power.py:81-128` | **gone** | same as above |
| `org.gnome.SettingsDaemon.Rfkill` `AirplaneMode` | `backends/network.py:164-185` | **gone** (the code already falls back to `nmcli radio all`, `network.py:181-183`) | Write `/dev/rfkill` (soft block of all types, the user has `uaccess`) **(verify)**, or `nmcli radio all off` plus BlueZ `Adapter1.Powered=false`. `nmcli` alone leaves Bluetooth on. |
| `org.gnome.Shell.Extensions` `ListExtensions`, `EnableExtension`, `DisableExtension`, `OpenExtensionPrefs` | `backends/linux.py:13,33-63` | **gone**. The page already shows "GNOME Shell is not running" (`fenestra.py:211`), but the page itself should be hidden. | none (shell options) |
| `org.gnome.OnlineAccounts` (ObjectManager, `Account.Remove`) | `backends/linux.py:14,76-101` | goa-daemon is D-Bus activated and works without the shell **(verify)** | keep; see the gnome-control-center row below for "Add account" |
| `grdctl` + `gnome-remote-desktop.service` | `backends/linux.py:105-139`; `fenestra.py:343-367` | **dead**. gnome-remote-desktop needs Mutter's RemoteDesktop/ScreenCast. | KRdp (`krdpserver`, uses KWin screencast) **(verify packaging)**, or hide |
| `gnome-user-share-webdav.service` | `backends/linux.py:142-158` | works as a plain user unit (gsd-sharing used to start it) **(verify)** | keep |
| `org.freedesktop.UPower`, `org.freedesktop.UPower.PowerProfiles` / `net.hadess.PowerProfiles` | `backends/power.py:8-77` | unchanged | power-profiles-daemon or tuned-ppd |
| hostnamed, timedated, localed, AccountsService, BlueZ, fprintd | `backends/system_info.py`, `timedate.py`, `accounts.py`, `bluetooth.py`, `hello.py` | unchanged, **but** interactive authorization needs a polkit agent (see §8.6) | |
| `bluetoothctl pair` | `backends/bluetooth.py:89-90` | GNOME Shell used to provide the default BlueZ agent. bluetoothctl registers a temporary agent, but it cannot answer PIN or confirmation prompts without a tty **(verify)**. | A BlueZ `Agent1` in the shell or in Settings |

`gnome-control-center` launches. They go through `util.launch()`, which switches to
`/usr/bin/gnome-control-center` and sets `FENESTRA_REAL_GCC=1` (`fs/util.py:122-150`).
GNOME Settings refuses to start when `XDG_CURRENT_DESKTOP` does not contain GNOME
**(verify on g-c-c 49)**. Even when it starts, its panels need Mutter or gsd. **Every row
below is a dead link under KWin.**

| Where | Panel | Under KWin |
|---|---|---|
| `about.py:92` | system | hide |
| `accounts.py:40-41`, `fenestra.py:328` | online-accounts | Needed for "Add account". Try `XDG_CURRENT_DESKTOP=GNOME gnome-control-center online-accounts` **(verify)**, otherwise hide "Add". |
| `accounts.py:289`, `accounts.py:309-310` | users / system users | Hide. The AccountsService UI in Fenestra Settings has to cover it. |
| `apps.py:36-37,143,226-227`; `privacy.py:48-49` | applications | Hide. Flatpak permissions could later come from the permission store. |
| `devices.py:110-111`, `fenestra.py:507-508` | printers | `system-config-printer` if installed, otherwise hide |
| `devices.py:116-117`, `fenestra.py:509-510` | wacom | hide (tablet mapping: `org.kde.KWin.InputDevice` tablet properties **(verify)**) |
| `devices.py:120-121` | keyboard | `fx-shortcuts` / `typing` |
| `display.py:76,102,121,123-124` | display (HDR, multiple displays, advanced, GPU) | Fenestra pages on top of KScreen (`hdr`, layout). GPU: switcheroo-control, or hide. |
| `gaming.py:39-40` | bluetooth | `bt-devices` |
| `network.py:69-79,142,250-251` | network / wifi (VPN, hotspot, advanced, IP/DNS) | `nm-connection-editor` (already used at `network.py:78` when installed), otherwise hide |
| `power.py:149-150` | power | hide |
| `sound.py:71-72` | sound | hide (pavucontrol if installed) |
| `system_misc.py:33-34` | sharing | `fx-sharing` |
| `system_misc.py:221-222` | system (remote desktop) | `fx-sharing` |
| `time_language.py:55-56` | accessibility (speech) | hide |
| `time_language.py:175-176` | system region | hide |
| `fenestra.py:65-66` | (none: "Advanced (GNOME Settings)") | hide |

Other binaries:

| Binary | Where | Under KWin |
|---|---|---|
| `gnome-tweaks` | `apps.py:253-255`; `personalization.py:402-403` | hide (it mostly edits GNOME Shell settings) |
| `extension-manager`, `gnome-extensions-app` | `fenestra.py:195-197` | hide |
| `gnome-extensions` (only as a hint) | `system_misc.py:241-242` ("Managed by the clipboard extension") | wrong text under KWin. Clipboard history is a shell feature (Klipper does not run). |
| `gnome-software` | `apps.py:38-40`; `update.py:85-87` | works (standalone GTK app) |
| `gnome-disks`, `baobab`, `gnome-logs`, `gnome-abrt`, `snapshot`, `orca -s`, `bluetooth-sendto`, `nm-connection-editor`, `firewall-config`, `timeshift` | `storage.py:93-96`; `system_misc.py:125-128,35-36,160-163`; `privacy.py:39-40,191-192`; `accounts.py:71-73`; `accessibility.py:204-206` | work (standalone apps) |
| `gnome-system-monitor` | `about.py:93`; `system_misc.py:127-128` | `/usr/local/bin/gnome-system-monitor` wrapper starts Task Manager (`desktop/bin/gnome-system-monitor`) |
| `gnome-network-displays` | `system_misc.py:223-225` | needs a ScreenCast portal. With `ScreenCast=kde` it may work **(verify)**. |

### 1.4 What breaks under KWin (must be hidden, not left dead)

1. **Accent / dark mode do not reach GTK apps the Fenestra way.** The wrapper GTK theme
   (`<Family>-Dark-AccentA/B`), `~/.config/gtk-4.0/fenestra-accent.css` and the caption
   button CSS are generated by the GNOME Shell extension `fenestra-tray`
   (`desktop/extensions/fenestra-tray@fenestra-os.github.io/appearance.js:277-316`,
   `captionSync.js:4-25`). Under KWin nothing regenerates them. Fenestra Shell (or a small
   helper it starts) has to take over that code.
2. Whole pages that are dead: `fx-extensions`, `fx-desktop-icons` (DING), `taskbar` (Dash
   to Panel part), `start` (ArcMenu part), `autoplay`, `focus` / `notifications` (until the
   shell server exists), `fx-shortcuts` (until the kglobalaccel backend exists), night
   light (until the KWin backend exists), `display` scale/resolution/orientation/refresh
   (they show "Not available" because `GetCurrentState` fails, `display.py:131-134`, which is
   at least not a silent dead control), and brightness.
3. Single dead rows: hot corner, dynamic workspaces, workspaces on primary, attach modal
   dialogs, locate pointer, show full name, Storage Sense / old-files age, automatic
   time zone, show week numbers, lock-screen picture, battery percentage, over-amplification,
   proxy (see §1.2), all `gnome-control-center` / Tweaks / extension rows (§1.3).
4. Remote desktop toggle (`fenestra.py:343-367`): `grdctl` is installed, so it shows a
   working-looking toggle that cannot work.
5. Airplane mode leaves Bluetooth on (nmcli fallback, `backends/network.py:181-183`).
6. Search results still list hidden pages: `search.py:41` indexes every `PAGES` entry, and
   `nav_row()` (`base.py:89-96`) and `ALIASES` (`app.py:21-35`) link to them. Hiding has to
   happen in the registry.

---

## 2. Fenestra Task Manager (`apps/fenestra-taskmgr`)

A Windows 11-style Task Manager (GTK 4, data from `/proc` and `/sys`). Pages
(`fenestra_taskmgr/pages/`): `processes.py` (Apps / Background / System groups),
`performance.py`, `apphistory.py`, `startup.py`, `users.py`, `details.py`, `services.py`,
`settings.py`. It replaces GNOME System Monitor through `desktop/bin/gnome-system-monitor`
and a `NoDisplay` override (`desktop/libexec/fenestra-post-install:61-68`).

| Dependency | Where | Under KWin |
|---|---|---|
| `org.gnome.desktop.interface color-scheme`, `accent-color` | `fenestra_taskmgr/theme.py:11,72-76,102,108` | read directly from gsettings. Works only if the shell keeps mirroring the keys (§1.2). |
| App grouping through `app-<launcher>-<id>-<pid>.scope` / `app-...@.service` cgroups | `fenestra_taskmgr/apps.py:1-53` | GNOME Shell put every launched app in such a scope. **Fenestra Shell must launch apps into systemd scopes** with the desktop id in the unit name (as KIO does). Otherwise everything shows up as "Background processes". A `fenestra` launcher prefix already parses (`apps.py:46-48`). |
| Friendly names list `gnome-shell`, `gnome-session-*`, `xdg-desktop-portal-gnome` | `apps.py:108-127,200` | cosmetic. Add `kwin_wayland`, `fenestra-shell`, `xdg-desktop-portal-kde`. |
| `org.freedesktop.FileManager1.ShowItems` | `actions.py:150-154` | unchanged (Nautilus provides it), but see §7 for which Nautilus starts |
| `gnome-control-center users` fallback | `actions.py:222` | tried after `fenestra-settings --page accounts`. Harmless, but it ends at a dead GNOME Settings. |
| `gnome-logs` for services | `actions.py:229-238` | works |
| `XDG_CURRENT_DESKTOP` filter for autostart (default `GNOME`) | `pages/startup.py:41-76` | works with `Fenestra`. `OnlyShowIn=GNOME` entries disappear, which is correct because they no longer start (§8.4). |
| `X-GNOME-Autostart-enabled` toggle | `pages/startup.py:76` | honoured by systemd's XDG autostart generator **(verify)** |
| Users page "Disconnect" | `pages/users.py:30-31` | not wired up (always insensitive). No change. |

Nothing becomes a dead control. The risk is grouping (scopes), which depends on the shell
launcher.

## 3. Fenestra OOBE (`apps/fenestra-oobe`)

First-boot setup replacing GNOME Initial Setup. Pages (`fenestra_oobe/pages/`):
`region.py`, `network.py`, `account.py`, `personal.py` (privacy / tailored), `icons.py`
(icon pack / Windows import). Backends: `accounts.py`, `crypt.py`, `dbus.py`, `gdm.py`,
`hostname.py`, `locale.py`, `network.py`, `privacy.py`, `system.py`.

It runs in two modes, through systemd drop-ins
(`apps/fenestra-oobe/data/systemd/*/fenestra.conf`, installed by `install.sh:60-66`):

* **System mode**, `gnome-initial-setup.service`: runs in GDM's initial-setup session,
  which is still GNOME Shell (GDM stays). It is not affected by KWin. The GDM greeter API
  (`backends/gdm.py`) keeps working.
* **Existing-user mode**, `gnome-initial-setup-first-login.service`: runs at the user's
  first login. GNOME's session targets pull this unit in **(verify on F43:
  `systemctl --user list-dependencies --reverse gnome-initial-setup-first-login.service`)**.
  `fenestra-session.target` (`session/systemd/fenestra-session.target`) does not, so **the
  first-login half of OOBE will not run in the Fenestra session**. Add
  `Wants=gnome-initial-setup-first-login.service` (or a Fenestra unit with the same
  `ConditionPathExists=!%E/gnome-initial-setup-done`).

| Dependency | Where | Under KWin |
|---|---|---|
| `org.gnome.system.location enabled` | `backends/privacy.py:26` | needs a GeoClue agent (§1.2) |
| `org.gnome.desktop.datetime automatic-timezone` | `backends/privacy.py:27,69-71` | **dead** (gsd-datetime). Hide that toggle in the Fenestra session, or have the shell implement it. |
| `org.gnome.desktop.privacy report-technical-problems`, `remember-recent-files` | `backends/privacy.py:28-29` | read (ABRT **(verify)**, GTK) |
| `org.gnome.desktop.interface icon-theme` reset | `backends/privacy.py:178-181` | read by GTK. The Qt shell needs the same theme (shell.conf / kdeglobals). |
| `org.gnome.desktop.interface text-scaling-factor`, `a11y.interface high-contrast`, `a11y.applications screen-reader-enabled`, `screen-keyboard-enabled` | `backends/system.py:20-58` | same as Settings Accessibility (§1.2): text scale and contrast reach GTK only; Orca and OSK need the shell / KWin |
| `org.gnome.system.locale region` | `backends/system.py:153-155` | **dead**. gnome-session read it and exported `LC_*`. The Fenestra session script must export `LC_TIME`, `LC_NUMERIC`, ... from this key or from AccountsService `FormatsLocale` (set at `backends/accounts.py:131`). |
| `org.gnome.desktop.input-sources sources`, `current` | `backends/system.py:157-177` | **dead** in the user session. Write `kxkbrc` as well. System mode keeps writing the key, because that session is GNOME. |
| `gnome-initial-setup-uid`, `/run/gdm/gnome-initial-setup` handoff | `backends/gdm.py:65`; `backends/system.py:128-145` | unchanged (GDM) |
| localed / timedated / hostnamed / AccountsService / nmcli / wpctl / udisksctl | `backends/locale.py`, `hostname.py`, `accounts.py`, `network.py`, `system.py:67-81`, `privacy.py:122-145` | unchanged. In existing-user mode, interactive polkit needs an agent (§8.6). |
| `fenestra-import-windows-assets` helper | `backends/privacy.py:152-170`; `tools/fenestra-import-windows-assets:273,396,677,731,737` | sets `cursor-theme`, `icon-theme`, `accent-color-custom` and **ArcMenu `menu-button-icon`** (line 396). Under KWin: cursor → also `kcminputrc`, Start button icon → shell.conf. |

## 4. Fenestra Notepad (`apps/fenestra-notepad`)

A Windows 11-style Notepad (GTK 4 + GtkSourceView 5): tabs in the title bar, File/Edit/View
menus, Markdown toolbar, find/replace, status bar, settings page (`settings_page.py`),
session restore (`session.py`), printing (`printing.py`). It is the default text editor
(`desktop/libexec/fenestra-post-install:70-79`).

| Dependency | Where | Under KWin |
|---|---|---|
| `org.gnome.desktop.interface color-scheme`, `accent-color`; `org.fenestra.desktop accent-color-custom` | `fenestra_notepad/theme.py:14-15,108-115` | read directly, so it needs the mirror (§1.2) |
| Title-bar tabs (client-side decorations) | `tabbar.py`, `window.py` | KWin honours GTK CSD. No change. |

No dead controls.

## 5. Fenestra Paint (`apps/fenestra-paint`)

A Windows 11-style Paint (GTK 4 + cairo): menu bar, toolbar (Selection, Image, Tools,
Brushes, Shapes, Colors, Layers), layers panel, settings page, status bar.

| Dependency | Where | Under KWin |
|---|---|---|
| `org.gnome.desktop.interface color-scheme`, `accent-color`; `org.fenestra.desktop accent-color-custom` | `fenestra_paint/theme.py:3-4,14-15,107-130`; helper `util.py:97-105` | read, so it needs the mirror |
| **"Set as desktop background"** writes `org.gnome.desktop.background picture-uri`, `picture-uri-dark`, `picture-options` | `fenestra_paint/fileio.py:236-242`; menu `window.py:545,575-578`; action `window.py:1224-1230` | **dead** under KWin. Shared wallpaper backend (shell.conf / shell D-Bus), or hide the menu under KWin. |
| `tools/screenshots.sh:52` uses `gnome-shell-disable-extensions` | dev tool only | none |

## 6. Fenestra Icon Extractor (`apps/fenestra-icon-extractor`)

A Windows (.NET) app that exports the user's own Windows icons into a Fenestra icon pack
(`docs/ICON-PACK-FORMAT.md`). It never runs on Fenestra, so it has no GNOME runtime
dependency. The only GNOME coupling is naming: the pack maps `explorer.exe` to the icon names
`system-file-manager`, `org.gnome.Nautilus`, `fenestra-file-explorer`
(`src/Exporter.cs:401`). Fenestra Shell must resolve app icons through the same icon theme
(including `org.gnome.*` names) for the taskbar and Start. The import side is covered under
OOBE.

## 7. Explorer layer on Nautilus

Pieces:

* `desktop/libexec/fenestra-patch-nautilus`: copies `/usr/bin/nautilus` to
  `/usr/libexec/fenestra/nautilus`, swaps sidebar icon-name strings (`TABLE`, lines 26-35)
  and writes `nautilus.stamp`. Run by `fenestra-patch-nautilus.service`
  (`desktop/systemd/fenestra-patch-nautilus.service`) and by
  `desktop/libexec/fenestra-post-install:34-35`.
* `desktop/libexec/fenestra-nautilus`: runs the patched copy with
  `G_RESOURCE_OVERLAYS=/org/gnome/nautilus=/usr/share/fenestra/nautilus/overlay/<major>`
  when the stamp matches. Otherwise it runs stock Nautilus.
* UI overlays: `desktop/nautilus/overlay/49/ui/*`, `desktop/nautilus/overlay/51/{ui,menu}/*`.
* nautilus-python extensions (`desktop/nautilus/python/`): `fenestra-explorer.py`,
  `fenestra_menus.py`, `fenestra_views.py`, `fenestra_pages.py`, `fenestra_sidebar.py`,
  `fenestra_folder_icons.py`. Installed to `/usr/share/nautilus-python/extensions`
  (`build/build-overlay.sh:62-67`).
* `desktop/applications/org.gnome.Nautilus.dbus.service`, which points D-Bus activation at the
  wrapper. Installed as `/usr/local/share/dbus-1/services/org.gnome.Nautilus.service`
  (`build/build-overlay.sh:68`).
* `/usr/local/share/applications/org.gnome.Nautilus.desktop`, with `Exec` pointing at the
  wrapper (`fenestra-post-install:38-41`).

GNOME dependencies: only Nautilus' own schema `org.gnome.nautilus.preferences`
(`fenestra_menus.py:281-286`) and libadwaita. Neither depends on GNOME Shell. The Explorer
layer keeps working under KWin. Things to check:

* `org.freedesktop.FileManager1` (used by Task Manager, `actions.py:150`, and by every Qt/KDE
  app's "Show in folder") is activated through Nautilus' own service file, which starts
  `/usr/bin/nautilus` and so **skips the Explorer layer** **(verify the Fedora file;
  pre-existing, but under KWin more callers use it)**. Fix: ship an override of
  `org.freedesktop.FileManager1.service` in `/usr/local/share/dbus-1/services`.
* `/usr/local/share` must be in `XDG_DATA_DIRS` of the Fenestra session for both overrides
  **(verify what GDM sets for a non-GNOME session)**.
* DING (desktop icons) is a GNOME Shell extension and is gone. The Fenestra Shell desktop
  must replace it (and honour the "Desktop icons" options, §1.2).
* "Set as Background" in Nautilus goes through the Wallpaper portal, so it depends on the
  portal backend (§8.5) and on the shell reading the result.
* The patched sidebar icons only exist in the Fenestra icon theme. That is unchanged.

---

## 8. Integration points

### 8.1 mimeapps

* `desktop/libexec/fenestra-post-install:70-88` writes
  `/usr/share/applications/fenestra-mimeapps.list` (Notepad default for text types, Paint
  added for images) and copies it to `/etc/xdg/gnome-mimeapps.list` (line 86).
* The lookup is per desktop: with `XDG_CURRENT_DESKTOP=Fenestra`, GIO and KIO read
  `fenestra-mimeapps.list` in `$XDG_CONFIG_DIRS` (`/etc/xdg`) and
  `$XDG_DATA_DIRS/applications`, and no longer read `gnome-mimeapps.list`.
  `/usr/share/applications/fenestra-mimeapps.list` therefore already applies. However:
  * there is no `/etc/xdg/fenestra-mimeapps.list`; install one next to the GNOME copy;
  * the distribution's GNOME defaults (`/usr/share/applications/gnome-mimeapps.list`, browser,
    image viewer, PDF, ...) stop applying under Fenestra. Generate `fenestra-mimeapps.list` as
    the GNOME list merged with the Fenestra lines.
* User choices made in Settings › Default apps go to `~/.config/mimeapps.list` through
  `Gio.AppInfo.set_as_default_for_type` (`fs/backends/apps.py:144-155`). That file is
  desktop-independent and outranks the system lists. No change.

### 8.2 .desktop overrides in /usr/local/share/applications

| File | Source | Under KWin |
|---|---|---|
| `org.gnome.Nautilus.desktop` | `fenestra-post-install:38-41` | still needed (Exec → wrapper) |
| `org.gnome.Settings.desktop` | `apps/fenestra-settings/data/org.gnome.Settings.desktop` via `install.sh:52` / `fenestra-post-install:47-52` | It has `OnlyShowIn=GNOME;` (line 16), so under Fenestra it is not shown. It is `NoDisplay` anyway, so launching by id still opens Fenestra Settings. Add `Fenestra` to `OnlyShowIn` so shell "Settings" links resolve it the same way. |
| `org.gnome.SystemMonitor.desktop` | `fenestra-post-install:61-67` | still needed |
| `fenestra-search.desktop` (in `/usr/share/applications`) | `desktop/applications/fenestra-search.desktop`, `build-overlay.sh:71` | **dead**. `Exec=gdbus call ... com.Extensions.ArcMenu.ToggleStandaloneRunner` (line 8) needs ArcMenu. Point it at Fenestra Shell's search, or add `OnlyShowIn=GNOME;` plus a Fenestra variant. |
| `org.fenestra.Shell.desktop` | `shell/data/org.fenestra.Shell.desktop` (`OnlyShowIn=Fenestra;`, line 7) | new |

Fenestra Shell's Start must apply `OnlyShowIn`/`NotShowIn` against `Fenestra` and honour
`NoDisplay`, as GIO does. GNOME-only entries (Tweaks, Extensions) then drop out by
themselves.

### 8.3 gnome-control-center redirect

`apps/fenestra-settings/bin/gnome-control-center` (installed to `/usr/local/bin`,
`install.sh:44-53`, `fenestra-post-install:54-58`): known panels go to
`fenestra-settings --page` (lines 29-31). Unknown panels, `--real` and `FENESTRA_REAL_GCC=1`
go to the real binary (lines 9-15, 32). Under Fenestra the real binary is dead (§1.3). In
the Fenestra session the wrapper should open Fenestra Settings Home for unknown panels and
only `exec` the real one for an allow-list such as `online-accounts`, if that works with
`XDG_CURRENT_DESKTOP=GNOME` **(verify)**.

### 8.4 Autostart and session units

* `/etc/xdg/autostart/fenestra-release-upgrade-user.desktop`
  (`desktop/autostart/fenestra-release-upgrade-user.desktop`, installed at
  `build-overlay.sh:46`) uses `X-GNOME-Autostart-Phase=Application` and
  `X-GNOME-Autostart-Delay=10` (lines 6-7). Those are gnome-session semantics.
* The Fenestra session has no gnome-session. XDG autostart only runs if
  `fenestra-session.target` pulls in `xdg-desktop-autostart.target`, and it does not
  (`session/systemd/fenestra-session.target`). systemd's xdg-autostart generator also skips
  entries that set `X-GNOME-Autostart-Phase` **(verify in systemd 258)**, and it ignores
  `X-GNOME-Autostart-Delay`. Ship this job as a user unit with
  `PartOf=graphical-session.target` instead.
* The same applies to distribution autostarts: GNOME Software's update service, IBus (GNOME
  Shell started it; under KWin the input method is set in `kwinrc [Wayland] InputMethod`),
  and the at-spi bus. Check each, especially those with `OnlyShowIn=GNOME`.
* OOBE first-login unit: see §3.
* `usr/lib/environment.d/60-fenestra-qt.conf` (`desktop/gtk/60-fenestra-qt.conf`) sets
  `QT_QPA_PLATFORM=xcb;wayland` so that Mutter draws caption buttons. Under KWin the
  session exports `wayland;xcb` (`session/libexec/fenestra-session:9`) and imports it into
  systemd (`fenestra-session-inner:5-7`), so units started before that import still get
  `xcb`. Fenestra Shell needs native Wayland for layer-shell. Make the shell unit set
  `QT_QPA_PLATFORM=wayland` explicitly.

### 8.5 Portals (xdg-desktop-portal)

The repo ships **no** `*-portals.conf` (no match for `portals.conf` outside `build/out`).
With `XDG_CURRENT_DESKTOP=Fenestra`, xdg-desktop-portal looks for
`/usr/share/xdg-desktop-portal/fenestra-portals.conf` (or `~/.config/xdg-desktop-portal/`,
`/etc/xdg-desktop-portal/`). Without it, backend choice falls back to `UseIn=`, which lists
no "Fenestra" **(verify the 1.20 fallback)**. Proposed file:

```ini
[preferred]
default=gtk
org.freedesktop.impl.portal.Settings=gtk
org.freedesktop.impl.portal.ScreenCast=kde
org.freedesktop.impl.portal.Screenshot=kde
org.freedesktop.impl.portal.RemoteDesktop=kde
org.freedesktop.impl.portal.GlobalShortcuts=kde
org.freedesktop.impl.portal.InputCapture=kde
org.freedesktop.impl.portal.Secret=gnome-keyring
```

Why: `xdg-desktop-portal-gnome`'s ScreenCast, Screenshot and RemoteDesktop need Mutter.
`-kde` talks to KWin (it needs KWin's restricted-interface authorization in its desktop
file). `Settings=gtk` serves `org.gnome.desktop.*` and `org.freedesktop.appearance` from
gsettings, which is why the mirror in §1.2 matters. Open items **(verify)**:
* `Inhibit`: gtk's backend uses `org.gnome.SessionManager` and kde's uses PowerDevil, and
  neither runs here. The shell or a small Fenestra backend has to provide it.
* `Wallpaper`, `Background`, `Notification`, `Lockdown`, `Access`, `Account`, `AppChooser`,
  `FileChooser`: confirm each works with gtk outside GNOME.
* KWin's `org.freedesktop.ScreenSaver` inhibition for video players.

### 8.6 polkit and other agents GNOME Shell used to provide

* Policies in the repo: `desktop/polkit/org.fenestra.update.policy`,
  `org.fenestra.reset.policy` (installed at `build-overlay.sh:56-58`). They are unchanged.
* **There is no polkit authentication agent in the session.** GNOME Shell was the agent.
  Without one, every interactive authorization fails: `pkexec` (Update, Recovery reset
  `system_misc.py:176`, ABRT in Diagnostics), and every D-Bus call made with
  `ALLOW_INTERACTIVE_AUTHORIZATION` (`fs/util.py:290-316`: hostname rename, time zone,
  locale, automatic login, BlueZ, NM system connections). Fenestra Shell needs a PolkitQt1
  agent, or a user unit running `polkit-kde-authentication-agent-1` /
  `polkit-gnome-authentication-agent-1`, `PartOf=fenestra-session.target`.
* The same holds for the **NetworkManager secret agent** (Wi-Fi, 802.1X and VPN password
  prompts outside Settings), the **BlueZ agent** (§1.3) and the **GeoClue agent** (§1.2).
* Keyring prompts (gcr) and the `gnome-keyring` PAM start do not depend on GNOME Shell
  **(verify the autostart entries' `OnlyShowIn`)**.

---

## 9. Settings backend split (prioritized plan)

Goal: pages stop calling `util.gget/gset` with GNOME schemas directly. They call a backend
module whose implementation is chosen once from `XDG_CURRENT_DESKTOP`. Every backend
reports `available()` (or per-feature `supports(feature)`), and pages, nav rows, search
entries and aliases are **hidden** when it returns False.

Layout: `fs/backends/<area>/__init__.py` picks `gnome.py` or `fenestra.py`. Each function
below exists in both implementations (or the Fenestra one returns "unsupported").

### P0: session detection and hiding

1. **`backends/session.py`**: `desktop() -> str`, `is_fenestra()`, `is_gnome()` (parse
   `XDG_CURRENT_DESKTOP` split on `:`); `supports(feature: str) -> bool`;
   `hidden_pages() -> set[str]`; `hidden_rows(page_id) -> set[str]`;
   `open_panel(name) -> bool` (replaces `util.open_control_center`; returns False, so the
   row is hidden, for panels without a Fenestra target). Wire it into `pages/base.py`
   (`register`, `nav_row`, `ext_row`), `search.py:41` and `app.py:resolve_page`.
   The control audit (`tests/control_audit.py`) should run once per desktop value.

### P0: the most used pages (dead today under KWin)

2. **`backends/displays/`** (replaces `backends/display.py`): `get_state(cb)`,
   `apply(state, connector, cb, mode_id=, scale=, transform=)`, `restore(old_state, cb)`,
   `resolutions(mon)`, `refresh_rates(mon)`, `set_primary(connector, cb)`,
   `set_hdr(connector, on, cb)`, `supports_hdr(connector)`.
   gnome: Mutter DisplayConfig. fenestra: `kscreen-doctor -j` and `kscreen-doctor output.*`.
3. **`backends/brightness/`**: `get() -> int|None`, `set(value, cb)`, `available()`.
   gnome: gsd-power Screen / Mutter Backlight (`backends/power.py:81-139`). fenestra:
   KScreen output brightness, then logind `SetBrightness`.
4. **`backends/appearance/`**: `color_scheme()/set_color_scheme(v)`, `accent()/set_accent(name_or_hex)`,
   `wallpaper(dark)/set_wallpaper(path, fit)`, `wallpaper_fit()/set_wallpaper_fit(v)`,
   `gtk_theme/icon_theme/cursor_theme` get/set, `cursor_size` get/set, `fonts()`/`set_font(kind, desc)`,
   `font_rendering` get/set, `text_scale` get/set, `animations` get/set, `connect(cb)`.
   gnome: current gsettings. fenestra: shell.conf (atomic write; the shell watches the file), **plus a gsettings
   mirror** of `color-scheme`, `accent-color`, `gtk-theme`, `icon-theme`, `cursor-theme`,
   `cursor-size`, fonts and `text-scaling-factor` (GTK reads them through the portal), plus
   `kcminputrc` for the cursor and regeneration of the GTK accent CSS (moved out of
   `fenestra-tray/appearance.js`). Also used by `system_info.wallpaper_path`, Home, and
   Paint (`fileio.set_wallpaper`).
5. **`backends/shell_options/`**: taskbar `alignment, position, size, autohide, combine,
   show_desktop_corner, transparency, opacity, search_mode, widgets`; start `layouts(), layout,
   show_frequent, show_recent_installed, show_avatar, pinned_count, reset_pins`; clock
   `weekday, date, seconds, format`; `battery_percentage`; `full_name_in_bar`;
   desktop icons `show_home, show_trash, show_volumes, show_network, keep_arranged, icon_size,
   start_corner`; `lockscreen_notifications`; `volume_above_100`. Each with get/set and `supports()`.
   gnome: Dash to Panel / ArcMenu / DING / `org.fenestra.desktop` / `org.gnome.desktop.interface`.
   fenestra: shell.conf.
6. **`backends/notifications/`**: `dnd()/set_dnd(on)`, `lockscreen()/set_lockscreen(on)`,
   `apps() -> [(app_id, enabled, banners)]`, `set_app_enabled(app_id, on)`.
   gnome: `org.gnome.desktop.notifications(.application)`. fenestra: Fenestra Shell
   notification server (D-Bus) / shell.conf.
7. **`backends/power_policy/`**: `screen_off_timeout` get/set, `sleep_timeout(ac|battery)` get/set,
   `power_button_action` get/set + `choices()`, `saver_on_low_battery` get/set.
   gnome: gsd-power keys + `org.gnome.desktop.session idle-delay`. fenestra: shell.conf
   `[Power]` (shell idle + logind).
8. **`backends/screenlock/`**: `auto_lock` get/set, `lock_delay` get/set, `lock_picture` get/set
   (+ `supports("lock-picture")`). gnome: `org.gnome.desktop.screensaver`. fenestra:
   `kscreenlockerrc [Daemon]` + reload.
9. **`backends/rfkill/`**: `airplane()`, `set_airplane(on, cb)`. gnome: gsd-rfkill. fenestra:
   `/dev/rfkill` (all types), with a fallback to nmcli + BlueZ `Powered`.

### P1: devices, input and window management

10. **`backends/pointer/`**: `devices(kind) -> [Device]`, `left_handed`, `speed`, `accel_flat`,
    `natural_scroll`, `tap_to_click`, `disable_while_typing`, `two_finger_scroll`,
    `enabled`, all get/set. gnome: peripherals schemas. fenestra: `org.kde.KWin.InputDevice`.
11. **`backends/nightlight/`**: `available()`, `enabled`, `strength` (temperature), `schedule`
    (`auto|manual`), `from_to`, all get/set; `supports("auto-schedule")`. gnome: gsd color.
    fenestra: `kwinrc [NightColor]` + `org.kde.KWin.NightLight`.
12. **`backends/keyboard_layouts/`**: `sources()`, `add(id)`, `remove(id)`, `per_window` get/set,
    `connect(cb)`. gnome: `org.gnome.desktop.input-sources`. fenestra: `kxkbrc` +
    `org.kde.keyboard reloadConfig`. Both also keep localed in sync.
13. **`backends/shortcuts/`**: `sections() -> [(title, [ShortcutId])]`, `get(id) -> [accel]`,
    `set(id, accel)`, `reset(id)`, `connect(id, cb)`. gnome: wm/shell/mutter/media-keys keys.
    fenestra: kglobalaccel (kwin component + Fenestra Shell component).
14. **`backends/windowing/`**: `workspaces` get/set, `dynamic_workspaces`, `only_primary`,
    `snap`, `hot_corner`, `alt_tab_scope`, `focus_mode`, `auto_raise`, `titlebar_action(button)`,
    `button_layout`, `center_new`, `attach_modal`, `resize_right_button`, `move_modifier`;
    each with `supports()`. gnome: mutter/wm/app-switcher. fenestra: `kwinrc` + reconfigure.
    `dynamic_workspaces`, `only_primary` and `attach_modal` are unsupported.
15. **`backends/a11y/`**: `magnifier` on/factor, `screen_reader`, `osk`, `sticky_keys`,
    `slow_keys`, `toggle_keys`, `visual_bell`, `locate_pointer`, `high_contrast`;
    `supports()` each. gnome: a11y keys. fenestra: KWin zoom effect, shell-managed Orca,
    KWin virtual keyboard, `kaccessrc`, plus gsettings mirror for high contrast.

### P2: smaller areas

16. **`backends/extensions/`**: `list(cb)`, `set_enabled(uuid, on)`, `open_prefs(uuid)`,
    `user_extensions` get/set. gnome only (`backends/linux.py:33-63`). fenestra: unsupported,
    so the page is hidden.
17. **`backends/sharing/`**: `remote_desktop_status(cb)`, `set_remote_desktop(on)`,
    `file_sharing_status(cb)`, `set_file_sharing(on)`. gnome: grdctl + gnome-user-share.
    fenestra: KRdp **(verify)** or unsupported; gnome-user-share shared.
18. **`backends/search_providers/`**: `providers()`, `external_enabled` get/set,
    `disabled`/`enabled` get/set, `order` get/set. Both read `org.gnome.desktop.search-providers`
    if the shell adopts SearchProvider2; otherwise fenestra is unsupported.
19. **`backends/housekeeping/`**: `trash_auto`, `temp_auto`, `max_age`, get/set. gnome:
    privacy keys (gsd-housekeeping). fenestra: a user systemd timer, or unsupported.
20. **`backends/autotime/`**: `automatic_timezone` get/set. gnome: datetime key.
    fenestra: unsupported (or shell + GeoClue). Also used by OOBE.
21. **`backends/media_handling/`**: `autorun`, `automount_open`, get/set. gnome: media-handling keys.
    fenestra: shell or unsupported.
22. **`backends/location/`**: `enabled` get/set, `agent_running()`. Both use the key. fenestra
    needs the shell agent and is unsupported until it exists.
23. **`backends/proxy/`**: `mode` + host fields get/set. gnome: `org.gnome.system.proxy`.
    fenestra: `environment.d` / libproxy **(verify)**, else unsupported.
24. **`backends/sound_policy/`**: `event_sounds` (shared key), `over_amplification`
    (gnome key / shell.conf).

Order of work: 1 → 4 → 5 → 2/3 → 6 → 7/8 → 9 → 10-15 → 16-24. Items 1, 4 and 5 remove the
largest number of dead controls. Until 2/3 and 10-15 are done, `session.supports()` must
return False for those areas so their rows are hidden under Fenestra.

### Implementation status (Fenestra Settings)

Done: items **1, 4, 5 and 6**. Under `XDG_CURRENT_DESKTOP=GNOME` (or any value without
`Fenestra`) Settings behaves exactly as before: same pages, same search index, same controls
(checked with `--list-pages`, `--export-search-index` and `tests/control_audit.py`).

* **1.** `fs/backends/session.py` holds the whole policy: `GNOME_ONLY` features, `PAGE_FEATURES`
  (page → feature) and `ROW_FEATURES` (page → row key → feature). `pages/base.py` `register()` keeps
  hidden pages (and their children) out of `PAGES` (they go to `HIDDEN_PAGES`), `Page.get_widget()`
  and `Group.add()` hide rows whose `key` is listed, `nav_row()` hides links to hidden pages/rows,
  `ext_row()` maps `gnome-control-center <panel>` to a Fenestra page or a standalone tool
  (`FENESTRA_PANELS`) or hides the row, and hides Tweaks / extension managers. `search.py` skips
  hidden rows; `app.py resolve_page()` sends a hidden page or alias to its nearest shown parent.
  `util.open_control_center()` callers use `session.open_panel()` / `panel_available()`.
  Hidden under Fenestra, pages: `fx-extensions`, `fx-desktop-icons`, `fx-shortcuts`,
  `fx-workspaces`, `fx-search`, `multitasking`, `autoplay`, `mouse`, `touchpad`, `magnifier`,
  `narrator`, `a11y-audio`, `a11y-keyboard`, `typing`, `screenlock`, `lockscreen`, `location`,
  `proxy`. Rows: display brightness / night light / HDR / scale / resolution / orientation /
  refresh / multiple displays / advanced (GNOME Settings); power screen and sleep, power button,
  battery percentage, battery saver; notification lock screen + per-app list; Storage Sense and
  old-files age; trash/temp housekeeping and "show my name"; automatic time zone, week numbers;
  over-amplification; locate pointer; wallpaper fit; ArcMenu layout / frequent / recently added /
  avatar; every Dash to Panel row except alignment; panel clock rows; window focus mode, auto
  raise, title bar actions, center new windows, attach modal dialogs, resize with secondary
  button, move modifier (title bar buttons stays: GTK reads it); remote desktop; online accounts
  "Add account"; password change (GNOME users panel); clipboard-extension row; every GNOME
  Settings / Tweaks / extension-manager row without a Fenestra target. Areas 2/3 and 7-24 stay
  unsupported (hidden) until their backends exist.
* **4.** `fs/backends/appearance/` (`gnome.py`, `fenestra.py`, `gtkaccent.py`). Fenestra writes
  shell.conf `[Appearance] ColorScheme, Accent, Wallpaper (path | #RRGGBB | spotlight),
  ReduceMotion` and mirrors to GSettings (`color-scheme`, `accent-color` +
  `org.fenestra.desktop accent-color-custom`, background `picture-uri(-dark)`, themes, cursor,
  fonts, `text-scaling-factor`, `enable-animations`); the cursor also goes to `kcminputrc [Mouse]`
  with a `org.kde.kconfig.notify ConfigChanged` signal **(verify on KWin)**. `gtkaccent.py` is a
  byte-identical Python port of `fenestra-tray` `appearance.js` (`palette()`, `_gtk()`) and
  `captionSync.js`; it runs from Settings in both sessions after every mode/accent/theme change.
  `fenestra-settings --sync-appearance` copies shell.conf's mode/accent/wallpaper to GSettings and
  regenerates those files (to be run by the session at login and by the shell after its own
  mode/accent changes); while Settings runs it does this whenever shell.conf changes.
* **5.** `fs/backends/shell_options/`: `alignment`, `search_mode` (`hide|icon|icon-label|box` ↔
  `hidden|icon|iconLabel|box`), `weather`, `taskbar_pins`, `start_pins`, `reset_start_pins`,
  `pinned_count`, `supports()`. Other taskbar/Start options are GNOME-only for now.
* **6.** `fs/backends/notifications/`: `dnd`/`set_dnd` (Fenestra: `[Notifications]
  DoNotDisturb`), used by System › Notifications and Focus. Lock-screen notifications and the
  per-app list are unsupported under Fenestra.

Open points found while doing it:

* Fenestra Shell reads `Notifications/DoNotDisturb` only at start-up
  (`shell/src/services/notifications.cpp`); it should reload it on `ShellSettings::fileChanged`
  so the Settings switch applies live.
* An empty `Start/Pinned` list is written as `@Invalid()` (QSettings' own encoding), which the
  shell reads as "not set" and replaces with its defaults.
* Paint's `fileio.set_wallpaper` still writes only the GNOME keys.
* Solid colour wallpaper uses `org.gnome.desktop.background primary-color`; there is no colour
  picker yet.
* Tests: `apps/fenestra-settings/tools/test_session_backends.py` (both sessions, temporary HOME;
  cross-checks the colour maths against `appearance.js` with gjs and shell.conf with Qt's
  QSettings when available) and `tests/control_audit.py` run with each `XDG_CURRENT_DESKTOP`.
