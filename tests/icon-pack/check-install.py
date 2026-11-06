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
check(sorted(ov['assets']) == sorted(asset_t), f'{len(asset_t)} Fenestra asset files redirected')
check(sorted(ov['snip']) == sorted(snip_t), f'{len(snip_t)} snipping toolbar glyphs')
check(all(Path(f).is_file() for v in ov['icons'].values() for f in v) and all(Path(f).is_file() for f in ov['assets'].values()),
      'every override points at an installed file')
gtk = sorted(p.stem for p in (theme / 'scalable' / 'actions').glob('*.svg'))
check(gtk == sorted(icon_t), f'{len(gtk)} icon: glyphs in {theme.name}/scalable/actions for GTK')
check(not any(n in gtk for n in shell_t), 'shell-only names (battery-level-50-symbolic, go-up-symbolic, ...) not given to GTK')
idx = (theme / 'index.theme').read_text()
check('scalable/actions' in idx.split('Directories=')[1].splitlines()[0] and '[scalable/actions]' in idx, 'index.theme lists scalable/actions')
calc = (theme / '48x48' / 'apps' / 'calculator.png').read_bytes()
check((theme / '48x48' / 'apps' / 'org.gnome.Calculator.png').read_bytes() == calc, 'calculator logo also as org.gnome.Calculator')
check((theme / '24x24' / 'apps' / 'org.gnome.Ptyxis.png').is_file(), 'terminal logo also as org.gnome.Ptyxis')
check(not list(theme.glob('*/apps/org.mozilla.firefox.png')), 'no Edge logo on Firefox')
check(ov['icons_light'].get('org.gnome.Calculator') == [str(pack / 'apps' / 'light' / '48x48' / 'calculator.png')], 'light logo variant')
check((pack / 'bitmaps' / 'bitmaps.json').is_file() and (pack / 'apps' / 'apps.json').is_file(), 'indexes kept with the pack')
print('ALL PASS' if not fails else f'{fails} FAILED')
sys.exit(1 if fails else 0)
