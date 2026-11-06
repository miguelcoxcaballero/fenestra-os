# Regression checklist

Every feature Fenestra has today, checked twice in a KVM VM: **A** = current GNOME session (reference),
**B** = Fenestra session (KWin + Fenestra Shell). Values: PASS, FAIL, NO-APLICA, SOLO-PORTÁTIL. Until a VM
run exists, B also records the container state: PASS-CONTAINER (tests/shell-kwin), PARTIAL, CODE
(written, not run), TODO. A feature is migrated only when B is PASS in the VM. Screenshots: demo data,
1920×1080 and 2560×1600 at 150 %, light and dark.

| ID | Feature | A (GNOME) | B (Fenestra/KWin) | Evidence / notes |
|---|---|---|---|---|
| B01 | Centred and left-aligned icons (Settings › Personalization › Taskbar) | pending (VM) | PASS-CONTAINER | tests/shell-kwin check B01-left-aligned, 05-left-icon.png |
| B02 | Pinned apps, open windows with indicator, grouping, pin/unpin | pending (VM) | PASS-CONTAINER | checks B02-pinned-buttons, -launch-from-pinned, -window-grouped-with-pinned, -unpinned-app-button, -app-menu, -unpin |
| B03 | Live preview on hover; click activates/minimizes; close from the preview | pending (VM) | PARTIAL | window list + close in the preview (check B03-preview); live thumbnails need OpenGL (VM) |
| B04 | Press animation (icon shrinks) and acrylic taskbar | pending (VM) | PARTIAL | press animation done; acrylic needs KWin blur (OpenGL, VM) |
| B05 | Weather at the left (icon, temperature, condition) opens Weather; hidden when left-aligned or without data; Settings option | pending (VM) | CODE | libgweather service; needs a real location (VM) |
| B06 | Search in four modes (hidden, icon, icon + label, box), live, light and dark | pending (VM) | PASS-CONTAINER | checks B06-icon-label, light-mode; screenshots 01, 05, 06, 07 |
| B07 | Empty-area right click: Task Manager, Taskbar settings; no context menu on Start | pending (VM) | PASS-CONTAINER | check B07-taskbar-menu; Start has no menu |
| B08 | Tray: overflow ^, language/keyboard, Wi-Fi, volume, battery, clock and date; mic/camera/location in use | pending (VM) | PARTIAL | app tray (StatusNotifierItem host + dbusmenu) and keyboard layout: checks B08-*; Wi-Fi/volume/battery glyphs written (NetworkManagerQt, PulseAudioQt, UPower), need the VM; privacy glyphs in H4 |
| B09 | Show desktop corner | pending (VM) | CODE | show_desktop request; not clicked in the bench yet |
| B10 | Multi-monitor and scaling (taskbar per monitor, flyouts on the right monitor) | pending (VM) | PASS-CONTAINER | OUTPUTS=2 bench: check B10-taskbar-per-output (one taskbar and wallpaper per output); scaling in the VM |
| B11 | Every taskbar flyout 12 px above the taskbar and 13 px from the screen edge, no arrow | pending (VM) | PASS-CONTAINER | Flyout.qml margins 12/13 + layer-shell exclusive zone; screenshots 02–04 |
| S01 | Start: search box, Pinned, Recommended, All apps (category, grid, list), account and power menus | pending (VM) | PASS-CONTAINER | checks S01-* (D-Bus/Super, pins, Recommended from recently-used.xbel, power and account menus, All apps in three views, light mode); screenshots 09–12, 16 |
| S02 | Start open/close animation, acrylic, no strip above the search box, no accent underline on focus | pending (VM) | PARTIAL | slide 96 px / 200 ms OutQuint, close 120 ms InQuad, no strip, no focus underline; acrylic blur needs KWin OpenGL (VM) |
| S03 | Start works for a new account | pending (VM) | CODE | defaults (Start pins, taskbar pins) apply without shell.conf; check with a new account in the VM |
| S04 | Search flyout: recent searches, top apps, chips (All, Web, Apps, Documents, Settings, Folders, Photos), best match, preview pane | pending (VM) | PASS-CONTAINER | checks S04-* (home, chips, results + preview, Settings filter, history file kept at the GNOME layer path); screenshots 13–15 |
| S05 | Search finds and opens apps, documents, folders and Settings pages | pending (VM) | PASS-CONTAINER | checks S05-finds-photo, -finds-settings-page (Fenestra Settings --export-search-index), -finds-app, -opens-app; documents via a folder index (localsearch not used yet) |
| Q01 | Quick settings tiles with subpages; volume, brightness, audio output | pending (VM) | PARTIAL | checks Q01-quick-settings (tiles, sliders, subpages written); Wi-Fi, Bluetooth, battery, brightness need real devices (VM) |
| Q02 | Media panel (MPRIS): play/pause, previous, next | pending (VM) | PASS-CONTAINER | checks Q02-media-player, Q02-play-pause (test MPRIS player) |
| Q03 | Volume and brightness OSD (keys and wheel) | pending (VM) | PARTIAL | OSD drawn (check Q03-osd); media keys via KGlobalAccel need the VM |
| Q04 | Notice after a screenshot | pending (VM) | PARTIAL | image notification layout (check Q04-image-notification); Print → KWin ScreenShot2 needs OpenGL (VM) |
| Q05 | Ctrl+Alt+Del security screen: Lock, Switch user, Sign out, Change a password, Task Manager, power; mouse works on every button | pending (VM) | PASS-CONTAINER | checks Q05-security-screen, Q05-power-menu; Ctrl+Alt+Del binding in the VM |
| Q06 | Administrator prompts (polkit) in the Fenestra account-control style; the password is always asked | pending (VM) | CODE | polkit agent + consent dialog written; needs polkitd and a logind session (VM) |
| N01 | Two separate cards: notification centre (Clear all, Do not disturb) and calendar (focus timer) | pending (VM) | PASS-CONTAINER | checks N01-center-and-calendar, -history, -do-not-disturb, -focus-session, -clear-all |
| N02 | Notification banners; grouping by app; working actions; history | pending (VM) | PASS-CONTAINER | checks N02-server-registered, -banner, -action-invoked (real D-Bus notifications) |
| D01 | Desktop icons with Fenestra folder icons; select, drag and drop | pending (VM) | PASS-CONTAINER | checks D01-* (icons, new folder + rename, move remembered, trash) |
| D02 | Desktop context menu like the Explorer's | pending (VM) | PASS-CONTAINER | checks D02-background-menu, D02-item-menu (glyphs of the GNOME layer) |
| D03 | Wallpapers: Fenestra originals, solid palette colours, Spotlight | pending (VM) | PASS-CONTAINER | checks D03-solid-colour, D03-spotlight (current.json, same allow-list) |
| W01 | Fenestra caption buttons (46 px, close #c42b1c on hover) on GTK 4/libadwaita, GTK 3, Qt, X11/Xwayland, Flatpak, Electron; always three buttons | pending (VM) | PARTIAL | GTK CSD windows keep their buttons (Notepad); server-side decoration in H6 |
| W02 | Rounded corners; square when snapped or maximized | pending (VM) | TODO |  |
| W03 | Snap to edges and quarters; layouts over maximize | pending (VM) | TODO |  |
| W04 | Alt+Tab, Task View, virtual desktops | pending (VM) | TODO |  |
| W05 | First login: never a half-built desktop (black → setup → black → desktop when smooth) | pending (VM) | TODO |  |
| L01 | Lock screen: Fenestra clock in the system language, Spotlight, network and battery state; really locks (Super+L, suspend) | pending (VM) | TODO |  |
| L02 | Direct fast unlock; user password prompt | pending (VM) | TODO |  |
| L03 | Login screen: clock over the background; key → the single account with its password; standard login if anything fails | pending (VM) | TODO |  |
| L04 | Fenestra Hello: face and fingerprint animations, live face while scanning, fingerprint fills bottom-up (real unlock SOLO-PORTÁTIL) | pending (VM) | TODO |  |
| L05 | Login guard turns off only the culprit, notifies, can be reverted; forced-failure test | pending (VM) | TODO |  |
| E01 | Explorer Home (Quick access; Recent, Favorites, Shared), Gallery, This PC with drive bars | pending (VM) | TODO |  |
| E02 | Sidebar icons, pins and separators; tabs in the title bar | pending (VM) | TODO |  |
| E03 | Command bar (New, Sort, View, Filter, Details); menus anchored under their button; details and preview panes | pending (VM) | TODO |  |
| E04 | Per-folder views, details view without sort arrow, status bar view buttons | pending (VM) | TODO |  |
| E05 | Context menus with icons, New ▸ templates, Copy as path, Open | pending (VM) | TODO |  |
| E06 | Address bar: path, edit mode, search | pending (VM) | TODO |  |
| C01 | Settings Home, System, Display (resolution, scale, orientation, multiple monitors, night light) | pending (VM) | TODO |  |
| C02 | Sound, Notifications, Power and battery (profiles), Storage, Multitasking, Clipboard, Project | pending (VM) | TODO |  |
| C03 | Bluetooth and devices (pairing), mouse and touchpad, keyboard, printers | pending (VM) | TODO |  |
| C04 | Network and internet (Wi-Fi, Ethernet, VPN, proxy, airplane mode) | pending (VM) | TODO |  |
| C05 | Personalization: light/dark, 48 accents + custom (#0078D4 default) everywhere; backgrounds; taskbar (B01, B05, B06); Start; lock screen; icon pack import | pending (VM) | TODO |  |
| C06 | Apps (installed, defaults, startup), Accounts (users, autologin, sign-in options with the Hello wizard) | pending (VM) | TODO |  |
| C07 | Time and language, Gaming, Accessibility, Privacy and security | pending (VM) | TODO |  |
| C08 | Fenestra Update: Fedora + Flatpak updates, Fenestra builds from GitHub with changelog, next Fedora release with checks and screens, «Migrar a KDE» | pending (VM) | TODO |  |
| C09 | Recovery: Reset this PC (keep files, remove everything) — VM only | pending (VM) | TODO |  |
| C10 | «Fenestra» section with the former GNOME options | pending (VM) | TODO |  |
| C11 | Read-only and demo modes; gnome-control-center <panel> opens the Fenestra Settings page | pending (VM) | TODO |  |
| T01 | Task Manager: Processes, Performance (CPU, memory, disk, network, GPU), App history, Startup apps, Users, Details, Services | pending (VM) | TODO |  |
| T02 | Ctrl+Shift+Esc and from Ctrl+Alt+Del; single instance; end task (VM only) | pending (VM) | TODO |  |
| O01 | OOBE on first boot: region, keyboard, network, device name, account, autologin, privacy, icon import, «Hi… this can take a few minutes» on black | pending (VM) | TODO |  |
| O02 | Works without a GPU (VM without acceleration) | pending (VM) | TODO |  |
| O03 | Anaconda installer with Fenestra name, art and boot menu; no account screens | pending (VM) | TODO |  |
| O04 | Plymouth «fenestra»: boot, reboot, shutdown, offline update with progress | pending (VM) | TODO |  |
| A01 | Notepad: tabs in the title bar, menus, Find/Replace, Go to, zoom, CRLF/LF/CR, encodings, Markdown preview, sessions, light/dark, printing | pending (VM) | TODO |  |
| A02 | Paint: tools, brushes, shapes, colours, layers, text, resize/skew, rotate/flip, zoom, image properties, light/dark | pending (VM) | TODO |  |
| A03 | Icon Extractor (on Windows): the pack is imported from Settings and the OOBE | pending (VM) | TODO |  |
| A04 | All apps: portal file chooser, notifications, printing, Fenestra icons and cursor, same sizes and fonts | pending (VM) | PARTIAL | Notepad starts from the taskbar under KWin (Wayland); portals and printing in H7 |
| M01 | Fedora release upgrade end to end in the VM (backup, simulation, download, offline restart, post-boot) | pending (VM) | TODO |  |
| M02 | Reset this PC in both modes, in the VM | pending (VM) | TODO |  |
| M03 | Laptop services: howdy-preload, galaxy-book-guard, camera relay watchdog, Howdy in GDM PAM, DKMS ov02c10, ipu-bridge-fix, max98390-hda (SOLO-PORTÁTIL) | SOLO-PORTÁTIL | SOLO-PORTÁTIL |  |
| M04 | Language: Fenestra UI in Spanish and English by system locale | pending (VM) | PARTIAL | shell strings es/en (design/Strings.qml) |
