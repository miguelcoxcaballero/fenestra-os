#!/usr/bin/env python3
"""Run PowerShell in the reference VM through the hidden agent (agent.ps1 polls guestserve).

    guest.py 'Get-Process notepad'        prints the output; the agent runs as Usuario Demo
"""
import os
import sys
import time

G = os.path.expanduser('~/fenestra-ref/guest')


def run(code, timeout=60):
    i = str(time.time_ns())
    out = os.path.join(G, 'out', 'agent.txt')
    with open(os.path.join(G, 'cmd.ps1.tmp'), 'w', encoding='utf-8') as f:
        f.write(f'# {i}\n{code}\n')
    os.replace(os.path.join(G, 'cmd.ps1.tmp'), os.path.join(G, 'cmd.ps1'))
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            txt = open(out, encoding='utf-8-sig').read()
            if txt.splitlines()[0].strip() == f'# {i}':
                return '\n'.join(txt.splitlines()[1:])
        except (OSError, IndexError):
            pass
        time.sleep(0.3)
    raise TimeoutError('agent did not answer')


if __name__ == '__main__':
    print(run(sys.argv[1]))
