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
└── raw/                        optional untouched source files (e.g. Sysbatt.ttf, imageres groups)
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
