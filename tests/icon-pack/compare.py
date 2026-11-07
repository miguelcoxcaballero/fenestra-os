#!/usr/bin/python3
"""Side-by-side pictures: Windows 11 (reference captures / the exported pack) vs what Fenestra draws
with the installed pack (GTK icon theme lookups, icon-overrides.json). Writes PNGs into
tests/icon-pack/compare/ (git-ignored).

    compare.py --pack-dir DIR [--explorer-list WIN.png --nautilus-list FEN.png]
               [--resolved48 TSV --resolved16 TSV] [--refshots DIR] [--icons-json icons.json]

--pack-dir is the unpacked pack zip; the resolved TSVs are "file<TAB>icon file GTK chose" (nautilus-shot.sh resolve
DIR SIZE | cut -f1,4 style output: the Gtk.IconTheme lookup of each sample file's GIcon).
"""
import argparse
import io
import json
import os
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE / 'compare'
DATA = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
FONT = ImageFont.load_default()
BG, FG, OK, BAD = (32, 32, 32, 255), (230, 230, 230, 255), (120, 220, 120, 255), (255, 110, 110, 255)


def svg(path, size, bg=None):
    png = subprocess.run(['magick', '-background', 'none', '-density', '600', str(path), '-resize', f'{size}x{size}',
                          'png:-'], capture_output=True).stdout
    try:
        im = Image.open(io.BytesIO(png)).convert('RGBA')
    except Exception:  # noqa: BLE001
        return Image.new('RGBA', (size, size))
    c = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    c.alpha_composite(im, ((size - im.width) // 2, (size - im.height) // 2))
    return c


def load(path, size):
    if path is None or not Path(path).exists():
        return None
    if str(path).endswith('.svg'):
        return svg(path, size)
    im = Image.open(path).convert('RGBA')
    return im if im.size == (size, size) else im.resize((size, size), Image.LANCZOS)


def table(rows, cols, cell, title, path, label_w=210):
    """rows: [(label, [Image|None, ...], ok|None)]"""
    w = label_w + len(cols) * (cell + 16) + 60
    h = 28 + 18 + len(rows) * (cell + 8)
    im = Image.new('RGBA', (w, h), BG)
    d = ImageDraw.Draw(im)
    d.text((8, 6), title, fill=FG, font=FONT)
    for i, c in enumerate(cols):
        d.text((label_w + i * (cell + 16), 28), c, fill=FG, font=FONT)
    for r, (label, imgs, ok) in enumerate(rows):
        y = 46 + r * (cell + 8)
        d.text((8, y + cell // 2 - 6), label[:34], fill=FG, font=FONT)
        for i, t in enumerate(imgs):
            if t is not None:
                im.alpha_composite(t, (label_w + i * (cell + 16), y))
            else:
                d.text((label_w + i * (cell + 16), y + cell // 2 - 6), '—', fill=BAD, font=FONT)
        if ok is not None:
            d.text((label_w + len(cols) * (cell + 16), y + cell // 2 - 6), 'same' if ok else 'DIFF', fill=OK if ok else BAD, font=FONT)
    im.convert('RGB').save(path)
    print(path)


def side_by_side(a, b, la, lb, path, crop_a=None, crop_b=None, height=900):
    A, B = Image.open(a).convert('RGB'), Image.open(b).convert('RGB')
    if crop_a:
        A = A.crop(crop_a)
    if crop_b:
        B = B.crop(crop_b)
    sa, sb = height / A.height, height / B.height
    A, B = A.resize((int(A.width * sa), height)), B.resize((int(B.width * sb), height))
    im = Image.new('RGB', (A.width + B.width + 30, height + 30), (20, 20, 20))
    im.paste(A, (0, 30))
    im.paste(B, (A.width + 30, 30))
    d = ImageDraw.Draw(im)
    d.text((8, 8), la, fill='white', font=FONT)
    d.text((A.width + 38, 8), lb, fill='white', font=FONT)
    im.save(path)
    print(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pack-dir', required=True)
    ap.add_argument('--explorer-list'); ap.add_argument('--nautilus-list')
    ap.add_argument('--explorer-icons')
    ap.add_argument('--resolved48'); ap.add_argument('--resolved16')
    ap.add_argument('--refshots', default=str(Path.home() / '.cache/fenestra-ref-shots/reference-shots'))
    ap.add_argument('--icons-json')
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    pack = Path(a.pack_dir)
    ov = json.loads((DATA / 'fenestra' / 'icon-overrides.json').read_text())

    # 1. file types: Explorer vs Nautilus screenshots, then per type: pack icon vs GTK's choice
    if a.explorer_list and a.nautilus_list:
        side_by_side(a.explorer_list, a.nautilus_list, 'Windows 11 File Explorer (VM, list)',
                     'Fenestra Explorer (Nautilus, headless GNOME Shell, Fenestra-Windows theme)',
                     OUT / 'filetypes-explorer-vs-nautilus.png', crop_a=(160, 120, 800, 1010), crop_b=(150, 180, 950, 1080))
    if a.explorer_icons:
        Image.open(a.explorer_icons).crop((160, 120, 1620, 500)).save(OUT / 'filetypes-explorer-medium-icons.png')
    if a.resolved48:
        r48 = dict(l.rstrip('\n').split('\t') for l in open(a.resolved48) if '\t' in l)
        r16 = dict(l.rstrip('\n').split('\t') for l in open(a.resolved16) if '\t' in l) if a.resolved16 else {}
        rows, same = [], 0
        for name in sorted(r48):
            ext = name.rsplit('.', 1)[1] if '.' in name else None
            key = 'folder' if not ext else ('unknown' if ext == 'desconocido' else ext)
            w48 = load(pack / 'filetypes' / '48x48' / f'{key}.png', 48)
            f48 = load(r48[name], 48)
            w16 = load(pack / 'filetypes' / '16x16' / f'{key}.png', 16)
            f16 = load(r16.get(name), 16)
            ok = w48 is not None and f48 is not None and w48.tobytes() == f48.tobytes()
            same += ok
            rows.append((name, [w48, f48, w16, f16], ok))
        table(rows, ['Windows 48', 'Fenestra 48', 'Win 16', 'Fen 16'], 48,
              f'File types: icon Explorer draws (pack, IShellItemImageFactory) vs the file GTK picks in Fenestra-Windows — {same}/{len(rows)} identical',
              OUT / 'filetypes-per-type.png')

    # 2. weather: Windows condition SVG vs what Fenestra Shell resolves for each GWeather name
    wj = json.loads((pack / 'weather' / 'weather.json').read_text())
    rows = []
    for name in sorted(n for n in ov['icons'] if n.startswith('weather-') and not n.endswith('-symbolic')):
        f = ov['icons'][name][0]
        win = pack / 'weather' / Path(f).name
        rows.append((f'{name} = {Path(f).stem}', [svg(win, 48), svg(f, 48)], win.read_bytes() == Path(f).read_bytes()))
    table(rows, ['Windows (Widgets)', 'Fenestra Shell'], 48, 'Weather: taskbar / Widgets condition icons', OUT / 'weather.png', 300)
    allw = sorted(wj['icons'])
    sheet = Image.new('RGBA', (10 * 110, ((len(allw) + 9) // 10) * 110), BG)
    d = ImageDraw.Draw(sheet)
    for i, n in enumerate(allw):
        x, y = (i % 10) * 110, (i // 10) * 110
        sheet.alpha_composite(svg(pack / 'weather' / f'{n}.svg', 72), (x + 19, y + 4))
        d.text((x + 4, y + 90), n[:18], fill=FG, font=FONT)
    sheet.convert('RGB').save(OUT / 'weather-all.png')

    # 3. Quick Settings / tray: reference crop vs the glyphs Fenestra Shell now draws
    ref = Path(a.refshots) / 'solid' / 'dark-100-12-quick.png'
    if ref.exists():
        Image.open(ref).crop((1540, 680, 1920, 1080)).resize((760, 800), Image.NEAREST).save(OUT / 'quicksettings-windows-reference.png')
    names = ['network-wireless-signal-none-symbolic', 'network-wireless-signal-weak-symbolic', 'network-wireless-signal-ok-symbolic',
             'network-wireless-signal-good-symbolic', 'network-wireless-signal-excellent-symbolic', 'network-wireless-offline-symbolic',
             'network-wired-symbolic', 'network-wired-no-route-symbolic', 'network-vpn-symbolic', 'bluetooth-active-symbolic',
             'airplane-mode-symbolic', 'battery-level-50-symbolic', 'night-light-symbolic', 'preferences-desktop-accessibility-symbolic',
             'nearby-share-symbolic', 'video-display-cast-symbolic', 'media-view-subtitles-symbolic', 'audio-volume-muted-symbolic',
             'audio-volume-low-symbolic', 'audio-volume-medium-symbolic', 'audio-volume-high-symbolic', 'audio-card-symbolic',
             'display-brightness-symbolic', 'emblem-system-symbolic', 'go-next-symbolic', 'go-previous-symbolic', 'document-edit-symbolic']
    rows = [(n.replace('-symbolic', ''), [svg(ov['icons'][n][0], 32) if n in ov['icons'] else None], None) for n in names]
    for rel in ['status/normal-0-5.svg', 'status/charging-0-5.svg', 'battery/normal-0-10.svg', 'osd/speaker-3.svg',
                'osd/speaker-mute.svg', 'osd/brightness.svg', 'status/media-play.svg', 'status/notifications-dnd.svg',
                'privacy/mic.svg', 'power/4.svg', 'power/7.svg']:
        rows.append((rel, [svg(ov['assets'][rel], 32) if rel in ov['assets'] else None], None))
    table(rows, ['Fenestra Shell (from the pack)'], 32, 'Quick Settings / tray / OSD glyphs (Segoe Fluent Icons and Sysbatt.ttf of the PC)',
          OUT / 'quicksettings-tray.png', 300)

    # 4. app-font glyphs (Paint, Snipping Tool, Settings, Store): reference crop vs exported SVG
    if a.icons_json:
        g = {x['name']: x for x in json.loads(Path(a.icons_json).read_text())['glyphs']}
        gj = json.loads((pack / 'glyphs' / 'glyphs.json').read_text())
        rows = []
        for name, meta in sorted(gj['glyphs'].items()):
            if 'font' not in meta or meta['font'] == 'SegoeIcons.ttf' and name not in ('shape-rounded-rectangle',):
                continue
            w = g[name]['where'][0]
            shot = Image.open(Path(a.refshots) / w['source']).convert('RGBA')
            x, y = w['at']
            crop = shot.crop((x - 16, y - 16, x + 16, y + 16)).resize((64, 64), Image.NEAREST)
            rows.append((f"{name} ({meta['font'].split('.')[0]} {meta['codepoint']})", [crop, svg(pack / 'glyphs' / f'{name}.svg', 64)], None))
        table(rows, ['Windows capture', 'exported glyph'], 64, 'Glyphs from the apps\' own icon fonts', OUT / 'app-font-glyphs.png', 330)


if __name__ == '__main__':
    main()
