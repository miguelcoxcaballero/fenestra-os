# Fenestra Shell migration inventory (GNOME Shell extensions → Qt6/QML shell on KWin)

This file lists, from the code, everything the GNOME layer of Fenestra does today, the
visual constants it uses, what it depends on inside GNOME, and where each piece goes in
the KWin architecture. It is meant to be grep-checked: every value carries `file:line`.

## Conventions

Path prefixes used in citations (all relative to the repository root):

| Prefix | Path |
|---|---|
| `tray/` | `desktop/extensions/fenestra-tray@fenestra-os.github.io/` |
| `spot/` | `desktop/extensions/fenestra-spotlight@fenestra-os.github.io/` |
| `lockclock/` | `desktop/extensions/fenestra-lock-clock@fenestra-os.github.io/` |
| `login/` | `desktop/extensions/fenestra-login@fenestra-os.github.io/` |
| `unlock/` | `desktop/extensions/fenestra-direct-unlock@fenestra-os.github.io/` |
| `ulp/` | `desktop/extensions/fenestra-user-lock-prompt@fenestra-os.github.io/` |
| `consent/` | `desktop/extensions/fenestra-consent@fenestra-os.github.io/` |
| `arc/` | `desktop/extensions/arcmenu@arcmenu.com/` |
| `dtp/` | `desktop/extensions/dash-to-panel@jderose9.github.com/` |
| `rwc/` | `desktop/extensions/rounded-window-corners@fxgn/` |
| `ding/` | `desktop/extensions/ding@rastersoft.com/` |
| `sysext/` | `extras/fedora-upgrade/system-extensions/` |
| `dconf/` | `desktop/dconf/` |
| `skel/` | `desktop/skel/` |
| `gtk/` | `desktop/gtk/` |
| `assets/` | `assets/generated/` |

"Reference" means the measured look the code comments describe ("like the reference").
Target names are the ones agreed for the new tree: `shell/qml/<area>`, `shell/src/services/<name>`,
`kwin/` (scripts/effects/decoration/tabbox), `design/tokens.json`.
Line numbers are those of the files at commit `c57df01` (branch `feature/fenestra-shell-kwin`). Files under `shell/`
are being written in parallel, so they are cited by name only (no line numbers).

Runtime facts shared by all Fenestra extensions:

- Asset lookup: `~/.local/share/fenestra/assets/<rel>` first, then `/usr/share/fenestra/assets/<rel>`
  (`tray/extension.js:29`, `consent/presentation.js:6`, `spot/hello.js:16`, `spot/lockStatus.js:7`,
  `arc/windowsSearchHome.js:8`, `arc/menulayouts/windowsPower.js:9`). The user copy exists because
  `fenestra-import-windows-assets` can drop user-owned replacements there (`THIRD-PARTY.md`).
  The new shell needs the same two-level lookup.
- Strings: most modules carry an inline English/Spanish table selected from `LANGUAGE`/`LC_MESSAGES`/`LANG`
  (e.g. `tray/calendarPanel.js:12-19`, `tray/securityScreen.js:20-30`). Qt translations (`qsTr` + `.ts`)
  replace all of them.
- Shell versions: every Fenestra extension declares GNOME Shell 49, 50, 51 (`*/metadata.json`).

## 1. Overview: piece → target

| Piece | Today (one line) | Target |
|---|---|---|
| `tray/extension.js` (clock, battery) | 2-line clock, battery glyph, wires all modules | `qml/taskbar` (clock), `qml/tray` (battery), `services/power` |
| `tray/appearance.js` | Light/dark + accent palette for shell, GTK, Dash to Panel, ArcMenu; SVG tinting | `design/tokens.json` (palette), theme singleton in shell, GTK wrapper writer in `services/session` |
| `tray/calendarPanel.js` | Notification centre card + calendar card + Focus timer | `qml/notifications` (centre), `qml/calendar`, `services/notifications` (DND), `services/calendar` |
| `tray/captionSync.js` | Copies GTK caption-button CSS to `~/.config` at login | `services/session` (login-time sync) or packaging; SSD side → `kwin/` decoration |
| `tray/flyoutGap.js` | All taskbar flyouts: no arrow, 12 px above taskbar, 13 px from edge | shared flyout placement in `qml/` + `design/tokens.json` |
| `tray/mediaPanel.js` | Media card above quick settings | `qml/quicksettings` (media card), `services/media` (MPRIS) |
| `tray/notifications.js` | Banner bin bottom-right, -12 px (not imported: dead code) | `qml/notifications` (toast position) |
| `tray/osdStyle.js` | 192×48 volume/brightness/mic flyout | `qml/osd`, `services/audio`, `services/brightness` |
| `tray/overviewBlock.js` | Disables Activities overview and swipes | not needed under KWin (no overview); keep KWin Overview/gestures off in `kwinrc` |
| `tray/powerSource.js` | AC-online truth from udev `power_supply` | `services/power` |
| `tray/pressAnimation.js` | Taskbar icon press shrink 0.82 | `qml/taskbar` (TaskButton) |
| `tray/previewStyle.js` | Blur + 3 px gap on Dash to Panel thumbnails | `qml/taskbar` (thumbnail flyout), `services/windows` |
| `tray/privacyIcons.js` | Mic/camera/location tray glyphs + tooltips | `qml/tray`, `services/privacy` |
| `tray/quickPanel.js` | 3-column quick settings with captions, footer | `qml/quicksettings`, services network/bluetooth/audio/brightness/power |
| `tray/screenshotToast.js` | Screenshot notification as a thumbnail toast | `qml/notifications` (image toast) |
| `tray/securityScreen.js` | Ctrl+Alt+Del full-screen menu | `qml/security`, `services/session`, KWin global shortcut |
| `tray/taskbarMenu.js` | Right-click empty taskbar → Task Manager / Taskbar settings | `qml/taskbar` |
| `tray/taskbarSearch.js` | Search icon / icon+label / box on taskbar | `qml/taskbar` (+ `ShellSettings.searchMode`) |
| `tray/taskbarStyle.js` | Accent running "dash" under focused app | `qml/taskbar` (TaskButton) |
| `tray/trayLayout.js` | Tray order, paddings, overflow chevron, ENG/ESP keyboard label | `qml/tray`, `services/keyboard`, `services/bluetooth` |
| `tray/weatherWidget.js` | Weather at the left end of a centred taskbar | `qml/taskbar` (widget), `services/weather` |
| `tray/stylesheet.css`, `tray/light.css` | All dark/light shell styling | `design/tokens.json` |
| `tray/schemas/*` | `org.fenestra.desktop` + security shortcut key | `~/.config/fenestra/shell.conf` (`ShellSettings`), KWin shortcut |
| `consent/` | Polkit dialog restyled as consent prompt | `qml/security` (consent dialog) + polkit agent in `services/session` |
| `unlock/` (disabled by default) | Lock screen goes straight to password | `qml/lock` (behaviour option) |
| `ulp/` (disabled by default) | Lock screen shows account name instead of clock | `qml/lock` (behaviour option) |
| `lockclock/` | Lock clock face, prompt transition, fast unlock | `qml/lock` |
| `login/` | GDM: clock curtain, auto-select single user, race guard | stays with GDM if GDM remains the greeter; otherwise greeter theme (outside listed targets) |
| `spot/` | Lock/login background, status, face-auth animation, startup cover, first-login curtain, panel guard, unlock fade | `qml/lock`, `qml/firstlogin`, `qml/desktop`; panel guard not needed |
| `sysext/windows-spotlight@local`, `sysext/single-user-gdm@local` | Older laptop copies of `spot/` and `login/` | not migrated (superseded) |
| ArcMenu (patched) | Start menu, Search flyout, acrylic, slide motion, power/account menus | `qml/start`, `qml/search`, `services/apps`, `services/search`, KWin blur |
| Dash to Panel (configured, 1 fix) | The taskbar | `qml/taskbar`, `services/windows` |
| Blur my Shell (configured) | Taskbar and popup blur | KWin blur (blur-behind on shell surfaces) |
| DING (patched) | Desktop icons, "New" menu, folder icons | `qml/desktop` |
| Rounded Window Corners (patched) | 8 px window corners, square when snapped | `kwin/` rounded corners |
| Tiling Assistant (configured) | Super+arrows halves/quarters | `kwin/` Snap Layouts + KWin quick tiling |
| Notification Banner (configured) | Banners bottom-right 12 px | `qml/notifications` |
| No Screenshot Box (default settings) | Empty initial screenshot selection | not needed under KWin (GNOME screenshot UI only) |
| Resources (assets, themes, skel, dconf, fonts, icons, cursor, Plymouth, docs/images) | see section 6 | mostly reused as-is; see per item |

---

## 2. fenestra-tray@fenestra-os.github.io

Metadata: name "Fenestra Taskbar & Tray", session mode `user` only, settings schema
`org.gnome.shell.extensions.fenestra-tray` (`tray/metadata.json:2-15`).

### 2.1 extension.js (entry point, clock, battery)

What it does:
- Installs every module in order; each wrapped so one failure does not stop the rest (`tray/extension.js:32-75`).
- Disables the icon "zoom out" launch animation of `BaseIcon` (`tray/extension.js:39-40`).
- Clock: replaces the panel clock text with two lines `HH:MM` (24 h, `hourCycle:'h23'`) and the date
  `dd/mm/yyyy` in the locale's order (`tray/extension.js:88-92`), letter spacing `-500` Pango units
  (`tray/extension.js:92`), right-aligned (`tray/extension.js:83-84`). Refreshes on the clock's
  `notify::clock` and on a 60 s timer (`tray/extension.js:69-74`).
- Battery: picks one of the generated SVGs `battery/<state>-<charging 0|1>-<level 0..10>.svg`
  (`tray/extension.js:113`). `level = round(percent/10)` (`tray/extension.js:108`); state is
  `charging` (on AC and charging/full/≥98 %), `plugged` (on AC, not charging), `low` (≤10 %), `saver`
  (power-profiles `power-saver`), else `normal` (`tray/extension.js:109-112`). ≥98 % is shown as 100 %
  (`tray/extension.js:104-105`). The percentage label is hidden; the percentage becomes the title of
  the quick-settings power item (`tray/extension.js:106-107`). AC state prefers udev (`powerSource.js`),
  falls back to UPower `on-battery` (`tray/extension.js:103`). Glyph tinted for the current mode via
  `Appearance.tint()` (`tray/extension.js:113`).

Visual parameters:
- Clock font "Fenestra Taskbar Text" 12 px weight 400, margin-top 1 px (`tray/extension.js:83`); trayLayout later
  sets letter-spacing -0.4 px and margin 0 (`tray/trayLayout.js:58`).
- Battery indicator icon 20 px, min 20×20 (`tray/extension.js:117`); footer icon 20 px (`tray/extension.js:115`);
  footer title "Segoe UI" 12 px 400 (`tray/extension.js:116`); hidden % label min-width 36 px (`tray/extension.js:118`).

GNOME dependencies: `DateMenuButton.prototype._init`, `Indicator.prototype._sync` of `ui/status/system.js`
(overrides, `tray/extension.js:45-46`), `BaseIcon.prototype.animateZoomOut*` (`tray/extension.js:39-40`),
`Main.panel.statusArea.dateMenu` / `quickSettings._system` / `_powerProfiles` internals,
UPowerGlib client (D-Bus `org.freedesktop.UPower`), power-profiles proxy `ActiveProfile`.

New architecture:
- Clock → `qml/taskbar` (already started in `shell/qml/taskbar/Taskbar.qml`, which wakes on the minute; the GNOME
  version uses a plain 60 s timer). Keep 24 h + locale date order and the tighter letter spacing.
- Battery → `qml/tray` battery glyph using the same asset naming; data from `services/power`
  (UPower device + udev `online` + power-profiles-daemon `ActiveProfile`).
- Icon zoom-out suppression: not needed under KWin.

### 2.2 appearance.js (mode + accent for the whole desktop)

What it does (`tray/appearance.js:7-23` describes it):
- Inputs: `org.gnome.desktop.interface color-scheme` and `accent-color`; `org.fenestra.desktop accent-color-custom`
  and `accent-from-wallpaper` (`tray/appearance.js:25-26`, `tray/appearance.js:215-221`).
- Accent resolution order: wallpaper accent (if enabled) → custom `#rrggbb` → GNOME enum → `blue`
  (`tray/appearance.js:231-241`).
- Palette (`tray/appearance.js:85-104`): for each GNOME enum a fixed triple [base, fill on dark, fill on light]
  (`tray/appearance.js:28-34`); for a custom colour the dark fill is the colour lightened (mix 10 % white per step)
  until contrast ≥ 3 against `#202020` (`tray/appearance.js:90`) and the light fill is `darker()` = HSL lightness −0.08
  then −0.01 steps until contrast ≥ 4.5 against white (`tray/appearance.js:72-77`).
  Derived: `on` = black if luminance > 0.25 else white (`tray/appearance.js:83`); `text` = dark: `lighter(darkFill)`
  (HSL L to 0.72, S×1.5) / light: lightFill (`tray/appearance.js:78-81`, `tray/appearance.js:98`);
  `hover` = dark: mix fill 15 % white / light: 10 % white (`tray/appearance.js:99`);
  `press` = dark: mix 14 % black / light: 20 % white (`tray/appearance.js:100`).
- Wallpaper accent: wallpaper scaled to 32×32, every 2nd pixel, score = S×(1−|L−0.5|×2), best pixel
  re-mapped to S clamped 0.25–0.75 and L 0.42 (`tray/appearance.js:141-156`).
- Outputs (all live, coalesced in one idle, `tray/appearance.js:248-266`):
  1. `Main.uiGroup` classes `fenestra-themed` and (light) `fenestra-light` (`tray/appearance.js:256-258`), which
     switch `light.css`.
  2. A generated accent stylesheet `~/.cache/fenestra/shell-accent-{0,1}.css` (alternating names, St caches per file)
     covering checked toggles, default buttons, today in calendar, switches, check boxes, sliders, OSD level,
     entry focus underline, focus rings, menu active items, screenshot toast button, consent dialog, ArcMenu search
     filters/indicator/preview buttons (`tray/appearance.js:159-189`, `tray/appearance.js:268-275`).
  3. GTK: `~/.config/gtk-4.0/fenestra-accent.css` with `@fenestra_accent_dark/light(_fg)` and libadwaita CSS
     variables `--accent-bg-color/--accent-fg-color/--accent-color` per scheme (`tray/appearance.js:281-286`);
     a wrapper GTK theme `~/.local/share/themes/<Family>-<Dark|Light>-Accent<A|B>` that imports the base theme and
     defines `accent_bg_color`, `accent_fg_color`, `accent_color`, `theme_selected_*` (`tray/appearance.js:192-201`),
     alternating A/B so running GTK3 apps reload; sets `gtk-theme` to it (`tray/appearance.js:297-313`). In light mode
     `gtk-dark.css` also points at the light CSS (`tray/appearance.js:294-300`).
  4. Dash to Panel keys (taskbar colours, see token list) (`tray/appearance.js:316-333`).
  5. ArcMenu keys (menu colours) (`tray/appearance.js:335-348`).
  6. `tint(path)`: recoloured copies of white SVG glyphs into `~/.cache/fenestra/tint/<d|l><text>/` — `#ffffff|#eeeeee`
     → `#ffffff` (dark) / `#1a1a1a` (light); `#9fd89f` (charging fill) → accent text; light mode also
     `#ff99a4|#e5484d` → `#c42b1c` and `#fce100|#e5a900` → `#9d5d00`; cache ≤256 entries (`tray/appearance.js:351-382`).
- Re-applies when Dash to Panel or ArcMenu are (re)enabled (`tray/appearance.js:224-226`).

GNOME dependencies: St theme context (`load_stylesheet/unload_stylesheet`), `Main.uiGroup`,
`Main.extensionManager` (lookup of other extensions' schemas), gsettings
`org.gnome.desktop.interface {color-scheme, accent-color, gtk-theme}`, `org.gnome.desktop.background {picture-uri, picture-uri-dark}`,
`org.fenestra.desktop`, Dash to Panel and ArcMenu schemas.

New architecture:
- Palette maths → one shared implementation (C++ theme singleton reading `design/tokens.json` +
  `ShellSettings.colorScheme/accentColor`). The enum table and derivation rules must move unchanged so GTK apps,
  Fenestra Settings and the shell agree.
- `accent-from-wallpaper` has no key in `shell/src/core/shellsettings.h` yet (only `Appearance/Accent`): add one.
- GTK wrapper theme + `fenestra-accent.css` writer → `services/session` (still needed: GTK apps keep running under KWin).
- Qt/KDE apps and the KWin decoration additionally need a KDE colour scheme (`kdeglobals` accent) — new work.
- Dash to Panel / ArcMenu key sync and the St stylesheet generation: not needed under KWin.
- `tint()` → keep for the shared white SVG assets, or recolour in QML (`ColorOverlay`/`MultiEffect` colorization).

### 2.3 calendarPanel.js (notification centre + calendar flyout)

What it does:
- Turns the date menu into two independent floating cards with no shared surface: notifications on top, calendar
  below (`tray/calendarPanel.js:52-56`, `tray/calendarPanel.js:59-62`).
- Notifications card: heading "Notifications", a Do-not-disturb icon button that toggles
  `org.gnome.desktop.notifications show-banners` and reflects it as checked (`tray/calendarPanel.js:63-67`,
  `tray/calendarPanel.js:82-84`), the native "Clear all" button moved into the heading, shown only when there are
  notifications (`tray/calendarPanel.js:68-81`); placeholder "No new notifications" without icon
  (`tray/calendarPanel.js:85-86`).
- Calendar card: header with the long date ("weekday, month day") and a collapse chevron (`tray/calendarPanel.js:95-105`);
  collapsing hides the month grid, state kept for the session (`tray/calendarPanel.js:36`, `tray/calendarPanel.js:216-224`).
  Month header "Month YYYY" on the left with ▲ / ▼ text glyphs for previous/next (`tray/calendarPanel.js:107-123`).
  Weekday headings = first two letters of the locale names (`tray/calendarPanel.js:125-133`). Grid starts on the
  week containing the 1st (shifts GNOME's grid by 7 days when needed), no leading zeros, `calendar-today` /
  `calendar-other-month` classes (`tray/calendarPanel.js:135-159`).
- Focus footer: duration default 30 min, −/+ by 5 within 5–240 (`tray/calendarPanel.js:162-170`); "Focus" button starts
  a countdown `m:ss`, turns banners off and restores the prior value at the end or on "End session"
  (`tray/calendarPanel.js:180-203`).
- Sizing: notification card `max-height = max(120, workArea.height − calendarHeight − 3×12)` (`tray/calendarPanel.js:206-215`).
- Blur my Shell: moves its popup blur from the menu box to the menu actor (`tray/calendarPanel.js:30-34`,
  `tray/calendarPanel.js:231-237`).

Visual parameters (`tray/stylesheet.css`):
- Cards 332 px wide, radius 8, bg `rgba(28,28,28,.96)`, border 1 px `rgba(255,255,255,.08)`, shadow `0 8px 16px rgba(0,0,0,.28)`,
  font "Segoe UI Variable" 14 px (`tray/stylesheet.css:220-226`); calendar card bg `rgba(36,36,36,.97)` (`tray/stylesheet.css:286`).
- Stack spacing 12, padding `12 13 0 12` (`tray/stylesheet.css:219`); comment: 334 px, 12 apart, 13 from edge, 12 above
  taskbar (`tray/stylesheet.css:207-209`); GAP 12 (`tray/calendarPanel.js:20`).
- Icon buttons 22×22 radius 4, bg `rgba(255,255,255,.06)`, border `rgba(255,255,255,.08)`, hover `.10`, active `.04`
  glyph `.78`, checked accent, focus 1 px white (`tray/stylesheet.css:227-236`); icons 16 px, footer/collapse 12 px
  (`tray/stylesheet.css:231-232`).
- Heading padding `11 16`, title 14 px 600 (`tray/stylesheet.css:239-240`); Clear all 22 px tall, padding `0 10`, 12 px
  (`tray/stylesheet.css:241-245`).
- Notification row: bg `#242424`, hover `#2a2a2a`, radius 6 (`tray/stylesheet.css:254-258`); header padding `10 8 0 12`
  (`tray/stylesheet.css:259`); source icon 16 (`tray/stylesheet.css:260`); source/time 12 px, time `#c5c5c5`
  (`tray/stylesheet.css:262-263`); expand/close 24×24, glyph 12 (`tray/stylesheet.css:264-271`); body padding
  `12 12 14`, app icon 48 px radius 4 (`tray/stylesheet.css:272-273`); title 14 px white, body 14 px `#c5c5c5`
  (`tray/stylesheet.css:275-276`); action buttons 32 px, padding `0 12`, 14 px (`tray/stylesheet.css:279-283`);
  placeholder padding `16 0 28`, `#c5c5c5` (`tray/stylesheet.css:248`).
- Calendar header 48 px, padding `0 16`, bg `rgba(28,28,28,1)`, radius `7 7 0 0`, bottom border `#191919`
  (`tray/stylesheet.css:287-291`); month header 56 px (`tray/stylesheet.css:297`); month label 14 px 600
  (`tray/stylesheet.css:298-300`); pager buttons 39×32 `#9d9d9d`, glyph 9 px (`tray/stylesheet.css:303-307`);
  weekday cells 47×24, padding `10 0 8` (`tray/stylesheet.css:308-311`); day cells 40×40, radius 20, margin `1 3 1 4`,
  tabular numbers (`tray/stylesheet.css:312-316`); hover `.06`, selected inset 1 px accent, other month `#7f7f7f`,
  today accent fill / black text (`tray/stylesheet.css:317-321`).
- Focus footer 48 px, top border `#191919`, radius `0 0 7 7` (`tray/stylesheet.css:325-328`); Focus button 22 px
  (`tray/stylesheet.css:330-335`).
- Light mode overrides: cards `rgba(243,243,243,.94)`, calendar card `rgba(249,249,249,.94)`, rows `rgba(255,255,255,.85)`
  etc. (`tray/light.css:135-186`).

GNOME dependencies: `Main.panel.statusArea.dateMenu` internals (`_messageList`, `_calendar`, `_date`,
`_displaysSection`, `_calendar._rebuildCalendar/_buttons/_topBox/_monthLabel`), gsettings
`org.gnome.desktop.notifications show-banners`, Blur my Shell's `stateObj._popup` API.

New architecture: `qml/notifications` (centre card, DND, Clear all, grouping per app), `qml/calendar` (month grid,
collapse, Focus footer), `services/notifications` (our own `org.freedesktop.Notifications` server: history, DND,
Focus timer), `services/calendar` (events: GNOME's date menu showed Evolution Data Server events; decide whether
to keep EDS). Under KWin nothing provides a notification server unless the shell does.

### 2.4 captionSync.js

What it does: at login copies `/usr/share/fenestra/gtk-{3,4}.0/caption-buttons.css` to
`~/.config/gtk-{3,4}.0/fenestra-caption-buttons.css` when the bytes differ (`tray/captionSync.js:9-29`), because Flatpak
apps can read `~/.config/gtk-*` but not `/usr/share/fenestra` (`tray/captionSync.js:4-8`). The user `gtk.css` imports
that copy (`skel/.config/gtk-4.0/gtk.css:4`, `skel/.config/gtk-3.0/gtk.css:2`).

GNOME dependencies: none beyond running inside the shell at login.

New architecture: still needed (GTK CSD apps keep drawing their own buttons under KWin): run from
`services/session` at shell start, or a systemd user oneshot. The CSS itself is described in 6.4.

### 2.5 flyoutGap.js

What it does: for every BoxPointer opened from a horizontal taskbar (inside a Dash to Panel panel box, or centred on
it), removes the arrow and rise (`tray/flyoutGap.js:52-60`) and, after GNOME's own placement, puts the bottom edge
exactly `FLYOUT_GAP` above the taskbar and clamps x to `FLYOUT_EDGE` from the monitor edges (`tray/flyoutGap.js:61-92`).
The calendar menu positions itself (`tray/flyoutGap.js:68-69`).

Visual parameters: `FLYOUT_GAP = 12`, `FLYOUT_EDGE = 13` logical px, multiplied by scale (`tray/flyoutGap.js:11-12`,
`tray/flyoutGap.js:74-76`). ArcMenu repeats the 12 (`arc/windowsPopupMotion.js:19-22`).

GNOME dependencies: `BoxPointer.prototype.open` and `_reposition` overrides.

New architecture: one QML "Flyout" base used by start, search, quicksettings, calendar, tray menus: layer-shell
anchored bottom with margin `taskbar height + 12` and horizontal margins ≥13. Tokens `flyout.gap`, `flyout.edge`.

### 2.6 mediaPanel.js

What it does: inserts a separate card above the quick settings surface (`tray/mediaPanel.js:7-10`) showing the first
MPRIS player that can play and is `Playing` (`tray/mediaPanel.js:19`): app name, title (fallback "Reproduciendo"),
artists, 64 px cover art (fallback `audio-x-generic`), previous / play-pause / next (`tray/mediaPanel.js:11-20`).
Hidden when nothing plays. Accessible names are Spanish-only ("Anterior", "Pausar", "Siguiente"; `tray/mediaPanel.js:17`).

Visual parameters: card 350 px, padding `22 24`, spacing 20 (`tray/stylesheet.css:342`; an earlier rule says 360,
`tray/stylesheet.css:202-206`), bg `rgba(32,32,36,.80)`, border `rgba(255,255,255,.12)`, radius 8
(`tray/stylesheet.css:203-204`); stack spacing 12 (`tray/stylesheet.css:341`); app 13 px, title 15 px 600, artist 13 px
(`tray/stylesheet.css:343-346`); art radius 4 (`tray/stylesheet.css:347`); controls spacing 24, buttons padding 6
radius 4, icon 22 (`tray/stylesheet.css:348-351`, `tray/mediaPanel.js:16`). Light: `tray/light.css:126-132`.

GNOME dependencies: `dateMenu._messageList._messageView._mediaSource` (shell's MPRIS source), quick settings
`menu.box` parent.

New architecture: `qml/quicksettings` media card; `services/media` (MPRIS over D-Bus `org.mpris.MediaPlayer2.*`).

### 2.7 notifications.js (not loaded)

What it does: would anchor `Main.messageTray._bannerBin` to END/END with translation −12/−12
(`tray/notifications.js:6-23`). `installNotificationPosition` is not imported by `tray/extension.js`; banner
placement is done by the Notification Banner extension instead (section 5.7).

New architecture: `qml/notifications` toast placement (bottom-right, 12 px from the work area).

### 2.8 osdStyle.js (volume / brightness flyout)

What it does: replaces GNOME's OSD for level OSDs (volume, display brightness, keyboard backlight, microphone) with a
pill centred horizontally `GAP` above the work-area bottom (`tray/osdStyle.js:99-107`). Glyph mapping
(`tray/osdStyle.js:30-40`): speaker 0 (0 %), 1 (<34 %), 2 (<67 %), 3, mute; brightness; keyboard; mic / mic-off.
Microphone mute without a level shows glyph + text "Microphone muted/on" (`tray/osdStyle.js:192-197`). Other OSDs
(caps lock, display switch) keep GNOME's window, restyled (`tray/stylesheet.css:388-403`). Fades in with an 8 px rise,
out with a 4 px drop (`tray/osdStyle.js:124-158`); unredirect disabled while visible (`tray/osdStyle.js:128`,
`tray/osdStyle.js:152`). Value label 0–100 (`tray/osdStyle.js:118`). One flyout per monitor (`tray/osdStyle.js:178-185`).

Visual parameters:
- `HIDE_TIMEOUT 1500 ms`, `FADE_TIME 150 ms`, `SLIDE 8`, `GAP 24` (`tray/osdStyle.js:12`); in EASE_OUT_CUBIC,
  out EASE_IN_QUAD (`tray/osdStyle.js:134-135`, `tray/osdStyle.js:156-157`); fallback bottom = monitor − 48 if no work
  area (`tray/osdStyle.js:105`).
- Pill min-width 192 (level mode fixed 192), height 48, padding `0 16`, spacing 12, bg `rgba(32,32,32,.85)`, border
  `rgba(255,255,255,.08)`, radius 8, shadow `0 8px 16px rgba(0,0,0,.26)`, font "Segoe UI Variable", "Selawik"
  (`tray/stylesheet.css:372-383`); icon 16 (`tray/stylesheet.css:384`, `tray/osdStyle.js:52`); slider area 20 px tall
  (`tray/stylesheet.css:385`); value 14 px, min-width 24, right aligned (`tray/stylesheet.css:386`).
- Slider drawn in Cairo: track width 4, round caps, thumb radius 9, track colour dark `rgba(255,255,255,.54)` / light
  `rgba(0,0,0,.45)`, fill = accent `text` colour, thumb disc dark `rgb(69,69,69)` (0.27) / light white, ring 1 px dark
  `rgba(255,255,255,.09)` / light `rgba(0,0,0,.08)`, inner accent dot radius 5 (`tray/osdStyle.js:69-97`).
- Fallback accent table "light accents on dark" (`tray/osdStyle.js:14-15`).
- Light: pill `rgba(249,249,249,.92)`, border `rgba(0,0,0,.06)`, shadow `0 8px 16px rgba(0,0,0,.14)` (`tray/light.css:207-213`).
- Generic OSD window: padding `12 16`, margin-bottom 72, level bar 4 px (`tray/stylesheet.css:389-403`).

GNOME dependencies: `OsdWindowManager.prototype._showOsdWindow/show/hideAll` overrides; icon names coming from
gnome-settings-daemon media keys; `org.gnome.desktop.interface accent-color`.

New architecture: `qml/osd` (one window per screen, layer-shell overlay). Triggers: `services/audio`
(PipeWire/Pulse volume and mute), `services/brightness` (backlight + keyboard backlight). Under KWin the media keys
are not handled by gnome-settings-daemon: the shell (or a KDE daemon that then calls an OSD D-Bus interface) must own
them — decision needed.

### 2.9 overviewBlock.js

What it does: makes `Main.overview.show/showApps/toggle` no-ops and keeps the overview and workspace swipe trackers
disabled (`tray/overviewBlock.js:5-18`).

New architecture: not needed under KWin (there is no GNOME overview). Equivalent hygiene: keep KWin's Overview /
Grid / Desktop-cube effects, touchpad gesture bindings and screen edges off in the shipped `kwinrc`, except the
Task View we build (`kwin/` Task View).

### 2.10 powerSource.js

What it does: reads `power_supply` devices from udev; any non-battery supply with `online` 0/1 decides AC state, which
wins over a briefly stale UPower `CHARGING` (`tray/powerSource.js:3-21`).

New architecture: `services/power` (udev via libudev or `/sys/class/power_supply/*/online` + UPower).

### 2.11 pressAnimation.js

What it does: while a taskbar app icon or the Start button is pressed, the glyph shrinks to 0.82 and springs back
(`tray/pressAnimation.js:6-61`). Start opens on press and grabs input, so release is detected by polling the pointer
button mask every 30 ms (`tray/pressAnimation.js:32-41`). Honours "enable animations" (`tray/pressAnimation.js:24`).

Visual parameters: press scale 0.82, 90 ms EASE_OUT_QUAD (`tray/pressAnimation.js:50`); release to 1.0, 180 ms
EASE_OUT_BACK (`tray/pressAnimation.js:29`); pivot centre (`tray/pressAnimation.js:23`).

GNOME dependencies: stage `captured-event`, Dash to Panel / ArcMenu actor internals.

New architecture: `qml/taskbar/TaskButton.qml` (`scale` behaviour on `pressed`); tokens `motion.press.*`.

### 2.12 previewStyle.js

What it does: adds a background blur to Dash to Panel's window-preview menu and a 3 px bottom margin
(`tray/previewStyle.js:4-19`); re-hooks on `panels-created` and every 30 s (`tray/previewStyle.js:23-35`).

Visual parameters: `GAP = 3`, `BLUR = 30`, brightness 1.0 (`tray/previewStyle.js:5`, `tray/previewStyle.js:14`). The
preview itself is configured in Dash to Panel (section 5.2: size 152, padding 8, title 13 px, 170 ms).

New architecture: `qml/taskbar` thumbnail flyout. Live thumbnails of other clients from a layer-shell client need a
KWin-side source (PipeWire window streams or a KWin script/effect) — design decision; `services/windows`.

### 2.13 privacyIcons.js

What it does: restyles GNOME's microphone/camera/location privacy indicators into 16 px foreground-coloured glyphs
(`tray/privacyIcons.js:73-105`, `assets/privacy/{mic,camera,location}.svg`) and adds hover tooltips: "<App> is using
your microphone" / "N apps are using your microphone" / generic camera and location text (`tray/privacyIcons.js:13-21`,
`tray/privacyIcons.js:35-51`). Source outputs of `org.gnome.VolumeControl`, `org.PulseAudio.pavucontrol`,
`org.gnome.Settings` are ignored (`tray/privacyIcons.js:23`). GNOME's visibility logic is kept.

Visual parameters: glyph 16 px (`tray/privacyIcons.js:103`); tooltip uses `.dash-label` style (section 2.22), centred
on the icon, ≥4 px from monitor edges, 10 px above a bottom taskbar (or 32 px below a top panel)
(`tray/privacyIcons.js:53-67`).

GNOME dependencies: `quickSettings._volumeInput/_camera/_location` indicators, Gvc mixer control source outputs.

New architecture: `qml/tray` privacy glyphs; `services/privacy` (PipeWire: capture streams for mic and camera
nodes with app names; GeoClue clients for location).

### 2.14 quickPanel.js

What it does: switches the quick-settings grid to 3 columns (`tray/quickPanel.js:13`); wraps every toggle in a tile
with the title moved to a caption below a square-ish button, icon centred (`tray/quickPanel.js:15-30`); orders sliders
brightness first then volume, full width (`tray/quickPanel.js:31-40`); moves the system item (battery etc.) out of the
grid into a footer and hides its Screenshot, Lock and Shutdown buttons (`tray/quickPanel.js:43-48`).

Visual parameters (`tray/stylesheet.css:123-143`): panel min-width 400, radius 8; grid column spacing 12, row spacing 18,
margin 20; tile 104 px wide, spacing 6; button 48 px tall radius 4, border `rgba(255,255,255,.10)`, padding `0 10`;
icon 18; split menu button 28 px wide, arrow 12; caption 12 px 400; slider padding `4 0`; footer bg `rgba(0,0,0,.14)`,
top border `rgba(255,255,255,.08)`, padding `10 20`, radius `0 0 8 8`; footer buttons 28×28. Checked hover/active
fallbacks `#7b937b` / `#566e56` (`tray/stylesheet.css:354-358`, overridden by the generated accent CSS).
Light: `tray/light.css:96-125`.

GNOME dependencies: `QuickToggle`, `QuickMenuToggle`, `QuickSlider` classes and the quick settings grid layout.

New architecture: `qml/quicksettings`. Tiles are fed by `services/network` (NetworkManager: Wi-Fi, airplane),
`services/bluetooth` (BlueZ), `services/power` (power profile / battery saver, battery footer), `services/audio`
(volume slider, output selector), `services/brightness` (slider), night light (KWin night colour D-Bus), accessibility.
Edit/settings button in the footer opens `fenestra-settings`.

### 2.15 screenshotToast.js

What it does: when a notification titled "Screenshot captured" (EN/ES variants, `tray/screenshotToast.js:8`) carries an
image, renames its source to "Snipping Tool", title "Screenshot copied to clipboard", body "Automatically saved to
screenshots folder.", relabels the first action "Mark-up and share" which opens the image
(`tray/screenshotToast.js:10-21`); the banner gets a thumbnail on top, no app icon, no time, always expanded
(`tray/screenshotToast.js:25-41`).

Visual parameters: thumbnail width 330, height `min(160, 330 × aspect)` (`tray/screenshotToast.js:32`); toast 362 px,
padding-bottom 12, radius 8 (`tray/stylesheet.css:364`); preview bg `rgba(255,255,255,.06)`, radius `8 8 0 0`, padding
`12 16` (`tray/stylesheet.css:365`); title/body 14 px, source 12 px, button min-height 32 (`tray/stylesheet.css:366-369`);
first button accent (`tray/appearance.js:180`).

GNOME dependencies: `MessageTray.Source.prototype.addNotification`, `_bannerBin` children.

New architecture: `qml/notifications` supports image notifications (`image-path`/`image-data` hints) with the
thumbnail layout; the screenshot tool under KWin (e.g. Spectacle or our own) sends the notification. Wording belongs
to the screenshot tool, not the shell.

### 2.16 securityScreen.js (Ctrl+Alt+Del)

What it does:
- Compositor keybinding `security-screen` (default `<Control><Alt>Delete`, `<Control><Alt>KP_Delete`), ignores
  autorepeat, non-maskable, all action modes (`tray/securityScreen.js:63-65`, `tray/schemas/org.gnome.shell.extensions.fenestra-tray.gschema.xml:4-5`).
  GNOME's logout binding is cleared for it (`dconf/local.d/10-fenestra-theme:38-39`).
- Full-screen black screen on top of the stage, built once at low-priority idle (`tray/securityScreen.js:46-54`),
  modal grab `SYSTEM_MODAL` (`tray/securityScreen.js:202`); closes when the session locks (`tray/securityScreen.js:66`);
  not shown in lock or greeter (`tray/securityScreen.js:193`).
- Items: Lock, Switch user, Sign out, Change a password, Task Manager; Cancel (`tray/securityScreen.js:100-122`).
  Corner buttons Network, Accessibility, Power, each with a small menu (`tray/securityScreen.js:124-138`):
  Network header (connection name, Connected / No internet access / Not connected) + Wi-Fi switch
  (`tray/securityScreen.js:360-370`); Accessibility switches Magnifier, Narrator (screen reader), On-screen keyboard,
  Sticky keys, High contrast (`tray/securityScreen.js:372-382`); Power Sleep, Shut down, Restart
  (`tray/securityScreen.js:384-390`).
- Actions: lock `screenShield.lock(true)`; switch user via SystemActions or `gdmflexiserver`; sign out
  `SessionManager.Logout(1)` (no confirmation); Shut down/Restart auto-confirm GNOME's 60 s end-session dialog;
  Change a password → `fenestra-settings --page signin` (or GNOME Settings users); Task Manager → first of
  `org.fenestra.TaskManager`, Resources, GNOME System Monitor (`tray/securityScreen.js:393-441`, `tray/securityScreen.js:68-82`).
- Keyboard: Esc closes; Up/Down cycle the list (wrapping), Left/Right/Up/Down move in the corner row, Tab/Shift+Tab
  cycle all, Enter/Space activate; everything else swallowed (`tray/securityScreen.js:231-263`); menus have their own
  Up/Down/Enter/Esc (`tray/securityScreen.js:334-343`). Focus rectangle: items 2 px outline 3 px above/below the row,
  buttons 3 px around (`tray/securityScreen.js:179-190`).

Visual parameters:
- Geometry from a 1920×1080 capture, relative to the primary monitor centre: list x −72, item width ≥139 (text + 19),
  first item y −177, row height 44; Cancel y +83, 120×32; corner buttons 40×40 at 168/120/72 px from the right,
  62 px from the bottom (`tray/securityScreen.js:33-36`, `tray/securityScreen.js:152-177`). Menus 12 px from screen edges,
  8 px above their button (`tray/securityScreen.js:317-320`).
- CSS (`tray/stylesheet.css:405-454`): bg `#000000`, text white 14 px 400; item padding `0 10 2 9`, hover `.06`, active `.04`
  glyph `.79`; focus 2 px white, radius 0; Cancel bg `#333333` hover `#3b3b3b` active `#2b2b2b` radius 4; corner radius 4,
  icon 16; menu bg `#2c2c2c`, border `rgba(255,255,255,.08)`, radius 8, shadow `0 8px 16px rgba(0,0,0,.36)`, padding 4,
  min-width 200; menu item min-height 36, padding `0 12`, radius 4; header padding `8 12 10 12`, title 14 px 600,
  sub 12 px `rgba(255,255,255,.79)`. Light mode keeps it dark (`tray/light.css:6`).
- Icons `assets/security/*.svg` 16 px (`tray/securityScreen.js:85-87`).

GNOME dependencies: `Main.wm.addKeybinding`, `Main.pushModal`, `Main.screenShield`, `Main.endSessionDialog.OpenAsync`
monkey-patch, `GnomeSession.SessionManager` (D-Bus `org.gnome.SessionManager`), `LoginManager` (logind D-Bus),
`SystemActions`, NetworkManager client from quick settings, gsettings `org.gnome.desktop.a11y.{applications,interface,keyboard}`.

New architecture: `qml/security` (layer-shell overlay, exclusive keyboard) + `services/session` (logind Lock/Suspend,
session logout/reboot/poweroff without dialog, switch user via the display manager), `services/network` (Wi-Fi switch),
accessibility toggles (KWin/Orca/Maliit equivalents). Shortcut: KWin global shortcut. KWin/ksmserver binds
Ctrl+Alt+Del to log out by default; the shipped config must free it.

### 2.17 taskbarMenu.js

What it does: right-click on an empty part of the taskbar opens a small menu "Task Manager" (`fenestra-taskmgr`) and
"Taskbar settings" (`fenestra-settings --page taskbar`) (`tray/taskbarMenu.js:12-16`, `tray/taskbarMenu.js:42-45`). It
intercepts Dash to Panel's hidden Show-Apps context menu when the source is the dummy cursor
(`tray/taskbarMenu.js:47-64`), re-patched every 5 s (`tray/taskbarMenu.js:67`).

New architecture: `qml/taskbar` context menu on the bar background.

### 2.18 taskbarSearch.js

What it does: implements `org.fenestra.desktop taskbar-search` (`hide`, `icon`, `icon-label`, `box`; default `box`,
`tray/schemas/org.fenestra.desktop.gschema.xml:14-21`). `icon` keeps the pinned Search app icon
(`fenestra-search.desktop`, legacy `windows-search.desktop`, `tray/taskbarSearch.js:17`); `icon-label` and `box` hide it
and insert a button in its place (`tray/taskbarSearch.js:53-86`); vertical taskbars fall back to the icon
(`tray/taskbarSearch.js:66-68`). Label "Search"/"Buscar" (`tray/taskbarSearch.js:19`). Click activates the Search app,
whose `.desktop` calls ArcMenu over D-Bus `com.Extensions.ArcMenu.ToggleStandaloneRunner`
(`desktop/applications/fenestra-search.desktop`).

Visual parameters: icon 18 px in box mode, 20 otherwise (`tray/taskbarSearch.js:35`); margin `0 2`, row spacing 10,
label 13 px (`tray/stylesheet.css:466-468`); icon+label 40 px tall, padding `0 12 0 10`, radius 4, hover `.06`
(`tray/stylesheet.css:469-471`); box 228×32, padding `0 14`, radius 16, bg `rgba(255,255,255,.06)`, border `.08`,
placeholder `#c5c5c5`, hover `.09` (`tray/stylesheet.css:472-475`). Light: `tray/light.css:259-263`.

New architecture: `qml/taskbar` search entry; `ShellSettings.searchMode` already exists with values
`"hidden" | "icon" | "iconLabel" | "box"` (`shell/src/core/shellsettings.h`) — note the different spelling
(`hide`/`icon-label`) when migrating the gsettings value.

### 2.19 taskbarStyle.js

What it does: replaces Dash to Panel's `DASHES` running indicator for horizontal panels with a single round-capped
line in the accent fill (`tray/taskbarStyle.js:7-33`); repaints on accent change (`tray/taskbarStyle.js:11-12`).

Visual parameters: thickness = Dash to Panel dot size (3, `dconf/local.d/00-fenestra:220`), `scale = thickness/3`,
length `min(w − 4·scale, 16·scale)`, centre `y = h − thickness/2 − 2·scale` (`tray/taskbarStyle.js:21-25`). Fallback colour
`rgb(100,124,100)` (`tray/taskbarStyle.js:10`). Unfocused running apps: Dash to Panel `DOTS`, colour `#a0a0a0`
(dark) / `#868686` (light) (`dconf/local.d/00-fenestra:214-222`, `tray/appearance.js:331`).

New architecture: `qml/taskbar/TaskButton.qml` indicator (focused: 16 px accent pill; running unfocused: short grey dot).

### 2.20 trayLayout.js

What it does:
- Adds an overflow chevron button (`pan-up-symbolic`, 12 px) left of the keyboard indicator; its menu has one item
  "Bluetooth" opening `fenestra-settings --page bluetooth` (`tray/trayLayout.js:14-20`, `tray/trayLayout.js:62-68`).
  Its accessible name is always Spanish "Mostrar iconos ocultos" (`tray/trayLayout.js:14`).
- Keyboard indicator: two lines `<LANG>\n<LAYOUT>`, language from the UI locale (C/en→ENG, es→ESP, fr→FRA, de→DEU,
  it→ITA, pt→POR, else upper-case code), layout = upper-case XKB id (`tray/trayLayout.js:21-34`); always shown.
- Quick settings indicators: Wi-Fi and volume 16 px, icon gap 4, Bluetooth indicator always hidden, battery % hidden
  (`tray/trayLayout.js:36-54`).
- Date button paddings and clock style (`tray/trayLayout.js:56-59`).
- Re-applies on panel/indicator changes, every 2 s for 20 s, then every 30 s (`tray/trayLayout.js:70-85`).

Visual parameters (`tray/trayLayout.js:10`): overflow h-padding 10, keyboard 7, quick settings 3, icon gap 4, date 10,
keyboard font 12, clock font 12, clock letter-spacing −0.4, vertical nudges +1 px for overflow/keyboard/Wi-Fi/volume,
0 for clock; overflow min-width 16 (`tray/trayLayout.js:16`); keyboard min-width 24 (`tray/trayLayout.js:33`); all
radius 4. Panel buttons share one hover surface `rgba(255,255,255,.08)` + inset 1 px `rgba(255,255,255,.09)`, radius 4
(`tray/stylesheet.css:144-174`); light hover `rgba(255,255,255,.70)` + inset `rgba(0,0,0,.06)` (`tray/light.css:63-72`).

GNOME dependencies: `Main.panel.statusArea.{keyboard,quickSettings,dateMenu}` internals, `PanelMenu.Button`,
`_inputSourceManager`, `_currentSourceChanged` override.

New architecture: `qml/tray` (order: overflow chevron, keyboard, network+volume+battery group opening quick settings,
clock/date opening calendar+notifications, show-desktop strip). `services/keyboard` (layouts via KWin's
`org.kde.KeyboardLayouts` D-Bus or XKB config), `services/bluetooth`, `services/network`, `services/audio`.

### 2.21 weatherWidget.js

What it does: a button at the left end of a centred horizontal taskbar showing the condition icon, temperature
(no space: "18°C") and condition text (`tray/weatherWidget.js:8-35`); coloured theme icon in dark mode, symbolic in
light mode (`tray/weatherWidget.js:65-70`); click opens GNOME Weather (`tray/weatherWidget.js:56`). Hidden when there is
no data, when the left area is ≤220 px (left-aligned taskbar), when vertical, or when `taskbar-widgets` is false
(`tray/weatherWidget.js:95-133`). Refreshes every 15 min (`tray/weatherWidget.js:154-157`), re-places every 10 s and on
signals (`tray/weatherWidget.js:140-153`).

Visual parameters: icon 28 px (`tray/weatherWidget.js:47`); x = panel x + 4, full panel height
(`tray/weatherWidget.js:129-130`); padding `4 10 4 6`, radius 4, hover `.06`, active `.04`, row spacing 8, temp 12 px white,
condition 12 px `#c5c5c5` (`tray/stylesheet.css:457-463`). Light: cond `#5c5c5c` (`tray/light.css:255-258`).

GNOME dependencies: `misc/weather.js WeatherClient` (GWeather + GNOME Weather's location settings
`org.gnome.shell.weather automatic-location`, `dconf/local.d/00-fenestra:366-367`), GeoClue.

New architecture: `qml/taskbar` weather widget; `services/weather` (libgweather or a direct provider; location from
GeoClue or a Settings city). Click target: a weather app (GNOME Weather can still be installed).

### 2.22 stylesheet.css and light.css (shared look)

What they do:
- Shared dark acrylic surface for menus, quick settings, date popover, dialogs, run dialog, OSD, Alt+Tab switcher,
  workspace switcher, notification banners: bg `rgba(32,32,36,0.80)`, radius 8, border `rgba(255,255,255,0.10)`, white text
  (`tray/stylesheet.css:7-24`). UI font "Segoe UI Variable" on stage (`tray/stylesheet.css:28-31`).
- Controls (static default accent `#4cc2ff` with black text, overridden by the generated accent CSS,
  `tray/stylesheet.css:26-27`): quick toggles radius 6 (`:32-36`), buttons/menu items radius 4 (`:45`), switch 40×20 pill,
  border `#a0a0a0`, handle 12 px `#cccccc` with 3 px margin, checked accent with black handle (`:46-62`); check box
  radius 4/3, border `#aaaaaa` (`:63-67`); slider bar 4 px, handle radius 7, track `rgba(255,255,255,0.25)` (`:68-74`);
  entry radius 4, focus 2 px accent underline (`:75-76`); focus ring inset 2 px `rgba(255,255,255,0.75)` (`:77-79`);
  menu item active `rgba(255,255,255,0.08)` (`:80`).
- Taskbar tiles 40×40 radius 4, focused/hover inset 1 px `rgba(255,255,255,0.09)` (`tray/stylesheet.css:82-113`);
  Start button 40 px, margin `0 2`, ArcMenu button margin 4 (`:91-109`, `:181-185`).
- Snap preview: bg `rgba(200,205,204,0.17)`, border 1 px `rgba(235,240,238,0.55)`, radius 8, inset 1 px `rgba(255,255,255,0.07)`
  (`tray/stylesheet.css:115-121`); light `rgba(255,255,255,0.35)` / `rgba(0,0,0,0.15)` (`tray/light.css:85-90`).
- Tooltips (app icons, Start, Search): radius 4, padding `5 9`, "Segoe UI" 12 px, bg `rgba(43,43,43,0.98)`, border
  `rgba(255,255,255,0.14)`, shadow `0 2px 6px rgba(0,0,0,0.24)` (`tray/stylesheet.css:187-200`); light
  `rgba(249,249,249,0.98)` / `rgba(0,0,0,0.10)` / `0.14` (`tray/light.css:77-84`).
- Notification banners radius 8, bg `rgba(32,32,36,.80)`, border `rgba(255,255,255,.12)` (`tray/stylesheet.css:336-339`).
- ArcMenu popup surface transparent (acrylic effect paints it) (`tray/stylesheet.css:360-361`, `tray/light.css:229-231`).
- `light.css` palette summary: cards `#f9f9f9`/`#ffffff`, strokes `rgba(0,0,0,.06-.10)`, text `#1a1a1a`, secondary
  `#5f5f5f` (`tray/light.css:4-5`); shared surface `rgba(249,249,249,0.85)`, shadow `0 8px 16px rgba(0,0,0,0.14)`
  (`tray/light.css:9-23`); Alt+Tab item selected `rgba(0,0,0,0.06)`, outline `rgba(0,0,0,0.3)` (`tray/light.css:224-227`);
  consent dialog light variant (`tray/light.css:233-247`).

New architecture: every value goes to `design/tokens.json` (section 8); Alt+Tab styles go to the `kwin/` tabbox theme;
snap preview to `kwin/` Snap Layouts.

### 2.23 schemas

| Key | Type / default | Source | New home |
|---|---|---|---|
| `org.fenestra.desktop accent-color-custom` | `s`, `''` (dconf default `'#0078D4'`) | `tray/schemas/org.fenestra.desktop.gschema.xml:4-8`, `dconf/local.d/10-fenestra-theme:30` | `shell.conf [Appearance] Accent` |
| `org.fenestra.desktop accent-from-wallpaper` | `b`, `false` | `tray/schemas/org.fenestra.desktop.gschema.xml:9-13` | new key needed |
| `org.fenestra.desktop taskbar-search` | enum `hide/icon/icon-label/box`, `'box'` | `tray/schemas/org.fenestra.desktop.gschema.xml:14-24` | `shell.conf [Taskbar] SearchMode` |
| `org.fenestra.desktop taskbar-widgets` | `b`, `true` | `tray/schemas/org.fenestra.desktop.gschema.xml:25-29` | `shell.conf [Taskbar] Weather` |
| `org.gnome.shell.extensions.fenestra-tray security-screen` | `as`, Ctrl+Alt+Delete, Ctrl+Alt+KP_Delete | `tray/schemas/org.gnome.shell.extensions.fenestra-tray.gschema.xml:4-8` | KWin global shortcut |

`tray/schemas/gschemas.compiled` is a 0-byte file in the repository (compiled at build).

---

## 3. Other fenestra-* extensions

The list under `desktop/extensions/` is: fenestra-consent, fenestra-direct-unlock, fenestra-lock-clock,
fenestra-login, fenestra-spotlight, fenestra-tray, fenestra-user-lock-prompt. Enabled by default in the user session:
lock-clock, spotlight, consent, tray (`dconf/local.d/00-fenestra:5`); explicitly disabled: direct-unlock and
user-lock-prompt (`dconf/local.d/00-fenestra:4`). Greeter (GDM) enables login + spotlight (`dconf/gdm.d/90-fenestra:3`).

### 3.1 fenestra-consent (administrator consent over polkit)

What it does: when GNOME's polkit agent opens its dialog, restyles it (`consent/extension.js:10-19`): hides the native
header, adds a title bar "User Account Control" with a 46×32 close button, the question "Do you want to allow this
app to make changes to your device?", a shield icon next to the genuine polkit action message (never an invented
publisher), a "Show more details" link that reveals "Action ID: <id>" (`consent/presentation.js:17-44`). The password
field always stays (no password-less consent), buttons renamed Yes / No (`consent/presentation.js:45-50`). Writes
`$XDG_RUNTIME_DIR/fenestra-consent-enabled` with the shell PID while enabled (`consent/extension.js:20-23`) — a marker
other components can test.

Visual parameters (`consent/stylesheet.css`): dialog 456 px, radius 8, border `rgba(255,255,255,0.15)`, bg `#2b2b2b`,
shadow `0 12px 36px rgba(0,0,0,0.4)` (`:7-12`); heading bg `#333333`, radius `8 8 0 0` (`:16-18`); title bar 32 px,
padding-left 24 (`:19`); caption 12 px, top 9 (`:20`); close 46×32, radius `0 7 0 0`, hover `#c42b1c` (`:21-22`), glyph 10 px
(`consent/presentation.js:28`); question 19 px, padding `16 24 22` (`:23`); body bg `#2b2b2b`, padding `20 24`, spacing 16
(`:24`); shield 32 px (`consent/presentation.js:33`); action text 14 px, min-height 60 (`:26`); details link 12 px
`#b9d1ba` (overridden to accent text by `tray/appearance.js:182`), underline on hover (`:27-28`); action id 12 px `#c5c5c5`
(`:29`); buttons bar padding `20 24`, spacing 8, bg `#202020`, radius `0 0 8 8` (`:30-32`); buttons min-height 30, padding
`0 12`, radius 3, border `#505050`, bg `#383838`, hover `#454545`, 13 px (`:33-37`); focused button accent fill, white border,
inset 1 px `#202020` (`:38-40`); password entry 388 px, padding `8 9`, 13 px, radius 4 (`:49-51`); avatar 32 px (`:45`).
Light: `tray/light.css:233-247`. Assets `assets/consent/{close,shield}.svg`.

GNOME dependencies: `PolkitAgent.Session.prototype.initiate` override, `Main.componentManager._allComponents.polkitAgent._currentDialog`
internals (`_session`, `_passwordEntry`, `_userAvatar`, `_okButton`, `_cancelButton`, `actionId`, `message`).

New architecture: under KWin the shell (or a separate agent) must register a polkit authentication agent
(PolkitQt1 Agent::Listener) — `services/session`; the dialog is `qml/security` (consent dialog, layer-shell overlay,
dimmed background). Keep the marker file if other tools rely on it (grep before dropping).

### 3.2 fenestra-direct-unlock (disabled by default)

What it does: after the lock screen resets, activates the unlock dialog so the password prompt shows immediately
(`unlock/extension.js:7-13`). Session modes user + unlock-dialog.

New architecture: `qml/lock` option "show prompt immediately".

### 3.3 fenestra-user-lock-prompt (disabled by default)

What it does: on the lock screen replaces the clock with the account's real name (or user name), styled as the date
line, until interaction (`ulp/extension.js:12-36`).

New architecture: `qml/lock` option. Contains personal data at runtime (real name) — fine on screen, do not log it.

### 3.4 fenestra-lock-clock

What it does:
- Replaces the native lock clock with Fenestra's clock face (`lockclock/extension.js:24-26`, `lockclock/extension.js:84-93`):
  large time in the system locale (from `/etc/locale.conf`, `LC_TIME` then `LANG`) with any AM/PM suffix stripped, long
  date "weekday day month" (`lockclock/face.js:33-56`), centred at 13 % of the primary monitor height
  (`lockclock/face.js:58-61`).
- Transition clock → prompt driven by the dialog's adjustment, eased to 1 in 300 ms EASE_OUT_CUBIC
  (`lockclock/extension.js:31-37`): clock fades and moves up by 12 % of the monitor height, a black dimmer rises to
  opacity 82/255, the prompt rises from +16 px and fades in after 25 % progress (`lockclock/extension.js:94-110`).
- Fast unlock: after a successful authentication drops queued informational hints of other services and keeps only the
  succeeding service's short (≤400 ms) messages, so a fingerprint/face hint does not delay unlock by ~1.5 s
  (`lockclock/extension.js:38-55`); GNOME 51 variant through `AuthServices._onVerificationComplete` + `handlePendingMessages`
  within 5 s (`lockclock/extension.js:56-80`).
- Also exports background helpers reading `/var/lib/fenestra-spotlight/current.json` with a path whitelist
  (`lockclock/face.js:10-31`, `lockclock/face.js:82-103`).

Visual parameters: time "Segoe UI Variable" 96 px 600 white, date 18 px 400 white (`lockclock/face.js:46-47`,
`lockclock/stylesheet.css:4-17`); y = 13 % of height (`lockclock/face.js:60`); clock move −12 % height
(`lockclock/extension.js:105`); dimmer 82/255 (`lockclock/extension.js:106`); prompt offset 16 px
(`lockclock/extension.js:108`); 300 ms EASE_OUT_CUBIC (`lockclock/extension.js:36`); background watch debounce 150 ms
(`lockclock/face.js:26`).

GNOME dependencies: `UnlockDialog.prototype._init/_setTransitionProgress/_showPrompt`, `ShellUserVerifier` / `AuthServices`
internals (`_messageQueue`, `_queueMessageTimeout`, `finishMessageQueue`), `GnomeDesktop.WallClock`, `Meta.Background`.

New architecture: `qml/lock`. Who draws the lock screen under KWin is an open decision (kscreenlocker greeter theme vs.
our own `ext-session-lock-v1` client); either way the clock face, transition and fast-unlock rule (do not wait for
stale PAM info messages after success) carry over. Background source: `services/session` reading `current.json`.

### 3.5 fenestra-login (GDM greeter)

What it does (session mode `gdm` only, `login/metadata.json:10-12`):
- Waits (100 ms poll, ≤300 tries) for GDM's user list (`login/extension.js:17-25`), checks every private method it needs
  and otherwise keeps the standard login (`login/extension.js:27-55`).
- Shows a full-screen "curtain": Spotlight background per monitor (or the shared one from fenestra-spotlight) + the clock
  face, modal grab (`login/extension.js:57-78`). Enter, keypad Enter, Space or a click dismisses it: dimmer eases to
  82 in 300 ms, the face fades and moves up 12 % in 300 ms EASE_OUT_CUBIC; with exactly one loaded, unlocked user it
  selects that user and starts verification directly (authentication still required) (`login/extension.js:79-107`).
  Any error → fail-safe to the standard login (`login/extension.js:35-43`).
- Race guard: coalesces simultaneous password + fingerprint successes of the same attempt so only one session starts,
  while real conflicting sessions still go through GNOME's check (`login/login-race.js:3-57`).

Visual parameters: same clock face as 3.4 (`login/face.js:44-72`); curtain bg black or transparent
(`login/extension.js:64`); 300 ms, 82/255, −12 % (`login/extension.js:88-89`).

GNOME dependencies: `gdm/loginDialog.js LoginDialog` internals (`_userList`, `_userSelectionBox`, `_beginVerificationForItem`,
`_showPrompt`, `_onSessionOpened`, `_findConflictingSession`, `_startSession`, `_onReset`), `LoginManager` (logind), GDM greeter proxy.

New architecture: tied to the display manager, not to the session compositor. If GDM stays the greeter for the KWin
session, this extension stays as is (it runs in GDM's own GNOME Shell). If the greeter changes (e.g. SDDM), the curtain,
single-user auto-select and fail-safe become a greeter theme — outside the listed targets; the clock face can be shared
with `qml/lock`.

### 3.6 fenestra-spotlight

Session modes gdm, user, unlock-dialog (`spot/metadata.json:10-14`). Modules:

| Module | What it does | Values | New home |
|---|---|---|---|
| `extension.js` | Lock and login backgrounds from `/var/lib/fenestra-spotlight/current.json` (`image` must match `/var/lib/fenestra-spotlight/images/<sha256>.jpg` or `/usr/share/backgrounds/fenestra/*.jpg`, `spot/extension.js:49-55`); unlock dialog background replaced (`spot/extension.js:32-35`); GDM backdrop + black shade used by fenestra-login (`spot/extension.js:57-76`); hides GDM's session-chooser gear (`spot/extension.js:28-29`); reloads on file change (`spot/extension.js:43`) | — | `qml/lock` background; `services/session` watches `current.json` |
| `face.js` | Background helpers (same as 3.4) + a `createClockFace` with hard-coded `es-ES` 24 h (`spot/face.js:38-43`) that nothing imports | bg fallback `#202020` (`spot/face.js:11`) | shared lock background helper |
| `firstLogin.js` | First login only (no `~/.config/gnome-initial-setup-done`): black curtain until the OOBE window `org.fenestra.Oobe` draws its first frame (fallback 3 s), back to black when it closes, fades out only after the shell runs smoothly (15 × 100 ms ticks within 130 ms each), max 15 s; safety 90 s (`spot/firstLogin.js:6-138`) | fade 450 ms EASE_OUT_QUAD (`spot/firstLogin.js:66-69`) | `qml/firstlogin` |
| `hello.js` | Face-unlock (Howdy) feedback on the auth prompt: detects "Attempting facial authentication" / "Identified face as" (EN/ES) on `gdm-password` (`spot/hello.js:18-23`), plays `assets/hello` frame sequences (searching loops, authentication 260 ms) in a 64×64 box with 8 px vertical margin (`spot/hello.js:74-117`); shortens those two notices in the verifier queue (searching 0 ms, success 260 ms) (`spot/hello.js:64-73`); pre-decodes frames 6 per idle only when a lock/login screen is coming (`spot/hello.js:47-63`) | `SUCCESS_ANIMATION_MS 260`, `SUCCESS_MESSAGE_MS 260` (`spot/hello.js:24-25`); frames 40 ms (`assets/hello/frames.json`) | `qml/lock` (PAM conversation messages drive the animation) |
| `lockControls.js` | Hides the top-panel a11y and quick-settings controls while locked or in GDM (`spot/lockControls.js:3-23`) | — | not needed (own lock surface has no panel) |
| `lockStatus.js` | Wi-Fi and battery glyphs bottom-right of lock/login screen: x = right − 100, y = bottom − 44 (`spot/lockStatus.js:28`); Wi-Fi levels ≥75/50/25 % (`spot/lockStatus.js:32`), battery `status/{normal,charging}-0-<0..10>.svg` (`spot/lockStatus.js:34-37`); refresh every 5 s only while visible (`spot/lockStatus.js:48-51`) | spacing 18, Wi-Fi 18 px, battery 22 px, white (`spot/lockStatus.js:11-13`) | `qml/lock` + `services/network`, `services/power` |
| `panelGuard.js` | After unlock keeps the native panel transparent until Dash to Panel has placed it at the bottom with stable geometry (2 × 50 ms), max 3 s (`spot/panelGuard.js:1-79`) | 50 ms, 3 s | not needed under KWin |
| `startup.js` | At session start covers the screen with the login photo (bg `#202020`) while the desktop builds; fades on `startup-complete` or after 750 ms (`spot/startup.js:7-36`) | fade 160 ms EASE_OUT_QUAD (`spot/startup.js:27`), timeout 750 ms (`spot/startup.js:34`) | `qml/desktop` (startup cover) or session start splash |
| `transitions.js` | Locking: zero-duration blank (no clock flash before display off) (`spot/transitions.js:35-39`); unlocking: the lock group fades out in 140 ms EASE_OUT_QUAD instead of sliding up (`spot/transitions.js:49-63`); `desktopReady()` helper checks Dash to Panel and DING (`spot/transitions.js:6-18`) | 140 ms | `qml/lock` exit animation |
| `stylesheet.css` | Login/unlock avatar 192 px round, user name 24 px (`spot/stylesheet.css:1-11`); duplicate of the tray control styles for GDM, where fenestra-tray is not loaded (`spot/stylesheet.css:13-67`) | see tokens | `qml/lock`; tokens |

GNOME dependencies: `UnlockDialog._createBackground`, `LoginDialog._init/_shouldShowSessionMenuButton`,
`Main.screenShield` (`_resetLockScreen`, `activate`, `_hideLockScreen`, `_continueDeactivate`, `_lockDialogGroup`),
`AuthPrompt._init`, `ShellUserVerifier._queueMessage`, `Meta.Background(Actor)`, libnm, UPowerGlib, `Main.layoutManager._startingUp`.

---

## 4. Laptop copies in extras/fedora-upgrade/system-extensions

These are earlier copies installed system-wide by `extras/fedora-upgrade/restore-login-extensions.sh`
(step 1 enables `windows-spotlight@local`, step 2 `single-user-gdm@local`; `extras/fedora-upgrade/restore-login-extensions.sh:1-19`).

| Copy | Differences from the repository extension (from `diff`) | Migration |
|---|---|---|
| `sysext/windows-spotlight@local` | No `firstLogin.js` import; state dir `/var/lib/windows-spotlight` and only `<sha256>.jpg` images accepted (`sysext/windows-spotlight@local/extension.js:48-51`); `Main.screenShield` not null-checked (`sysext/windows-spotlight@local/lockStatus.js:25`, `:39`); `hello.js` uses try/catch import; stylesheet hard-codes a green accent: fill `#647c64` with white text, slider text `#a8bea7`, focus ring `rgba(168,190,167,0.7)`, menu active `rgba(100,124,100,0.45)`, checked switch handle white (`sysext/windows-spotlight@local/stylesheet.css:28-66`); ships its own `status-assets/` where the 7 `network-wireless-*.svg` files are 0 bytes | superseded by `spot/`; do not migrate |
| `sysext/single-user-gdm@local` | Same as `login/` except `face.js`: `/var/lib/windows-spotlight` paths and a hard-coded `es-ES` 24 h clock (`sysext/single-user-gdm@local/face.js:41-42`) instead of the system locale | superseded by `login/`; do not migrate |

---

## 5. Third-party extensions: what Fenestra configures or patches

Licences and change summary: `THIRD-PARTY.md`. Settings: `dconf/local.d/00-fenestra` (generated by
`tools/export-dconf-defaults.py`, `dconf/local.d/00-fenestra:1`), plus `dconf/local.d/10-fenestra-theme`.

### 5.1 ArcMenu (patched heavily) → `qml/start`, `qml/search`, `services/apps`, `services/search`

Configuration (`dconf/local.d/00-fenestra:8-75`, `dconf/local.d/10-fenestra-theme:33-34`):
layout `'11'` (`:53`), location `BottomCentered` (`:17`), height 864 (`:47`), grid icon cell 88×84 with 32 px icons
(`:23`), border radius 8 / width 1 / colour `rgba(255,255,255,0.14)` (`:29-31`), background transparent (`:28`),
foreground `rgb(245,245,245)` (`:46`), separator `rgb(63,62,64)` (`:54`), item hover `rgba(238,238,236,0.08)` (`:51`),
item active `rgba(255,255,255,0.08)` (`:48`), Start button: icon only, 32 px, radius 4, no padding, hover
`rgba(255,255,255,0.08)`, active `rgba(255,255,255,0.12)` (`:32-44`), menu font 12 (`:45`), search entry radius 25 (`:69`),
no Activities button (`:71`), tooltips on (`:75`), right-click on Start does nothing (`:9-10`), pinned apps list of 15
(`:58`), Search ("runner") hotkey `<Super>s`, 832×864 static, search bar top, no settings button (`:61-67`); default
`arcmenu-hotkey` is `Super_L` (`arc/schemas/org.gnome.shell.extensions.arcmenu.gschema.xml:522-525`). Start button icon
`/usr/share/fenestra/assets/branding/start-button.svg` (`dconf/local.d/10-fenestra-theme:34`). Mode-dependent colours are
rewritten live by `tray/appearance.js:335-348`.

Fenestra code inside ArcMenu:
- `arc/windowsPopupMotion.js` (installed on every ArcMenu BoxPointer, `arc/menuButton.js:782`): live background blur
  radius 60 × scale (`arc/windowsPopupMotion.js:15`, `:68-76`) + luminosity effect; no arrow (`:42-44`); open = slide up
  from 96 px below, clipped at the taskbar edge (12 px gap), 200 ms EASE_OUT_QUINT, no opacity fade (fades break the
  background blur) (`:16-19`, `:84-94`, `:105-138`); close = slide down 120 ms EASE_IN_QUAD (`:140-163`); offscreen
  redirect off, dim effect off (`:112-115`); honours enable-animations (`:103`).
- `arc/windowsAcrylic.js`: Clutter effect after the blur that copies the blurred backdrop and remaps luminance to
  `base + gain × L` keeping chroma × `chroma`, output opaque with rounded corners radius 8 (`arc/windowsAcrylic.js:6-33`,
  `:38`). Map dark `[0.128, 0.265, 0.65]`, light `[0.84, 0.13, 0.45]` (`arc/fenestraTheme.js:46-47`).
- `arc/fenestraTheme.js`: light = `color-scheme != prefer-dark`; `pick(dark, light)`; light tinting of white glyphs
  (`#ffffff|#eeeeee` → `#1a1a1a`) into `~/.cache/fenestra/tint/arcmenu-light/` (`arc/fenestraTheme.js:13-44`).
- `arc/menulayouts/eleven.js` (Start): default width 832 (`:32`); header with the search pill on the acrylic, padding
  `16 32 8` (`:87-91`); footer band dark `rgba(0,0,0,0.21)` / light `rgba(0,0,0,0.03)`, top border `rgba(0,0,0,0.2)` /
  `rgba(0,0,0,0.06)`, padding `0 55 6 56`, min-height 58, bottom radius = menu radius (`:274-289`; a first version at `:136`
  says 64 px and `0.25`/`0.04`); menu box padding 0, "Segoe UI" 14 px (`:288`); footer: avatar + first two words of the
  name, padding `4 12 4 8`, radius 4, 12 px (`:178-189`), power button at the right (`:211-217`); mouse button 8 = Back
  (`:41-44`).
- `arc/menulayouts/windowsStartHome.js` (Start home page): search pill 32 px, radius 16, padding `0 14`, 13 px, bg
  `rgba(28,28,28,0.75)` / `rgba(255,255,255,0.85)`, border `rgba(255,255,255,0.06)` / `rgba(0,0,0,0.08)`, hint "Search for apps,
  settings, and documents" (`:78-81`); section headings 14 px 600, margins `top 68 bottom 57` (`:20-24`); "Pinned" with
  "Show all ⌄ / Show less ⌃" (`:82`), 8-column grid, margin `11 42 0 22`, first 16 visible unless expanded, tiles 80 px wide,
  min-height 69, padding 4, margin `0 4 8`, radius 4, label 12 px, icon 32 (`:84-91`); "Recommended" with "Show all ›":
  up to 6 recent files from `recently-used.xbel` in 3 columns, 224 px buttons, 32 px icon, "Today at HH:MM" /
  "Yesterday at HH:MM" / "N days ago", empty text "Your recent files will appear here." (`:92-117`); "All" with
  "View: Category/Grid/List" (`:118`): Category = cards 154×154 radius 8 with 4 app icons (32 px), 4 per row, groups
  Productivity, Social, Creativity, Utilities & Tools, Games, Other from desktop categories (`:119-144`); Grid = 8 columns
  66 px; List = 2 columns 306 px (`:124-133`). Rebuilt while hidden (400 ms idle after close, stale after 5 min) so
  opening never builds (`:42-52`). All strings English-only.
- `arc/menulayouts/windowsPower.js`: power menu Lock, Sleep, Shut down, Restart (`:29`) and account menu (on the avatar)
  Sign out, Switch user (`:31-35`); menu min-width 124, padding 4, radius 8, bg `rgba(44,44,44,0.96)` /
  `rgba(249,249,249,0.96)`, border `rgba(255,255,255,0.14)` / `rgba(0,0,0,0.10)`, 14 px (`:14`); items min-height 30, padding
  `0 10`, spacing 12, radius 4, 13 px (`:19-20`); glyphs `assets/power/<PowerType>.svg` 16 px (`:21`; PowerType numbers
  `arc/constants.js:220-229`).
- `arc/menulayouts/runner.js` (Search flyout): positioned with its bottom 12 px above the taskbar
  (`arc/menulayouts/runner.js:259-263`); height `runner-menu-height − 13`, no padding (`:269-273`); attaches
  `WindowsSearchHome` (`:106`).
- `arc/windowsSearchHome.js`: home page "Recent searches" (queries and launched apps, up to 10, with "Just now /
  N minutes/hours/days ago"; empty text "Your recent searches will appear here.") and "Top apps" (6: most used, then
  favourites, then a fixed list) (`:45-105`); history persisted in `~/.local/state/windows-search/history.json` (mode
  0700 dir, private file; ≤8 queries, ≤10 apps, ≤10 entries) (`:26-28`, `:67-70`); filter chips All, Web, Apps,
  Documents, Settings, Folders, Photos with ← back and ▶ next (`:31-37`), provider filtering by category (`:56-60`);
  account button → `fenestra-settings --page yourinfo`, settings → `--page privacy` (`:39-49`); web search opens
  `https://www.bing.com/search?q=` (`:55`); search glyph `assets/search/search.png` 16 px, no clear icon, no hint
  (`:62-65`). Strings English-only.
- `arc/windowsSearchResults.js`: results column + preview pane (`:9-13`): sections Best match, Apps, Documents,
  Folders, Photos, Settings (4 each, 12 when filtered), other providers (2), Web suggestions (`:223-273`); up to 60
  results collected (`:139`); Up/Down/Enter in the entry drive the selection (`:95-109`); preview for files/folders/
  photos: name, type, icon card (64, photos 96), Open + Options (Open file location, Copy full path), Details: Location,
  Last modified `dd/mm/YYYY, HH:MM` (`:56-59`, `:343-373`, `:411-428`); for apps/settings/web: hero icon 64, name,
  type, actions Open / Pin to Start / Unpin from Start / desktop actions, web "Open results in browser" (`:374-409`).
- `arc/windows-search.css` (all Search metrics): entry margin `8 30 0 33`, radius 16, 32 px, 13 px, bg
  `rgba(28,28,28,0.75)` (`:2-5`); home padding `14 33 20` (`:7`); heading 18 px 600 (`:9`); rows min-height 48, radius 4,
  hover `.06` (`:13-14`); recent icon 40×40 radius 4 (`:16`); name 14 px, type/age 12 px `#c8c8c8` (`:18-20`); filters
  padding `17 26 0 21`, chips 28 px, radius 15, bg `rgba(255,255,255,.055)`, 14.3 px (`:21-35`); results padding
  `23 32 18 25`, spacing 22, list 328 px (`:38-40`); result padding `11 0`, best `9 0`, hover `.05`, selected `.075`,
  indicator 3×16 radius 2 (`:45-52`); result icon 40×40 radius 4 (`:53`); name 14 px, sub 12 px `#c8cbca` (`:57-58`);
  preview 376 px, radius 8, bg `rgba(255,255,255,.05)`, padding `23 25 25 24` (`:60`); preview card 107 px radius 6
  (`:63`); buttons 120×32 radius 4 (`:65`); detail key 124 px (`:72`); hero name 20 px 600 (`:77`); actions 36 px (`:81`);
  top apps 108 px wide (`:129`); light mode `:87-125`, `:133-134`; no focus ring/underline on Start/Search entries
  (`:136-140`). Static green leftovers `#a8bea6` (`:34`), `#a8bba7` (`:52`) are overridden by `tray/appearance.js:183-187`.

New architecture: `qml/start` (pinned grid 8×2/expand, Recommended, All with three views, footer with account and power
menus, search pill opening search), `qml/search` (home, filters, results + preview), `services/apps` (installed apps,
categories, pinned list — `ShellSettings.pinnedApps` exists — most-used ranking, desktop actions), `services/search`
(apps, settings, files via Tracker/Baloo, recent files, history file; keep the same history path or migrate it).
Acrylic: KWin's blur-behind (layer-shell surface + KWindowEffects/`org_kde_kwin_blur`) gives the blur; the luminosity
remap has no KWin equivalent — approximate with a tint layer in QML or a custom `kwin/` effect. Motion: slide-up 96 px,
200 ms EASE_OUT_QUINT, clip at the taskbar top.

### 5.2 Dash to Panel (configured; one stability fix) → `qml/taskbar`, `services/windows`

Configuration (`dconf/local.d/00-fenestra:134-292`): bottom panel 48 px on every monitor (`:243`, `:246`), length 100 %,
no side margins, top/bottom padding 4 (`:242-248`); elements: left box + taskbar centred, Show-Apps and Activities hidden,
right box + system menu + date menu + show-desktop at the right (`:240`); app icon margin 2, padding 4 (`:203-204`);
favourites + running apps grouped (`:229`, `:255-257`); focused indicator `DASHES`, unfocused `DOTS`, size 3, bottom,
accent `#4cc2ff` / unfocused `#a0a0a0` (`:208-222`); focus highlight white 8 % (`:224-227`); hover bg
`rgba(255,255,255,0.08)`, radius 4, pressed `rgba(255,255,255,0.12)` (`:231-233`); hover animation SIMPLE (`:137-141`); no
launch animation (`:142`); panel bg `#000402` at 0.63, border 1 px `rgba(255,255,255,0.10)` (`:267-281`); hotkeys Super+1..0
(+Ctrl, +Shift, keypad) (`:143-202`), hotkey overlay `TEMPORARILY`, Super+Q shortcut (`:234`, `:254`); window previews on,
152 px, padding 8, title top 13 px normal white, custom icon 16, opacity 52 %, 500 ms hover timeout, 170 ms animation, hide on
click (`:250-251`, `:261-262`, `:283-292`); peek mode after 500 ms at 80 % (`:223`, `:249`); show-desktop button 7 px, peek on
hover after 500 ms (`:258-259`, `:263`); scroll on icon cycles windows (`:253`); intellihide off (`:235`); workspaces not
isolated (`:237`). Light-mode values are written by `tray/appearance.js:316-333` (bg `#f3f3f3` at 0.85, border
`rgba(0,0,0,0.08)`, hover `rgba(255,255,255,0.70)`, pressed `rgba(255,255,255,0.50)`, preview title `#1a1a1a`, focus
highlight black, unfocused dots `#868686`).

Patch: `dtp/taskbar.js:1665-1690` tears down a raised clone container when it is destroyed while raised (avoids
"already disposed" log floods).

New architecture: `qml/taskbar` (already started: 48 px, `#000402` 63 %, 1 px top border, centred icons;
`shell/qml/taskbar/Taskbar.qml`). Its show-desktop strip is 8 px (`shell/qml/taskbar/Taskbar.qml`) versus 7 px
here. Missing so far: grouping, pinned + running merge, Super+number hotkeys (KWin global shortcuts), thumbnails, peek,
hover/press surfaces, indicators, tooltips, progress/count badges (`progress-show-count=true`, `:252`), scroll-to-cycle.
`services/windows` (KWin `org_kde_plasma_window_management` or a KWin script bridge) already exists as `WindowsModel`.

### 5.3 Blur my Shell (configured) → KWin blur

Configuration (`dconf/local.d/00-fenestra:77-132`): taskbar pipeline `pipeline_windows_taskbar` = dual Kawase radius 40,
brightness 1.0, static (`:78`, `:105-112`); popups (menus, quick settings, calendar, OSD, notifications, dialogs) pipeline
`pipeline_windows_panels` radius 90 brightness 1.0, corner radius 8 everywhere, keep shell theme (`:114-129`); application
blur only for `org.gnome.Settings`, opacity 210, radius 40 (`:85-93`); lock screen not blurred (`:98-100`); Dash to Panel
original panel blurred (`:95-96`). Fenestra retargets the popup blur for the calendar cards (`tray/calendarPanel.js:30-34`).

New architecture: KWin's blur effect enabled, shell surfaces request blur-behind for their own shapes (taskbar strength
≈ radius 40, flyouts ≈ radius 90 equivalent, corners 8). App blur for Settings: not needed (Settings is our own app).

### 5.4 Desktop Icons NG (patched) → `qml/desktop`

Configuration (`dconf/local.d/00-fenestra:294-301`): small icons, Trash shown, Home not shown, no volumes, no link
emblem. Patches: empty vs non-empty folder icons (`assets/folders/folder-{empty,full}.png`), updated by a directory
monitor unless the user chose an icon (`ding/app/fileItem.js:280-320`); context-menu items get `win11-menu-*` icons
(`ding/app/desktopIconsUtil.js:400-428`); "New" submenu with Folder first, then `~/Templates` files
(`ding/app/desktopManager.js:693-694`, templates in `skel/Templates/`). GTK3 menu styling `.desktopmenu` min-width 260,
items 30 px (`skel/.config/gtk-4.0/gtk.css:81-83`).

New architecture: `qml/desktop` desktop icon grid (DING is a GNOME Shell extension + GTK app and does not run under KWin).

### 5.5 Rounded Window Corners Reborn (patched) → `kwin/` rounded corners

Configuration: radius 8, border colour `[0.5,0.5,0.5,1.0]`, no smoothing, no padding, not kept for maximized/fullscreen,
libadwaita/libhandy windows not skipped (`dconf/local.d/00-fenestra:309-315`). Patches: snapped/tiled windows (half,
column, row, quarter, or tiled by Tiling Assistant/mutter) get square corners (`rwc/manager/utils.js:252-255`,
`rwc/manager/utils.js:288-310`); GNOME 51 compatibility base class replacing the removed `Shell.GLSLEffect`
(`rwc/effect/glsl_compat.js:1-40`).

New architecture: `kwin/` rounded corners effect (radius 8, square when maximized/fullscreen/tiled, thin border) — or a
decoration that rounds the frame for SSD windows plus the effect for CSD.

### 5.6 Tiling Assistant (configured) → `kwin/` Snap Layouts + KWin quick tiling

Configuration (`dconf/local.d/00-fenestra:317-359`): tiling popup off, gap 0, focus hint off; Super+Left/Right halves
(+KP_4/KP_6), Super+Up maximize (+KP_5), Super+Down restore, keypad quarters/halves (KP_1,2,3,7,8,9); it overrides mutter
edge tiling and the maximize keybindings (`:334`), and mutter `edge-tiling=false` / toggle-tiled bindings empty
(`dconf/local.d/00-fenestra:396-404`). Snap preview styled in `tray/stylesheet.css:115-121`.

New architecture: KWin quick tiling for the keyboard shortcuts; `kwin/` Snap Layouts script (layout picker on maximize
button hover / drag to top) — not present in the GNOME build (popup disabled); preview style from tokens.

### 5.7 Notification Banner (configured) → `qml/notifications`

Configuration: banners bottom-right, padding 12 / 12 (`dconf/local.d/00-fenestra:303-307`). It moves
`Main.messageTray._bannerBin`. New: toast stack anchored bottom-right, 12 px from the work area.

### 5.8 No Screenshot Box (defaults only)

Not configured in dconf (its defaults apply): GNOME's screenshot UI starts with no pre-selected area and captures on
release (`desktop/extensions/no-screenshot-box@screenshot/extension.js:1-40`). Shortcuts are GNOME's: Super+Shift+S and
Print (`dconf/local.d/00-fenestra:361-364`). Not needed under KWin; the replacement screenshot tool must be bound to the
same shortcuts and should start without a pre-selection.

---

## 6. Resources

### 6.1 assets/generated (installed to /usr/share/fenestra/assets)

| Folder | Content | Used by | New home |
|---|---|---|---|
| `battery/` | 99 SVGs `{normal,low,saver,charging}-{0,1}-{0..10}` + `plugged-1-{0..10}`, 24×24, white strokes, `#ff99a4` for low | `tray/extension.js:113` | `qml/tray` battery |
| `status/` | 22 battery SVGs (`normal|charging-0-*`) + 8 `network-wireless-*-symbolic.svg` | `spot/lockStatus.js:20-37` | `qml/lock` |
| `osd/` | brightness, keyboard, mic, mic-off, speaker-0..3, speaker-mute (16×16, stroke `#ffffff` 1 px) | `tray/osdStyle.js:30-40` | `qml/osd` |
| `privacy/` | camera, location, mic | `tray/privacyIcons.js:31` | `qml/tray` |
| `security/` | accessibility, network-{offline,wifi,wired}, power, restart, shutdown, sleep | `tray/securityScreen.js` | `qml/security` |
| `power/` | `0,1,2,3,4,7.svg` = ArcMenu PowerType logout, lock, restart, power-off, suspend, switch-user (`#eeeeee` fill) | `arc/menulayouts/windowsPower.js:21` | `qml/start` power/account menus |
| `consent/` | close, shield | `consent/presentation.js:28-33` | `qml/security` |
| `search/` | `search.svg`, `search.png` 64×64 | Search entry glyph, `fenestra-search.desktop` icon | `qml/search`, `qml/taskbar` |
| `hello/` | 24 `search-*.png` + 12 `auth-*.png` (300×300, 16-bit grey+alpha), `frames.json` (40 ms per frame: 960 ms loop, 480 ms success) | `spot/hello.js` | `qml/lock` |
| `folders/` | `folder-empty`, `folder-full` (SVG + 256×256 PNG) | DING, Files | `qml/desktop` |
| `menu-icons/` | 81 SVGs: `win11-explorer-*`, `win11-menu-*`, `win11-view-*`, `window-{close,maximize,minimize,restore}-symbolic` | copied into the Fenestra icon theme (`tools/build-fenestra-icons.py:46-52`) | icon theme (unchanged); caption glyphs also for `kwin/` decoration |
| `branding/` | `fenestra-logo.svg`, `fenestra-logo-256.png`, `start-button.svg` | ArcMenu button (`dconf/local.d/10-fenestra-theme:34`), shell Start (`shell/qml/taskbar/Taskbar.qml`) | `qml/taskbar` |
| `wallpapers/` | `fenestra-bloom-{dark,light}.jpg` 3840×2400 | `dconf/local.d/10-fenestra-theme:17-22` | `qml/desktop` wallpaper per scheme |

Licences: Fluent UI System Icons MIT (`assets/LICENSES/fluentui-system-icons-MIT.txt`). Generated by
`tools/generate-assets.py`. The `tint()` rule (2.2) assumes white `#ffffff`/`#eeeeee` source fills.

### 6.2 desktop/themes (GTK)

`Fenestra-Dark` and `Fenestra-Light` (GTK 3 + 4, based on Fluent GTK theme) with `gtk-auto.css` that switches on
`prefers-color-scheme` (`desktop/themes/Fenestra-Dark/gtk-4.0/gtk-auto.css:1-5`). Fenestra block at the end of each theme:
`fenestra_menu_bg rgba(44,44,44,0.96)` / light `rgba(249,249,249,0.96)`, menu fg `#f4f4f4` / `#1a1a1a`, border
`rgba(255,255,255,0.10)` / `rgba(0,0,0,0.08)`, hover `rgba(255,255,255,0.065)` / `rgba(0,0,0,0.04)`, separator
`rgba(255,255,255,0.07)` / `rgba(0,0,0,0.08)`, caption fg `#eeeeee` / `#1a1a1a`, caption hover `.08/.10` / `.05/.06`, active
`.16` / `.09` (`desktop/themes/Fenestra-Dark/gtk-4.0/gtk.css:8398-8411`, `desktop/themes/Fenestra-Light/gtk-4.0/gtk.css:8402-8410`);
window bg `#333333` / `#F2F2F2` (`:8345`). The static default accent baked into the themes is green `#647C64`
(light `#526552`, accent text `#a8bea7`) (`desktop/themes/Fenestra-Dark/gtk-4.0/gtk.css:8399-8401`,
`desktop/themes/Fenestra-Dark/gtk-4.0/gtk-auto.css:4-5`), while the shipped default accent is `#0078D4` — the live wrapper
theme from `tray/appearance.js` hides the difference; without fenestra-tray (KWin session) GTK apps would show green until
`services/session` writes the wrapper. `index.theme` still names `IconTheme=Windows11-status-original`
(`desktop/themes/Fenestra-Dark/index.theme:6`). New home: unchanged (GTK apps), accent writer moves to `services/session`.

### 6.3 desktop/skel (per-user defaults)

- `skel/.config/gtk-4.0/gtk.css`: imports `gtk-auto.css`, `fenestra-accent.css`, `fenestra-caption-buttons.css` (`:1-5`);
  GTK menus/popovers radius 8, padding 4, rows 30 px radius 4, dark `rgba(44,44,44,0.96)`, hover `rgba(255,255,255,0.065)`,
  separator `rgba(255,255,255,0.07)` (`:69-79`), light variants (`:474-479`); Chromium CSD caption tweaks: header 32 px,
  buttons 46×32 (40 px when restored), close hover `#c42b1c`, pressed `#a51c28`, close top-right radius 8 except maximized /
  tiled / fullscreen (`:87-142`); `:144-576` is File Explorer (patched Nautilus) styling — app-level, not part of the shell.
- `skel/.config/gtk-3.0/gtk.css`: imports `colors.css` and `fenestra-caption-buttons.css` (`:1-2`), same menu and Chromium
  rules using the theme's named colours (`:47-124`).
- `colors.css` (identical GTK 3/4) are Breeze-named colour definitions (`skel/.config/gtk-4.0/colors.css:1-40`);
  `window_decorations.css` points GTK 3 title buttons at PNG/SVG assets in `skel/.config/gtk-3.0/assets/`
  (`skel/.config/gtk-4.0/window_decorations.css:1-71`).
- `settings.ini`: cursor Bibata-Original-Classic 32, decoration layout `appmenu:minimize,maximize,close`, font "Segoe UI
  Variable Text 10", icon theme Fenestra, theme Fenestra-Dark (GTK 3 also prefer-dark) (`skel/.config/gtk-4.0/settings.ini`,
  `skel/.config/gtk-3.0/settings.ini`).
- `skel/Templates/`: Bitmap image.bmp, Compressed (zipped) Folder.zip, Excel Worksheet.xlsx, PowerPoint Presentation.pptx,
  Rich Text Format.rtf, Text Document.txt, Word Document.docx (desktop "New" menu, 5.4).

New home: unchanged for GTK apps; the shell reads the same cursor/font/icon defaults for Qt (see 6.6).

### 6.4 Caption buttons CSS (desktop/gtk)

`gtk/caption-buttons-gtk4.css` (installed as `/usr/share/fenestra/gtk-4.0/caption-buttons.css`, synced by 2.4):
buttons 46×32, no border/radius, transparent, glyph 16 px from the icon theme (`:11-22`); hover `alpha(currentColor, 0.0605)`,
pressed `0.0419` with glyph opacity 0.786, inactive window glyph 0.3628 (`:23-26`); close hover `#c42b1c` white glyph,
pressed 90 % with glyph 0.7 (`:27-29`); transitions 83 ms linear (`:17`); close top-right radius 8 on floating windows
(`:31`); mutter X11 frame title 12 px 400 (`:33`); in header bars buttons fill 47 px height, flush with the corner (−6 px
margins) (`:34-40`). `gtk/caption-buttons-gtk3.css` has the same metrics for GTK 3 (`:1-38`, header bar 46 px, −6 px
between buttons). `gtk/settings-gtk{3,4}.ini`: system fallback decoration layout, icon theme, GTK theme.
`gtk/60-fenestra-qt.conf` sets `QT_QPA_PLATFORM=xcb;wayland` so Qt apps get mutter's X11 frames (`:1-6`).

New home: GTK CSD CSS unchanged. The same metrics define the `kwin/` window decoration (SSD apps, Qt apps). Under KWin,
Qt apps can use server-side decorations natively, so `60-fenestra-qt.conf` (forcing XWayland) should be revisited.

### 6.5 desktop/dconf (defaults)

Besides the extension settings already listed:
- Fonts: UI "Segoe UI Variable Text 10", documents 11, monospace "Cascadia Mono 10", title bar "Segoe UI Variable 10"
  (`dconf/local.d/10-fenestra-theme:9-11`, `dconf/local.d/00-fenestra:389`); antialiasing grayscale, hinting slight
  (`dconf/local.d/00-fenestra:376-377`).
- Theme: GTK `Fenestra-Dark`, icons `Fenestra`, cursor `Bibata-Original-Classic` 32, `prefer-dark`, accent `blue`, custom
  accent `#0078D4` (`dconf/local.d/10-fenestra-theme:3-8`, `:30-31`); battery percentage off, no weekday, no hot corners
  (`:12-14`).
- Wallpaper light/dark and lock picture (`dconf/local.d/10-fenestra-theme:16-22`), zoom.
- Window manager: buttons `appmenu:minimize,maximize,close` (`dconf/local.d/00-fenestra:387`), 1 workspace but dynamic
  workspaces true (`dconf/local.d/00-fenestra:388`, `:397`), mutter experimental features `scale-monitor-framebuffer`,
  `variable-refresh-rate`, `xwayland-native-scaling` (`:399`), overlay key `Super_L` (`:400`), overview/app-view
  shortcuts cleared (`:363-364`).
- Shortcuts: Ctrl+Shift+Esc → `fenestra-taskmgr` (`dconf/local.d/10-fenestra-theme:46-53`); Ctrl+Alt+Del freed for the
  security screen (`:36-39`); screenshot Super+Shift+S, Print (`dconf/local.d/00-fenestra:362`).
- Input: mouse natural scroll off, touchpad natural scroll on, speed 0.0864, two-finger scrolling (`:422-432`).
- Misc: night light off (`:435`), event sounds off (`:442`), banners on (`:445`), Tracker indexes on AC only (`:469-471`),
  Nautilus views (`:406-420`), GTK file chooser (`:451-461`).
- GDM: enabled extensions login + spotlight, icons/cursor/font/dark, user list enabled (`dconf/gdm.d/90-fenestra:1-12`).

New home: `kwinrc`/`kdeglobals`/`kcminputrc` defaults for the KWin session (fonts, cursor, input, shortcuts, decoration
button order, no virtual desktops by default, VRR/scaling are KWin defaults), `shell.conf` for shell options; GTK keys
stay in dconf for GTK apps.

### 6.6 desktop/fontconfig

`desktop/fontconfig/60-fenestra.conf:7-14`: "Segoe UI Variable" → Segoe UI Variable Text → Segoe UI → Selawik; the
Text/Display/Small variants → Segoe UI → Selawik; "Segoe UI" → Selawik; "Fenestra Taskbar Text" → Segoe UI Variable Small
→ Segoe UI → Selawik; "Fenestra UI" → Segoe UI Variable Text → Segoe UI → Selawik; Consolas → Cascadia Mono. The Segoe
files exist only if the user imported their own (`desktop/fontconfig/60-fenestra.conf:3-5`); Selawik 1.01 is downloaded at
build (`build/build-overlay.sh:17`, `:119-125`). New home: unchanged; QML should name "Fenestra UI" / "Fenestra Taskbar
Text" families (token `font.*`).

### 6.7 Icon theme (tools/build-fenestra-icons.py)

Builds `/usr/share/icons/Fenestra` on top of Win11 + Win11-dark (pinned commit, `build/build-overlay.sh:15`, `:103-109`):
copies alias names for the patched Files sidebar (`twne`→user-trash, `twnf`→user-trash-full, `rwin`→folder-temp,
`dwin`→folder-documents, `dlwin`→folder-download, `mwin`→folder-music, `pwin`→folder-camera, `pubwin`→folder-public,
`tmpwin`→folder-templates, `vwin`→folder-videos, `nwin`/`network-drvwin`→network-server, `drvwin`→drive-harddisk,
`hwin`→home, `non-swin`→starred) (`tools/build-fenestra-icons.py:16-21`, `:33-45`); adds all `assets/menu-icons/*.svg` under
`scalable/actions` (`:46-52`); `Inherits=Win11-dark,Win11,Adwaita,hicolor` (`:53-54`). New home: unchanged (Qt reads XDG
icon themes; set `Fenestra` in `kdeglobals`).

### 6.8 Cursor

Bibata Original Classic v2.0.7, downloaded at build (`build/build-overlay.sh:16`, `:112-117`), size 32
(`dconf/local.d/10-fenestra-theme:5-6`). New home: same theme name/size in `kcminputrc` for KWin.

### 6.9 Plymouth theme (desktop/libexec/fenestra-plymouth-theme)

Generates a script theme (`ModuleName=script`) with frames drawn by Pillow (`desktop/libexec/fenestra-plymouth-theme:1-20`):
- Boot: firmware BGRT logo at native size/position (`:115-128`, `:206-221`) and a progress ring of 60 frames (2 s cycle):
  42 px arc, 4 px stroke, round caps, head runs 285° with a cubic ease then the tail catches up, whole ring rotating 300°
  per cycle, centred at 78.4 % of the height (`:36`, `:58-80`, `:108`).
- Restart / shut down / updates: black, six 6.5 px dots on a 29.5 px circle, 96 frames (3.2 s at 30 fps), two turns with a
  fast-top/slow-bottom easing, centred at 48.5 % (`:35`, `:39-55`, `:101`); text "Restarting", "Shutting down", or
  "Working on updates / NN% complete / Don't turn off your computer" with live progress (`:27-32`, `:137-156`), EN/ES.
- Everything scales with `k = H/1080`; frames drawn at 2× and 4× supersampling (`:33-34`, `:87`); font "Segoe UI
  Variable Text" if installed, else "Selawik Semilight", else Sans (`:223-226`); text size `15·k`, first line `46·k` below
  the spinner centre, line step `30·k` (`:130-134`) — the docstring says ~20 px and 60 px (`:14-15`), the code uses 15/46/30.
- Password / question prompts at 60 % height (`:165-181`); optional dracut module links the theme font as Plymouth.ttf
  (`:246-272`).
New home: unchanged (independent of the compositor); its dot/ring geometry can be reused for the shell's restart/shutdown
overlay in `qml/security` if one is wanted.

### 6.10 docs/images

48 PNG reference screenshots of the GNOME implementation: desktop, taskbar weather/search, Start/Search/menus/quick
settings/calendar/notifications/OSD in dark and light (`theme-{dark,light}-*.png`), accent blue/green variants
(`accent-*`), notification states (`notifications-calendar-{collapsed,empty}.png`), OSD (`osd-{brightness,volume,volume-muted}.png`),
Ctrl+Alt+Del (`ctrl-alt-del*.png`), File Explorer pages (`explorer-*.png`), wordmarks. Use as the visual baseline when
comparing the QML surfaces.

---

## 7. Findings (present in code, not obvious from the piece list)

1. `tray/notifications.js` is never imported (dead); banner position comes from Notification Banner.
2. Hard-coded Spanish UI strings regardless of locale: overflow tooltip "Mostrar iconos ocultos"
   (`tray/trayLayout.js:14`), media buttons "Anterior/Pausar/Siguiente" and fallbacks "Reproduciendo"/"Multimedia"
   (`tray/mediaPanel.js:17-19`). ArcMenu Start/Search additions are English-only (`arc/menulayouts/windowsStartHome.js`,
   `arc/windowsSearchHome.js`, `arc/windowsSearchResults.js`).
3. `spot/face.js:38-43` contains an unused clock face with a hard-coded `es-ES` 24 h format (the laptop copy
   `sysext/single-user-gdm@local/face.js` actually uses that variant).
4. Static default accent mismatch: GTK themes and some CSS fallbacks are green (`#647C64`, `#7b937b`, `#566e56`, `#a8bea6`,
   `#b9d1ba`; `desktop/themes/Fenestra-Dark/gtk-4.0/gtk.css:8399`, `tray/stylesheet.css:322`, `:357-358`,
   `arc/windows-search.css:34`, `consent/stylesheet.css:27`) while the shipped accent is `#0078D4` and the CSS fallback
   `#4cc2ff`. Everything is corrected at runtime by `tray/appearance.js`; the new shell must not depend on these fallbacks.
5. `tray/light.css:148` and `tray/appearance.js:164` style classes no JS creates (`.windows-calendar-time`,
   `.windows-panel-small-button`).
6. Two different Start footer styles in `arc/menulayouts/eleven.js` (`:136` vs `:283-286`); the second wins.
7. `sysext/windows-spotlight@local/status-assets/network-wireless-*.svg` are empty files.
8. Privacy-relevant state: Search history in `~/.local/state/windows-search/history.json`
   (`arc/windowsSearchHome.js:26`); web search goes to bing.com (`arc/windowsSearchHome.js:55`,
   `arc/windowsSearchResults.js:217`).
9. Workspaces: `num-workspaces=1` with `dynamic-workspaces=true` (`dconf/local.d/00-fenestra:388`, `:397`) and the overview
   blocked — there is no Task View today; Task View under KWin is new work.
10. The Snap Layouts picker does not exist today (Tiling Assistant popup disabled, `dconf/local.d/00-fenestra:328`); only
    keyboard snapping and the snap preview style.
11. `gtk/60-fenestra-qt.conf` forces Qt apps onto XWayland (for mutter frames) — counterproductive under KWin.
12. `fenestra-consent` writes a PID marker `$XDG_RUNTIME_DIR/fenestra-consent-enabled` (`consent/extension.js:20-21`).
13. `shell/qml/taskbar/Taskbar.qml` show-desktop strip is 8 px; Dash to Panel used 7 px (`dconf/local.d/00-fenestra:263`).
14. Plymouth docstring metrics (~20 px text, 60 px offset) differ from the code (15·k, 46·k).

---

## 8. Values for design/tokens.json

Units: logical px unless noted; durations ms. "dark/light" = colour scheme. Accent-derived values are formulas
(see `accent.*`). Sorted by area.

### 8.1 Accent and palette

| Name | Value | Source |
|---|---|---|
| accent.default.custom | `#0078D4` | `dconf/local.d/10-fenestra-theme:30` |
| accent.default.enum | `blue` | `dconf/local.d/10-fenestra-theme:8` |
| accent.enum.blue | base `#0078d4`, dark fill `#4cc2ff`, light fill `#005fb8` | `tray/appearance.js:29` |
| accent.enum.teal | `#038387`, `#4fd6cb`, `#00777b` | `tray/appearance.js:29` |
| accent.enum.green | `#107c10`, `#6ccb5f`, `#0f7b0f` | `tray/appearance.js:30` |
| accent.enum.yellow | `#ffb900`, `#ffd75e`, `#9d5d00` | `tray/appearance.js:30` |
| accent.enum.orange | `#ca5010`, `#ff9a5c`, `#bc4b09` | `tray/appearance.js:31` |
| accent.enum.red | `#e81123`, `#ff99a4`, `#c42b1c` | `tray/appearance.js:31` |
| accent.enum.pink | `#e3008c`, `#f7a2cf`, `#bf0077` | `tray/appearance.js:32` |
| accent.enum.purple | `#744da9`, `#d6a4f2`, `#8764b8` | `tray/appearance.js:32` |
| accent.enum.slate | `#68768a`, `#a8bccf`, `#515c6b` | `tray/appearance.js:33` |
| accent.custom.darkFill | lighten by 10 % white steps until contrast ≥ 3.0 vs `#202020` | `tray/appearance.js:90` |
| accent.custom.lightFill | HSL L −0.08, then −0.01 until contrast ≥ 4.5 vs `#ffffff` (min L 0.05) | `tray/appearance.js:72-77` |
| accent.on | `#000000` if relative luminance > 0.25 else `#ffffff` | `tray/appearance.js:83` |
| accent.text.dark | lighter(darkFill): L→0.72, S×1.5 (if L < 0.72) | `tray/appearance.js:78-81`, `:98` |
| accent.text.light | lightFill | `tray/appearance.js:98` |
| accent.hover.dark / light | mix(fill, white, 0.15) / mix(fill, white, 0.10) | `tray/appearance.js:99` |
| accent.press.dark / light | mix(fill, black, 0.14) / mix(fill, white, 0.20) | `tray/appearance.js:100` |
| accent.wallpaper | 32×32 sample, step 2, score S·(1−2·|L−0.5|), S clamp 0.25–0.75, L 0.42 | `tray/appearance.js:144-154` |
| accent.menuActive.dark / light | fill at 0.45 / 0.25 alpha | `tray/appearance.js:178` |
| accent.startMenuActive.dark / light | fill at 0.35 / 0.25 alpha | `tray/appearance.js:344` |
| accent.focusRing | accent text at 0.7 alpha, inset 2 px | `tray/appearance.js:177` |
| accent.entryFocus | border fill + inset 0 −2 px accent text | `tray/appearance.js:176` |
| accent.splitDivider | 1 px `on` at 0.12 | `tray/appearance.js:169` |
| accent.fallback.css | `#4cc2ff` fill, `#000000` text | `tray/stylesheet.css:42-43` |
| accent.osdFallback | blue `#4cc2ff`, teal `#4fd6cb`, green `#6ccb5f`, yellow `#ffd75e`, orange `#ff9a5c`, red `#ff99a4`, pink `#f7a2cf`, purple `#d6a4f2`, slate `#a8bccf` | `tray/osdStyle.js:14-15` |
| glyph.tint.dark / light | `#ffffff` / `#1a1a1a` (replaces `#ffffff`, `#eeeeee`) | `tray/appearance.js:367-368` |
| glyph.tint.lightCritical | `#ff99a4`/`#e5484d` → `#c42b1c`; `#fce100`/`#e5a900` → `#9d5d00` | `tray/appearance.js:371` |

### 8.2 Neutral colours and surfaces

| Name | Value | Source |
|---|---|---|
| color.text.dark | `#ffffff` | `tray/stylesheet.css:23` |
| color.text.light | `#1a1a1a` | `tray/light.css:5` |
| color.textSecondary.dark | `#c5c5c5` | `tray/stylesheet.css:263`, `:276` |
| color.textSecondary.light | `#5f5f5f` | `tray/light.css:5` |
| color.textSecondary.light.alt | `#5c5c5c` (weather, search box) | `tray/light.css:258`, `:262` |
| color.textDisabled.light | `rgba(0,0,0,0.36)` | `tray/light.css:29` |
| color.otherMonth.dark / light | `#7f7f7f` / `#8a8a8a` | `tray/stylesheet.css:319`, `tray/light.css:157` |
| surface.flyout.dark | `rgba(32,32,36,0.80)`, border `rgba(255,255,255,0.10)`, radius 8 | `tray/stylesheet.css:20-22` |
| surface.flyout.light | `rgba(249,249,249,0.85)`, border `rgba(0,0,0,0.08)`, shadow `0 8px 16px rgba(0,0,0,0.14)` | `tray/light.css:19-22` |
| surface.quickSettings.light | `rgba(243,243,243,0.88)` | `tray/light.css:97` |
| surface.card.dark | `rgba(28,28,28,0.96)`, border `rgba(255,255,255,0.08)`, shadow `0 8px 16px rgba(0,0,0,0.28)` | `tray/stylesheet.css:223-224` |
| surface.card.light | `rgba(243,243,243,0.94)`, border `rgba(0,0,0,0.08)`, shadow `0 8px 16px rgba(0,0,0,0.14)` | `tray/light.css:137-138` |
| surface.calendarCard.dark / light | `rgba(36,36,36,0.97)` / `rgba(249,249,249,0.94)` | `tray/stylesheet.css:286`, `tray/light.css:140` |
| surface.cardHeader.dark / light | `rgba(28,28,28,1)` (collapsed `rgba(36,36,36,1)`) / `rgba(243,243,243,1)` | `tray/stylesheet.css:288`, `:291`, `tray/light.css:143` |
| stroke.cardDivider.dark / light | `#191919` / `rgba(0,0,0,0.06)` | `tray/stylesheet.css:289`, `tray/light.css:143` |
| surface.notification.dark | `#242424`, hover `#2a2a2a`, radius 6 | `tray/stylesheet.css:255`, `:258` |
| surface.notification.light | `rgba(255,255,255,0.85)`, hover `rgba(249,249,249,0.70)`, border `rgba(0,0,0,0.06)` | `tray/light.css:166-169` |
| surface.toast.dark | `rgba(32,32,36,0.80)`, border `rgba(255,255,255,0.12)`, radius 8 | `tray/stylesheet.css:336-339` |
| surface.media.dark | `rgba(32,32,36,0.80)`, border `rgba(255,255,255,0.12)` | `tray/stylesheet.css:203` |
| surface.media.light | `rgba(249,249,249,0.85)`, border `rgba(0,0,0,0.08)` | `tray/light.css:127` |
| surface.quickFooter.dark / light | `rgba(0,0,0,0.14)` + top `rgba(255,255,255,0.08)` / `rgba(238,238,238,0.85)` + top `rgba(0,0,0,0.06)` | `tray/stylesheet.css:137`, `tray/light.css:117` |
| surface.quickSubmenu.dark / light | `rgba(32,32,36,0.80)` / `rgba(249,249,249,0.92)` | `tray/stylesheet.css:140`, `tray/light.css:122` |
| surface.osd.dark / light | `rgba(32,32,32,0.85)`, border `rgba(255,255,255,0.08)`, shadow `0 8px 16px rgba(0,0,0,0.26)` / `rgba(249,249,249,0.92)`, `rgba(0,0,0,0.06)`, `0 8px 16px rgba(0,0,0,0.14)` | `tray/stylesheet.css:376-379`, `tray/light.css:208-210` |
| surface.tooltip.dark | `rgba(43,43,43,0.98)`, border `rgba(255,255,255,0.14)`, shadow `0 2px 6px rgba(0,0,0,0.24)` | `tray/stylesheet.css:197-199` |
| surface.tooltip.light | `rgba(249,249,249,0.98)`, border `rgba(0,0,0,0.10)`, shadow `0 2px 6px rgba(0,0,0,0.14)` | `tray/light.css:81-83` |
| surface.security.bg | `#000000` | `tray/stylesheet.css:407` |
| surface.security.menu | `#2c2c2c`, border `rgba(255,255,255,0.08)`, shadow `0 8px 16px rgba(0,0,0,0.36)` | `tray/stylesheet.css:438-441` |
| surface.security.cancel | `#333333`, hover `#3b3b3b`, active `#2b2b2b` | `tray/stylesheet.css:425`, `:432-433` |
| surface.consent.dialog | `#2b2b2b`, border `rgba(255,255,255,0.15)`, shadow `0 12px 36px rgba(0,0,0,0.4)` | `consent/stylesheet.css:9-11` |
| surface.consent.heading | `#333333` | `consent/stylesheet.css:17` |
| surface.consent.buttons | `#202020` | `consent/stylesheet.css:31` |
| surface.consent.light | dialog `#ffffff` border `rgba(0,0,0,0.10)` shadow `0 12px 36px rgba(0,0,0,0.22)`; heading/buttons `#f3f3f3` | `tray/light.css:235-240` |
| control.consentButton | bg `#383838`, hover `#454545`, border `#505050`; light `#fbfbfb`/`#f6f6f6`/`rgba(0,0,0,0.10)` | `consent/stylesheet.css:35-37`, `tray/light.css:241-244` |
| color.close.hover | `#c42b1c` | `gtk/caption-buttons-gtk4.css:27`, `consent/stylesheet.css:22` |
| color.close.pressed | `alpha(#c42b1c, 0.9)` (Chromium rule `#a51c28`) | `gtk/caption-buttons-gtk4.css:28`, `skel/.config/gtk-4.0/gtk.css:140` |
| taskbar.bg.dark / light | `#000402` at 0.63 / `#f3f3f3` at 0.85 | `dconf/local.d/00-fenestra:267`, `:277`, `tray/appearance.js:322-323` |
| taskbar.border.dark / light | 1 px `rgba(255,255,255,0.10)` / `rgba(0,0,0,0.08)` | `dconf/local.d/00-fenestra:268-270`, `tray/appearance.js:324` |
| taskbar.hover.dark / light | `rgba(255,255,255,0.08)` + inset 1 px `rgba(255,255,255,0.09)` / `rgba(255,255,255,0.70)` + inset `rgba(0,0,0,0.06)` | `tray/stylesheet.css:157-158`, `tray/light.css:70-71` |
| taskbar.pressed.dark / light | `rgba(255,255,255,0.12)` / `rgba(255,255,255,0.50)` | `dconf/local.d/00-fenestra:233`, `tray/appearance.js:326` |
| taskbar.dotUnfocused.dark / light | `#a0a0a0` / `#868686` | `dconf/local.d/00-fenestra:214`, `tray/appearance.js:331` |
| taskbar.previewTitle.dark / light | `#ffffff` / `#1a1a1a` | `tray/appearance.js:327` |
| control.subtle.bg / border | `rgba(255,255,255,0.06)` / `rgba(255,255,255,0.08)`; hover `0.10`; active `0.04` | `tray/stylesheet.css:229`, `:233-234` |
| control.subtle.light | `rgba(255,255,255,0.70)` + border `rgba(0,0,0,0.06)`, hover `rgba(249,249,249,0.50)` | `tray/light.css:179`, `:185` |
| control.hover.listRow.dark / light | `rgba(255,255,255,0.06)` / `rgba(0,0,0,0.04)` | `tray/stylesheet.css:317`, `tray/light.css:159` |
| control.switch | 40×20, border 1 px `#a0a0a0`, handle 12 px `#cccccc` margin 3, hover `rgba(255,255,255,0.06)`; light border `rgba(0,0,0,0.6)`, handle `rgba(0,0,0,0.62)` | `tray/stylesheet.css:46-58`, `tray/light.css:49-51` |
| control.checkbox | radius 4 (bin) / 3 (box), border `#aaaaaa`; light `rgba(0,0,0,0.45)` | `tray/stylesheet.css:63-64`, `tray/light.css:52` |
| control.slider | bar 4 px, handle radius 7, track `rgba(255,255,255,0.25)` / light `rgba(0,0,0,0.45)` | `tray/stylesheet.css:68-74`, `tray/light.css:53` |
| control.focusRing.neutral | inset 2 px `rgba(255,255,255,0.75)` | `tray/stylesheet.css:78` |
| control.menuItemActive | `rgba(255,255,255,0.08)` | `tray/stylesheet.css:80` |
| menu.gtk.dark / light | `rgba(44,44,44,0.96)` border `rgba(255,255,255,0.10)` hover `rgba(255,255,255,0.065)` separator `rgba(255,255,255,0.07)` / `rgba(249,249,249,0.96)` `rgba(0,0,0,0.06)` `rgba(0,0,0,0.039)` `rgba(0,0,0,0.042)` | `skel/.config/gtk-4.0/gtk.css:69-79`, `:474-479` |
| menu.start.foreground.dark / light | `rgb(245,245,245)` / `rgb(26,26,26)` | `tray/appearance.js:339` |
| menu.start.border.dark / light | `rgba(255,255,255,0.14)` / `rgba(0,0,0,0.10)` | `tray/appearance.js:340` |
| menu.start.separator.dark / light | `rgb(63,62,64)` / `rgb(229,229,229)` | `tray/appearance.js:341` |
| menu.start.itemHover.dark / light | `rgba(238,238,236,0.08)` / `rgba(0,0,0,0.04)` | `tray/appearance.js:342` |
| start.footer.dark / light | `rgba(0,0,0,0.21)` + top 1 px `rgba(0,0,0,0.2)` / `rgba(0,0,0,0.03)` + `rgba(0,0,0,0.06)` | `arc/menulayouts/eleven.js:283-284` |
| start.searchPill.dark / light | `rgba(28,28,28,0.75)` border `rgba(255,255,255,0.06)` / `rgba(255,255,255,0.85)` border `rgba(0,0,0,0.08)` | `arc/menulayouts/windowsStartHome.js:78` |
| start.categoryCard.dark / light | `rgba(255,255,255,0.04)` border `rgba(255,255,255,0.05)` / `rgba(255,255,255,0.6)` border `rgba(0,0,0,0.05)` | `arc/menulayouts/windowsStartHome.js:138` |
| start.secondaryText.dark / light | `#c8c8c8` (empty `#bcbcbc`) / `#5f5f5f` | `arc/menulayouts/windowsStartHome.js:94`, `:113` |
| start.powerMenu.dark / light | `rgba(44,44,44,0.96)` border `rgba(255,255,255,0.14)` / `rgba(249,249,249,0.96)` border `rgba(0,0,0,0.10)` | `arc/menulayouts/windowsPower.js:14` |
| acrylic.luminosity.dark | base 0.128, gain 0.265, chroma 0.65 | `arc/fenestraTheme.js:47`, `arc/windowsAcrylic.js:38` |
| acrylic.luminosity.light | base 0.84, gain 0.13, chroma 0.45 | `arc/fenestraTheme.js:47` |
| search.rowHover / selected (dark) | `rgba(255,255,255,0.05)` / `rgba(255,255,255,0.075)` | `arc/windows-search.css:47-48` |
| search.rowHover / selected (light) | `rgba(0,0,0,0.035)` / `rgba(0,0,0,0.052)` | `arc/windows-search.css:105-106` |
| search.chip | `rgba(255,255,255,0.055)`, border `rgba(255,255,255,0.04)`, hover `0.09`; light `rgba(255,255,255,0.7)`, border `rgba(0,0,0,0.06)`, hover `rgba(0,0,0,0.06)` | `arc/windows-search.css:29-33`, `:101-102` |
| search.preview | `rgba(255,255,255,0.05)`; card `rgba(255,255,255,0.045)` border `rgba(255,255,255,0.06)`; light `rgba(255,255,255,0.7)` | `arc/windows-search.css:60`, `:63`, `:110` |
| search.secondaryText | `#c8c8c8` / `#c8cbca`; detail key `#d0d3d2` | `arc/windows-search.css:19`, `:58`, `:72` |
| snap.preview.dark | `rgba(200,205,204,0.17)`, border `rgba(235,240,238,0.55)`, inset `rgba(255,255,255,0.07)` | `tray/stylesheet.css:117-120` |
| snap.preview.light | `rgba(255,255,255,0.35)`, border `rgba(0,0,0,0.15)`, inset `rgba(255,255,255,0.4)` | `tray/light.css:87-89` |
| tabbox.selected.light / outline.light | `rgba(0,0,0,0.06)` / `rgba(0,0,0,0.3)` | `tray/light.css:226-227` |
| osd.track.dark / light | `rgba(255,255,255,0.54)` / `rgba(0,0,0,0.45)` | `tray/osdStyle.js:77-78` |
| osd.thumb.dark / light | `rgb(69,69,69)` ring `rgba(255,255,255,0.09)` / `#ffffff` ring `rgba(0,0,0,0.08)` | `tray/osdStyle.js:86-91` |
| caption.hover / pressed / inactiveGlyph / pressedGlyph | `alpha(currentColor,0.0605)` / `0.0419` / opacity 0.3628 / 0.786 | `gtk/caption-buttons-gtk4.css:23-26` |
| window.border | `[0.5,0.5,0.5,1.0]` (rounded corners border) | `dconf/local.d/00-fenestra:311` |
| lock.fallbackBg | `#202020` | `lockclock/face.js:11`, `spot/startup.js:12` |
| lock.dimmer | black at 82/255 | `lockclock/extension.js:106`, `login/extension.js:88` |
| bgrt/plymouth.bg | `#000000`, text white | `desktop/libexec/fenestra-plymouth-theme:84-85`, `:139` |

### 8.3 Typography

| Name | Value | Source |
|---|---|---|
| font.ui | "Segoe UI Variable" → Segoe UI Variable Text → Segoe UI → Selawik ("Fenestra UI" alias) | `tray/stylesheet.css:28`, `desktop/fontconfig/60-fenestra.conf:7`, `:13` |
| font.taskbar | "Fenestra Taskbar Text" (→ Segoe UI Variable Small) | `tray/extension.js:83`, `desktop/fontconfig/60-fenestra.conf:12` |
| font.mono | "Cascadia Mono" 10 | `dconf/local.d/10-fenestra-theme:11` |
| font.system.size | 10 pt ("Segoe UI Variable Text 10"), documents 11 pt | `dconf/local.d/10-fenestra-theme:9-10` |
| font.titlebar | "Segoe UI Variable" 10 pt; X11 frame title 12 px 400 | `dconf/local.d/00-fenestra:389`, `gtk/caption-buttons-gtk4.css:33` |
| type.caption | 12 px 400 (clock, tray, captions, tooltips, time, chips 12) | `tray/stylesheet.css:134`, `:194`, `:262` |
| type.body | 14 px 400 | `tray/stylesheet.css:225`, `:275` |
| type.bodyStrong | 14 px 600 (card titles, month, section headings) | `tray/stylesheet.css:240`, `:299`, `arc/menulayouts/windowsStartHome.js:22` |
| type.searchBox | 13 px | `tray/stylesheet.css:468`, `arc/windows-search.css:3` |
| type.subtitle | 18 px 600 (Search home heading) | `arc/windows-search.css:9` |
| type.title | 20 px 600 (Search preview hero) | `arc/windows-search.css:77` |
| type.consentQuestion | 19 px 400 | `consent/stylesheet.css:23` |
| type.mediaTitle | 15 px 600; app/artist 13 px | `tray/stylesheet.css:343-346` |
| type.lockTime | 96 px 600 | `lockclock/face.js:46` |
| type.lockDate | 18 px 400 | `lockclock/face.js:47` |
| type.loginName | 24 px 400 | `spot/stylesheet.css:6-11` |
| type.clock.letterSpacing | −0.4 px (Pango −500) | `tray/trayLayout.js:10`, `tray/extension.js:92` |
| type.calendarPager | 9 px glyphs ▲ ▼ | `tray/stylesheet.css:307` |
| type.searchChip | 14.3 px | `arc/windows-search.css:30` |
| type.startMenu | 14 px box, tiles 12 px, links 13 px | `arc/menulayouts/eleven.js:288`, `arc/menulayouts/windowsStartHome.js:15`, `:88` |
| type.plymouth | 15·k (k = H/1080) | `desktop/libexec/fenestra-plymouth-theme:130` |

### 8.4 Sizes, spacing, radii

| Name | Value | Source |
|---|---|---|
| radius.control | 4 | `tray/stylesheet.css:45`, `:127` |
| radius.toggle | 6 (GNOME toggles), 4 in the quick panel | `tray/stylesheet.css:32`, `:128` |
| radius.surface | 8 | `tray/stylesheet.css:21`, `dconf/local.d/00-fenestra:30` |
| radius.window | 8 | `dconf/local.d/00-fenestra:311` |
| radius.notification | 6 | `tray/stylesheet.css:255` |
| radius.pill | 16 (search box/pill), chips 15 | `tray/stylesheet.css:472`, `arc/windows-search.css:3`, `:29` |
| radius.calendarDay | 20 (circle in 40 px cell) | `tray/stylesheet.css:314` |
| radius.consentButton | 3 | `consent/stylesheet.css:34` |
| taskbar.height | 48 (padding top/bottom 4) | `dconf/local.d/00-fenestra:246`, `:248` |
| taskbar.tile | 40×40, icon margin 2, padding 4 | `tray/stylesheet.css:110-113`, `dconf/local.d/00-fenestra:203-204` |
| taskbar.startButton | 40×40, margin 0 2, icon 32 slot with 4 margin | `tray/stylesheet.css:91-103`, `dconf/local.d/00-fenestra:42` |
| taskbar.indicator.focused | length min(w−4s, 16s), thickness 3, 2s above bottom, s = 1 | `tray/taskbarStyle.js:21-25`, `dconf/local.d/00-fenestra:220` |
| taskbar.showDesktop.width | 7 | `dconf/local.d/00-fenestra:263` |
| tray.padding | overflow 10, keyboard 7, quick settings 3, date 10; icon gap 4; icons 16; nudge +1 | `tray/trayLayout.js:10`, `:47-48` |
| tray.battery.icon | 20 | `tray/extension.js:117` |
| tray.minWidth | overflow 16, keyboard 24 | `tray/trayLayout.js:16`, `:33` |
| tooltip.padding | 5 9, radius 4 | `tray/stylesheet.css:189-190` |
| tooltip.offset | 10 above icon, ≥4 from edges | `tray/privacyIcons.js:63-65` |
| flyout.gap | 12 above taskbar | `tray/flyoutGap.js:11` |
| flyout.edge | 13 from screen edge | `tray/flyoutGap.js:12` |
| quick.panel | min-width 400; grid margin 20; columns gap 12, rows 18; tile 104 wide, button 48 tall; icon 18; menu button 28; footer padding 10 20 | `tray/stylesheet.css:124-138` |
| media.card | 350 wide, padding 22 24, spacing 20; art 64; controls spacing 24; button padding 6; icon 22 | `tray/stylesheet.css:342-351`, `tray/mediaPanel.js:14` |
| calendar.card | 332 wide; stack spacing 12; header 48; month header 56; weekday 47×24; day 40×40 margin 1 3 1 4; pager 39×32; footer 48 | `tray/stylesheet.css:219-222`, `:287-330` |
| notification.card | heading padding 11 16; row header padding 10 8 0 12; body 12 12 14; app icon 48; buttons 32 tall | `tray/stylesheet.css:239`, `:259`, `:272-273`, `:280` |
| notification.maxHeightMin | 120 | `tray/calendarPanel.js:213` |
| iconButton.small | 22×22, icons 16 / 12 | `tray/stylesheet.css:228`, `:231-232` |
| osd.size | 192×48, padding 0 16, spacing 12, icon 16, value min-width 24 | `tray/stylesheet.css:373-386` |
| osd.slider | stroke 4, thumb radius 9, centre dot 5 | `tray/osdStyle.js:72`, `:76`, `:93` |
| osd.gap | 24 above work area | `tray/osdStyle.js:12` |
| toast.screenshot | 362 wide; thumbnail 330 × ≤160; preview padding 12 16 | `tray/stylesheet.css:364-365`, `tray/screenshotToast.js:32` |
| toast.margin | 12 right / 12 bottom | `dconf/local.d/00-fenestra:305-306` |
| security.layout | list x −72, width ≥139 (+19 text padding), y −177, row 44; Cancel y +83, 120×32; corner 40×40 at right 168/120/72, bottom 62; menu min-width 200, item 36, edge 12, gap 8 | `tray/securityScreen.js:35-36`, `:163`, `:319-320`, `tray/stylesheet.css:443-446` |
| security.focus | 2 px white; items 3 px above/below, buttons 3 px around | `tray/stylesheet.css:423`, `tray/securityScreen.js:185` |
| consent.dialog | 456 wide; title bar 32; close 46×32; padding 24; body 20 24; password entry 388; shield 32 | `consent/stylesheet.css:8-50`, `consent/presentation.js:33` |
| weather.widget | icon 28; padding 4 10 4 6; spacing 8; x +4; min free space 220 | `tray/weatherWidget.js:47`, `:125`, `:129`, `tray/stylesheet.css:457-460` |
| search.taskbarBox | 228×32, padding 0 14; icon+label 40 tall, padding 0 12 0 10; icon 18/20 | `tray/stylesheet.css:469-472`, `tray/taskbarSearch.js:35` |
| start.size | 832 wide, 864 tall (search 832×851 content) | `dconf/local.d/00-fenestra:47`, `:63-65`, `arc/menulayouts/runner.js:271` |
| start.header | padding 16 32 8; search pill 32 tall, padding 0 14 | `arc/menulayouts/eleven.js:90`, `arc/menulayouts/windowsStartHome.js:78` |
| start.pinned | 8 columns, 2 rows visible (16), tile 80×≥69, padding 4, margin 0 4 8, icon 32, grid margin 11 42 0 22 | `arc/menulayouts/windowsStartHome.js:84-90` |
| start.recommended | 3 columns × 2, item 224×≥40, icon 32, margin 9 24 8 50 | `arc/menulayouts/windowsStartHome.js:93`, `:104-106` |
| start.categoryCard | 154×154, 4 per row, icons 32 (margin 26 18 18 18) | `arc/menulayouts/windowsStartHome.js:137-143` |
| start.footer | min-height 58, padding 0 55 6 56; avatar padding 4 12 4 8 | `arc/menulayouts/eleven.js:283-284`, `:184` |
| start.powerMenu | min-width 124, padding 4, item 30 tall padding 0 10, icon 16 | `arc/menulayouts/windowsPower.js:14-21` |
| search.layout | results padding 23 32 18 25, list 328, preview 376 padding 23 25 25 24, result icon 40, best icon 32, indicator 3×16 | `arc/windows-search.css:38-60` |
| thumbnail.preview | 152, padding 8, title 13, icon 16, gap 3 | `dconf/local.d/00-fenestra:284-289`, `tray/previewStyle.js:5` |
| caption.button | 46×32 (header bar 47 / GTK3 46), glyph 16 | `gtk/caption-buttons-gtk4.css:12`, `:20`, `:39` |
| caption.closeRadius | top-right 8 when floating | `gtk/caption-buttons-gtk4.css:31` |
| gtk.menu | radius 8, padding 4, row 30 tall, padding 2 10, margin 1 0 | `skel/.config/gtk-4.0/gtk.css:69-70` |
| lock.clock.y | 13 % of height | `lockclock/face.js:60` |
| lock.status | right −100, bottom −44, spacing 18, Wi-Fi 18, battery 22 | `spot/lockStatus.js:11-13`, `:28` |
| lock.avatar | 192 round | `spot/stylesheet.css:3-4` |
| lock.hello | 64×64, margin 8 0 | `spot/hello.js:77-78` |
| plymouth.ring | 42 diameter, stroke 4, centre y 78.4 % | `desktop/libexec/fenestra-plymouth-theme:63-68`, `:108` |
| plymouth.dots | 6 dots of 6.5 on radius 29.5, centre y 48.5 % | `desktop/libexec/fenestra-plymouth-theme:40-47`, `:101` |
| cursor | Bibata-Original-Classic, 32 | `dconf/local.d/10-fenestra-theme:5-6` |
| blur.taskbar | radius 40, brightness 1.0 | `dconf/local.d/00-fenestra:78` |
| blur.flyout | radius 90, brightness 1.0, corners 8 | `dconf/local.d/00-fenestra:78`, `:116-129` |
| blur.start | radius 60 | `arc/windowsPopupMotion.js:15` |
| blur.thumbnail | radius 30 | `tray/previewStyle.js:5` |

### 8.5 Motion

| Name | Value | Source |
|---|---|---|
| motion.start.open | slide from +96, 200 ms, EASE_OUT_QUINT, clipped at taskbar | `arc/windowsPopupMotion.js:16-18`, `:132` |
| motion.start.close | slide to +96, 120 ms, EASE_IN_QUAD | `arc/windowsPopupMotion.js:17`, `:156` |
| motion.osd.in | opacity 0→1, rise 8, 150 ms, EASE_OUT_CUBIC | `tray/osdStyle.js:12`, `:134-135` |
| motion.osd.out | opacity →0, drop 4, 150 ms, EASE_IN_QUAD | `tray/osdStyle.js:156-157` |
| motion.osd.hideDelay | 1500 ms | `tray/osdStyle.js:12` |
| motion.press.down | scale 0.82, 90 ms, EASE_OUT_QUAD | `tray/pressAnimation.js:50` |
| motion.press.up | scale 1.0, 180 ms, EASE_OUT_BACK | `tray/pressAnimation.js:29` |
| motion.caption.hover | 83 ms linear (background, colour) | `gtk/caption-buttons-gtk4.css:17` |
| motion.lock.prompt | 300 ms EASE_OUT_CUBIC; clock −12 % H; prompt +16 → 0, opacity from 25 % progress | `lockclock/extension.js:36`, `:105-109` |
| motion.lock.unlock | fade 140 ms EASE_OUT_QUAD | `spot/transitions.js:55-56` |
| motion.lock.lock | no animation | `spot/transitions.js:37-38` |
| motion.login.dismiss | 300 ms EASE_OUT_CUBIC | `login/extension.js:88-89` |
| motion.startupCover | fade 160 ms EASE_OUT_QUAD, max wait 750 ms | `spot/startup.js:27`, `:34` |
| motion.firstLogin | fade 450 ms EASE_OUT_QUAD; smooth = 15 × 100 ms ticks (<130 ms), max 15 s; safety 90 s; OOBE first-frame fallback 3 s | `spot/firstLogin.js:17-19`, `:66-69`, `:77`, `:116` |
| motion.hello | frames 40 ms; success 260 ms | `assets/hello/frames.json`, `spot/hello.js:24-25` |
| motion.dtp.preview | 170 ms; hover delay 500 ms; peek 500 ms at 80 % | `dconf/local.d/00-fenestra:283`, `:262`, `:223`, `:249` |
| motion.dtp.hover | SIMPLE, travel 0.05, extent 1 | `dconf/local.d/00-fenestra:137-141` |
| motion.plymouth | ring 60 frames (2 s), dots 96 frames (3.2 s), cubic in-out ease | `desktop/libexec/fenestra-plymouth-theme:35-36`, `:58-59` |
| timing.weather.refresh | 15 min | `tray/weatherWidget.js:154` |
| timing.focus.default | 30 min, step 5, range 5–240 | `tray/calendarPanel.js:162`, `:167` |
| timing.clock.refresh | 60 s (GNOME); the QML taskbar aligns to the minute | `tray/extension.js:69`, `shell/qml/taskbar/Taskbar.qml` |
