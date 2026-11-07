# Fenestra icon pack format (v1)

A Fenestra icon pack is a `.zip` file. Fenestra never ships or downloads Microsoft
assets itself: packs are produced by the user from their own Windows installation
(with *Fenestra Icon Extractor* for Windows) or by third parties under their own
licences, and imported by the user.

```
pack.zip
├── fenestra-pack.json          (required)
├── fonts/                      *.ttf / *.otf          -> ~/.local/share/fonts/fenestra-pack/<id>/
├── cursors/                    *.cur / *.ani (raw)    -> converted to Xcursor on import
├── assets/                     same layout as /usr/share/fenestra/assets
│   ├── battery/  status/  power/  consent/  search/  folders/  branding/  menu-icons/  hello/
├── icons/                      freedesktop icon theme (index.theme + dirs) -> ~/.local/share/icons/<theme>/
├── glyphs/                     Segoe Fluent Icons glyphs as SVG + glyphs.json (see below)
├── apps/                       apps.json (app logo index) + light/<n>x<n>/<name>.png
├── bitmaps/                    <n>x<n>/<name>.png + bitmaps.json (reference icons and bitmaps)
├── filetypes/                  <n>x<n>/<key>.png + filetypes.json (file types, folders, drives, places)
├── weather/                    <Name>.svg + weather.json (taskbar / Widgets weather condition icons)
└── raw/                        optional untouched source files (e.g. Sysbatt.ttf, imageres groups, appx logos)
```

`fenestra-pack.json`:
```json
{
  "format": "fenestra-icon-pack",
  "version": 1,
  "id": "windows-11-user-export",
  "name": "Windows 11 (exported from my PC)",
  "generator": "Fenestra Icon Extractor 1.0",
  "source": {"os": "Windows 11", "build": "26200.6584", "locale": "es-ES"},
  "created": "2026-11-05T20:00:00Z",
  "contents": ["fonts", "cursors", "assets", "icons", "raw"],
  "icon_theme": "Fenestra-Windows",
  "cursor_theme": "Fenestra-Windows-Cursors",
  "accent": "#0078D4",
  "licence_note": "Personal export of files from the user's own Windows licence. Do not redistribute."
}
```

Optional fields and files (importers ignore anything they don't know):

| Field / file | Meaning |
|---|---|
| `accent` | `"#RRGGBB"`, the user's Windows accent colour (`HKCU\Software\Microsoft\Windows\DWM\AccentColor`) |
| `source.version`, `source.edition` | Windows display version (e.g. `25H2`) and edition ID |
| `cursor_scheme` | `{"name": "...", "roles": {"Arrow": "aero_arrow.cur", ...}}`: the user's pointer scheme (`HKCU\Control Panel\Cursors` role -> file in `cursors/`) |
| `assets/branding/settings.png` | Settings app icon (256 px), in addition to `icons/<theme>/256x256/apps/fenestra-settings.png` |
| `assets/wallpapers/windows-desktop.*`, `windows-lockscreen.*` | current wallpaper / lock screen picture (only when the user opts in) |
Importers must validate `format`/`version`, refuse paths with `..` or absolute paths,
cap total size (1 GB), and install everything per-user (never system-wide).

## Glyphs, app logos and reference bitmaps (Fenestra Icon Extractor 1.2)

What to export comes from `design/reference/icons.json` (branch `visual/reference`): every icon seen in
the Windows 11 reference screenshots, as names, module ids, Segoe Fluent Icons code points and package
families; no artwork. The extractor carries that table compiled in (`src/ReferenceIcons.g.cs`, generated
by `tools/gen-reference-icons.py`) and never reads icons.json at run time.

The files come from the user's own Windows (`C:\Windows\Fonts\SegoeIcons.ttf`, the `.mun`/`.dll`
modules, the installed app packages). They are never committed to this repository, attached to
releases or downloaded by Fenestra OS: Microsoft's page about the font says it may be used for design
and development "but you may not ship it to another platform"
([Segoe Fluent Icons font, Microsoft Learn](https://learn.microsoft.com/en-us/windows/apps/design/iconography/segoe-fluent-icons-font)).
Fenestra OS looks complete without them: every glyph and logo has a Fenestra-original fallback.

`"glyphs"`, `"apps"` and `"bitmaps"` are added to `contents` when present; the format `version` stays 1
and older importers ignore them.

### `glyphs/`

```
glyphs/glyphs.json        index (required when glyphs/ exists)
glyphs/<name>.svg         one per icons.json glyphs[] entry with a code point or an app-font glyph (265 of 293 today)
glyphs/u/<HEX>.svg        only with --all-glyphs: every code point of the font's cmap
glyphs/fonts/<stem>/<HEX>.svg  only with --all-glyphs: every code point of the apps' icon fonts (PaintIcons, SnSkFluent, …)
```

Each SVG is made from the font by the extractor's TrueType reader (`src/TrueType.cs`: `cmap` formats 4
and 12, `loca`/`glyf`, composite glyphs; quadratic contours to `M`/`L`/`Q` with the implied on-curve
midpoints; no hinting, no rasterising):

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2048 2048" width="16" height="16"><path fill="currentColor" fill-rule="nonzero" d="M…Z"/></svg>
```

viewBox = the em square (`unitsPerEm` read from the font), x as in the font, `y' = baseline - y` where
`baseline` is the hhea ascender (scaled into the em when ascender - descender differs from unitsPerEm;
for Segoe Fluent Icons they are equal). All glyphs share the em square, so they line up when layered.
`width`/`height` are only a hint.

```json
{
  "font": "SegoeIcons.ttf", "font_revision": "1.47", "units_per_em": 2048, "baseline": 2048,
  "reference": "design/reference/icons.json @ b8fa1b0",
  "glyphs": {"go-previous": {"codepoint": "U+E72B", "glyph": "Back", "file": "go-previous.svg", "verified": true}},
  "missing": ["document-edit", "draw-freehand", "edit-select-text", "cloud-offline"],
  "missing_reasons": {"draw-freehand": "no public code point (…)"}
}
```

Names are icons.json `glyphs[].name` (`^[a-z0-9][a-z0-9.+-]*$`), a namespace separate from `icons/`.

### App logos: `icons/<theme>/<n>x<n>/apps/`, `apps/`

For the 44 icons.json `apps[]` (sizes 256, 48, 32, 24, 16):

* `Appx` / `SystemApps` entries with a package family: the packages of the family registered for the
  current user (`GetPackagesByPackageFamily` + `GetPackagePathByFullName`, resource packages included;
  `%WINDIR%\SystemApps\<family>` as fallback) → `AppxManifest.xml` → the application (the one a hint such as
  "(Get Started)" names, else the first in the app list) → `VisualElements/@Square44x44Logo` → its qualified
  files: `targetsize-N_altform-unplated` (smallest N ≥ size, else the largest), then plated `targetsize-N`,
  then the largest `scale-N`; never `contrast-*`. `altform-lightunplated` files go to
  `apps/light/<n>x<n>/<name>.png`. The files used are copied to `raw/appx/<family>/`.
* `Exe` entries (Edge, OneDrive, PowerShell, cmd, Explorer): the executable's first icon group
  (`SystemResources\<exe>.mun` first for files under `C:\Windows`).
* Settings, the Start button and the Search icon are the existing steps; apps.json points at their files.

`apps/apps.json`: `{"theme": "Fenestra-Windows", "sizes": [...], "apps": {"<name>": {"status": …, "verified": …,
"source": "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App Assets\\CalculatorAppList.png", "variants_used": {"48": "…"}}}}`.

### `bitmaps/`

`bitmaps/<n>x<n>/<name>.png` at 16, 20, 24, 32, 48 px and `bitmaps/bitmaps.json` with two sections:

* `modules`: icons.json `modules[]`: imageres icon groups (also written to the icon theme; the 4 ids
  marked unverified are tried and recorded as `candidate`) and the default account picture
  (`C:\ProgramData\Microsoft\User Account Pictures\user*.png` → `assets/account/` and `status/avatar-default`).
* `bitmaps`: icons.json `bitmaps[]`: those a documented API draws: `SHGetStockIconInfo` (`SIID_HELP`,
  `SIID_FIND`, `SIID_DELETE`, `SIID_RENAME`; module + resource id, then the icon group itself) and
  `DrawThemeBackground` (Header `HP_HEADERSORTARROW`, Status `SP_GRIPPER`; drawn on black and on white to
  recover alpha), all `candidate`. The others are `unresolved`, `substitute` (the glyph that stands in) or
  `skipped` (the Microsoft account logo).

Statuses used in all three indexes: `exported` (verified source), `candidate` (unverified id, family,
path or API mapping: compare with Windows), `missing` (not on this PC), `unresolved` (no documented
source; nothing exported), `substitute`, `skipped`, `error`. `--probe-modules` additionally writes
`raw/probe/<module>/<id>.png` (every icon group of explorerframe, shell32, imageres, compstui,
comctl32, OneDrive.exe at 32 px) so the unresolved ids can be found on a real PC.

### Importer (`fenestra-import-windows-assets --pack`, Settings › Personalization › Icon pack, OOBE)

* `glyphs/`: only files listed in glyphs.json whose name matches the rule above; each must be well-formed
  SVG with a single `<svg>` root, no DOCTYPE/entities, only plain shape elements (`svg g path title desc defs
  use rect circle ellipse line polyline polygon linearGradient radialGradient stop clipPath mask symbol`),
  no event attributes, no `href`/`url()` to anything but `#…`; at most 64 KB each and 16 MB in all.
  Installed to `~/.local/share/fenestra/packs/<id>/glyphs/` plus a white copy in `glyphs/white/` (Fenestra
  Shell shows its glyphs white on dark surfaces and tints them elsewhere).
* The table `GLYPH_TARGETS` in the importer maps 66 glyph names onto what Fenestra asks for: icon names
  (`icon:` also go to the pack theme's `scalable/actions` for GTK, `shell:` only to the shell), Fenestra Shell
  assets (`/usr/share/fenestra/assets/menu-icons/…`, `power/N.svg`, `security/…`) and the snipping toolbar
  glyphs. `APP_ALIASES` gives app logos the icon names of the Fenestra apps in the same role
  (calculator → `org.gnome.Calculator`, …; no other vendor's brand is swapped: no Edge logo on Firefox).
* `~/.local/share/fenestra/icon-overrides.json` (rewritten on every pack import):
  `{"version": 1, "pack": id, "icons": {name: [files]}, "icons_light": {…}, "assets": {relative path: file},
  "assets_light": {…}, "snip": {name: file}}`. Fenestra Shell reads it (`shell/src/core/iconoverrides.cpp`):
  `image://icon/` and `image://tint/` look names, asset files and `qrc:…/snip/icons/` up there first, and a QML
  URL interceptor sends `file:///usr/share/fenestra/assets/…` sources to the pack file. Entries whose file
  is gone are ignored; without the file every icon is Fenestra's own.
* `apps/light/`, `bitmaps/` and the indexes are kept in the pack folder (PNG signature and square size checked).

## File types, folders and places (Fenestra Icon Extractor 1.3)

```
filetypes/filetypes.json
filetypes/<n>x<n>/<key>.png      n = 16, 20, 24, 32, 48, 64, 96, 256
```

What File Explorer shows, read with the API Explorer itself uses: `SHCreateItemFromParsingName` +
`IShellItemImageFactory::GetImage(SIIGBF_ICONONLY | SIIGBF_SCALEUP)` at each size (32-bit, alpha kept;
premultiplied pixels are un-premultiplied), on empty sample files `sample.<ext>` in a temporary folder.
So the icon is the one of the app the type is associated with on that PC (Photos for `.png`, Edge for
`.pdf`, Notepad for `.txt`), and Windows' blank page for types nothing handles. `.url` samples are valid
Internet shortcuts. Keys:

* about 230 extensions (`txt`, `png`, `pdf`, `docx`, `mp4`, `zip`, `exe`, `py`, `ttf`, `lnk`…; list in
  `src/FileTypeIcons.cs`), key = the extension without the dot, plus `unknown` (an extension nobody registers);
* places, through their shell items: `folder` (an empty folder), `folder-full` (a folder holding a document,
  without ICONONLY: Explorer's content preview), `user-desktop`, `documents`, `downloads`, `music`, `pictures`,
  `videos`, `home`, `public`, `templates`, `this-pc`, `network`, `home-quick-access`, `gallery`, `onedrive`,
  `control-panel`, `drive-system` (the Windows drive);
* stock icons (`SHGetStockIconInfo` location + `SHDefExtractIcon` at each size): `folder-open`,
  `recycle-bin-empty`, `recycle-bin-full`, `drive-harddisk`, `drive-removable`, `drive-network`,
  `drive-network-offline`, `drive-optical`, `drive-ram`, `computer`, `computer-laptop`, `network-workgroup`,
  `server`, `printer`, `application`, `document`, `shield` (UAC), `shortcut-overlay`, `lock-overlay`, `shared-overlay`.

```json
{"sizes": [16, 20, 24, 32, 48, 64, 96, 256],
 "items": {"png": {"kind": "extension", "ext": ".png", "type_name": "Archivo PNG", "content_type": "image/png",
                   "perceived": "image", "progid": "pngfile", "source": "IShellItemImageFactory SIIGBF_ICONONLY",
                   "files": {"16": "16x16/png.png", "…": "…"}},
           "recycle-bin-full": {"kind": "special", "source": "SHGetStockIconInfo SIID_RECYCLERFULL",
                                "location": "C:\\WINDOWS\\system32\\imageres.dll,-54", "files": {"…": "…"}}}}
```

Importer: the PNGs go to `~/.local/share/fenestra/packs/<id>/filetypes/` (PNG signature and square size
checked) and are hard-linked into the pack's icon theme:

* every MIME type of the shared-mime-info database (`$XDG_DATA_HOME/mime` and `$XDG_DATA_DIRS/*/mime`:
  `types`, `globs2`, `subclasses`, `aliases`, `icons`) gets the icon of the extension its globs name (highest
  glob weight), else of the `content_type` Windows registers for an extension, else of its nearest parent
  type, else Windows' `unknown` page, as `<n>x<n>/mimetypes/<icon name>.png` (the `icons` file's name, else
  the type with `/` → `-`; aliases too). A type nothing handles on the exporting PC keeps Windows' blank
  page, exactly as Explorer shows it; text types with no Windows extension at all get the `txt` icon.
* generic names (`text-x-generic`, `image-x-generic`, `x-office-document`, `package-x-generic`, `unknown`…)
  get the icon of a representative extension;
* places and devices: `folder`, `inode-directory`, `user-desktop`, `user-home`, `folder-documents`,
  `folder-download`, `folder-music`, `folder-pictures`, `folder-videos`, `folder-publicshare`,
  `folder-templates`, `computer`, `network-workgroup`, `user-trash`, `user-trash-full`, `drive-harddisk`,
  `drive-harddisk-system`, `drive-removable-media`, `drive-optical`, `printer`, `emblem-symbolic-link`…, and the
  sidebar names Fenestra's patched Nautilus asks for (`hwin`, `dwin`, `dlwin`, `twne`…) (table `PLACE_NAMES`).

`index.theme` gets a `Type=Fixed` directory per size and context; `icon-overrides.json` gets every name
(all sizes) so Fenestra Shell's desktop, Start › Recommended and Search show the same icons.

## Weather condition icons

Windows installs no weather condition artwork: Widgets (`MicrosoftWindows.Client.WebExperience`) loads
`https://assets.msn.com/weathermapdata/1/static/weather/Icons/taskbar_v10/Condition_Card/<Name>.svg`
for the current condition and keeps it in the WebView2 HTTP cache of its package. The extractor reads every
`…/weather/Icons/…/*.svg` entry of the Chromium blockfile caches of Widgets
(`%LOCALAPPDATA%\Packages\MicrosoftWindows.Client.WebExperience_cw5n1h2txyewy\LocalState\EBWebView\*\Cache\Cache_Data`)
and Edge (`…\Microsoft\Edge\User Data\*\Cache\Cache_Data`): `index`-less scan of `data_1` entries, bodies
from `data_N` blocks or `f_xxxxxx` files, `br`/`gzip`/`deflate` decoded. With `--weather-download` (opt-in,
the extractor's only network access) it asks that same address for the conditions the cache lacks; the
names and sky codes are the ones Windows' own Widgets code uses (`src/WeatherIcons.cs`).

```
weather/<Name>.svg            Condition_Card icons (SunnyDayV3, PartlyCloudyNightV2, ThunderstormsV2, …)
weather/other/<name>.svg      other cached weather glyphs
weather/weather.json          {"base": "…/Condition_Card/", "icons": {"SunnyDayV3": {"file": "SunnyDayV3.svg",
                              "source": "cache"|"download", "url": "…"}}, "skycodes": {"1": "SunnyDayV3", …}}
```

The importer checks each SVG like a glyph (plus the filter primitives `filter`, `feGaussianBlur`, `feOffset`,
`feFlood`, `feBlend`, `feColorMatrix`, `feComposite`, `feMerge`, `feMergeNode`, `feMorphology`,
`feDropShadow`; 256 KB each) and maps them onto the GWeather icon names Fenestra Shell asks for
(`WEATHER_TARGETS`: `weather-clear` → `SunnyDayV3`, `weather-few-clouds-night` → `PartlyCloudyNightV2`, …),
the `-symbolic` names included (Windows draws the coloured icon on light and dark taskbars), in
`icon-overrides.json` and in the theme's `scalable/status`.

## App icon fonts and code point glyphs

Some icons.json glyphs are not in Segoe Fluent Icons but in fonts the apps carry: `PaintIcons.ttf`
(Microsoft.Paint), `SnSkFluent.ttf` (Microsoft.ScreenSketch), `SettingsIcons.ttf` and `StoreIcons.ttf`
(SystemApps). `src/AppFontGlyphs.cs` lists the font and code point of each (found by shape on the reference
screenshots); glyphs.json entries of those carry `"font"`. The fonts themselves go to `raw/fonts/` and, with
`--all-glyphs`, every code point of each to `glyphs/fonts/<font stem>/<HEX>.svg`. `app_fonts` in glyphs.json
records path and revision. Still missing (`missing_reasons`): Paint's shape gallery (vector shapes, no
glyph), Explorer's view menu icons, Notepad's format icons and a few Settings rows.

The importer composes Quick Settings and tray glyphs from `glyphs/u/` (table `CODEPOINT_TARGETS`;
layers `XXXX@opacity` are drawn like Windows does, e.g. the Wi-Fi bars over the dimmed full fan
`E701@0.3` + `E873`): Wi-Fi signal levels / off / no internet, wired, VPN, volume muted / 0 / low / medium /
high, brightness, airplane mode, Bluetooth, night light, accessibility, settings, edit, cast, live captions,
battery saver, microphone, and battery levels 0–100 % (plain and charging; GTK theme only: Fenestra Shell
keeps its Sysbatt pictures). Names a verified icons.json glyph already provides are left as they are.
