"""Independent numpy model of the WinUI acrylic recipe (for checking src/core/acrylic.cpp).
acrylic_ref.py WALLPAPER dark|light OUT.png  -> 1920x48 strip (noise omitted: compared in mean)"""
import sys, numpy as np
from PIL import Image
wp, scheme, out = sys.argv[1:4]
W, H, S = 1920, 1080, 48
tint = np.array([0x20]*3 if scheme == 'dark' else [0xf3]*3) / 255.
aT, aL = (0.5, 0.96) if scheme == 'dark' else (0.0, 0.90)
im = Image.open(wp).convert('RGB')
sc = max(W / im.width, H / im.height)
im = im.resize((round(im.width * sc), round(im.height * sc)), Image.LANCZOS)
ox, oy = (im.width - W) // 2, (im.height - H) // 2
a = np.asarray(im).astype(float)[oy:oy + H, ox:ox + W] / 255.
sig = 30; r = 90
x = np.arange(-r, r + 1); k = np.exp(-x**2 / (2 * sig**2)); k /= k.sum()
band = a[H - S - r:H]
pad = np.concatenate([band, np.repeat(band[-1:], r, 0)], 0)          # clamp below the screen
v = sum(k[i] * pad[i:i + S] for i in range(2 * r + 1))                # rows H-S..H-1
p2 = np.concatenate([np.repeat(v[:, :1], r, 1), v, np.repeat(v[:, -1:], r, 1)], 1)
b = sum(k[i] * p2[:, i:i + W] for i in range(2 * r + 1))
lum = lambda c: 0.3 * c[..., 0] + 0.59 * c[..., 1] + 0.11 * c[..., 2]
def clip(c):
    l = lum(c)[..., None]; n = c.min(-1, keepdims=True); m = c.max(-1, keepdims=True)
    c = np.where(n < 0, l + (c - l) * l / np.where(l - n == 0, 1, l - n), c)
    m = c.max(-1, keepdims=True)
    return np.where(m > 1, l + (c - l) * (1 - l) / np.where(m - l == 0, 1, m - l), c)
setlum = lambda c, l: clip(c + (l - lum(c))[..., None])
s1 = b + (setlum(b, np.full(b.shape[:2], lum(tint))) - b) * aL
s2 = s1 + (setlum(np.broadcast_to(tint, s1.shape).copy(), lum(s1)) - s1) * aT
Image.fromarray(np.clip(np.round(s2 * 255), 0, 255).astype(np.uint8)).save(out)
print('mean', (s2 * 255).reshape(-1, 3).mean(0).round(2), 'min', (s2*255).reshape(-1,3).min(0).round(1), 'max', (s2*255).reshape(-1,3).max(0).round(1))
