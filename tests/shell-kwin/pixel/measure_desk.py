"""measure_desk.py SHOT.png : bounding boxes of desktop items in the first column (x < 200),
found against the cover-scaled bloom-dark wallpaper.  Prints icon box / label glyph rows."""
import os, sys, numpy as np
from PIL import Image
W, H = 1920, 1080
wp = Image.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../assets') + '/generated/wallpapers/fenestra-bloom-dark.jpg').convert('RGB')
sc = max(W / wp.width, H / wp.height)
wp = wp.resize((round(wp.width * sc), round(wp.height * sc)), Image.LANCZOS)
ox, oy = (wp.width - W) // 2, (wp.height - H) // 2
bg = np.asarray(wp).astype(int)[oy:oy + H, ox:ox + W]
a = np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype(int)
d = np.abs(a - bg).max(2)[:1000, :200] > int(sys.argv[2]) if len(sys.argv) > 2 else np.abs(a - bg).max(2)[:1000, :200] > 40
runs = []; s = None
for y in range(d.shape[0]):
    if d[y].any() and s is None: s = y
    if not d[y].any() and s is not None: runs.append((s, y - 1)); s = None
for r in runs:
    xs = np.where(d[r[0]:r[1] + 1].any(0))[0]
    print('rows %4d-%4d (h %3d)  cols %3d-%3d (w %3d, centre %.1f)' % (r[0], r[1], r[1]-r[0]+1, xs.min(), xs.max(), xs.max()-xs.min()+1, (xs.min()+xs.max())/2))
