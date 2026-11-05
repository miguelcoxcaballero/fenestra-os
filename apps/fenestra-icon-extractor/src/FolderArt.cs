using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;

namespace FenestraIconExtractor;

/// <summary>Builds the "folder with content" picture from Explorer's own folder art.</summary>
static class FolderArt
{
    /// <summary>Paints a white sheet between the back and front flaps of the folder.
    /// Returns null if the artwork doesn't look like the Windows 11 yellow folder.</summary>
    public static Bitmap? AddSheet(Bitmap src)
    {
        int w = src.Width, h = src.Height;
        var px = Read(src);
        static bool Opaque(int c) => (uint)c >> 24 > 200;
        static bool Front(int c)
        {
            int r = (c >> 16) & 255, g = (c >> 8) & 255, b = c & 255;
            return Opaque(c) && r > 235 && b > 85 && Math.Min(r, Math.Min(g, b)) <= 200;
        }
        // Per column: first opaque row (top of the back flap) and first front-flap row.
        var top = new int[w];
        var front = new int[w];
        int left = -1, right = -1;
        for (int x = 0; x < w; x++)
        {
            top[x] = front[x] = -1;
            for (int y = 0; y < h; y++)
            {
                int c = px[y * w + x];
                if (top[x] < 0 && Opaque(c)) top[x] = y;
                if (top[x] >= 0 && Front(c)) { front[x] = y; break; }
            }
            if (top[x] >= 0) { if (left < 0) left = x; right = x; }
        }
        if (left < 0 || right - left < w / 2) return null;
        int fw = right - left;
        int sl = left + (int)(0.10 * fw), sr = right - (int)(0.10 * fw);
        if (front[sl] < 0 || front[sr] < 0 || front[(sl + sr) / 2] < 0) return null;
        // Back-flap top on the right half (the left half has the tab).
        var rightTops = Enumerable.Range((left + right) / 2, right - (left + right) / 2).Where(x => top[x] >= 0).Select(x => top[x]).OrderBy(t => t).ToList();
        int backTop = rightTops[rightTops.Count / 2];
        int st = Math.Max(1, backTop - (int)(0.075 * h));
        int sb = Math.Max(front[sl], front[sr]) + (int)(0.04 * h);
        if (sb - st < h / 20) return null;

        using var sheet = new Bitmap(w, h, PixelFormat.Format32bppArgb);
        using (var g = Graphics.FromImage(sheet))
        {
            g.SmoothingMode = SmoothingMode.AntiAlias;
            float s = h / 256f;
            var rect = new RectangleF(sl, st, sr - sl, sb - st);
            using var path = Theme.Round(rect, 9 * s);
            using var fill = new LinearGradientBrush(new PointF(0, st), new PointF(0, st + 48 * s),
                Color.FromArgb(253, 253, 254), Color.FromArgb(244, 245, 246)) { WrapMode = WrapMode.TileFlipX };
            g.FillPath(fill, path);
            using var pen = new Pen(Color.FromArgb(205, 207, 210), Math.Max(1f, 2 * s));
            g.DrawPath(pen, path);
        }
        var sp = Read(sheet);
        var outPx = (int[])px.Clone();
        for (int x = 0; x < w; x++)
        {
            int limit = front[x] >= 0 ? front[x] : (top[x] >= 0 ? h : 0);
            for (int y = 0; y < limit; y++)
            {
                int i = y * w + x, s2 = sp[i];
                uint a = (uint)s2 >> 24;
                if (a == 0) continue;
                outPx[i] = Over(s2, outPx[i]);
            }
        }
        var result = new Bitmap(w, h, PixelFormat.Format32bppArgb);
        Write(result, outPx);
        return result;
    }

    static int Over(int fg, int bg)
    {
        float fa = ((uint)fg >> 24) / 255f, ba = ((uint)bg >> 24) / 255f;
        float oa = fa + ba * (1 - fa);
        if (oa <= 0) return 0;
        int Ch(int sh) => (int)Math.Round((((fg >> sh) & 255) * fa + ((bg >> sh) & 255) * ba * (1 - fa)) / oa);
        return ((int)Math.Round(oa * 255) << 24) | (Ch(16) << 16) | (Ch(8) << 8) | Ch(0);
    }

    static int[] Read(Bitmap b)
    {
        var px = new int[b.Width * b.Height];
        var d = b.LockBits(new Rectangle(0, 0, b.Width, b.Height), ImageLockMode.ReadOnly, PixelFormat.Format32bppArgb);
        try { for (int y = 0; y < b.Height; y++) Marshal.Copy(d.Scan0 + y * d.Stride, px, y * b.Width, b.Width); }
        finally { b.UnlockBits(d); }
        return px;
    }

    static void Write(Bitmap b, int[] px)
    {
        var d = b.LockBits(new Rectangle(0, 0, b.Width, b.Height), ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
        try { for (int y = 0; y < b.Height; y++) Marshal.Copy(px, y * b.Width, d.Scan0 + y * d.Stride, b.Width); }
        finally { b.UnlockBits(d); }
    }
}
