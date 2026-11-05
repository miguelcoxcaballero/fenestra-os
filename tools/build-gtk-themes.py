#!/usr/bin/env python3
"""Build Fenestra-Dark and Fenestra-Light GTK 3/4 themes from Fluent-gtk-theme.

    git clone https://github.com/vinceliuice/Fluent-gtk-theme /tmp/fluent
    git -C /tmp/fluent checkout 7a49a464b0188c340101c52965c18190b1c694cf
    pip install libsass
    tools/build-gtk-themes.py --fluent /tmp/fluent [--out desktop/themes]

Fluent is compiled with the 'round' window tweak, the Fenestra structural
patch (tools/gtk-theme/gtk{3,4}.patch: square Windows caption buttons,
Windows-style entry borders) is applied, and every accent-derived colour is
replaced by a GTK named colour (@accent_bg_color, shade()/mix()/alpha() of
it). The theme defines Windows' default sage accent; the live accent comes
from ~/.config/gtk-{3,4}.0/fenestra-accent.css, which the fenestra-tray
extension rewrites (user CSS has higher priority, so its @define-color wins).
"""
import argparse, colorsys, pathlib, re, shutil, subprocess, sys, tempfile

REPO = pathlib.Path(__file__).resolve().parent.parent
PATCHES = REPO / 'tools' / 'gtk-theme'
A = '#647C64'      # sentinel 1 (also the default accent)
B = '#3C5A8C'      # sentinel 2, only used to find accent-derived tokens
TOKEN = re.compile(r'#[0-9a-fA-F]{6}\b|rgba?\([^)]*\)')


def hex_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def lum(rgb):
    c = [v / 255 for v in rgb]
    c = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def light_fill(base):
    """Accent used on light surfaces (Windows 'Dark1'): darker, >= 4.5:1 on white."""
    r, g, b = (v / 255 for v in hex_rgb(base))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = min(l, l - 0.08)
    while l > 0.05:
        rgb = tuple(round(v * 255) for v in colorsys.hls_to_rgb(h, l, s))
        if 1.05 / (lum(rgb) + 0.05) >= 4.5:
            break
        l -= 0.01
    return '#%02x%02x%02x' % rgb


def expr(tok_a, tok_b):
    """GTK colour expression for an accent-derived token."""
    if tok_a.upper() == A:
        return '@accent_bg_color'
    m = re.fullmatch(r'rgba\((\d+), (\d+), (\d+), ([\d.]+)\)', tok_a)
    if m and tuple(map(int, m.groups()[:3])) == hex_rgb(A):
        return f'alpha(@accent_bg_color, {m.group(4)})'
    if m:  # translucent mix of the accent with black
        rgb, alpha = tuple(map(int, m.groups()[:3])), m.group(4)
        f = 1 - rgb[0] / hex_rgb(A)[0]
        return f'alpha(mix(@accent_bg_color, black, {f:.2f}), {alpha})'
    rgb, base = hex_rgb(tok_a), hex_rgb(A)
    if sum(rgb) < sum(base):  # darken()
        f = sum(rgb) / sum(base)
        return f'shade(@accent_bg_color, {f:.2f})'
    f = sum(c - b for c, b in zip(rgb, base)) / sum(255 - b for b in base)
    return f'mix(@accent_bg_color, white, {f:.2f})'


def tokenise(text_a, text_b):
    out = []
    for la, lb in zip(text_a.splitlines(), text_b.splitlines()):
        if la != lb and not la.lstrip().startswith('@define-color accent_'):
            ta, tb = TOKEN.findall(la), TOKEN.findall(lb)
            for x, y in zip(ta, tb):
                if x != y:
                    la = la.replace(x, expr(x, y), 1)
        out.append(la)
    return '\n'.join(out) + '\n'


# Neutral colours used by the user CSS (desktop/skel/.config/gtk-3.0/gtk.css) so
# that menus and caption buttons follow the mode when GTK reloads the theme.
NEUTRAL = {
    'fenestra_menu_bg': ('rgba(44,44,44,0.96)', 'rgba(249,249,249,0.96)'),
    'fenestra_menu_fg': ('#f4f4f4', '#1a1a1a'),
    'fenestra_menu_border': ('rgba(255,255,255,0.10)', 'rgba(0,0,0,0.08)'),
    'fenestra_menu_hover': ('rgba(255,255,255,0.065)', 'rgba(0,0,0,0.04)'),
    'fenestra_separator': ('rgba(255,255,255,0.07)', 'rgba(0,0,0,0.08)'),
    'fenestra_caption_fg': ('#eeeeee', '#1a1a1a'),
    'fenestra_caption_hover': ('rgba(255,255,255,0.08)', 'rgba(0,0,0,0.05)'),
    'fenestra_caption_hover_strong': ('rgba(255,255,255,0.10)', 'rgba(0,0,0,0.06)'),
    'fenestra_caption_active': ('rgba(255,255,255,0.16)', 'rgba(0,0,0,0.09)'),
}


def footer(variant):
    dark = variant == 'Dark'
    fill = A if dark else light_fill(A)
    neutral = ''.join(f'@define-color {k} {v[0 if dark else 1]};\n' for k, v in NEUTRAL.items())
    return f'''
/* Fenestra: Windows font; default accent (live accent: fenestra-tray's wrapper theme). */
@define-color accent_bg_color {fill};
@define-color accent_fg_color {'#ffffff'};
@define-color accent_color {'#a8bea7' if dark else fill};
{neutral}window {{ font-family: "Segoe UI Variable", "Segoe UI"; }}
entry:focus, entry:focus-within {{ background-image: none; border-color: @accent_bg_color; }}
popover > contents, menu {{ background-color: {'rgba(44,44,44,0.92)' if dark else 'rgba(249,249,249,0.96)'}; }}
'''


def statements(css):
    """Split a stylesheet into top-level statements (comments dropped)."""
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    out, depth, start = [], 0, 0
    for i, ch in enumerate(css):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                out.append(css[start:i + 1].strip()); start = i + 1
        elif ch == ';' and depth == 0:
            out.append(css[start:i + 1].strip()); start = i + 1
    return [s for s in out if s]


def auto_css(dark, light):
    """Both variants behind prefers-color-scheme, for user CSS (libadwaita apps
    such as Nautilus ignore gtk-theme but honour the media query, GTK >= 4.20)."""
    def split(css):
        st = statements(css)
        return ([s for s in st if s.startswith('@keyframes')],
                [s for s in st if not s.startswith('@')])
    kd, rd = split(dark.replace('@accent_bg_color', '@fenestra_accent_dark'))
    _, rl = split(light.replace('@accent_bg_color', '@fenestra_accent_light'))
    body = lambda rules: '\n'.join('  ' + r.replace('\n', '\n  ') for r in rules)
    return ('/* Fenestra-Dark + Fenestra-Light for user CSS (generated by tools/build-gtk-themes.py).\n'
            '   Accent: @fenestra_accent_dark/@fenestra_accent_light from ~/.config/gtk-4.0/fenestra-accent.css. */\n'
            f'@define-color theme_text_color white;\n@define-color fenestra_accent_dark {A};\n@define-color fenestra_accent_light {light_fill(A)};\n' + '\n'.join(kd) + '\n'
            f'@media (prefers-color-scheme: dark) {{\n{body(rd)}\n}}\n'
            f'@media (prefers-color-scheme: light) {{\n{body(rl)}\n}}\n')


def compile_all(fluent, primary, work):
    src = work / f'fluent-{primary[1:]}'
    shutil.copytree(fluent / 'src', src / 'src', ignore=shutil.ignore_patterns('*.png', 'assets*'))
    colors = src / 'src/_sass/_colors.scss'
    text = colors.read_text()
    text = re.sub(r"(\$theme == 'default'\) \{ @return )#[0-9A-Fa-f]{6}", rf'\g<1>{primary}', text)
    colors.write_text(text)
    tweaks = (src / 'src/_sass/_tweaks.scss').read_text().replace("$window: 'default'", "$window: 'round'")
    (src / 'src/_sass/_tweaks-temp.scss').write_text(tweaks)
    import sass
    res = {}
    for ver in ('3', '4'):
        for var in ('Dark', 'Light'):
            css = sass.compile(filename=str(src / f'src/gtk/{ver}.0/gtk-{var}.scss'), output_style='expanded')
            f = work / f'{primary[1:]}-{ver}-{var}.css'
            f.write_text(css)
            subprocess.run(['patch', '-s', '-F3', '--no-backup-if-mismatch', str(f), str(PATCHES / f'gtk{ver}.patch')], check=True)
            css = f.read_text()
            if var == 'Light':  # Fenestra's entry border images: light PNGs
                css = re.sub(r'(entry-[a-z-]+?)-dark(@2)?\.png', r'\1\2.png', css)
            res[ver, var] = css + footer(var)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fluent', required=True, type=pathlib.Path)
    ap.add_argument('--out', type=pathlib.Path, default=REPO / 'desktop/themes')
    args = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        work = pathlib.Path(tmp)
        a, b = compile_all(args.fluent, A, work), compile_all(args.fluent, B, work)
        assets = REPO / 'desktop/themes/Fenestra-Dark'
        for var in ('Dark', 'Light'):
            theme = args.out / f'Fenestra-{var}'
            for ver in ('3', '4'):
                d = theme / f'gtk-{ver}.0'
                d.mkdir(parents=True, exist_ok=True)
                if not (d / 'assets').exists():
                    shutil.copytree(assets / f'gtk-{ver}.0/assets', d / 'assets')
                css = tokenise(a[ver, var], b[ver, var])
                (d / 'gtk.css').write_text(css)
                (d / 'gtk-dark.css').write_text(tokenise(a[ver, 'Dark'], b[ver, 'Dark']))
            if var == 'Dark':  # user-CSS stylesheet with both variants
                (theme / 'gtk-4.0' / 'gtk-auto.css').write_text(
                    auto_css(tokenise(a['4', 'Dark'], b['4', 'Dark']), tokenise(a['4', 'Light'], b['4', 'Light'])))
            if not (theme / 'COPYING').exists():
                shutil.copy(assets / 'COPYING', theme / 'COPYING')
            if not (theme / 'index.theme').exists():
                (theme / 'index.theme').write_text(
                    f'[Desktop Entry]\nType=X-GNOME-Metatheme\nName=Fenestra-{var}\n'
                    f'[X-GNOME-Metatheme]\nGtkTheme=Fenestra-{var}\nIconTheme=Fenestra\n')
            print('wrote', theme)


if __name__ == '__main__':
    sys.exit(main())
