#!/usr/bin/env python3
"""Drive one capture pass on the Windows reference VM (theme/scale already applied with pass.ps1).

    winpass.py THEME PCT [--wall solid|bloom] [--only 06,07] [--dir DIR]

Coordinates were read on the 100 % pass and are scaled per pass around their anchor:
cb = centre-bottom (taskbar, Start, Search), rb = right-bottom (tray, flyouts), abs = as is.
Every capture goes through cap.py's naming and sidecar rules (files only in ~/fenestra-ref).
Panels that need a guest-side action (toasts, media) use helper scripts served by
guestserve.py from ~/fenestra-ref/guest.
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'vm'))
import qmp  # noqa: E402
from PIL import Image  # noqa: E402

W, H = 1920, 1080
SOCK = os.path.expanduser('~/VMs/win11-ref/qmp.sock')


class VM:
    def __init__(self, scale):
        self.s, self.f = qmp.connect(SOCK)
        self.k = scale

    def p(self, x, y, anchor='cb'):
        k = self.k
        if anchor == 'cb':
            return round(W / 2 + (x - W / 2) * k), round(H - (H - y) * k)
        if anchor == 'rb':
            return round(W - (W - x) * k), round(H - (H - y) * k)
        return x, y

    def move(self, x, y, anchor='abs'):
        x, y = self.p(x, y, anchor)
        qmp.cmd(self.f, 'input-send-event', events=[
            {'type': 'abs', 'data': {'axis': 'x', 'value': int(x * 32767 / (W - 1))}},
            {'type': 'abs', 'data': {'axis': 'y', 'value': int(y * 32767 / (H - 1))}}])
        return x, y

    def click(self, x, y, anchor='abs', button='left', settle=0.35):
        pt = self.move(x, y, anchor)
        time.sleep(settle)
        for down in (True, False):
            qmp.cmd(self.f, 'input-send-event', events=[{'type': 'btn', 'data': {'down': down, 'button': button}}])
            time.sleep(0.06)
        return pt

    def key(self, *combo):
        for c in combo:
            qmp.cmd(self.f, 'send-key', keys=[{'type': 'qcode', 'data': k} for k in c.split('-')])
            time.sleep(0.12)

    def hold(self, mod, *taps, then=None):
        """Hold MOD, tap keys, run THEN while still held, release."""
        ev = lambda k, d: {'type': 'key', 'data': {'down': d, 'key': {'type': 'qcode', 'data': k}}}
        qmp.cmd(self.f, 'input-send-event', events=[ev(mod, True)])
        time.sleep(0.1)
        for t in taps:
            qmp.cmd(self.f, 'input-send-event', events=[ev(t, True)])
            time.sleep(0.05)
            qmp.cmd(self.f, 'input-send-event', events=[ev(t, False)])
            time.sleep(0.15)
        if then:
            then()
        qmp.cmd(self.f, 'input-send-event', events=[ev(mod, False)])

    def type(self, text):
        for ch in text:
            k = qmp.KEYMAP.get(ch)
            if k is None:
                k = ('shift', ch.lower()) if ch.isupper() else ch
            parts = list(k) if isinstance(k, tuple) else [k]
            qmp.cmd(self.f, 'send-key', keys=[{'type': 'qcode', 'data': q} for q in parts])
            time.sleep(0.04)

    def run(self, script):
        """Run a helper from ~/fenestra-ref/guest through the hidden agent (agent.ps1)."""
        import guest
        return guest.run(f"iex ([Text.Encoding]::UTF8.GetString((iwr http://10.0.2.2:8765/{script} -UseBasicParsing).Content))")

    def park(self):
        self.move(W - 20, 20)

    def clean(self):
        self.key('esc')
        time.sleep(0.3)
        self.key('esc')
        self.park()
        time.sleep(0.8)


class Pass:
    def __init__(self, a):
        self.theme, self.pct, self.wall = a.theme, a.pct, a.wall
        self.vm = VM(a.pct / 100)
        self.dir = a.dir or os.path.expanduser(f'~/fenestra-ref/raw/{a.wall}')
        os.makedirs(self.dir, exist_ok=True)
        self.bg = '#1f1f1f' if a.wall == 'solid' else None

    def panel_origin(self):
        """Top-left of the panel centred above the taskbar (Start can be clipped at 150 %)."""
        tmp = os.path.join(self.dir, '.probe.ppm')
        qmp.cmd(self.vm.f, 'screendump', filename=tmp)
        im = Image.open(tmp).convert('RGB')
        os.unlink(tmp)
        px = im.load()
        bg = px[W // 2, 2]
        y0 = next(y for y in range(H) if max(abs(px[W // 2, y][i] - bg[i]) for i in range(3)) > 6)
        x0 = next(x for x in range(W) if max(abs(px[x, y0 + 40][i] - bg[i]) for i in range(3)) > 6)
        return x0, y0

    def shot(self, num, name, note='', seed=None, **meta):
        fn = f'{self.theme}-{self.pct}-{num}-{name}'
        png = os.path.join(self.dir, fn + '.png')
        tmp = png + '.ppm'
        qmp.cmd(self.vm.f, 'screendump', filename=tmp)
        Image.open(tmp).save(png)
        os.unlink(tmp)
        m = {'wallpaper': self.wall, 'bg': self.bg or '#1f1f1f', 'note': note}
        if seed:
            m['seed'] = list(seed)
        m.update(meta)
        json.dump(m, open(png[:-4] + '.json', 'w'), ensure_ascii=False)
        print(fn, flush=True)


def steps(P):
    v = P.vm
    S = time.sleep

    def s01():
        v.clean(); v.move(960, 500); S(1); v.park(); S(0.5)
        P.shot('01', 'taskbar', 'escritorio vacío')

    def s06():
        v.clean(); v.key('meta_l'); S(1.5)
        P.shot('06', 'start', 'tecla Windows')

    def s07():
        v.clean(); v.key('meta_l'); S(1.5)
        x0, y0 = P.panel_origin()
        v.click(x0 + round(542 * v.k), y0 + round(116 * v.k)); S(1.5); v.park(); S(0.5)
        P.shot('07', 'start-all', 'Inicio > Todos (vista de lista; 26100 no tiene otras vistas)')
        # Build 26100 has a single (list) view in All: no view selector to switch.
        v.clean()

    def s08():
        v.clean(); v.key('meta_l'); S(1.5)
        v.click(1207, 987, 'cb'); S(1.2); v.park(); S(0.4)
        P.shot('08', 'power-menu', 'Inicio > botón de inicio/apagado')

    def s09():
        v.clean(); v.key('meta_l'); S(1.5)
        v.click(765, 987, 'cb'); S(1.5); v.park(); S(0.4)
        P.shot('09', 'account-menu', 'Inicio > Usuario Demo')

    def s10():
        v.clean(); v.click(895, 1056, 'cb'); S(2.5); v.park(); S(0.5)
        P.shot('10', 'search', 'clic en el cuadro Buscar de la barra')

    def s11():
        v.type('playa'); S(3)
        P.shot('11', 'search-query', 'Búsqueda «playa»')
        v.clean()

    def s12():
        v.clean(); v.key('meta_l-a'); S(2); v.park(); S(0.3)
        P.shot('12', 'quick', 'Win+A')

    def s13():
        # The VM has no Wi-Fi adapter: Quick Settings has no Wi-Fi tile, so no subpage.
        pass

    def s15():
        v.clean(); v.key('meta_l-n'); S(2); v.park(); S(0.3)
        P.shot('15', 'notifications', 'Win+N (centro + calendario desplegado)')

    def s16():
        # calendar collapsed: the chevron at the calendar header's right
        v.clean(); v.key('meta_l-n'); S(2)
        P.shot('16', 'calendar', 'Win+N, calendario desplegado')
        v.click(1878, 591, 'rb'); S(1.2); v.park(); S(0.4)
        P.shot('16', 'calendar-collapsed', 'Win+N, calendario plegado (clic en v)')
        v.click(1878, 946, 'rb'); S(0.8)   # unfold it again for later passes
        v.clean()

    def s18():
        v.clean(); v.key('volumeup'); S(0.8)
        P.shot('18', 'osd-volume', 'tecla de volumen +')
        v.key('volumedown'); S(2.5)

    def s20():
        v.clean(); v.key('ctrl-alt-delete'); S(3)
        P.shot('20', 'secure-attention', 'Ctrl+Alt+Supr')
        v.key('esc'); S(3)

    def s21():
        v.clean(); v.key('meta_l-r'); S(1.2); v.type('cmd'); v.key('ctrl-shift-ret'); S(4)
        P.shot('21', 'uac', 'Win+R cmd, Ctrl+Mayús+Intro')
        v.key('esc'); S(3)

    def s22():
        v.clean(); v.click(1757, 1056, 'rb'); S(1.2); v.park(); S(0.3)
        P.shot('22', 'tray-overflow', 'clic en ^ de la bandeja')

    def s23():
        v.clean(); v.click(960, 400, 'cb', button='right'); S(1.2)
        P.shot('23', 'desktop-menu', 'clic derecho en el escritorio')
        v.clean()

    def apps():
        v.clean(); v.run('apps.ps1'); S(3)
        v.click(round(700 * v.k), round(215 * v.k)); S(0.8); v.park(); S(1)   # Notepad's title bar: focus it

    def s02():
        x, y = v.move(1117, 1056, 'cb'); S(0.25)
        P.shot('02', 'taskbar-hover', 'ratón sobre Bloc de notas abierto (0,25 s)', seed=[x - int(14 * v.k), y])

    def s03():
        v.move(1117, 1056, 'cb'); S(2)
        P.shot('03', 'preview', 'ratón 2 s sobre Bloc de notas abierto')
        v.park(); S(1)

    def s04():
        v.click(1400, 1056, 'cb', button='right'); S(1.2)
        P.shot('04', 'taskbar-menu', 'clic derecho en zona vacía de la barra')
        v.clean()

    def s05():
        v.click(1117, 1056, 'cb', button='right'); S(1.5)
        P.shot('05', 'app-menu', 'clic derecho en Bloc de notas')
        v.clean()

    def s24():
        # Notepad was placed at 300,200 1000x600 by apps.ps1 (logical px, scaled)
        k = v.k
        top = round(200 * k)
        right = round(300 * k + 1000 * k)
        P.shot('24', 'caption-buttons', 'Bloc de notas activo, sin hover',
               seed=[right - round(23 * k), top + round(8 * k)])
        x, y = v.move(right - round(23 * k), top + round(15 * k)); S(0.8)
        P.shot('24', 'caption-close-hover', 'hover en Cerrar', seed=[x, y - round(8 * k)])
        x, y = v.move(right - round(115 * k), top + round(15 * k)); S(0.4)
        P.shot('24', 'caption-min-hover', 'hover en Minimizar', seed=[x, y - round(8 * k)])
        x, y = v.move(right - round(69 * k), top + round(15 * k)); S(2.2)
        P.shot('27', 'snap-layouts', 'hover 2 s en Maximizar')
        v.park(); S(1)

    def s25():
        v.hold('alt', 'tab', then=lambda: (S(1.5), P.shot('25', 'alt-tab', 'Alt mantenido + Tab')))
        S(1)

    def s26():
        v.key('meta_l-tab'); S(2.5)
        P.shot('26', 'task-view', 'Win+Tab')
        v.key('esc'); S(1.5)

    def close_apps():
        v.run('closeapps.ps1'); S(2)

    def s17():
        v.clean(); v.run('toast.ps1'); S(2.5)
        P.shot('17', 'toast', 'banner de notificación de demo')
        S(8)

    def s15b():
        v.clean(); v.key('meta_l-n'); S(2); v.park(); S(0.3)
        P.shot('15', 'notifications-2', 'Win+N con 2 notificaciones de demo')
        v.clean()

    def s14():
        v.clean(); v.run('media.ps1'); S(8); v.key('meta_l-a'); S(2); v.park(); S(0.3)
        P.shot('14', 'quick-media', 'Win+A con demo-tono.wav sonando')
        v.clean(); v.run('closeapps.ps1'); S(4)

    def s28():
        v.clean(); v.key('meta_l-l'); S(4)
        P.shot('28', 'lock', 'Win+L')
        v.key('spc'); S(3)
        P.shot('29', 'login', 'pantalla de inicio de sesión tras Espacio')
        v.key('ret'); S(8)

    return [('01', s01), ('06', s06), ('07', s07), ('08', s08), ('09', s09), ('10', s10), ('11', s11),
            ('12', s12), ('13', s13), ('15', s15), ('16', s16), ('18', s18), ('20', s20), ('21', s21),
            ('22', s22), ('23', s23), ('apps', apps), ('02', s02), ('03', s03), ('04', s04), ('05', s05),
            ('24', s24), ('25', s25), ('26', s26), ('close', close_apps), ('17', s17), ('15b', s15b),
            ('14', s14), ('28', s28)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('theme', choices=['dark', 'light'])
    ap.add_argument('pct', type=int)
    ap.add_argument('--wall', default='solid')
    ap.add_argument('--only')
    ap.add_argument('--dir')
    a = ap.parse_args()
    P = Pass(a)
    only = set(a.only.split(',')) if a.only else None
    for name, fn in steps(P):
        if only and name not in only:
            continue
        fn()
    P.vm.clean()


if __name__ == '__main__':
    main()
