#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# cmp_popup.py ours.png ref.png x0 y0 x1 y1 out.png [scale [dx dy]]: ours moved by (dx, dy) logical px
# Mean abs diff and share of pixels off by > 24 levels inside the box; writes ref|ours|diff.
import sys
import numpy as np
from PIL import Image
o = Image.open(sys.argv[1]).convert('RGB'); r = Image.open(sys.argv[2]).convert('RGB')
x0, y0, x1, y1 = map(int, sys.argv[3:7]); s = float(sys.argv[8]) if len(sys.argv) > 8 else 1
dx, dy = (int(sys.argv[9]), int(sys.argv[10])) if len(sys.argv) > 10 else (0, 0)
if s != 1:  # ours at scale s, ref at 100 %: bring the ref box up to ours
    rb = r.crop((x0, y0, x1, y1)).resize((round((x1 - x0) * s), round((y1 - y0) * s)), Image.LANCZOS)
    ob = o.crop((round((x0 + dx) * s), round((y0 + dy) * s), round((x0 + dx) * s) + rb.width, round((y0 + dy) * s) + rb.height))
else:
    rb = r.crop((x0, y0, x1, y1)); ob = o.crop((x0 + dx, y0 + dy, x1 + dx, y1 + dy))
a = np.asarray(ob).astype(int); b = np.asarray(rb).astype(int)
d = np.abs(a - b).max(axis=2)
print(f"mean {d.mean():.2f}  >24: {100 * (d > 24).mean():.1f}%  size {ob.size}")
w = Image.new('RGB', (ob.width * 3, ob.height))
w.paste(rb, (0, 0)); w.paste(ob, (ob.width, 0)); w.paste(Image.fromarray(np.clip(d * 3, 0, 255).astype('uint8')).convert('RGB'), (ob.width * 2, 0))
w.save(sys.argv[7])
