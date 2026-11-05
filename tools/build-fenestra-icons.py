#!/usr/bin/env python3
"""Create the "Fenestra" icon theme on top of an installed Win11 icon theme.

Adds the alias names used by Fenestra's Explorer-style Files sidebar (the
patched Nautilus asks for e.g. "dwin" instead of "folder-documents-symbolic")
and points them at Win11's coloured place icons. Usage:

    build-fenestra-icons.py /usr/share/icons   (expects Win11 and Win11-dark there)
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ALIASES = {
    'twne': 'user-trash', 'twnf': 'user-trash-full', 'rwin': 'folder-temp', 'dwin': 'folder-documents',
    'dlwin': 'folder-download', 'mwin': 'folder-music', 'pwin': 'folder-camera', 'pubwin': 'folder-public',
    'tmpwin': 'folder-templates', 'vwin': 'folder-videos', 'nwin': 'network-server', 'drvwin': 'drive-harddisk',
    'hwin': 'home', 'network-drvwin': 'network-server', 'non-swin': 'starred',
}


def main(root):
    root = Path(root)
    base = root / 'Win11-dark'
    if not base.is_dir():
        sys.exit(f'{base} missing')
    theme = root / 'Fenestra'
    if theme.exists():
        shutil.rmtree(theme)
    theme.mkdir()
    dirs = set()
    for src_theme in (root / 'Win11', base):
        for path in src_theme.rglob('*'):
            if not (path.is_file() or path.is_symlink()):
                continue
            name = path.name.rsplit('.', 1)[0]
            for alias, target in ALIASES.items():
                if name in (target, target + '-symbolic'):
                    rel = path.parent.relative_to(src_theme)
                    out = theme / rel / (alias + path.suffix)
                    out.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path.resolve(), out)
                    dirs.add(str(rel))
    menu = Path(__file__).resolve().parent.parent / 'assets' / 'generated' / 'menu-icons'
    if menu.is_dir():
        out = theme / 'scalable' / 'actions'
        out.mkdir(parents=True, exist_ok=True)
        for svg in menu.glob('*.svg'):
            shutil.copyfile(svg, out / svg.name)
        dirs.add('scalable/actions')
    index = ['[Icon Theme]', 'Name=Fenestra', 'Comment=Fenestra icons (Win11 icon theme by yeyushengfan258, GPL-3.0)',
             'Inherits=Win11-dark,Win11,Adwaita,hicolor', 'Example=folder', '']
    entries = []
    win_index = (base / 'index.theme').read_text().splitlines()
    sections = {}
    current = None
    for line in win_index:
        if line.startswith('[') and line != '[Icon Theme]':
            current = line.strip('[]')
            sections[current] = []
        elif current:
            sections[current].append(line)
    for d in sorted(dirs):
        entries.append(d)
    index.insert(4, 'Directories=' + ','.join(entries))
    for d in entries:
        index.append(f'[{d}]')
        index.extend(l for l in sections.get(d, ['Size=32', 'Type=Scalable', 'MinSize=8', 'MaxSize=512']) if l.strip())
        index.append('')
    (theme / 'index.theme').write_text('\n'.join(index))
    for t in ('Win11', 'Win11-dark', 'Fenestra'):
        subprocess.run(['gtk-update-icon-cache', '-qf', str(root / t)], check=False)
    print(f'Fenestra icon theme: {len(dirs)} dirs, aliases for {len(ALIASES)} names')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '/usr/share/icons')
