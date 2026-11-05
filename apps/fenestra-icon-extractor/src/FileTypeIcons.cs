using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.InteropServices;

namespace FenestraIconExtractor;

/// <summary>
/// The icon File Explorer shows for each file type, exactly as the shell resolves it on this PC
/// (the default app's document icon: Photos for .png, Edge for .pdf, Notepad for .txt…).
/// Read through the shell image lists (SHGetFileInfo + SHGetImageList), so no files are needed.
/// Kept free of other project types so it can also be loaded with PowerShell's Add-Type.
/// </summary>
public static class FileTypeIcons
{
    /// <summary>extension -> freedesktop icon names (mime type with '/' -> '-') it stands for.</summary>
    public static readonly (string Ext, string[] Names)[] Map =
    {
        (".txt", new[] { "text-plain", "text-x-generic" }),
        (".log", new[] { "text-x-log" }),
        (".md", new[] { "text-markdown", "text-x-markdown" }),
        (".ini", new[] { "text-x-ini", "text-x-dbus-service", "application-x-desktop" }),
        (".csv", new[] { "text-csv", "text-x-csv" }),
        (".rtf", new[] { "application-rtf", "text-rtf" }),
        (".png", new[] { "image-png", "image-x-generic" }),
        (".jpg", new[] { "image-jpeg" }),
        (".gif", new[] { "image-gif" }),
        (".bmp", new[] { "image-bmp", "image-x-bmp" }),
        (".webp", new[] { "image-webp" }),
        (".tif", new[] { "image-tiff" }),
        (".heic", new[] { "image-heif", "image-heic" }),
        (".avif", new[] { "image-avif" }),
        (".ico", new[] { "image-vnd.microsoft.icon", "image-x-ico" }),
        (".svg", new[] { "image-svg+xml", "image-svg+xml-compressed" }),
        (".pdf", new[] { "application-pdf" }),
        (".html", new[] { "text-html", "application-xhtml+xml" }),
        (".xml", new[] { "application-xml", "text-xml" }),
        (".json", new[] { "application-json" }),
        (".js", new[] { "application-javascript", "text-javascript" }),
        (".css", new[] { "text-css" }),
        (".py", new[] { "text-x-python", "text-x-python3" }),
        (".ps1", new[] { "text-x-script", "application-x-shellscript", "text-x-sh" }),
        (".bat", new[] { "application-x-bat", "application-x-msdos-program" }),
        (".c", new[] { "text-x-csrc", "text-x-chdr", "text-x-c++src", "text-x-c++hdr", "text-x-java", "text-x-csharp", "text-x-makefile", "text-x-patch" }),
        (".docx", new[] { "application-vnd.openxmlformats-officedocument.wordprocessingml.document", "application-msword", "application-vnd.oasis.opendocument.text", "x-office-document" }),
        (".xlsx", new[] { "application-vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application-vnd.ms-excel", "application-vnd.oasis.opendocument.spreadsheet", "x-office-spreadsheet" }),
        (".pptx", new[] { "application-vnd.openxmlformats-officedocument.presentationml.presentation", "application-vnd.ms-powerpoint", "application-vnd.oasis.opendocument.presentation", "x-office-presentation" }),
        (".zip", new[] { "application-zip", "application-x-zip", "application-x-zip-compressed" }),
        (".7z", new[] { "application-x-7z-compressed" }),
        (".rar", new[] { "application-vnd.rar", "application-x-rar" }),
        (".tar", new[] { "application-x-tar", "application-x-compressed-tar", "application-gzip", "application-x-xz", "application-x-xz-compressed-tar", "application-x-bzip", "application-zstd", "package-x-generic" }),
        (".mp3", new[] { "audio-mpeg", "audio-x-generic" }),
        (".wav", new[] { "audio-x-wav", "audio-wav" }),
        (".flac", new[] { "audio-flac", "audio-x-flac" }),
        (".ogg", new[] { "audio-ogg", "audio-x-vorbis+ogg", "audio-x-opus+ogg" }),
        (".m4a", new[] { "audio-mp4", "audio-x-m4a", "audio-aac" }),
        (".mp4", new[] { "video-mp4", "video-x-generic" }),
        (".mkv", new[] { "video-x-matroska" }),
        (".webm", new[] { "video-webm" }),
        (".avi", new[] { "video-x-msvideo" }),
        (".mov", new[] { "video-quicktime" }),
        (".exe", new[] { "application-x-ms-dos-executable", "application-x-msdownload", "application-x-executable", "application-x-sharedlib" }),
        (".msi", new[] { "application-x-msi", "application-x-ms-installer", "application-x-rpm", "application-vnd.debian.binary-package", "application-vnd.flatpak.ref" }),
        (".iso", new[] { "application-x-cd-image", "application-x-iso9660-image", "application-x-raw-disk-image" }),
        (".ttf", new[] { "font-ttf", "font-otf", "font-woff", "font-woff2", "font-x-generic", "application-x-font-ttf" }),
        (".lnk", new[] { "application-x-ms-shortcut" }),
        (".eml", new[] { "message-rfc822" }),
        (".ics", new[] { "text-calendar" }),
        (".vcf", new[] { "text-vcard", "text-x-vcard" }),
        (".epub", new[] { "application-epub+zip" }),
        (".torrent", new[] { "application-x-bittorrent" }),
        (".fenestra-unknown-type", new[] { "unknown", "application-octet-stream", "application-x-generic" }),
    };

    // SHIL_*: image list per size, in the order of the sizes exported.
    public static readonly (int Size, int List)[] Lists = { (256, 4), (48, 2), (32, 0), (16, 1) };

    /// <summary>PNG of the Explorer icon for <paramref name="ext"/> at <paramref name="size"/> px, or null.</summary>
    public static byte[]? Png(string ext, int size)
    {
        int list = -1;
        foreach (var (s, l) in Lists) if (s == size) list = l;
        if (list < 0) return null;
        var info = new SHFILEINFO();
        var r = SHGetFileInfoW("file" + ext, 0x80 /* FILE_ATTRIBUTE_NORMAL */, ref info, (uint)Marshal.SizeOf<SHFILEINFO>(),
            0x10 /* USEFILEATTRIBUTES */ | 0x4000 /* SYSICONINDEX */);
        if (r == IntPtr.Zero) return null;
        var iid = new Guid("46EB5926-582E-4017-9FDF-E8998DAA0950");
        if (SHGetImageList(list, ref iid, out var il) != 0 || il == null) return null;
        IntPtr hicon = IntPtr.Zero;
        try
        {
            if (il.GetIcon(info.iIcon, 0x1 /* ILD_TRANSPARENT */, ref hicon) != 0 || hicon == IntPtr.Zero)
                return null;
            using var bmp = ToArgb(hicon);
            if (bmp == null) return null;
            // Types with no 256 px art come back as a 48 px icon in the jumbo list's corner:
            // Explorer scales those up, so do the same.
            using var final = size == 256 && Extent(bmp) <= 48 ? ScaleUp(ext) : null;
            using var ms = new MemoryStream();
            (final ?? bmp).Save(ms, ImageFormat.Png);
            return ms.ToArray();
        }
        finally
        {
            if (hicon != IntPtr.Zero) DestroyIcon(hicon);
            Marshal.ReleaseComObject(il);
        }
    }

    static Bitmap? ScaleUp(string ext)
    {
        var png = Png(ext, 48);
        if (png == null) return null;
        using var src = new Bitmap(new MemoryStream(png));
        var dst = new Bitmap(256, 256, PixelFormat.Format32bppArgb);
        using var g = Graphics.FromImage(dst);
        g.InterpolationMode = System.Drawing.Drawing2D.InterpolationMode.HighQualityBicubic;
        g.PixelOffsetMode = System.Drawing.Drawing2D.PixelOffsetMode.HighQuality;
        g.DrawImage(src, 0, 0, 256, 256);
        return dst;
    }

    /// <summary>Largest x/y with a visible pixel (+1).</summary>
    static int Extent(Bitmap b)
    {
        int max = 0;
        for (int y = 0; y < b.Height; y++)
            for (int x = 0; x < b.Width; x++)
                if (b.GetPixel(x, y).A > 8) max = Math.Max(max, Math.Max(x, y) + 1);
        return max;
    }

    /// <summary>HICON -> 32-bit ARGB bitmap keeping the alpha channel (Icon.ToBitmap can drop it).</summary>
    static Bitmap? ToArgb(IntPtr hicon)
    {
        if (!GetIconInfo(hicon, out var ii)) return null;
        try
        {
            using var color = Image.FromHbitmap(ii.hbmColor);
            int w = color.Width, h = color.Height;
            var bm = new BITMAP();
            GetObject(ii.hbmColor, Marshal.SizeOf<BITMAP>(), ref bm);
            var bits = new byte[w * h * 4];
            var bi = new BITMAPINFOHEADER { biSize = 40, biWidth = w, biHeight = -h, biPlanes = 1, biBitCount = 32 };
            var dc = GetDC(IntPtr.Zero);
            try { GetDIBits(dc, ii.hbmColor, 0, (uint)h, bits, ref bi, 0); }
            finally { ReleaseDC(IntPtr.Zero, dc); }
            bool hasAlpha = false;
            for (int i = 3; i < bits.Length; i += 4) if (bits[i] != 0) { hasAlpha = true; break; }
            if (!hasAlpha)
            {
                using var ico = Icon.FromHandle(hicon);
                return ico.ToBitmap();
            }
            var outBmp = new Bitmap(w, h, PixelFormat.Format32bppArgb);
            var data = outBmp.LockBits(new Rectangle(0, 0, w, h), ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
            Marshal.Copy(bits, 0, data.Scan0, bits.Length);
            outBmp.UnlockBits(data);
            return outBmp;
        }
        finally
        {
            if (ii.hbmColor != IntPtr.Zero) DeleteObject(ii.hbmColor);
            if (ii.hbmMask != IntPtr.Zero) DeleteObject(ii.hbmMask);
        }
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct SHFILEINFO
    {
        public IntPtr hIcon; public int iIcon; public uint dwAttributes;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string szDisplayName;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 80)] public string szTypeName;
    }
    [StructLayout(LayoutKind.Sequential)] struct ICONINFO { public bool fIcon; public int xHotspot, yHotspot; public IntPtr hbmMask, hbmColor; }
    [StructLayout(LayoutKind.Sequential)] struct BITMAP { public int bmType, bmWidth, bmHeight, bmWidthBytes; public ushort bmPlanes, bmBitsPixel; public IntPtr bmBits; }
    [StructLayout(LayoutKind.Sequential)]
    struct BITMAPINFOHEADER
    {
        public uint biSize; public int biWidth, biHeight; public ushort biPlanes, biBitCount;
        public uint biCompression, biSizeImage; public int biXPelsPerMeter, biYPelsPerMeter; public uint biClrUsed, biClrImportant;
    }

    [ComImport, Guid("46EB5926-582E-4017-9FDF-E8998DAA0950"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IImageList
    {
        [PreserveSig] int Add(IntPtr a, IntPtr b, ref int c);
        [PreserveSig] int ReplaceIcon(int a, IntPtr b, ref int c);
        [PreserveSig] int SetOverlayImage(int a, int b);
        [PreserveSig] int Replace(int a, IntPtr b, IntPtr c);
        [PreserveSig] int AddMasked(IntPtr a, int b, ref int c);
        [PreserveSig] int Draw(IntPtr a);
        [PreserveSig] int Remove(int a);
        [PreserveSig] int GetIcon(int i, int flags, ref IntPtr picon);
    }

    [DllImport("shell32.dll", CharSet = CharSet.Unicode)] static extern IntPtr SHGetFileInfoW(string path, uint attr, ref SHFILEINFO info, uint size, uint flags);
    [DllImport("shell32.dll", EntryPoint = "#727")] static extern int SHGetImageList(int list, ref Guid riid, out IImageList ppv);
    [DllImport("user32.dll")] static extern bool DestroyIcon(IntPtr h);
    [DllImport("user32.dll")] static extern bool GetIconInfo(IntPtr h, out ICONINFO info);
    [DllImport("user32.dll")] static extern IntPtr GetDC(IntPtr h);
    [DllImport("user32.dll")] static extern int ReleaseDC(IntPtr h, IntPtr dc);
    [DllImport("gdi32.dll")] static extern bool DeleteObject(IntPtr h);
    [DllImport("gdi32.dll")] static extern int GetObject(IntPtr h, int size, ref BITMAP bm);
    [DllImport("gdi32.dll")] static extern int GetDIBits(IntPtr dc, IntPtr bmp, uint start, uint lines, byte[] bits, ref BITMAPINFOHEADER bi, uint usage);
}
