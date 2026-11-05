#!/usr/bin/env python3
"""Maintainer helper: turn the reference machine's dconf state into Fenestra's
system-wide defaults (/etc/dconf/db/local.d/00-fenestra).

Personal values (recent files, monitor serials, user file paths, apps that
Fenestra does not ship) are removed or rewritten so the result is generic.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / 'desktop' / 'dconf' / 'local.d' / '00-fenestra'

PATHS = [
    '/org/gnome/shell/', '/org/gnome/desktop/interface/', '/org/gnome/desktop/wm/',
    '/org/gnome/desktop/screensaver/', '/org/gnome/mutter/', '/org/gnome/nautilus/',
    '/org/gnome/desktop/peripherals/', '/org/gnome/settings-daemon/plugins/',
    '/org/gnome/desktop/sound/', '/org/gnome/desktop/notifications/', '/org/gtk/',
    '/org/gnome/desktop/a11y/', '/org/gnome/desktop/privacy/',
]

# Keys never shipped (personal state / machine specific / runtime caches).
DROP = re.compile(r'''^(
    recently-installed-apps|pinned-apps-history|arcmenu-hotkey-.*-x11|
    last-selected-.*|window-state|initial-size|search-filter-time-type|
    command-history|app-picker-layout|welcome-dialog-last-shown-version|
    remember-recent-files|recent-files-max-age|.*-last-.*|prefs-opened|
    primary-monitor|panel-monitors|available-monitors|extension-version|
    update-notifier-.*|disable-user-extensions|last-coordinates|
    weather|world-clocks|locations|picture-uri.*|primary-color|secondary-color|
    cursor-theme|cursor-size|font-name|document-font-name|monospace-font-name|
    gtk-theme|icon-theme|color-scheme|accent-color|text-scaling-factor|
    clock-.*|show-battery-percentage|application-children|custom-keybindings|theme-name
)$''', re.X)

# Monitor-keyed JSON (dash-to-panel): re-key by monitor index so it applies
# to any screen ("0" is the primary monitor, see panelSettings.getMonitorSetting).
MONITOR_JSON = {'panel-anchors', 'panel-element-positions', 'panel-lengths', 'panel-positions', 'panel-sizes'}

# Desktop files Fenestra ships by default (others are filtered out of pins/favorites).
SHIPPED_APPS = {
    'org.gnome.Nautilus.desktop', 'firefox.desktop', 'org.mozilla.firefox.desktop',
    'org.gnome.TextEditor.desktop', 'org.gnome.Calculator.desktop', 'org.gnome.Calendar.desktop',
    'org.gnome.clocks.desktop', 'org.gnome.Snapshot.desktop', 'org.gnome.Loupe.desktop',
    'org.gnome.Contacts.desktop', 'org.gnome.Weather.desktop', 'org.gnome.Maps.desktop',
    'libreoffice-writer.desktop', 'libreoffice-calc.desktop', 'libreoffice-impress.desktop',
    'org.gnome.Software.desktop', 'org.gnome.Ptyxis.desktop', 'fenestra-settings.desktop',
    'org.gnome.Settings.desktop', 'windows-search.desktop', 'fenestra-search.desktop',
}
RENAME_APPS = {
    'brave-browser.desktop': 'org.mozilla.firefox.desktop',
    'org.gnome.Settings.desktop': 'fenestra-settings.desktop',
    'windows-search.desktop': 'fenestra-search.desktop',
}
RENAME_UUIDS = {
    'windows-tray@local': 'fenestra-tray@fenestra-os.github.io',
    'windows-consent@local': 'fenestra-consent@fenestra-os.github.io',
    'windows-lock-clock@local': 'fenestra-lock-clock@fenestra-os.github.io',
    'windows-spotlight@local': 'fenestra-spotlight@fenestra-os.github.io',
    'direct-unlock@local': 'fenestra-direct-unlock@fenestra-os.github.io',
    'user-lock-prompt@local': 'fenestra-user-lock-prompt@fenestra-os.github.io',
}
SHIPPED_UUIDS = {
    'arcmenu@arcmenu.com', 'dash-to-panel@jderose9.github.com', 'ding@rastersoft.com',
    'blur-my-shell@aunetx', 'rounded-window-corners@fxgn', 'tiling-assistant@leleat-on-github',
    'notification-banner@VitalyOstanin', 'no-screenshot-box@screenshot',
    *RENAME_UUIDS.values(),
}


def dump(path):
    return subprocess.run(['dconf', 'dump', path], capture_output=True, text=True, check=True).stdout


def fix_value(key, value):
    for a, b in {**RENAME_APPS, **RENAME_UUIDS}.items():
        value = value.replace(a, b)
    value = value.replace(str(Path.home()), '/usr/share')
    if key in MONITOR_JSON and value.startswith("'{"):
        data = json.loads(value[1:-1])
        if data:
            first = next(iter(data.values()))
            value = "'" + json.dumps({str(i): first for i in range(4)}, separators=(',', ':')) + "'"
    if key in ('enabled-extensions',):
        items = [x for x in re.findall(r"'([^']+)'", value) if x in SHIPPED_UUIDS]
        value = '[' + ', '.join(f"'{x}'" for x in items) + ']'
    if key == 'pinned-apps':
        ids = [x for x in re.findall(r"'id': '([^']+)'", value) if x in SHIPPED_APPS]
        value = '[' + ', '.join("{'id': '%s'}" % x for x in ids) + ']'
    if key == 'favorite-apps':
        items = [x for x in re.findall(r"'([^']+)'", value) if x in SHIPPED_APPS]
        value = '[' + ', '.join(f"'{x}'" for x in items) + ']'
    return value


def main():
    out = []
    for base in PATHS:
        section = None
        for line in dump(base).splitlines():
            if line.startswith('['):
                rel = line[1:-1]
                section = (base.strip('/') + ('' if rel == '/' else '/' + rel)).strip('/')
                if re.search(r'blur-my-shell/(dash-to-dock|coverflow|window-list)|openbar|window-list|emoji-copy|day-progress|notifications/application|custom-keybindings|nautilus/window-state|plugins/power', section):
                    section = None
                    continue
                out.append(f'\n[{section}]')
                continue
            if not section or '=' not in line:
                continue
            key, value = line.split('=', 1)
            if DROP.match(key) or 'miguel' in value.lower():
                continue
            out.append(f'{key}={fix_value(key, value)}')
    # Drop empty sections.
    text = re.sub(r'\n\[[^\]]+\](?=\n\[|\s*$)', '', '\n'.join(out))
    header = ('# Fenestra system defaults (generated by tools/export-dconf-defaults.py).\n'
              '# Users can change all of these; nothing is locked.\n')
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(header + text.strip() + '\n')
    print(f'wrote {OUT} ({len(text.splitlines())} lines)')


if __name__ == '__main__':
    sys.exit(main())
