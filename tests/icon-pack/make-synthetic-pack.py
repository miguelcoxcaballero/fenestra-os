#!/usr/bin/python3
"""Writes a synthetic Fenestra icon pack in the layout Fenestra Icon Extractor 1.2 produces.

Usage: make-synthetic-pack.py OUT.zip

Everything in it is made up here (simple shapes and solid squares), nothing comes from Windows:
it exercises the importer and the shell's icon lookup without any Microsoft file.
  glyphs/<name>.svg     one per glyph the importer maps (GLYPH_TARGETS) plus one unmapped glyph,
                        a ring with a dot whose angle encodes the glyph index, fill="currentColor"
  glyphs/evil.svg       listed in glyphs.json but contains <script>: must be refused
  icons/Fenestra-Windows/<n>x<n>/apps/<app>.png, apps/apps.json, apps/light/48x48/calculator.png
  bitmaps/16x16/dialog-help.png, bitmaps/bitmaps.json
"""
import importlib.machinery
import importlib.util
import io
import json
import math
import sys
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[2]


def importer():
    loader = importlib.machinery.SourceFileLoader('fenestra_import', str(REPO / 'tools/fenestra-import-windows-assets'))
    spec = importlib.util.spec_from_loader('fenestra_import', loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def glyph_svg(i):
    a = 2 * math.pi * (i % 16) / 16
    cx, cy = 1024 + 560 * math.cos(a), 1024 - 560 * math.sin(a)
    # ring (outer clockwise, inner counter-clockwise: non-zero leaves a hole) and a dot
    ring = 'M1024 224A800 800 0 1 1 1023.9 224ZM1024 424A600 600 0 1 0 1024.1 424Z'
    dot = f'M{cx - 120:.0f} {cy - 120:.0f}h240v240h-240Z'
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 2048 2048" width="16" height="16">'
            f'<path fill="currentColor" fill-rule="nonzero" d="{ring}{dot}"/></svg>\n')


def png(size, rgb, mark=None):
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=max(1, size // 6), fill=rgb + (255,))
    if mark:
        d.rectangle((size // 4, size // 4, 3 * size // 4, 3 * size // 4), fill=mark + (255,))
    b = io.BytesIO()
    im.save(b, 'PNG')
    return b.getvalue()


def main():
    out = Path(sys.argv[1])
    mod = importer()
    names = sorted(mod.GLYPH_TARGETS) + ['megaphone']        # megaphone: in the pack, mapped nowhere
    files = {}
    glyphs = {}
    for i, n in enumerate(names):
        files[f'glyphs/{n}.svg'] = glyph_svg(i).encode()
        glyphs[n] = {'codepoint': f'U+{0xE700 + i:04X}', 'glyph': n.title().replace('-', ''), 'file': f'{n}.svg', 'verified': True}
    files['glyphs/evil.svg'] = (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><script>alert(1)</script>'
                                b'<path fill="currentColor" d="M0 0h16v16z"/></svg>')
    glyphs['evil'] = {'codepoint': 'U+F000', 'glyph': 'Evil', 'file': 'evil.svg', 'verified': True}
    files['glyphs/glyphs.json'] = json.dumps({'font': 'Synthetic.ttf', 'font_revision': '0.1', 'units_per_em': 2048,
                                              'baseline': 2048, 'glyphs': glyphs, 'missing': ['draw-freehand']}, indent=1).encode()
    theme = 'icons/Fenestra-Windows'
    sizes = (256, 48, 32, 24, 16)
    apps = {'calculator': ((0, 120, 212), None), 'microsoft-edge': ((0, 150, 100), None),
            'terminal': ((40, 40, 40), (200, 200, 200)), 'outlook': ((0, 90, 160), None)}
    report = {}
    for name, (rgb, mark) in apps.items():
        for s in sizes:
            files[f'{theme}/{s}x{s}/apps/{name}.png'] = png(s, rgb, mark)
        report[name] = {'status': 'candidate', 'verified': False, 'module': 'Appx'}
    report['windows-backup'] = {'status': 'unresolved', 'verified': False, 'reason': 'no package family'}
    files['apps/light/48x48/calculator.png'] = png(48, (250, 200, 0))
    files['apps/apps.json'] = json.dumps({'theme': 'Fenestra-Windows', 'sizes': list(sizes), 'apps': report}, indent=1).encode()
    dirs = [f'{s}x{s}/apps' for s in sizes]
    files[f'{theme}/index.theme'] = ('[Icon Theme]\nName=Fenestra-Windows\nInherits=Fenestra,Win11,Adwaita,hicolor\n'
                                     f'Directories={",".join(dirs)}\n'
                                     + ''.join(f'\n[{d}]\nSize={d.split("x")[0]}\nContext=Applications\nType=Fixed\n' for d in dirs)).encode()
    files['bitmaps/16x16/dialog-help.png'] = png(16, (0, 100, 220))
    files['bitmaps/bitmaps.json'] = json.dumps({'modules': {}, 'bitmaps': {'dialog-help': {'status': 'candidate'}}}).encode()
    manifest = {'format': 'fenestra-icon-pack', 'version': 1, 'id': 'synthetic-test-pack', 'name': 'Synthetic test pack',
                'generator': 'tests/icon-pack/make-synthetic-pack.py', 'source': {'os': 'none'}, 'created': '2026-11-06T00:00:00Z',
                'contents': ['icons', 'glyphs', 'apps', 'bitmaps'], 'icon_theme': 'Fenestra-Windows',
                'licence_note': 'Synthetic test data.'}
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('fenestra-pack.json', json.dumps(manifest, indent=1))
        for k, v in sorted(files.items()):
            z.writestr(k, v)
    print(f'{out}: {len(names)} glyphs (+1 unsafe), {len(apps)} apps')


if __name__ == '__main__':
    main()
