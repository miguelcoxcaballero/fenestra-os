#!/usr/bin/env python3
"""Tiny QMP client for the Fenestra VM tests (screenshots + input)."""
import json
import os
import socket
import sys
import tempfile
import time


def connect(path):
    s = socket.socket(socket.AF_UNIX)
    s.connect(path)
    f = s.makefile('rw')
    json.loads(f.readline())
    cmd(f, 'qmp_capabilities')
    return s, f


def cmd(f, _cmd, **args):
    f.write(json.dumps({'execute': _cmd, 'arguments': args} if args else {'execute': _cmd}) + '\n')
    f.flush()
    while True:
        r = json.loads(f.readline())
        if 'return' in r or 'error' in r:
            if 'error' in r:
                raise SystemExit(r['error'])
            return r['return']


KEYMAP = {' ': 'spc', '\n': 'ret', '.': 'dot', ',': 'comma', '-': 'minus', '/': 'slash', '@': ('shift', '2'),
          '_': ('shift', 'minus'), '!': ('shift', '1'), ':': ('shift', 'semicolon'), ';': 'semicolon', '\\': 'backslash',
          '"': ('shift', 'apostrophe'), "'": 'apostrophe', '=': 'equal', '(': ('shift', '9'), ')': ('shift', '0'), '[': 'bracket_left', ']': 'bracket_right', '{': ('shift', 'bracket_left'), '}': ('shift', 'bracket_right'), '$': ('shift', '4'), '|': ('shift', 'backslash'), '+': ('shift', 'equal'), '<': ('shift', 'comma'), '>': ('shift', 'dot'), '?': ('shift', 'slash'), '#': ('shift', '3'), '&': ('shift', '7'), '%': ('shift', '5')}


def keyseq(f, keys):
    for k in keys:
        parts = k.split('-') if len(k) > 1 and '-' in k and k != '-' else [k]
        cmd(f, 'send-key', keys=[{'type': 'qcode', 'data': p} for p in parts])
        time.sleep(0.08)


def main():
    sock, f = connect(sys.argv[1])
    op = sys.argv[2]
    if op == 'shot':
        out = sys.argv[3]
        tmp = tempfile.mktemp(suffix='.ppm', dir='/tmp')
        cmd(f, 'screendump', filename=tmp)
        from PIL import Image
        Image.open(tmp).save(out)
        os.unlink(tmp)
        print(out)
    elif op == 'key':
        keyseq(f, sys.argv[3:])
    elif op == 'type':
        for ch in sys.argv[3]:
            k = KEYMAP.get(ch)
            if k is None:
                k = ('shift', ch.lower()) if ch.isupper() else ch
            parts = list(k) if isinstance(k, tuple) else [k]
            cmd(f, 'send-key', keys=[{'type': 'qcode', 'data': p} for p in parts])
            time.sleep(0.05)
    elif op in ('click', 'move', 'rclick'):
        x, y, w, h = map(int, sys.argv[3:7])
        ax, ay = int(x * 32767 / (w - 1)), int(y * 32767 / (h - 1))
        cmd(f, 'input-send-event', events=[{'type': 'abs', 'data': {'axis': 'x', 'value': ax}},
                                           {'type': 'abs', 'data': {'axis': 'y', 'value': ay}}])
        if op in ('click', 'rclick'):
            time.sleep(0.1)
            for down in (True, False):
                cmd(f, 'input-send-event', events=[{'type': 'btn', 'data': {'down': down, 'button': 'left' if op == 'click' else 'right'}}])
                time.sleep(0.08)
    elif op == 'link':
        cmd(f, 'set_link', name='n0', up=sys.argv[3] == 'on')
    elif op == 'quit':
        cmd(f, 'quit')
    sock.close()


if __name__ == '__main__':
    main()
