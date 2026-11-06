#!/usr/bin/env python3
"""Capture a dialog's states on the Windows reference VM: hover, pressed, focus, menus.

    dialogcap.py PREFIX SPEC.json

SPEC: {"hover": {"name": [x, y], ...}, "press": {...}, "menus": {"name": [x, y], ...},
       "tabs": N, "clicks": {"name": [x, y], ...}}
Screens go to ~/fenestra-ref/raw/dialogs/PREFIX-<state>-<name>.png with a .json sidecar
recording the pointer position and what was done (never into the repo).
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'vm'))
import qmp  # noqa: E402
import winpass  # noqa: E402
from PIL import Image  # noqa: E402

D = os.path.expanduser('~/fenestra-ref/raw/dialogs')


def shot(v, name, **meta):
    os.makedirs(D, exist_ok=True)
    png = os.path.join(D, name + '.png')
    qmp.cmd(v.f, 'screendump', filename=png + '.ppm')
    Image.open(png + '.ppm').save(png)
    os.unlink(png + '.ppm')
    json.dump(meta, open(png[:-4] + '.json', 'w'), ensure_ascii=False)
    print(name, flush=True)


def btn(v, down, button='left'):
    qmp.cmd(v.f, 'input-send-event', events=[{'type': 'btn', 'data': {'down': down, 'button': button}}])


def main():
    prefix, spec = sys.argv[1], json.load(open(sys.argv[2]))
    v = winpass.VM(1.0)
    S = time.sleep
    v.move(1900, 20); S(0.6)
    shot(v, f'{prefix}-normal', note='sin ratón encima')
    for n, (x, y) in spec.get('hover', {}).items():
        v.move(x, y); S(0.9)
        shot(v, f'{prefix}-hover-{n}', pointer=[x, y], note=f'ratón encima de {n}')
    v.move(1900, 20); S(0.4)
    for n, (x, y) in spec.get('press', {}).items():
        v.move(x, y); S(0.5); btn(v, True); S(0.5)
        shot(v, f'{prefix}-pressed-{n}', pointer=[x, y], note=f'botón pulsado (sin soltar) en {n}')
        v.move(1900, 20); S(0.3); btn(v, False); S(0.6)   # release off the control: no action
    for i in range(spec.get('tabs', 0)):
        v.key('tab'); S(0.5)
        shot(v, f'{prefix}-focus-{i + 1:02d}', note=f'{i + 1} pulsaciones de Tab desde el estado inicial')
    for n, (x, y) in spec.get('menus', {}).items():
        v.click(x, y); S(1.2)
        mx, my = spec.get('menu_hover', {}).get(n, [None, None])
        if mx:
            v.move(mx, my); S(0.6)
        shot(v, f'{prefix}-menu-{n}', pointer=[x, y], note=f'clic en {n}: menú desplegado')
        v.key('esc'); S(0.8); v.move(1900, 20); S(0.3)
    for n, (x, y) in spec.get('clicks', {}).items():
        v.click(x, y); S(1.5); v.move(1900, 20); S(0.4)
        shot(v, f'{prefix}-click-{n}', pointer=[x, y], note=f'tras clic en {n}')


if __name__ == '__main__':
    main()
