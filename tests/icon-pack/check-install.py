#!/usr/bin/python3
"""check-install.py DATA_HOME PACK_ID: where fenestra-import-windows-assets put the synthetic pack."""
import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
loader = importlib.machinery.SourceFileLoader('fenestra_import', str(REPO / 'tools/fenestra-import-windows-assets'))
spec = importlib.util.spec_from_loader('fenestra_import', loader)
mod = importlib.util.module_from_spec(spec)
loader.exec_module(mod)

data, pack_id = Path(sys.argv[1]), sys.argv[2]
pack = data / 'fenestra' / 'packs' / pack_id
theme = data / 'icons' / 'Fenestra-Windows'
fails = 0


def check(ok, what):
    global fails
    print(('ok   ' if ok else 'FAIL ') + what)
    fails += not ok


ov = json.loads((data / 'fenestra' / 'icon-overrides.json').read_text())
glyphs = sorted(p.stem for p in (pack / 'glyphs').glob('*.svg'))
check(len(glyphs) == len(mod.GLYPH_TARGETS) + 1, f'{len(glyphs)} glyphs in {pack}/glyphs (every mapped glyph + megaphone)')
check(not (pack / 'glyphs' / 'evil.svg').exists(), 'glyph with <script> refused')
check(all((pack / 'glyphs' / 'white' / f'{g}.svg').read_text().count('#ffffff') for g in glyphs), 'white copies for the shell')
icon_t = [t.split(':', 1)[1] for v in mod.GLYPH_TARGETS.values() for t in v if t.startswith('icon:')]
shell_t = [t.split(':', 1)[1] for v in mod.GLYPH_TARGETS.values() for t in v if t.startswith('shell:')]
asset_t = [t.split(':', 1)[1] for v in mod.GLYPH_TARGETS.values() for t in v if t.startswith('asset:')]
snip_t = [t.split(':', 1)[1] for v in mod.GLYPH_TARGETS.values() for t in v if t.startswith('snip:')]
check(all(n in ov['icons'] and n in ov['icons_light'] for n in icon_t + shell_t), f'{len(icon_t) + len(shell_t)} icon names in icon-overrides.json')
ft_assets = ['folders/folder-empty.png', 'folders/folder-empty.svg', 'folders/folder-full.png', 'folders/folder-full.svg']
check(sorted(ov['assets']) == sorted(set(asset_t) | set(ft_assets)), f'{len(asset_t)} Fenestra asset files redirected (+ Explorer folders)')
check(sorted(ov['snip']) == sorted(snip_t), f'{len(snip_t)} snipping toolbar glyphs')
check(all(Path(f).is_file() for v in ov['icons'].values() for f in v) and all(Path(f).is_file() for f in ov['assets'].values()),
      'every override points at an installed file')
gtk = sorted(p.stem for p in (theme / 'scalable' / 'actions').glob('*.svg'))
unmapped = [f'{n}-symbolic' for n in ov['glyphs'] if n not in mod.GLYPH_TARGETS]
check(gtk == sorted(set(icon_t) | set(unmapped)),
      f'{len(gtk)} icon: glyphs in {theme.name}/scalable/actions for GTK ({len(unmapped)} unmapped as <name>-symbolic)')
check(not any(n in gtk for n in shell_t), 'shell-only names (battery-level-50-symbolic, go-up-symbolic, ...) not given to GTK')
idx = (theme / 'index.theme').read_text()
check('scalable/actions' in idx.split('Directories=')[1].splitlines()[0] and '[scalable/actions]' in idx, 'index.theme lists scalable/actions')
calc = (theme / '48x48' / 'apps' / 'calculator.png').read_bytes()
check((theme / '48x48' / 'apps' / 'org.gnome.Calculator.png').read_bytes() == calc, 'calculator logo also as org.gnome.Calculator')
check((theme / '24x24' / 'apps' / 'org.gnome.Ptyxis.png').is_file(), 'terminal logo also as org.gnome.Ptyxis')
check(not list(theme.glob('*/apps/org.mozilla.firefox.png')), 'no Edge logo on Firefox')
check(ov['icons_light'].get('org.gnome.Calculator') == [str(pack / 'apps' / 'light' / '48x48' / 'calculator.png')], 'light logo variant')
check((pack / 'bitmaps' / 'bitmaps.json').is_file() and (pack / 'apps' / 'apps.json').is_file(), 'indexes kept with the pack')
# file types and weather
mt = theme / '48x48' / 'mimetypes'
check((mt / 'text-plain.png').read_bytes() == (pack / 'filetypes' / '48x48' / 'txt.png').read_bytes(), 'text/plain gets the .txt icon')
check((mt / 'image-png.png').is_file() and (mt / 'application-pdf.png').is_file(), 'image-png and application-pdf in mimetypes')
check((mt / 'text-x-python.png').read_bytes() == (pack / 'filetypes' / '48x48' / 'txt.png').read_bytes(),
      'text/x-python (no Windows extension in this pack) falls back to its parent text/plain')
check((theme / '96x96' / 'places' / 'folder.png').is_file() and (theme / '20x20' / 'places' / 'user-trash.png').is_file(),
      'folder and user-trash at 96 and 20 px')
check((theme / '16x16' / 'places' / 'dwin.png').is_file(), "patched Nautilus sidebar name dwin (Documents)")
check('[64x64/mimetypes]' in idx and '[20x20/places]' in idx, 'index.theme lists the new size directories')
check(not (pack / 'filetypes' / 'evil.png').exists() and not (data / 'fenestra' / 'evil.png').exists(), 'filetypes key with .. refused')
check(len(ov['icons']['text-plain']) == 8 and ov['icons']['folder'], 'file icons in icon-overrides.json for the shell')
check(ov['icons'].get('weather-clear') == [str(pack / 'weather' / 'SunnyDayV3.svg')]
      and ov['icons'].get('weather-overcast-symbolic') == [str(pack / 'weather' / 'CloudyV3.svg')], 'weather states mapped')
check(not (pack / 'weather' / 'Evil.svg').exists(), 'weather SVG with an external <image> refused')
check((theme / 'scalable' / 'status' / 'weather-clear.svg').is_file(), 'weather icons in the theme')
print('ALL PASS' if not fails else f'{fails} FAILED')

sys.exit(1 if fails else 0)
