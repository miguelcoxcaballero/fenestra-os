# Window frames: corners and caption buttons per toolkit

Windows 11 (DWM) rounds every top-level window itself (8 px at 100 %) whatever draws its frame,
and squares it while it is maximized or snapped. Fenestra does the same in KWin; the caption
buttons stay with whoever draws the title bar.

## Corners: `kwin/plugins/fenestra-corners` (KWin C++ effect)

| Window state | Corners | How |
|---|---|---|
| free-floating app window / dialog | round, 8 px x scale | offscreen copy + corner shader: square opaque corners clipped (antialiased) with a 1 px ring in the window's own edge colour; corners the toolkit already rounds, and its shadow, kept |
| quick-tiled / custom tile (snapped) | square | same shader in "square" mode: round corners (Aurorae's title bar, a toolkit that ignores the tiled state) rebuilt from the window's own edges |
| maximized / full screen | square | not touched (Aurorae and the toolkits square these), no offscreen copy, direct scan-out possible |
| shell surfaces, menus, tooltips, OSDs, lock screen | as drawn | not touched |

The plugin is built against kwin-devel and KWin loads it only at that exact version
(`KWIN_PLUGIN_VERSION_STRING`); the RPM requires the matching kwin-libs. On a running system:
`tools/install-kwin-corners.sh` (sudo into `/usr/lib64/qt6/plugins/kwin/effects/plugins`, then
`org.kde.KWin /Effects loadEffect fenestra-corners`, no restart). There is no per-user plugin
directory: kwin_wayland has file capabilities and ignores `QT_PLUGIN_PATH`.

Bench: `tests/window-frames` (`CORNERS=` the built `.so`, `APPS=1` Brave + Claude desktop,
`split.sh` tiles windows and captures frames in a row).

## Caption buttons

| Toolkit / app | Who draws the buttons | Fenestra |
|---|---|---|
| Qt, X11/Xwayland, GTK without header bar, anything asking for server-side decorations | KWin (Aurorae `Fenestra-Dark/Light`, `tools/build-aurorae-theme.py`) | 46 x 32, Segoe Fluent Chrome* glyph line art, hover 6 %, close #c42b1c |
| GTK 4 / libadwaita (Nautilus, Settings, Text Editor, Loupe, Calculator) | the app (CSD) | `desktop/gtk/caption-buttons-gtk4.css` imported by `~/.config/gtk-4.0/gtk.css` |
| GTK 3 header bars (gnome-disks, …) | the app (CSD) | `desktop/gtk/caption-buttons-gtk3.css` |
| Chromium / Brave with "GTK" theme and the custom frame | Chromium, with GTK 3's titlebutton CSS and window-*-symbolic icons | the GTK 3 file above; one glyph per button (bench: Brave 1.99) |
| Electron with `titleBarStyle: hidden` + `titleBarOverlay` (Claude desktop, VS Code-like apps) | Electron's own `FreedesktopNavButtonProvider` | **not themable**: a 24 px circle at 10 % of the text colour behind each glyph (Adwaita style), always; only a GTK theme whose name starts with "Breeze" switches it to its Breeze style (glyph alone at rest, 18 px circle on hover). The app hard-codes the overlay; no flag replaces it |
| Firefox | Firefox (GTK 3 CSD with `browser.tabs.inTitlebar`) | GTK 3 file; untested here |
| LibreOffice | VCL gtk3 backend: a plain GTK 3 window, KWin decorates it | Aurorae |
