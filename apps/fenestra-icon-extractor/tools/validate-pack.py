#!/usr/bin/python3
"""Validates a Fenestra icon pack against docs/ICON-PACK-FORMAT.md (v1).

Usage: validate-pack.py PACK.zip [--sheet out.png]   (exit 0 = valid)
"""
import argparse
import io
import json
import sys
import zipfile

REQUIRED_KEYS = ('format', 'version', 'id', 'name', 'generator', 'source', 'created', 'contents', 'licence_note')
EXPECTED = ['fonts/segoeui.ttf', 'assets/folders/folder-empty.png', 'assets/folders/folder-full.png',
            'assets/branding/start-button.svg', 'assets/search/search.png', 'raw/Sysbatt.ttf',
            'icons/Fenestra-Windows/index.theme', 'icons/Fenestra-Windows/256x256/apps/fenestra-settings.png',
            'cursors/aero_arrow.cur']
THEME_ICONS = ['places/folder', 'places/folder-documents', 'places/user-desktop', 'places/user-trash',
               'places/user-trash-full', 'devices/computer', 'devices/drive-harddisk', 'places/network-workgroup',
               'mimetypes/text-x-generic', 'mimetypes/image-x-generic', 'mimetypes/application-pdf']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pack')
    ap.add_argument('--sheet')
    a = ap.parse_args()
    errors, warnings = [], []
    z = zipfile.ZipFile(a.pack)
    names = z.namelist()
    total = sum(i.file_size for i in z.infolist())
    for n in names:
        if n.startswith('/') or '\\' in n or '..' in n.split('/') or (len(n) > 1 and n[1] == ':'):
            errors.append(f'unsafe path: {n}')
    if total > 1 << 30:
        errors.append(f'pack too large: {total}')
    try:
        m = json.loads(z.read('fenestra-pack.json'))
    except KeyError:
        print('INVALID: no fenestra-pack.json')
        return 1
    for k in REQUIRED_KEYS:
        if k not in m:
            errors.append(f'manifest missing {k}')
    if m.get('format') != 'fenestra-icon-pack' or m.get('version') != 1:
        errors.append('bad format/version')
    tops = sorted({n.split('/')[0] for n in names if '/' in n})
    if sorted(m.get('contents', [])) != tops:
        errors.append(f'contents {m.get("contents")} != top-level dirs {tops}')
    for t in tops:
        if t not in ('fonts', 'cursors', 'assets', 'icons', 'raw'):
            errors.append(f'unknown top-level dir {t}')
    if 'icons' in tops and m.get('icon_theme') != 'Fenestra-Windows':
        errors.append('icon_theme missing')
    if 'cursors' in tops and m.get('cursor_theme') != 'Fenestra-Windows-Cursors':
        errors.append('cursor_theme missing')
    for e in EXPECTED:
        if e not in names:
            warnings.append(f'missing {e}')
    from PIL import Image
    pngs = 0
    for n in names:
        if n.startswith('icons/') and n.endswith('.png'):
            size = int(n.split('/')[2].split('x')[0])
            im = Image.open(io.BytesIO(z.read(n)))
            if im.size != (size, size):
                errors.append(f'{n}: {im.size} != {size}')
            if im.mode != 'RGBA':
                errors.append(f'{n}: mode {im.mode}')
            elif im.getextrema()[3][0] != 0:
                warnings.append(f'{n}: no transparent pixels')
            pngs += 1
    for icon in THEME_ICONS:
        for s in (256, 48, 32, 16):
            ctx, name = icon.split('/')
            if f'icons/Fenestra-Windows/{s}x{s}/{ctx}/{name}.png' not in names:
                warnings.append(f'missing theme icon {s}/{icon}')
    if 'icons/Fenestra-Windows/index.theme' in names:
        idx = z.read('icons/Fenestra-Windows/index.theme').decode()
        dirs = next(l for l in idx.splitlines() if l.startswith('Directories=')).split('=', 1)[1].split(',')
        for d in dirs:
            if f'[{d}]' not in idx:
                errors.append(f'index.theme: no section for {d}')
            if not any(n.startswith(f'icons/Fenestra-Windows/{d}/') for n in names):
                errors.append(f'index.theme: empty dir {d}')
    print(json.dumps(m, indent=1))
    print(f'{len(names)} entries, {total / 1048576:.1f} MB uncompressed, {pngs} theme PNGs')
    for w in warnings:
        print('WARN', w)
    for e in errors:
        print('ERROR', e)
    if a.sheet:
        icons = sorted(n for n in names if n.startswith('icons/') and '/48x48/' in n and n.endswith('.png'))
        extra = [n for n in names if n.startswith('assets/') and n.endswith('.png')]
        items = icons + extra
        cols, cell = 10, 96
        sheet = Image.new('RGB', (cols * cell, ((len(items) + cols - 1) // cols) * cell), (128, 128, 128))
        from PIL import ImageDraw
        d = ImageDraw.Draw(sheet)
        for i, n in enumerate(items):
            im = Image.open(io.BytesIO(z.read(n))).convert('RGBA')
            im.thumbnail((48, 48))
            x, y = (i % cols) * cell, (i // cols) * cell
            sheet.paste(im, (x + 24, y + 6), im)
            d.text((x + 2, y + 62), n.rsplit('/', 1)[1][:15], fill=(0, 0, 0))
        sheet.save(a.sheet)
    print('VALID' if not errors else 'INVALID')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
