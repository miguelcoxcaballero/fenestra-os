using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;

namespace FenestraIconExtractor;

/// <summary>One image inside an icon group (RT_ICON resource).</summary>
sealed record IconImage(int Width, int Height, int BitCount, byte[] Data)
{
    public bool IsPng => Data.Length > 8 && Data[0] == 0x89 && Data[1] == 0x50 && Data[2] == 0x4E && Data[3] == 0x47;
}

/// <summary>An RT_GROUP_ICON resource with all its images.</summary>
sealed class IconGroup
{
    public required object Id { get; init; }
    public required List<IconImage> Images { get; init; }

    /// <summary>Rebuilds a standalone .ico file (byte-identical images).</summary>
    public byte[] ToIco()
    {
        using var ms = new MemoryStream();
        using var w = new BinaryWriter(ms);
        w.Write((ushort)0); w.Write((ushort)1); w.Write((ushort)Images.Count);
        int offset = 6 + 16 * Images.Count;
        foreach (var im in Images)
        {
            w.Write((byte)(im.Width >= 256 ? 0 : im.Width));
            w.Write((byte)(im.Height >= 256 ? 0 : im.Height));
            w.Write((byte)0); w.Write((byte)0);
            w.Write((ushort)1); w.Write((ushort)im.BitCount);
            w.Write(im.Data.Length); w.Write(offset);
            offset += im.Data.Length;
        }
        foreach (var im in Images) w.Write(im.Data);
        w.Flush();
        return ms.ToArray();
    }

    /// <summary>Renders the group at <paramref name="size"/> px, using the exact image when
    /// present and otherwise high-quality resampling of the nearest larger one.</summary>
    public Bitmap Render(int size)
    {
        if (Images.Count == 0) throw new InvalidOperationException("empty icon group");
        foreach (var im in Images.Where(i => i.Width == size).OrderByDescending(i => i.IsPng ? 64 : i.BitCount))
        {
            try
            {
                var bmp = IconCodec.Decode(im);
                if (bmp.Width == size && bmp.Height == size) return bmp;
                bmp.Dispose();
            }
            catch (Exception) { /* try the next candidate */ }
        }
        var src = Images.Where(i => i.Width >= size).OrderBy(i => i.Width).ThenByDescending(i => i.IsPng ? 64 : i.BitCount).FirstOrDefault()
                  ?? Images.OrderByDescending(i => i.Width).ThenByDescending(i => i.BitCount).First();
        using var big = IconCodec.Decode(src);
        return IconCodec.Scale(big, size);
    }

    public int LargestSize => Images.Count == 0 ? 0 : Images.Max(i => i.Width);
}

/// <summary>A PE file (.dll, .exe or .mun) opened as a resource-only data file. Never executed.</summary>
sealed class ResourceModule : IDisposable
{
    const uint LOAD_LIBRARY_AS_DATAFILE = 0x00000002;
    const uint LOAD_LIBRARY_AS_IMAGE_RESOURCE = 0x00000020;
    static readonly IntPtr RT_ICON = 3;
    static readonly IntPtr RT_GROUP_ICON = 14;

    IntPtr _h;
    public string Path { get; }

    ResourceModule(IntPtr h, string path) { _h = h; Path = path; }

    /// <summary>Opens the first candidate file that exists and contains icon groups.</summary>
    public static ResourceModule? Open(params string?[] candidates)
    {
        foreach (var c in candidates)
        {
            if (string.IsNullOrEmpty(c) || !File.Exists(c)) continue;
            var h = LoadLibraryExW(c, IntPtr.Zero, LOAD_LIBRARY_AS_DATAFILE | LOAD_LIBRARY_AS_IMAGE_RESOURCE);
            if (h == IntPtr.Zero) h = LoadLibraryExW(c, IntPtr.Zero, LOAD_LIBRARY_AS_DATAFILE);
            if (h == IntPtr.Zero) continue;
            var m = new ResourceModule(h, c);
            if (m.GroupIds().Count > 0) return m;
            m.Dispose();
        }
        return null;
    }

    public List<object> GroupIds()
    {
        var list = new List<object>();
        EnumResNameProc cb = (_, _, name, _) =>
        {
            list.Add(((long)name >> 16) == 0 ? (object)(int)(long)name : Marshal.PtrToStringUni(name) ?? "");
            return true;
        };
        EnumResourceNamesW(_h, RT_GROUP_ICON, cb, IntPtr.Zero);
        GC.KeepAlive(cb);
        return list;
    }

    byte[]? Resource(object name, IntPtr type)
    {
        IntPtr r = name is int i ? FindResourceW(_h, (IntPtr)i, type) : FindResourceStr(_h, (string)name, type);
        if (r == IntPtr.Zero) return null;
        uint size = SizeofResource(_h, r);
        IntPtr g = LoadResource(_h, r);
        IntPtr p = g == IntPtr.Zero ? IntPtr.Zero : LockResource(g);
        if (p == IntPtr.Zero || size == 0) return null;
        var data = new byte[size];
        Marshal.Copy(p, data, 0, (int)size);
        return data;
    }

    /// <summary>The group Windows itself uses as the file's icon (the first enumerated one).</summary>
    public IconGroup? FirstGroup()
    {
        var ids = GroupIds();
        return ids.Count == 0 ? null : Group(ids[0]);
    }

    public IconGroup? Group(object id)
    {
        var dir = Resource(id, RT_GROUP_ICON);
        if (dir == null || dir.Length < 6) return null;
        int count = BitConverter.ToUInt16(dir, 4);
        var images = new List<IconImage>();
        for (int k = 0; k < count && 6 + 14 * k + 14 <= dir.Length; k++)
        {
            int o = 6 + 14 * k;
            int w = dir[o] == 0 ? 256 : dir[o];
            int h = dir[o + 1] == 0 ? 256 : dir[o + 1];
            int bits = BitConverter.ToUInt16(dir, o + 6);
            int nId = BitConverter.ToUInt16(dir, o + 12);
            var data = Resource(nId, RT_ICON);
            if (data == null) continue;
            var img = new IconImage(w, h, bits, data);
            if (img.IsPng && data.Length >= 24)
            {
                // Real dimensions from the PNG IHDR (the directory byte saturates at 256).
                int pw = (data[16] << 24) | (data[17] << 16) | (data[18] << 8) | data[19];
                int ph = (data[20] << 24) | (data[21] << 16) | (data[22] << 8) | data[23];
                img = img with { Width = pw, Height = ph, BitCount = bits == 0 ? 32 : bits };
            }
            images.Add(img);
        }
        return images.Count == 0 ? null : new IconGroup { Id = id, Images = images };
    }

    public void Dispose()
    {
        if (_h != IntPtr.Zero) { FreeLibrary(_h); _h = IntPtr.Zero; }
    }

    delegate bool EnumResNameProc(IntPtr hModule, IntPtr type, IntPtr name, IntPtr param);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern IntPtr LoadLibraryExW(string path, IntPtr hFile, uint flags);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool FreeLibrary(IntPtr h);
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern bool EnumResourceNamesW(IntPtr h, IntPtr type, EnumResNameProc cb, IntPtr param);
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern IntPtr FindResourceW(IntPtr h, IntPtr name, IntPtr type);
    [DllImport("kernel32.dll", EntryPoint = "FindResourceW", SetLastError = true, CharSet = CharSet.Unicode)]
    static extern IntPtr FindResourceStr(IntPtr h, string name, IntPtr type);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern IntPtr LoadResource(IntPtr h, IntPtr res);
    [DllImport("kernel32.dll")]
    static extern IntPtr LockResource(IntPtr g);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern uint SizeofResource(IntPtr h, IntPtr res);
}

/// <summary>Decodes icon images (PNG or DIB with AND mask) to 32-bit ARGB, keeping alpha.</summary>
static class IconCodec
{
    public static Bitmap Decode(IconImage im)
    {
        if (im.IsPng)
        {
            using var ms = new MemoryStream(im.Data);
            using var src = new Bitmap(ms);
            return src.Clone(new Rectangle(0, 0, src.Width, src.Height), PixelFormat.Format32bppArgb);
        }
        return DecodeDib(im.Data);
    }

    static Bitmap DecodeDib(byte[] d)
    {
        int hdr = BitConverter.ToInt32(d, 0);
        int w = BitConverter.ToInt32(d, 4);
        int h = Math.Abs(BitConverter.ToInt32(d, 8)) / 2;
        int bpp = BitConverter.ToUInt16(d, 14);
        int clrUsed = hdr >= 36 ? BitConverter.ToInt32(d, 32) : 0;
        int pal = bpp <= 8 ? (clrUsed > 0 ? clrUsed : 1 << bpp) : 0;
        int pxOff = hdr + pal * 4;
        int stride = ((w * bpp + 31) / 32) * 4;
        int mStride = ((w + 31) / 32) * 4;
        int mOff = pxOff + stride * h;
        bool hasMask = mOff + mStride * h <= d.Length;
        var px = new int[w * h];
        var mask = new bool[w * h];
        bool anyAlpha = false;
        for (int y = 0; y < h; y++)
        {
            int row = pxOff + (h - 1 - y) * stride;
            int mrow = mOff + (h - 1 - y) * mStride;
            for (int x = 0; x < w; x++)
            {
                int a = 255, r, g, b;
                switch (bpp)
                {
                    case 32:
                        b = d[row + 4 * x]; g = d[row + 4 * x + 1]; r = d[row + 4 * x + 2]; a = d[row + 4 * x + 3];
                        if (a != 0) anyAlpha = true;
                        break;
                    case 24:
                        b = d[row + 3 * x]; g = d[row + 3 * x + 1]; r = d[row + 3 * x + 2];
                        break;
                    case 16:
                        {
                            int v = d[row + 2 * x] | (d[row + 2 * x + 1] << 8);
                            r = ((v >> 10) & 31) * 255 / 31; g = ((v >> 5) & 31) * 255 / 31; b = (v & 31) * 255 / 31;
                            break;
                        }
                    default:
                        {
                            int idx = bpp switch
                            {
                                1 => (d[row + x / 8] >> (7 - x % 8)) & 1,
                                4 => (d[row + x / 2] >> (4 * (1 - x % 2))) & 15,
                                _ => d[row + x],
                            };
                            int p = hdr + 4 * Math.Min(idx, Math.Max(pal - 1, 0));
                            b = d[p]; g = d[p + 1]; r = d[p + 2];
                            break;
                        }
                }
                bool masked = hasMask && ((d[mrow + x / 8] >> (7 - x % 8)) & 1) == 1;
                if (bpp != 32 && masked) a = 0;
                mask[y * w + x] = masked;
                px[y * w + x] = (a << 24) | (r << 16) | (g << 8) | b;
            }
        }
        if (bpp == 32 && !anyAlpha)
        {
            // Old-style 32-bit icon without alpha: transparency comes from the AND mask.
            for (int i = 0; i < px.Length; i++)
                px[i] = (mask[i] ? 0 : unchecked((int)0xFF000000)) | (px[i] & 0xFFFFFF);
        }
        var bmp = new Bitmap(w, h, PixelFormat.Format32bppArgb);
        var bd = bmp.LockBits(new Rectangle(0, 0, w, h), ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
        try
        {
            for (int y = 0; y < h; y++) Marshal.Copy(px, y * w, bd.Scan0 + y * bd.Stride, w);
        }
        finally { bmp.UnlockBits(bd); }
        return bmp;
    }

    public static Bitmap Scale(Image src, int size)
    {
        var b = new Bitmap(size, size, PixelFormat.Format32bppArgb);
        using var g = Graphics.FromImage(b);
        g.CompositingMode = CompositingMode.SourceCopy;
        g.CompositingQuality = CompositingQuality.HighQuality;
        g.InterpolationMode = InterpolationMode.HighQualityBicubic;
        g.PixelOffsetMode = PixelOffsetMode.HighQuality;
        g.SmoothingMode = SmoothingMode.HighQuality;
        using var ia = new ImageAttributes();
        ia.SetWrapMode(WrapMode.TileFlipXY);
        g.DrawImage(src, new Rectangle(0, 0, size, size), 0, 0, src.Width, src.Height, GraphicsUnit.Pixel, ia);
        return b;
    }

    public static byte[] ToPng(Image bmp)
    {
        using var ms = new MemoryStream();
        bmp.Save(ms, ImageFormat.Png);
        return ms.ToArray();
    }
}
