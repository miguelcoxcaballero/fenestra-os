"""cmp_taskbar.py BENCH_TASKBAR.png REF.png [y0]: max/mean |diff| per channel over the empty
taskbar background (x 150-700 and 1200-1680, rows 1-47; row 0 = border compared separately)."""
import sys, numpy as np
from PIL import Image
b = np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype(int)
r = np.asarray(Image.open(sys.argv[2]).convert('RGB')).astype(int)
if r.shape[0] > 48: r = r[-48:]
cols = np.r_[150:700, 1200:1680]
d = np.abs(b[1:48][:, cols] - r[1:48][:, cols])
print('background: max %d mean %.2f  (bench mean %s, ref mean %s)' % (d.max(), d.mean(), b[1:48][:, cols].reshape(-1,3).mean(0).round(1), r[1:48][:, cols].reshape(-1,3).mean(0).round(1)))
db = np.abs(b[0, cols] - r[0, cols]); print('border row: max %d mean %.2f' % (db.max(), db.mean()))
