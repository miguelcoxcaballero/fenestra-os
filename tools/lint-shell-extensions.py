#!/usr/bin/env python3
"""Check GNOME Shell extensions for APIs that the GNOME versions they declare no longer have.

    tools/lint-shell-extensions.py [--target N] [PATH...]

PATH: extension directories or folders that contain them (default: desktop/extensions and
extras/fedora-upgrade/system-extensions). A rule applies when the extension's metadata.json
declares a shell-version >= the release that removed the API (or >= --target, to check a
GNOME release before upgrading to it). A use is accepted when the same file also has the
rule's guard (a feature check such as `typeof Meta.Background.prototype.set_file`).

Exit code 1 when there are errors. Prints `file:line: [rule] message`.
Add a rule here whenever a GNOME release removes something an extension used.
"""
import argparse
import json
import os
import re
import sys

# (id, removed in, pattern, guard or None, message)
RULES = [
    ('meta-background-set-file', 51, r'\.set_file\s*\(', r'HAS_SET_FILE|typeof\s+[\w.?]*set_file',
     'Meta.Background.set_file() was removed in GNOME 51 (backgrounds are glycin textures); '
     'guard it and fall back to an St background'),
    ('st-vertical', 51, r'\bvertical\s*:\s*(true|false)\b', None,
     'St.BoxLayout "vertical" was removed in GNOME 51: use orientation: Clutter.Orientation.VERTICAL'),
    ('st-set-vertical', 51, r'\.vertical\s*=\s*(true|false)\b', None,
     'St.BoxLayout.vertical was removed in GNOME 51: set orientation'),
    ('gdm-util-verifier', 51, r"gdm/util\.js['\"]", r'gdm/userVerifier\.js',
     'ShellUserVerifier/MessageType moved to gdm/userVerifier.js in GNOME 51: import it there '
     '(keep gdm/util.js only as the fallback for older releases)'),
    ('verifier-on-complete', 51, r'_onVerificationComplete', r"typeof\s+[\w.]*_onVerificationComplete",
     'ShellUserVerifier._onVerificationComplete is gone in GNOME 51 (AuthServices reports success): '
     'check that it exists before overriding it'),
    ('queue-message-positional', 51, r'\._queueMessage\(\s*(?!\{)[^)\s]', None,
     '_queueMessage(service, message, type) became _queueMessage({serviceName, message, messageType, wiggle}) in GNOME 51'),
    ('shell-glsl-effect', 51, r'Shell\.GLSLEffect', r'glsl_compat|typeof\s+Shell\.GLSLEffect|Shell\.GLSLEffect\s*\?',
     'Shell.GLSLEffect was removed in GNOME 51: use Clutter.ShaderEffect + Cogl.Snippet'),
    ('chrome-affects-input-region', 51,
     r'layoutManager\.(addChrome|addTopChrome|trackChrome)\([^)]*affectsInputRegion', None,
     'addChrome({affectsInputRegion}) was removed in GNOME 51 (Params.parse throws on it)'),
    ('legacy-imports', 45, r'\bimports\.(gi|ui|misc)\b', None,
     'GNOME 45+ extensions are ES modules: the legacy imports object is gone'),
    ('clutter-container', 46, r'\.add_actor\s*\(|\.remove_actor\s*\(|Clutter\.Container\b',
     r'(?m)^\s*(add_actor|remove_actor)\s*\(|if\s*\(\s*[\w.]+\.(add_actor|remove_actor)\s*\)',
     'Clutter.Container (add_actor/remove_actor) was removed in GNOME 46: use add_child/remove_child'),
    ('meta-later-add', 44, r'Meta\.later_add\b', None,
     'Meta.later_add was removed in GNOME 44: use global.compositor.get_laters().add'),
]


def declared_versions(ext_dir):
    try:
        meta = json.load(open(os.path.join(ext_dir, 'metadata.json')))
    except (OSError, ValueError):
        return None, []
    out = []
    for v in meta.get('shell-version', []):
        try:
            out.append(int(str(v).split('.')[0]))
        except ValueError:
            pass
    return meta.get('uuid', os.path.basename(ext_dir)), out


def extension_dirs(paths):
    for p in paths:
        if os.path.isfile(os.path.join(p, 'metadata.json')):
            yield p
        elif os.path.isdir(p):
            for d in sorted(os.listdir(p)):
                if os.path.isfile(os.path.join(p, d, 'metadata.json')):
                    yield os.path.join(p, d)


def strip_comments(line, in_block):
    """Code part of a JS line (good enough for rules: drops // and /* */ comments)."""
    out, i = '', 0
    while i < len(line):
        if in_block:
            j = line.find('*/', i)
            if j < 0:
                return out, True
            i, in_block = j + 2, False
        elif line.startswith('/*', i):
            in_block = True
            i += 2
        elif line.startswith('//', i):
            break
        else:
            out += line[i]
            i += 1
    return out, in_block


SHELL_ONLY = {'legacy-imports', 'clutter-container', 'chrome-affects-input-region', 'meta-later-add'}


def standalone_dir(root, files):
    """A folder with its own `#!/usr/bin/env gjs` program runs outside GNOME Shell."""
    for name in files:
        if name.endswith('.js'):
            try:
                with open(os.path.join(root, name), encoding='utf-8', errors='replace') as f:
                    first = f.readline()
            except OSError:
                continue
            if first.startswith('#!') and 'gjs' in first:
                return True
    return False


def version_specific(name):
    """altTab-48.js: a copy of GNOME 48 code that the extension only uses on GNOME 48."""
    m = re.search(r'-(\d{2})\.js$', name)
    return int(m.group(1)) if m else None


def lint(paths, target=None):
    errors = 0
    for ext in extension_dirs(paths):
        uuid, versions = declared_versions(ext)
        newest = max(versions + ([target] if target else []), default=0)
        for root, _dirs, files in os.walk(ext):
            standalone = standalone_dir(root, files)
            for name in sorted(files):
                if not name.endswith('.js'):
                    continue
                path = os.path.join(root, name)
                text = open(path, encoding='utf-8', errors='replace').read()
                in_block = False
                for n, raw in enumerate(text.splitlines(), 1):
                    code, in_block = strip_comments(raw, in_block)
                    for rid, removed, pat, guard, msg in RULES:
                        if standalone and rid in SHELL_ONLY:
                            continue
                        only_for = version_specific(name)
                        if only_for is not None and only_for < removed:
                            continue
                        if newest < removed or not re.search(pat, code):
                            continue
                        if guard and re.search(guard, text):
                            continue
                        print(f'{path}:{n}: [{rid}] {uuid} declares GNOME {newest}: {msg}')
                        errors += 1
    return errors


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--target', type=int, help='also check against this GNOME release (before upgrading)')
    ap.add_argument('paths', nargs='*')
    a = ap.parse_args()
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    paths = a.paths or [os.path.join(repo, 'desktop', 'extensions'),
                        os.path.join(repo, 'extras', 'fedora-upgrade', 'system-extensions')]
    n = lint(paths, a.target)
    print(f'{n} problem(s)' if n else 'no removed APIs found')
    return 1 if n else 0


if __name__ == '__main__':
    sys.exit(main())
