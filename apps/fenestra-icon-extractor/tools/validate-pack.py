#!/usr/bin/python3
"""Validates a Fenestra icon pack against docs/ICON-PACK-FORMAT.md (v1).

Usage: validate-pack.py PACK.zip [--sheet out.png] [--report]   (exit 0 = valid)
--report prints the status of every icons.json entry (glyphs, apps, modules, bitmaps): names, ids
and sources only, no artwork.
"""
import argparse
import io
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

REQUIRED_KEYS = ('format', 'version', 'id', 'name', 'generator', 'source', 'created', 'contents', 'licence_note')
EXPECTED = ['fonts/segoeui.ttf', 'assets/folders/folder-empty.png', 'assets/folders/folder-full.png',
            'assets/branding/start-button.svg', 'assets/search/search.png', 'raw/Sysbatt.ttf',
            'icons/Fenestra-Windows/index.theme', 'icons/Fenestra-Windows/256x256/apps/fenestra-settings.png',
            'cursors/aero_arrow.cur']
THEME_ICONS = ['places/folder', 'places/folder-documents', 'places/user-desktop', 'places/user-trash',
               'places/user-trash-full', 'devices/computer', 'devices/drive-harddisk', 'places/network-workgroup',
               'mimetypes/text-x-generic', 'mimetypes/image-x-generic', 'mimetypes/application-pdf']


TOPS = ('fonts', 'cursors', 'assets', 'icons', 'glyphs', 'apps', 'bitmaps', 'filetypes', 'weather', 'raw')
NAME_RE = re.compile(r'^[a-z0-9][a-z0-9.+-]*$')
SVG_NS = '{http://www.w3.org/2000/svg}'
SVG_ELEMENTS = {'svg', 'g', 'path', 'title', 'desc', 'defs', 'use', 'rect', 'circle', 'ellipse', 'line', 'polyline',
                'polygon', 'linearGradient', 'radialGradient', 'stop', 'clipPath', 'mask', 'symbol'}


def svg_problem(data, limit=64 * 1024):
    """Same rules as the importer (tools/fenestra-import-windows-assets: svg_problem)."""
    if len(data) > limit:
        return f'larger than {limit // 1024} KB'
    if b'<!DOCTYPE' in data or b'<!ENTITY' in data:
        return 'DOCTYPE/ENTITY not allowed'
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        return f'not well-formed XML ({exc})'
    if root.tag != SVG_NS + 'svg':
        return 'root element is not <svg>'
    for el in root.iter():
        tag = el.tag[len(SVG_NS):] if el.tag.startswith(SVG_NS) else el.tag
        if tag not in SVG_ELEMENTS:
            return f'element <{tag}> not allowed'
        for k, v in el.attrib.items():
            local = k.rsplit('}', 1)[-1]
            if local.lower().startswith('on'):
                return f'event attribute {local}'
            if local == 'href' and not v.startswith('#'):
                return f'external reference {v[:40]}'
            if re.search(r'url\(\s*[\'"]?(?!#)', v) or '@import' in v:
                return f'external reference in {local}'
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pack')
    ap.add_argument('--sheet')
    ap.add_argument('--report', action='store_true')
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
        if t not in TOPS:
            errors.append(f'unknown top-level dir {t}')
    # glyphs/: index, one SVG per entry, every SVG listed, importer safety rules.
    if 'glyphs' in tops:
        try:
            gi = json.loads(z.read('glyphs/glyphs.json'))
        except (KeyError, ValueError):
            errors.append('glyphs/ without a valid glyphs/glyphs.json')
            gi = {'glyphs': {}}
        listed = set()
        for gname, g in gi.get('glyphs', {}).items():
            if not NAME_RE.match(gname):
                errors.append(f'glyphs.json: bad name {gname}')
            f = 'glyphs/' + str(g.get('file', ''))
            listed.add(f)
            if f not in names:
                errors.append(f'glyphs.json: {gname} -> missing {f}')
            if not re.match(r'^U\+[0-9A-F]{4,6}$', str(g.get('codepoint', ''))):
                errors.append(f'glyphs.json: {gname} has a bad codepoint')
        # filetypes/: every listed size file is a square PNG of that size
        if 'filetypes/filetypes.json' in names:
            ft = json.loads(z.read('filetypes/filetypes.json'))
            for key, meta in ft.get('items', {}).items():
                if not re.match(r'^[a-z0-9][a-z0-9.+_-]{0,63}$', key):
                    errors.append(f'filetypes.json: bad key {key}')
                for size, rel in meta.get('files', {}).items():
                    if rel != f'{size}x{size}/{key}.png' or 'filetypes/' + rel not in names:
                        errors.append(f'filetypes.json: {key} {size} -> {rel}')
        if 'weather/weather.json' in names:
            wj = json.loads(z.read('weather/weather.json'))
            for wname, meta in wj.get('icons', {}).items():
                if 'weather/' + str(meta.get('file')) not in names:
                    errors.append(f'weather.json: {wname} -> missing {meta.get("file")}')
        for n in names:
            if n.startswith('glyphs/') and n.endswith('.svg'):
                if n not in listed and not n.startswith(('glyphs/u/', 'glyphs/fonts/')):
                    errors.append(f'{n}: not listed in glyphs.json')
                why = svg_problem(z.read(n))
                if why:
                    errors.append(f'{n}: {why}')
        print(f"glyphs: {len(gi.get('glyphs', {}))} named, missing {gi.get('missing', [])}")
    for idx_name in ('apps/apps.json', 'bitmaps/bitmaps.json'):
        if idx_name.split('/')[0] in tops:
            try:
                data = json.loads(z.read(idx_name))
            except (KeyError, ValueError):
                errors.append(f'no valid {idx_name}')
                continue
            for section in ('apps', 'modules', 'bitmaps'):
                entries = data.get(section, {})
                if isinstance(entries, dict) and entries:
                    counts = {}
                    for e in entries.values():
                        counts[e.get('status')] = counts.get(e.get('status'), 0) + 1
                    print(f'{idx_name} {section}: ' + ', '.join(f'{k} {v}' for k, v in sorted(counts.items(), key=str)))
                    if a.report:
                        for en, e in entries.items():
                            detail = e.get('source') or e.get('reason') or e.get('note') or e.get('error') or ''
                            extra = f" apps={e['applications']}" if 'applications' in e else ''
                            print(f"  {section[:-1]:6} {en:28} {e.get('status', '?'):10} {detail}{extra}")
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
        sized = (n.startswith('icons/') or n.startswith('apps/light/') or n.startswith('bitmaps/')) and n.endswith('.png')
        if sized:
            size = int(n.split('/')[2 if n.startswith(('icons/', 'apps/light/')) else 1].split('x')[0])
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
