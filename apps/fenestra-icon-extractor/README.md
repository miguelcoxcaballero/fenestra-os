# Fenestra Icon Extractor

A small Windows 10/11 app that exports **your own** Windows look into a Fenestra icon
pack (`.zip`, format: [`docs/ICON-PACK-FORMAT.md`](../../docs/ICON-PACK-FORMAT.md)).
Fenestra OS never ships Microsoft files; you make the pack on your PC and import it.

Version 1.2.0 (release tag `extractor-v1.2.0`). For use with your own Windows licence. Don't
redistribute the exported pack: it is never committed to this repository or attached to a release
(the CI smoke test exports on the runner's own Windows only to validate the program, and uploads
only the program).

## Using it

1. Download `FenestraIconExtractorSetup.exe` (or the portable `FenestraIconExtractor.exe`)
   from the [latest `extractor-v*` release](https://github.com/miguelcoxcaballero/fenestra-os/releases/latest).
2. Run it, keep the default choices and press **Export**. The pack is saved to
   `Desktop\Fenestra-Windows-icons.zip` unless you choose another place.
3. Copy the zip to Fenestra OS and import it there.

Windows is only read. The only file written is the `.zip` you choose. No network access.

Headless use (scripts):
`FenestraIconExtractor.exe --export D:\pack.zip [--wallpapers] [--no-fonts] [--no-cursors] [--no-icons] [--no-folders] [--no-taskbar] [--no-apps] [--no-battery] [--log FILE]`
`  [--no-glyphs] [--all-glyphs] [--no-package-logos] [--no-bitmaps] [--probe-modules]`

## What goes into the pack

| Pack path | Source on Windows |
|---|---|
| `fonts/` | `C:\Windows\Fonts`: Segoe UI (all weights), Segoe UI Variable, Segoe Fluent Icons, Consolas |
| `cursors/` | `C:\Windows\Cursors\aero_*`, `beam_*`, `cross_*` (`.cur`/`.ani`) plus files of your current pointer scheme (`HKCU\Control Panel\Cursors`), role mapping in `fenestra-pack.json` → `cursor_scheme` |
| `icons/Fenestra-Windows/` | freedesktop icon theme, 256/48/32/16 px PNGs from `SystemResources\imageres.dll.mun`, `shell32.dll.mun` and Edge's PDF/HTML document icons: `folder`, `folder-documents`, `folder-pictures`, `folder-music`, `folder-videos`, `folder-download`, `user-desktop`, `user-trash`, `user-trash-full`, `network-workgroup`, `computer`, `drive-harddisk`, `drive-optical`, `text-x-generic`, `image-x-generic`, `application-pdf`, … |
| `icons/Fenestra-Windows/*/apps/` | `fenestra-settings` (ImmersiveControlPanel logo), `org.fenestra.TaskManager` / `utilities-system-monitor` (Taskmgr.exe), `system-file-manager` / `org.gnome.Nautilus` (explorer.exe) |
| `assets/folders/folder-empty.png`, `folder-full.png` | imageres icon groups 3 and 162; Explorer draws the content of a full folder at run time, so the extractor adds a white sheet between the two flaps of group 162 |
| `assets/branding/settings.png` | Settings app logo (256 px) |
| `assets/branding/start-button.svg` | `SystemApps\MicrosoftWindows.Client.Core_cw5n1h2txyewy\Icons\WindowsLogo.svg` |
| `assets/search/search.png` | `SystemApps\Shared\SearchIconOnDark.scale-400\*\*.png` |
| `assets/wallpapers/windows-desktop.*`, `windows-lockscreen.*` | optional (off by default): current wallpaper and lock screen picture |
| `glyphs/<name>.svg`, `glyphs/glyphs.json` | every Segoe Fluent Icons glyph named in `design/reference/icons.json` (237 of 293; the 56 without a public code point are listed as missing), drawn from `Fonts\SegoeIcons.ttf` (`segmdl2.ttf` on Windows 10) by the built-in TrueType reader (`src/TrueType.cs`): outline → SVG path, `fill="currentColor"`, viewBox = the em square. `--all-glyphs` adds `glyphs/u/<HEX>.svg` for every code point of the font |
| `icons/Fenestra-Windows/{256,48,32,24,16}/apps/<name>.png`, `apps/light/…`, `apps/apps.json` | the 44 apps of `icons.json`: Store/system packages by package family (`GetPackagesByPackageFamily` + `GetPackagePathByFullName`, `%WINDIR%\SystemApps` as fallback) → `AppxManifest.xml` → `Square44x44Logo` → the `targetsize-N_altform-unplated` file (light-theme `altform-lightunplated` files go to `apps/light/`); Edge, OneDrive, PowerShell, cmd and Explorer from the executable's first icon group. `raw/appx/<family>/` keeps the files used |
| `bitmaps/<n>x<n>/<name>.png`, `bitmaps/bitmaps.json` | `icons.json` `modules[]` (imageres ids, the default account picture) and the `bitmaps[]` a documented API can draw (`SHGetStockIconInfo`: help, find, delete, rename; `DrawThemeBackground`: header sort arrow, size grip) at 16/20/24/32/48 px. The rest are recorded as `unresolved`, `substitute` (which glyph stands in) or `skipped` (the Microsoft account logo) |
| `raw/probe/<module>/<id>.png` | only with `--probe-modules`: every icon group of explorerframe, shell32, imageres, compstui, comctl32 and OneDrive.exe at 32 px, to identify the ids of the unresolved bitmaps on a real PC |
| `raw/Sysbatt.ttf` | taskbar battery glyph font |
| `raw/icons/<module>/<id>.ico` | untouched copies of every icon group used |
| `fenestra-pack.json` | Windows version/build, locale, accent colour (`HKCU\…\DWM\AccentColor`) |

### What is verified and what is a candidate

`icons.json` marks each entry `verificado` (true: the id is documented or already checked; false:
Microsoft publishes no list of imageres ids or package families). The extractor keeps that flag and
writes a status for every entry into `glyphs/glyphs.json`, `apps/apps.json` and `bitmaps/bitmaps.json`:

| status | meaning |
|---|---|
| `exported` | verified source, exported |
| `candidate` | exported from an unverified id, package family, path or API mapping: compare it with Windows before relying on it (the log lists each one) |
| `missing` | the source is not on this PC (app not installed, id not in this build) |
| `unresolved` | no documented source known; nothing exported (for apps: e.g. no manifest application matches the hint, the ids found are listed) |
| `substitute` | not exported; the pack file named in `note` stands in for it |
| `skipped` | deliberately not exported (brand logos) |

Nothing is guessed silently: an app whose package family isn't installed, an imageres id that
doesn't exist in the user's build, or a manifest without the expected application is reported, not
replaced by something else. To check the candidates on a real PC: export with `--probe-modules`,
open `bitmaps/bitmaps.json` and compare the PNGs with what Windows shows; fix the id in
`design/reference/icons.json` (branch `visual/reference`) and regenerate the table.

`src/ReferenceIcons.g.cs` is generated from `icons.json` (names, ids, code points, package families;
no artwork) by `tools/gen-reference-icons.py PATH/TO/icons.json`.

## Building (Linux, no Windows needed)

```sh
./build.sh            # out/portable/FenestraIconExtractor.exe + out/FenestraIconExtractorSetup.exe
NO_INSTALLER=1 ./build.sh
```

`build.sh` installs the .NET 8 SDK into `~/.dotnet` if missing (official `dotnet-install.sh`;
`EnableWindowsTargeting` lets the WinForms target build on Linux) and Inno Setup 6 into the
Wine prefix `~/.cache/fenestra-build/wine-inno`, then runs `ISCC.exe` under Wine.
On Windows: `dotnet publish -c Release -o out\portable` and `iscc installer\FenestraIconExtractor.iss`.
CI: `.github/workflows/icon-extractor.yml` builds both on `windows-latest`.

`tools/validate-pack.py PACK.zip [--sheet contact.png]` checks a pack against the format spec
(including the SVG rules the importer applies to `glyphs/`).

### Tests (Linux)

`tests/TrueTypeTests` compiles `src/TrueType.cs` and `src/AppxLogos.cs` (no Windows APIs) for
`net8.0`: fixed contour → path cases, logo variant choice, and SVG export from any TrueType font.
`tests/compare-glyph-svg.py` rasterises those SVGs (cairosvg) and compares them with FreeType's own
unhinted rendering of the font (freetype-py):

```sh
dotnet run --project tests/TrueTypeTests -c Release                       # unit cases
dotnet run --project tests/TrueTypeTests -c Release -- /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf /tmp/svg ALL
python3 tests/compare-glyph-svg.py /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf /tmp/svg --size 128
```
`tools/make-icon.py` regenerates the app icon (`app.ico`, original Fenestra artwork).

## Testing under Wine

```sh
export WINEPREFIX=~/.cache/fenestra-build/wine-test
# copy a few files of YOUR Windows into $WINEPREFIX/drive_c/windows/... (never into the repo)
wine out/portable/FenestraIconExtractor.exe --export 'C:\users\Public\pack.zip' --log 'C:\users\Public\pack.log'
wine out/portable/FenestraIconExtractor.exe --screenshot 'C:\users\Public\ui.png'   # renders the window to PNG
python3 tools/validate-pack.py "$WINEPREFIX/drive_c/users/Public/pack.zip"
```
