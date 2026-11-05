#!/usr/bin/env python3
"""Generate Fenestra's open-licensed default assets.

Everything here is either drawn from scratch by this script or derived from
Microsoft's Fluent UI System Icons (MIT license, @fluentui/svg-icons). Nothing
is copied from a Windows installation; the user's own Windows assets can be
imported later with fenestra-import-windows-assets, which writes overrides to
~/.local/share/fenestra/assets with the same layout as produced here.

Output: assets/generated/  (installed to /usr/share/fenestra/assets)
"""
import argparse
import json
import math
import re
import subprocess
import tarfile
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / 'assets' / 'generated'
CACHE = Path.home() / '.cache' / 'fenestra-build'
FLUENT_VERSION = '1.1.345'
FLUENT_URL = f'https://registry.npmjs.org/@fluentui/svg-icons/-/svg-icons-{FLUENT_VERSION}.tgz'


def fluent_dir():
    target = CACHE / f'fluent-{FLUENT_VERSION}'
    if not (target / 'package' / 'icons').is_dir():
        CACHE.mkdir(parents=True, exist_ok=True)
        tgz = CACHE / f'fluent-{FLUENT_VERSION}.tgz'
        if not tgz.exists():
            urllib.request.urlretrieve(FLUENT_URL, tgz)
        with tarfile.open(tgz) as t:
            t.extractall(target, filter='data')
    return target / 'package' / 'icons'


def fluent(name, fill='#ffffff', size=None):
    svg = (fluent_dir() / f'{name}.svg').read_text()
    svg = svg.replace('<path ', f'<path fill="{fill}" ')
    if size:
        svg = re.sub(r'width="\d+" height="\d+"', f'width="{size}" height="{size}"', svg, count=1)
    return svg


def write(rel, text):
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def png(svg_path, png_path, size):
    png_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['magick', '-background', 'none', '-density', str(96 * size // 24 * 2),
                    str(svg_path), '-resize', f'{size}x{size}', str(png_path)], check=True)


# --------------------------------------------------------------- battery ---
BOLT = 'M12.6 6.2 7.9 12.6h3.3l-1 5.2 4.9-6.6h-3.4z'


def battery_svg(state, variant, level, color='#ffffff'):
    """Horizontal battery like the Windows 11 tray glyph (own drawing)."""
    w = 14.4 * level / 10
    fill_col = {'low': '#ff99a4', 'saver': color}.get(state, color)
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">',
        '<defs><mask id="m"><rect width="24" height="24" fill="#fff"/>',
    ]
    bolt = state == 'charging' or (variant == 1 and state in ('normal', 'plugged'))
    if bolt:
        parts.append(f'<path d="{BOLT}" fill="#000" stroke="#000" stroke-width="2.6" stroke-linejoin="round"/>')
    parts.append('</mask></defs><g mask="url(#m)">')
    parts.append(f'<rect x="1.85" y="7.35" width="17.6" height="9.3" rx="2.6" fill="none" stroke="{color}" stroke-width="1.3"/>')
    parts.append(f'<rect x="20.15" y="10.2" width="1.75" height="3.6" rx="0.85" fill="{color}"/>')
    if w > 0:
        parts.append(f'<rect x="3.45" y="8.95" width="{w:.2f}" height="6.1" rx="1.25" fill="{fill_col}"/>')
    parts.append('</g>')
    if bolt:
        parts.append(f'<path d="{BOLT}" fill="{color}"/>')
    if state == 'plugged' and not bolt:
        parts.append(f'<path d="M9 9.5h1.2v-2h1v2h1.6v-2h1v2H15v2.1a3 3 0 0 1-2.4 2.9V17h-1.2v-2.5A3 3 0 0 1 9 11.6z" fill="{color}"/>')
    if state == 'saver':
        parts.append(f'<path d="M7.2 15.2c0-4 3-6.2 7.6-6.2 0 4.4-2.4 6.6-6 6.6l-1.6.1c1.1-1.7 2.6-3 4.4-3.9" fill="none" stroke="{color}" stroke-width="1.1" stroke-linecap="round"/>')
    parts.append('</svg>')
    return ''.join(parts)


def gen_battery():
    for state in ('normal', 'low', 'saver', 'charging', 'plugged'):
        for variant in ((0,) if state == 'plugged' else (0, 1)):
            for level in range(11):
                write(f'battery/{state}-{variant}-{level}.svg', battery_svg(state, variant, level))
    # Lock screen status (same glyphs, consumed by fenestra-spotlight).
    for level in range(11):
        write(f'status/normal-0-{level}.svg', battery_svg('normal', 0, level))
        write(f'status/charging-0-{level}.svg', battery_svg('charging', 0, level))
    wifi = {'excellent': 'wifi_1_24_regular', 'good': 'wifi_2_24_regular', 'ok': 'wifi_3_24_regular',
            'weak': 'wifi_4_24_regular', 'none': 'wifi_4_24_regular'}
    for name, icon in wifi.items():
        write(f'status/network-wireless-signal-{name}-symbolic.svg', fluent(icon))
    for name in ('disabled', 'offline'):
        write(f'status/network-wireless-{name}-symbolic.svg', fluent('wifi_off_24_regular'))
    write('status/network-wireless-no-route-symbolic.svg', fluent('wifi_warning_24_regular'))


# ----------------------------------------------------------------- power ---
def gen_power():
    # ArcMenu PowerType ids: 0 logout, 1 lock, 2 restart, 3 power off, 4 suspend, 7 switch user.
    icons = {0: 'sign_out_24_regular', 1: 'lock_closed_16_regular', 2: 'arrow_clockwise_16_regular',
             3: 'power_24_regular', 4: 'weather_moon_16_regular', 7: 'person_swap_16_regular'}
    for key, icon in icons.items():
        write(f'power/{key}.svg', fluent(icon, '#eeeeee', 16))


# --------------------------------------------------------------- consent ---
def gen_consent():
    write('consent/close.svg', fluent('dismiss_16_regular', '#ffffff', 16))
    # Own two-tone shield (blue/gold quarters echo the classic admin shield idea).
    write('consent/shield.svg', '''<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
<defs><linearGradient id="b" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#4fb3ff"/><stop offset="1" stop-color="#0a5fc4"/></linearGradient>
<linearGradient id="y" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffe17a"/><stop offset="1" stop-color="#f2a900"/></linearGradient>
<clipPath id="c"><path d="M16 2.5 4.5 6.6v8.2c0 7.1 4.8 12.6 11.5 14.7 6.7-2.1 11.5-7.6 11.5-14.7V6.6z"/></clipPath></defs>
<g clip-path="url(#c)"><rect width="16" height="16" fill="url(#b)"/><rect x="16" width="16" height="16" fill="url(#y)"/>
<rect y="16" width="16" height="16" fill="url(#y)"/><rect x="16" y="16" width="16" height="16" fill="url(#b)"/></g>
<path d="M16 2.5 4.5 6.6v8.2c0 7.1 4.8 12.6 11.5 14.7 6.7-2.1 11.5-7.6 11.5-14.7V6.6z" fill="none" stroke="#ffffff" stroke-opacity=".35"/></svg>''')


# ---------------------------------------------------------------- search ---
def gen_search():
    svg = write('search/search.svg', '''<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#5ee0ff"/><stop offset=".55" stop-color="#2aa7f0"/><stop offset="1" stop-color="#1366d6"/></linearGradient></defs>
<circle cx="27" cy="27" r="17" fill="none" stroke="url(#g)" stroke-width="7"/>
<path d="M39.5 39.5 54 54" stroke="#0f5bc4" stroke-width="8" stroke-linecap="round"/></svg>''')
    png(svg, OUT / 'search' / 'search.png', 64)


# --------------------------------------------------------------- folders ---
def gen_folders():
    back = '<path d="M14 40a10 10 0 0 1 10-10h56c4 0 7 2 9.4 5l7 9H232a10 10 0 0 1 10 10v150a10 10 0 0 1-10 10H24a10 10 0 0 1-10-10z" fill="url(#back)"/>'
    front = '<path d="M14 82a10 10 0 0 1 10-10h208a10 10 0 0 1 10 10v118a10 10 0 0 1-10 10H24a10 10 0 0 1-10-10z" fill="url(#front)"/>'
    defs = ('<defs><linearGradient id="back" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f5b52a"/><stop offset="1" stop-color="#e09a12"/></linearGradient>'
            '<linearGradient id="front" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffe08a"/><stop offset=".55" stop-color="#ffd25e"/><stop offset="1" stop-color="#f9bf35"/></linearGradient>'
            '<linearGradient id="paper" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#e9edf2"/></linearGradient></defs>')
    paper = '<rect x="34" y="56" width="188" height="60" rx="5" fill="url(#paper)"/><rect x="34" y="56" width="188" height="60" rx="5" fill="none" stroke="#000" stroke-opacity=".08"/>'
    head = '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">'
    empty = write('folders/folder-empty.svg', head + defs + back + front + '</svg>')
    full = write('folders/folder-full.svg', head + defs + back + paper + front.replace('M14 82', 'M14 92').replace('v118', 'v108') + '</svg>')
    png(empty, OUT / 'folders' / 'folder-empty.png', 256)
    png(full, OUT / 'folders' / 'folder-full.png', 256)


# ------------------------------------------------------------- hello face ---
def gen_hello():
    """Face-recognition animation (own design): pulsing ring, then a check."""
    frames = {'searching': [], 'authentication': []}
    d = OUT / 'hello'
    d.mkdir(parents=True, exist_ok=True)
    n = 24
    for i in range(n):
        t = i / n
        a1, a2 = 360 * t, 360 * t + 110
        r = 110

        def arc(a, b, rr=r):
            x1, y1 = 150 + rr * math.cos(math.radians(a)), 150 + rr * math.sin(math.radians(a))
            x2, y2 = 150 + rr * math.cos(math.radians(b)), 150 + rr * math.sin(math.radians(b))
            return f'M{x1:.1f} {y1:.1f}A{rr} {rr} 0 0 1 {x2:.1f} {y2:.1f}'
        glow = 0.35 + 0.25 * math.sin(2 * math.pi * t)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 300 300">'
               f'<circle cx="150" cy="150" r="{r}" fill="none" stroke="#ffffff" stroke-opacity=".18" stroke-width="5"/>'
               f'<path d="{arc(a1, a2)}" fill="none" stroke="#ffffff" stroke-width="5" stroke-linecap="round"/>'
               f'<circle cx="150" cy="128" r="30" fill="none" stroke="#ffffff" stroke-opacity="{glow:.2f}" stroke-width="5"/>'
               f'<path d="M98 205c10-24 30-36 52-36s42 12 52 36" fill="none" stroke="#ffffff" stroke-opacity="{glow:.2f}" stroke-width="5" stroke-linecap="round"/></svg>')
        sp = d / f'search-{i:02d}.svg'
        sp.write_text(svg)
        png(sp, d / f'search-{i:02d}.png', 300)
        sp.unlink()
        frames['searching'].append({'file': f'search-{i:02d}.png', 'duration': 40})
    for i in range(12):
        t = min(1, i / 8)
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 300 300">'
               '<circle cx="150" cy="150" r="110" fill="none" stroke="#ffffff" stroke-width="5"/>'
               f'<path d="M105 152l30 30 62-64" fill="none" stroke="#ffffff" stroke-width="9" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="140" stroke-dashoffset="{140 * (1 - t):.1f}"/></svg>')
        sp = d / f'auth-{i:02d}.svg'
        sp.write_text(svg)
        png(sp, d / f'auth-{i:02d}.png', 300)
        sp.unlink()
        frames['authentication'].append({'file': f'auth-{i:02d}.png', 'duration': 40})
    (d / 'frames.json').write_text(json.dumps(frames))


# ----------------------------------------------------------------- logos ---
LOGO = '''<svg xmlns="http://www.w3.org/2000/svg" width="{s}" height="{s}" viewBox="0 0 64 64">
<defs><linearGradient id="a" x1="0" y1="0" x2="0.6" y2="1"><stop offset="0" stop-color="#6fdcff"/><stop offset="1" stop-color="#0c62d8"/></linearGradient>
<linearGradient id="b" x1="0" y1="0" x2="0.6" y2="1"><stop offset="0" stop-color="#52c6ff"/><stop offset="1" stop-color="#0a4fb4"/></linearGradient></defs>
<path d="M10 30C10 17.8 19.8 8 32 8v22z" fill="url(#a)"/>
<path d="M34 8c12.2 0 20 9.8 20 22H34z" fill="url(#b)"/>
<path d="M10 34h22v22H12a2 2 0 0 1-2-2z" fill="url(#b)"/>
<path d="M34 34h20v20a2 2 0 0 1-2 2H34z" fill="url(#a)"/></svg>'''


def gen_logos():
    # Fenestra mark: an arched window (fenestra = window in Latin), deliberately unlike the Windows logo.
    svg = write('branding/fenestra-logo.svg', LOGO.format(s=64))
    png(svg, OUT / 'branding' / 'fenestra-logo-256.png', 256)
    write('branding/start-button.svg', LOGO.format(s=48))


# ------------------------------------------------------------ wallpapers ---
def gen_wallpapers(size=(3840, 2400)):
    import numpy as np
    from PIL import Image, ImageFilter

    def bloom(dark):
        w, h = size
        y, x = np.mgrid[0:h, 0:w].astype(np.float32)
        x = (x / w - 0.5) * (w / h)
        y = y / h - 0.5
        base = np.array([12, 22, 48] if dark else [210, 226, 246], np.float32)
        img = np.ones((h, w, 3), np.float32) * base
        # Soft vignette background.
        rr = np.sqrt(x ** 2 + y ** 2)
        img *= (1.0 - 0.35 * rr[..., None]) if dark else (1.0 - 0.12 * rr[..., None])
        # Ribbon petals: rotated soft ellipses with gradient colours.
        cols = [(40, 140, 255), (0, 90, 220), (90, 200, 255), (30, 110, 240), (130, 210, 255)]
        for k in range(7):
            ang = math.radians(-60 + k * 22)
            cx, cy = 0.0, 0.04
            xr = (x - cx) * math.cos(ang) + (y - cy) * math.sin(ang)
            yr = -(x - cx) * math.sin(ang) + (y - cy) * math.cos(ang)
            petal = np.exp(-((xr - 0.2) ** 2 / 0.04 + (yr ** 2) / 0.0016))
            petal += 0.6 * np.exp(-((xr - 0.24) ** 2 / 0.02 + ((yr - 0.012) ** 2) / 0.0003))
            c = np.array(cols[k % len(cols)], np.float32)
            a = (0.85 if dark else 0.75) * petal[..., None]
            img = img * (1 - a) + c * a
        img = np.clip(img, 0, 255).astype(np.uint8)
        return Image.fromarray(img).filter(ImageFilter.GaussianBlur(2))

    d = OUT / 'wallpapers'
    d.mkdir(parents=True, exist_ok=True)
    bloom(True).save(d / 'fenestra-bloom-dark.jpg', quality=92)
    bloom(False).save(d / 'fenestra-bloom-light.jpg', quality=92)


MENU = {'cancel': 'dismiss_16_regular', 'commandprompt': 'window_console_20_regular', 'copy': 'copy_16_regular',
        'cut': 'cut_16_regular', 'delete': 'delete_16_regular', 'document': 'document_16_regular',
        'eject': 'arrow_eject_20_regular', 'favoritestar': 'star_16_regular', 'folderopen': 'folder_open_16_regular',
        'folder': 'folder_16_regular', 'harddrive': 'hard_drive_20_regular', 'link': 'link_16_regular',
        'newfolder': 'folder_add_16_regular', 'openfile': 'open_16_regular', 'openinnewwindow': 'window_new_16_regular',
        'page': 'document_16_regular', 'paste': 'clipboard_paste_16_regular', 'personalize': 'paint_brush_16_regular',
        'play': 'play_16_regular', 'redo': 'arrow_redo_16_regular', 'refresh': 'arrow_clockwise_16_regular',
        'rename': 'rename_16_regular', 'selectall': 'select_all_on_16_regular', 'settings': 'settings_16_regular',
        'share': 'share_16_regular', 'sort': 'arrow_sort_16_regular', 'stop': 'stop_16_regular',
        'tvmonitor': 'desktop_16_regular', 'undo': 'arrow_undo_16_regular', 'viewall': 'grid_16_regular',
        'zipfolder': 'folder_zip_16_regular'}


def gen_menu():
    # Context-menu icons (Fluent UI System Icons, MIT) in the light accent tint used by Windows 11 menus.
    for name, icon in MENU.items():
        write(f'menu-icons/win11-menu-{name}.svg', fluent(icon, '#9fc8dc', 16))


EXPLORER = {'add': ('add_circle_20_regular', '#9fc8dc'), 'more': ('more_horizontal_20_regular', '#ffffff'),
            'refresh': ('arrow_clockwise_20_regular', '#ffffff'), 'up': ('arrow_up_20_regular', '#ffffff'),
            'view': ('grid_20_regular', '#ffffff')}


def gen_explorer():
    # Files (Explorer layer) command bar / navigation icons, Fluent UI System Icons (MIT).
    for name, (icon, fill) in EXPLORER.items():
        write(f'menu-icons/win11-explorer-{name}.svg', fluent(icon, fill, 16))
    # Plain "x" for tab/dialog close buttons: the Win11 icon theme resolves
    # window-close-symbolic to its red titlebar circle in some sizes.
    write('menu-icons/window-close-symbolic.svg', fluent('dismiss_16_regular', '#ffffff', 16))


STEPS = {'menu': gen_menu, 'explorer': gen_explorer, 'battery': gen_battery, 'power': gen_power, 'consent': gen_consent, 'search': gen_search,
         'folders': gen_folders, 'hello': gen_hello, 'logos': gen_logos, 'wallpapers': gen_wallpapers}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('steps', nargs='*', default=list(STEPS))
    args = ap.parse_args()
    for step in args.steps:
        STEPS[step]()
        print('generated', step)


if __name__ == '__main__':
    main()
