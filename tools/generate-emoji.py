#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""tools/generate-emoji.py EMOJI-TEST.TXT > design/emoji.json

The emoji panel's list (Win+.), from Unicode's emoji-test.txt
(https://unicode.org/Public/emoji/<version>/emoji-test.txt): fully-qualified emoji in Unicode's
own order and groups, without the skin-tone and hair variants (the panel shows the base emoji).
Names in the user's language come from CLDR's annotations at run time (shell/src/services/emoji.cpp)."""
import json
import re
import sys

groups, cur = [], None
for line in open(sys.argv[1], encoding='utf-8'):
    m = re.match(r'# group: (.+)', line)
    if m:
        cur = {'group': m.group(1), 'items': []}
        if m.group(1) != 'Component':
            groups.append(cur)
        continue
    m = re.match(r'([0-9A-F ]+);\s*fully-qualified\s*#\s*(\S+)\s+E[\d.]+\s+(.+)', line)
    if not m or cur is None:
        continue
    cps = [int(c, 16) for c in m.group(1).split()]
    if any(0x1F3FB <= c <= 0x1F3FF or 0x1F9B0 <= c <= 0x1F9B3 for c in cps):
        continue
    cur['items'].append([m.group(2), m.group(3).strip()])
json.dump(groups, sys.stdout, ensure_ascii=False, separators=(',', ':'))
