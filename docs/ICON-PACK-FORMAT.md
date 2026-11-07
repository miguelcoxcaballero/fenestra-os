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
glyphs/<name>.svg         one per icons.json glyphs[] entry with a code point (218 of 293 today)
glyphs/u/<HEX>.svg        only with --all-glyphs: every code point of the font's cmap
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
