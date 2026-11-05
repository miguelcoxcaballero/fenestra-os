# Fenestra Icon Extractor

A small Windows 10/11 app that exports **your own** Windows look into a Fenestra icon
pack (`.zip`, format: [`docs/ICON-PACK-FORMAT.md`](../../docs/ICON-PACK-FORMAT.md)).
Fenestra OS never ships Microsoft files; you make the pack on your PC and import it.

For use with your own Windows licence. Don't redistribute the exported pack.

## Using it

1. Download `FenestraIconExtractorSetup.exe` (or the portable `FenestraIconExtractor.exe`)
   from the [latest `extractor-v*` release](https://github.com/miguelcoxcaballero/fenestra-os/releases/latest).
2. Run it, keep the default choices and press **Export**. The pack is saved to
   `Desktop\Fenestra-Windows-icons.zip` unless you choose another place.
3. Copy the zip to Fenestra OS and import it there.

Windows is only read. The only file written is the `.zip` you choose. No network access.

Headless use (scripts):
`FenestraIconExtractor.exe --export D:\pack.zip [--wallpapers] [--no-fonts] [--no-cursors] [--no-icons] [--no-folders] [--no-taskbar] [--no-apps] [--no-battery] [--log FILE]`

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
| `raw/Sysbatt.ttf` | taskbar battery glyph font |
| `raw/icons/<module>/<id>.ico` | untouched copies of every icon group used |
| `fenestra-pack.json` | Windows version/build, locale, accent colour (`HKCU\…\DWM\AccentColor`) |

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

`tools/validate-pack.py PACK.zip [--sheet contact.png]` checks a pack against the format spec.
`tools/make-icon.py` regenerates the app icon (`app.ico`, original Fenestra artwork).

## Testing under Wine

```sh
export WINEPREFIX=~/.cache/fenestra-build/wine-test
# copy a few files of YOUR Windows into $WINEPREFIX/drive_c/windows/... (never into the repo)
wine out/portable/FenestraIconExtractor.exe --export 'C:\users\Public\pack.zip' --log 'C:\users\Public\pack.log'
wine out/portable/FenestraIconExtractor.exe --screenshot 'C:\users\Public\ui.png'   # renders the window to PNG
python3 tools/validate-pack.py "$WINEPREFIX/drive_c/users/Public/pack.zip"
```
