#!/usr/bin/python3
"""Which icons Fenestra Shell draws from the imported Windows icon pack and which still fall back
to Fenestra's own artwork.

Fenestra Shell (KWin session) looks every icon name and asset up in
~/.local/share/fenestra/icon-overrides.json first (shell/src/core/iconoverrides.cpp); anything not
there comes from the Fenestra icon theme / /usr/share/fenestra/assets. This script collects the
icon names and assets the shell asks for (QML literals, C++ string literals, the asset folders the
QML builds paths into, the GWeather / NetworkManager / PulseAudio name families its services use)
and reports, per slot, whether the pack covers it.

    tests/icon-pack/audit-shell-icons.py [--overrides FILE] [--json]
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SHELL = REPO / 'shell'
DATA = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
SYSTEM_ASSETS = Path('/usr/share/fenestra/assets')

# Names the services build at run time (status.cpp, weather.cpp, desktop.cpp, startservices.cpp).
DYNAMIC_NAMES = {
    'tray / Quick Settings network (status.cpp)': [
        f'network-wireless-signal-{l}-symbolic' for l in ('none', 'weak', 'ok', 'good', 'excellent')] + [
        'network-wireless-no-route-symbolic', 'network-wired-no-route-symbolic', 'network-wired-symbolic',
        'network-vpn-symbolic', 'network-wireless-disabled-symbolic', 'network-wireless-offline-symbolic'],
    'tray / Quick Settings volume (status.cpp)': [
        'audio-volume-muted-symbolic', 'audio-volume-low-symbolic', 'audio-volume-medium-symbolic',
        'audio-volume-high-symbolic'],
    'taskbar weather button (weather.cpp: GWeather icon names)': [
        n + s for n in ('weather-clear', 'weather-clear-night', 'weather-few-clouds', 'weather-few-clouds-night',
                        'weather-overcast', 'weather-fog', 'weather-showers', 'weather-showers-scattered',
                        'weather-snow', 'weather-storm', 'weather-severe-alert') for s in ('', '-symbolic')],
    'desktop / Start Recommended / Search file icons (QMimeDatabase iconName)': [
        'text-plain', 'image-png', 'image-jpeg', 'application-pdf', 'application-zip', 'video-mp4', 'audio-mpeg',
        'application-x-msdownload', 'text-html', 'application-json', 'text-x-python', 'text-x-shellscript',
        'application-vnd.openxmlformats-officedocument.wordprocessingml.document', 'font-ttf', 'inode-directory',
        'folder', 'user-trash', 'user-trash-full', 'application-x-zerosize', 'application-octet-stream'],
}
ASSET_DIRS = ('menu-icons', 'power', 'security', 'status', 'osd', 'privacy', 'consent', 'battery', 'folders', 'search',
              'branding')


def collect_names():
    names = {}
    pats = [
        (re.compile(r'(?:iconName|glyph|name|symbolicIconName)\s*:\s*"([a-z][a-z0-9.+-]*)"'), 'QML'),
        (re.compile(r'image://(?:icon|tint/[^/"]*)/([a-z][a-z0-9.+-]+)"'), 'QML image://'),
        (re.compile(r'QStringLiteral\("([a-z][a-z0-9-]*-symbolic|user-trash[a-z-]*|folder|application-x-executable)"\)'), 'C++'),
    ]
    for f in sorted(SHELL.rglob('*')):
        if f.suffix not in ('.qml', '.cpp', '.h', '.js'):
            continue
        text = f.read_text(errors='replace')
        for rx, kind in pats:
            for m in rx.finditer(text):
                n = m.group(1)
                if n.endswith('-') or n in ('restart', 'shutdown', 'sleep') or n.startswith('snip-'):
                    continue
                names.setdefault(n, set()).add(str(f.relative_to(REPO)))
    return names


def collect_assets():
    used = {}
    for f in sorted(SHELL.rglob('*.qml')):
        text = f.read_text(errors='replace')
        for m in re.finditer(r'Metrics\.assets\s*\+\s*"([^"]+)"', text):
            used.setdefault(m.group(1), set()).add(str(f.relative_to(REPO)))
        for m in re.finditer(r'glyph\("([a-z]+)"\)', text):
            if 'win11-menu-" + name' in text:
                used.setdefault(f'menu-icons/win11-menu-{m.group(1)}.svg', set()).add(str(f.relative_to(REPO)))
    for f in sorted(SHELL.rglob('*.cpp')):
        for m in re.finditer(r'/usr/share/fenestra/assets/([a-z-]+/)', f.read_text(errors='replace')):
            used.setdefault(m.group(1), set()).add(str(f.relative_to(REPO)))
    # prefixes ("status/", "osd/", "battery/"): every file of that folder the shell ships
    out = {}
    for rel, where in used.items():
        if rel.endswith('-'):
            continue                          # glyph("name") calls are listed one by one above
        if rel == 'status/':
            for n in ('media-previous', 'media-play', 'media-pause', 'media-next'):   # QuickSettings.qml media card
                out.setdefault(f'status/{n}.svg', set()).update(where)
        if rel.endswith('/'):
            base = SYSTEM_ASSETS / rel.rstrip('-').rsplit('/', 1)[0] if rel.endswith('-') else SYSTEM_ASSETS / rel
            prefix = rel if rel.endswith('/') else rel
            files = sorted(base.glob('*.svg')) if base.is_dir() else []
            for p in files:
                r = f'{base.name}/{p.name}'
                if r.startswith(prefix.rstrip('/') if rel.endswith('/') else prefix):
                    out.setdefault(r, set()).update(where)
        else:
            out.setdefault(rel, set()).update(where)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--overrides', default=str(DATA / 'fenestra' / 'icon-overrides.json'))
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    try:
        ov = json.loads(Path(a.overrides).read_text())
    except (OSError, ValueError):
        ov = {}
    icons, assets = ov.get('icons', {}), ov.get('assets', {})
    conf = (Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'fenestra' / 'shell.conf')
    conf = conf.read_text(errors='replace') if conf.exists() else ''
    by_conf = {'branding/start-button.svg': 'StartIcon=', 'search/search.svg': 'SearchIcon='}
    report = {'names': {}, 'assets': {}, 'dynamic': {}}
    for n, where in sorted(collect_names().items()):
        report['names'][n] = {'windows': n in icons, 'where': sorted(where)}
    for group, names in DYNAMIC_NAMES.items():
        report['dynamic'][group] = {n: n in icons for n in names}
    for rel, where in sorted(collect_assets().items()):
        ok = rel in assets or (rel in by_conf and by_conf[rel] in conf)
        report['assets'][rel] = {'windows': ok, 'where': sorted(where)}
    if a.json:
        print(json.dumps(report, indent=1))
        return 0
    miss = 0
    print('Icon names (QML / C++ literals):')
    for n, r in report['names'].items():
        miss += not r['windows']
        print(f"  {'WINDOWS ' if r['windows'] else 'FENESTRA'}  {n}  ({', '.join(r['where'])})")
    for group, d in report['dynamic'].items():
        print(f'{group}:')
        for n, ok in d.items():
            miss += not ok
            print(f"  {'WINDOWS ' if ok else 'FENESTRA'}  {n}")
    print('Assets (Metrics.assets / file:///usr/share/fenestra/assets):')
    for rel, r in report['assets'].items():
        miss += not r['windows']
        print(f"  {'WINDOWS ' if r['windows'] else 'FENESTRA'}  {rel}  ({', '.join(r['where'])})")
    total = len(report['names']) + sum(len(d) for d in report['dynamic'].values()) + len(report['assets'])
    print(f'{total - miss} of {total} icon slots come from the Windows pack, {miss} fall back to Fenestra')
    return 0


if __name__ == '__main__':
    sys.exit(main())
