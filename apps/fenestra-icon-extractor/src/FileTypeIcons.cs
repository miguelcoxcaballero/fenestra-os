using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.InteropServices;

namespace FenestraIconExtractor;

/// <summary>
/// The icons File Explorer shows for files, folders, drives and special places, exactly as the shell
/// resolves them on this PC (the default app's document icon: Photos for .png, Edge for .pdf, Notepad
/// for .txt…; the blank page for types no app handles). Read with the API Explorer itself uses,
/// IShellItemImageFactory (SIIGBF_ICONONLY), on empty sample files of each type in a temporary folder,
/// so every size (16…256 px) comes straight from the shell with its alpha channel, with no scaling of
/// ours. Stock icons (Recycle Bin empty/full, drive kinds) come from SHGetStockIconInfo + SHDefExtractIcon.
/// Kept free of other project types so it can also be loaded with PowerShell's Add-Type.
/// </summary>
public static class FileTypeIcons
{
    /// <summary>Pixel sizes exported (Explorer: details 16/20/24, list 32, medium 48, large 96, extra large 256).</summary>
    public static readonly int[] Sizes = { 16, 20, 24, 32, 48, 64, 96, 256 };

    /// <summary>Extensions exported (without the dot); the pack key is the extension itself.</summary>
    public static readonly string[] Extensions =
    {
        // text and documents
        "txt", "log", "md", "ini", "cfg", "conf", "inf", "csv", "tsv", "rtf", "pdf", "xps", "oxps", "epub",
        "doc", "docx", "dot", "dotx", "xls", "xlsx", "xlsm", "ppt", "pptx", "pps", "ppsx", "odt", "ods", "odp", "odg",
        "eml", "msg", "ics", "vcf", "one",
        // images
        "png", "jpg", "jpeg", "jfif", "gif", "bmp", "dib", "webp", "svg", "svgz", "ico", "cur", "tif", "tiff", "heic", "heif",
        "avif", "jxr", "wdp", "dng", "raw", "cr2", "nef", "arw", "psd", "xcf", "emf", "wmf",
        // audio
        "mp3", "wav", "flac", "ogg", "oga", "opus", "m4a", "aac", "wma", "mid", "midi", "aif", "aiff", "amr", "ac3",
        // video
        "mp4", "m4v", "mkv", "avi", "mov", "webm", "wmv", "mpg", "mpeg", "ts", "m2ts", "3gp", "flv", "ogv",
        // archives and disk images
        "zip", "7z", "rar", "tar", "gz", "tgz", "bz2", "xz", "zst", "cab", "iso", "img", "vhd", "vhdx", "wim", "dmg",
        // programs and installers
        "exe", "msi", "msix", "msixbundle", "appx", "appxbundle", "dll", "sys", "ocx", "cpl", "scr", "com", "jar", "apk",
        "deb", "rpm", "appimage", "flatpakref",
        // scripts and code
        "bat", "cmd", "ps1", "psm1", "vbs", "js", "mjs", "sh", "bash", "py", "pyw", "rb", "pl", "php", "lua",
        "json", "xml", "yaml", "yml", "toml", "html", "htm", "xhtml", "mht", "css", "scss", "sql", "reg",
        "c", "cpp", "cc", "cxx", "h", "hpp", "cs", "csproj", "sln", "vb", "java", "kt", "rs", "go", "swift", "dart",
        "r", "m", "asm", "diff", "patch", "makefile", "cmake", "qml", "ipynb",
        // fonts, shortcuts, certificates, misc
        "ttf", "otf", "ttc", "fon", "woff", "woff2", "lnk", "url", "website", "cer", "crt", "pem", "pfx", "p12", "key",
        "torrent", "db", "sqlite", "mdb", "accdb", "bak", "tmp", "dat", "bin", "nfo", "theme", "deskthemepack",
        "desktop", "service", "pdb", "obj", "o", "lib", "a", "so",
    };

    /// <summary>Unknown type (no app, no class): a made-up extension nobody registers.</summary>
    public const string UnknownExtension = "fenestra-unknown-type";

    /// <summary>Folders and places Explorer shows: key -> how to get it.</summary>
    public enum SpecialKind { EmptyFolder, FullFolder, Path, ParsingName, Stock }

    public sealed record Special(string Key, SpecialKind Kind, string? Arg, int Stock = -1, string? Note = null);

    public static IEnumerable<Special> Specials()
    {
        string profile = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
        string Known(Environment.SpecialFolder f) => Environment.GetFolderPath(f);
        yield return new("folder", SpecialKind.EmptyFolder, null, Note: "empty folder");
        yield return new("folder-full", SpecialKind.FullFolder, null, Note: "folder with a document inside (Explorer's content preview)");
        yield return new("folder-open", SpecialKind.Stock, null, 4, "SIID_FOLDEROPEN");
        yield return new("user-desktop", SpecialKind.Path, Known(Environment.SpecialFolder.DesktopDirectory));
        yield return new("documents", SpecialKind.Path, Known(Environment.SpecialFolder.MyDocuments));
        yield return new("downloads", SpecialKind.ParsingName, "shell:Downloads");
        yield return new("music", SpecialKind.Path, Known(Environment.SpecialFolder.MyMusic));
        yield return new("pictures", SpecialKind.Path, Known(Environment.SpecialFolder.MyPictures));
        yield return new("videos", SpecialKind.Path, Known(Environment.SpecialFolder.MyVideos));
        yield return new("home", SpecialKind.Path, profile);
        yield return new("public", SpecialKind.ParsingName, "shell:Public");
        yield return new("templates", SpecialKind.Path, Known(Environment.SpecialFolder.Templates));
        yield return new("this-pc", SpecialKind.ParsingName, "::{20D04FE0-3AEA-1069-A2D8-08002B30309D}");
        yield return new("network", SpecialKind.ParsingName, "::{F02C1A0D-BE21-4350-88B0-7367FC96EF3C}");
        yield return new("home-quick-access", SpecialKind.ParsingName, "::{F874310E-B6B7-47DC-BC84-B9E6B38F5903}", Note: "Explorer's Home");
        yield return new("gallery", SpecialKind.ParsingName, "::{E88865EA-0E1C-4E20-9AA6-EDCD0212C87C}");
        yield return new("onedrive", SpecialKind.ParsingName, "::{018D5C66-4533-4307-9B53-224DE2ED1FE6}");
        yield return new("control-panel", SpecialKind.ParsingName, "::{26EE0668-A00A-44D7-9371-BEB064C98683}");
        yield return new("recycle-bin-empty", SpecialKind.Stock, null, 31, "SIID_RECYCLER");
        yield return new("recycle-bin-full", SpecialKind.Stock, null, 32, "SIID_RECYCLERFULL");
        yield return new("drive-system", SpecialKind.Path, Path.GetPathRoot(Environment.SystemDirectory) ?? @"C:\", Note: "the Windows drive");
        yield return new("drive-harddisk", SpecialKind.Stock, null, 8, "SIID_DRIVEFIXED");
        yield return new("drive-removable", SpecialKind.Stock, null, 7, "SIID_DRIVEREMOVE");
        yield return new("drive-network", SpecialKind.Stock, null, 9, "SIID_DRIVENET");
        yield return new("drive-network-offline", SpecialKind.Stock, null, 10, "SIID_DRIVENETDISABLED");
        yield return new("drive-optical", SpecialKind.Stock, null, 11, "SIID_DRIVECD");
        yield return new("drive-ram", SpecialKind.Stock, null, 12, "SIID_DRIVERAM");
        yield return new("computer", SpecialKind.Stock, null, 94, "SIID_DESKTOPPC");
        yield return new("computer-laptop", SpecialKind.Stock, null, 95, "SIID_MOBILEPC");
        yield return new("network-workgroup", SpecialKind.Stock, null, 17, "SIID_MYNETWORK");
        yield return new("server", SpecialKind.Stock, null, 15, "SIID_SERVER");
        yield return new("printer", SpecialKind.Stock, null, 16, "SIID_PRINTER");
        yield return new("application", SpecialKind.Stock, null, 2, "SIID_APPLICATION");
        yield return new("document", SpecialKind.Stock, null, 0, "SIID_DOCNOASSOC");
        yield return new("shield", SpecialKind.Stock, null, 77, "SIID_SHIELD");
        yield return new("shortcut-overlay", SpecialKind.Stock, null, 29, "SIID_LINK");
        yield return new("lock-overlay", SpecialKind.Stock, null, 47, "SIID_LOCK");
        yield return new("shared-overlay", SpecialKind.Stock, null, 28, "SIID_SHARE");
    }

    /// <summary>Creates the sample files and folders in <paramref name="dir"/> (empty files: Explorer
    /// shows the type icon for them, never a thumbnail of content).</summary>
    public static void PrepareSamples(string dir)
    {
        Directory.CreateDirectory(dir);
        foreach (var ext in Extensions)
        {
            var f = Path.Combine(dir, "sample." + ext);
            if (File.Exists(f)) continue;
            // A valid Internet shortcut so .url shows its class icon (an empty one is "broken").
            if (ext is "url" or "website") File.WriteAllText(f, "[InternetShortcut]\r\nURL=about:blank\r\n");
            else File.WriteAllBytes(f, Array.Empty<byte>());
        }
        File.WriteAllBytes(Path.Combine(dir, "sample." + UnknownExtension), Array.Empty<byte>());
        Directory.CreateDirectory(Path.Combine(dir, "empty-folder"));
        var full = Path.Combine(dir, "full-folder");
        Directory.CreateDirectory(full);
        File.WriteAllText(Path.Combine(full, "document.txt"), "Fenestra\r\n");
    }

    public static string SamplePath(string dir, string ext) => Path.Combine(dir, "sample." + ext);

    const int SIIGBF_RESIZETOFIT = 0x0, SIIGBF_BIGGERSIZEOK = 0x1, SIIGBF_ICONONLY = 0x4, SIIGBF_SCALEUP = 0x100;

    /// <summary>The icon Explorer draws for <paramref name="parsingName"/> (a path or a shell
    /// parsing name such as "::{CLSID}") at exactly <paramref name="size"/> px, or null.</summary>
    public static Bitmap? ShellItem(string parsingName, int size, bool allowThumbnail = false)
    {
        var iid = typeof(IShellItemImageFactory).GUID;
        if (SHCreateItemFromParsingName(parsingName, IntPtr.Zero, ref iid, out var obj) != 0 || obj is not IShellItemImageFactory f)
            return null;
        try
        {
            int flags = (allowThumbnail ? SIIGBF_RESIZETOFIT : SIIGBF_ICONONLY) | SIIGBF_SCALEUP;
            if (f.GetImage(new SIZE { cx = size, cy = size }, flags, out var hbmp) != 0 || hbmp == IntPtr.Zero) return null;
            try { return FromHBitmap(hbmp); }
            finally { DeleteObject(hbmp); }
        }
        finally { Marshal.ReleaseComObject(f); }
    }

    /// <summary>A stock shell icon (SHGetStockIconInfo location) at exactly <paramref name="size"/> px.</summary>
    public static Bitmap? Stock(int siid, int size, out string? location)
    {
        location = null;
        var info = new SHSTOCKICONINFO { cbSize = (uint)Marshal.SizeOf<SHSTOCKICONINFO>() };
        if (SHGetStockIconInfo(siid, 0 /* SHGSI_ICONLOCATION */, ref info) != 0 || string.IsNullOrEmpty(info.szPath)) return null;
        location = $"{info.szPath},{info.iIcon}";
        if (SHDefExtractIconW(info.szPath, info.iIcon, 0, out var large, out var small, (uint)(size | (size << 16))) != 0)
            return null;
        try { return large == IntPtr.Zero ? null : FromHIcon(large); }
        finally
        {
            if (large != IntPtr.Zero) DestroyIcon(large);
            if (small != IntPtr.Zero) DestroyIcon(small);
        }
    }

    /// <summary>Explorer's "Type" column text and the registered MIME type of an extension.</summary>
    public static (string? TypeName, string? ContentType, string? Perceived, string? ProgId) Describe(string ext)
    {
        var info = new SHFILEINFO();
        string? typeName = null;
        if (SHGetFileInfoW("file." + ext, 0x80, ref info, (uint)Marshal.SizeOf<SHFILEINFO>(), 0x10 /* USEFILEATTRIBUTES */ | 0x400 /* TYPENAME */) != IntPtr.Zero)
            typeName = string.IsNullOrWhiteSpace(info.szTypeName) ? null : info.szTypeName;
        string? ct = null, perceived = null, progid = null;
        try
        {
            using var k = Microsoft.Win32.Registry.ClassesRoot.OpenSubKey("." + ext);
            ct = k?.GetValue("Content Type") as string;
            perceived = k?.GetValue("PerceivedType") as string;
            progid = k?.GetValue(null) as string;
        }
        catch (Exception) { /* unreadable class key: leave empty */ }
        return (typeName, ct, perceived, progid);
    }

    public static byte[] ToPng(Bitmap b)
    {
        using var ms = new MemoryStream();
        b.Save(ms, ImageFormat.Png);
        return ms.ToArray();
    }

    /// <summary>32-bit DIB from the shell -> straight-alpha ARGB bitmap. The image factory hands out
    /// premultiplied pixels; they are un-premultiplied when no channel exceeds alpha.</summary>
    static Bitmap? FromHBitmap(IntPtr hbmp)
    {
        var bm = new BITMAP();
        if (GetObject(hbmp, Marshal.SizeOf<BITMAP>(), ref bm) == 0) return null;
        int w = bm.bmWidth, h = Math.Abs(bm.bmHeight);
        var bits = new byte[w * h * 4];
        var bi = new BITMAPINFOHEADER { biSize = 40, biWidth = w, biHeight = -h, biPlanes = 1, biBitCount = 32 };
        var dc = GetDC(IntPtr.Zero);
        try { if (GetDIBits(dc, hbmp, 0, (uint)h, bits, ref bi, 0) == 0) return null; }
        finally { ReleaseDC(IntPtr.Zero, dc); }
        bool anyAlpha = false, premultiplied = true;
        for (int i = 0; i < bits.Length; i += 4)
        {
            byte a = bits[i + 3];
            if (a != 0) anyAlpha = true;
            if (bits[i] > a || bits[i + 1] > a || bits[i + 2] > a) premultiplied = false;
        }
        if (!anyAlpha)
            for (int i = 3; i < bits.Length; i += 4) bits[i] = 255;   // old 24-bit art: opaque
        else if (premultiplied)
            for (int i = 0; i < bits.Length; i += 4)
            {
                int a = bits[i + 3];
                if (a == 0 || a == 255) continue;
                for (int c = 0; c < 3; c++) bits[i + c] = (byte)Math.Min(255, (bits[i + c] * 255 + a / 2) / a);
            }
        var outBmp = new Bitmap(w, h, PixelFormat.Format32bppArgb);
        var data = outBmp.LockBits(new Rectangle(0, 0, w, h), ImageLockMode.WriteOnly, PixelFormat.Format32bppArgb);
        Marshal.Copy(bits, 0, data.Scan0, bits.Length);
        outBmp.UnlockBits(data);
        return outBmp;
    }

    /// <summary>HICON -> 32-bit ARGB bitmap keeping the alpha channel (Icon.ToBitmap can drop it).</summary>
    static Bitmap? FromHIcon(IntPtr hicon)
    {
        if (!GetIconInfo(hicon, out var ii)) return null;
        try
        {
            var bm = new BITMAP();
            GetObject(ii.hbmColor, Marshal.SizeOf<BITMAP>(), ref bm);
            int w = bm.bmWidth, h = Math.Abs(bm.bmHeight);
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

    [StructLayout(LayoutKind.Sequential)] struct SIZE { public int cx, cy; }

    [ComImport, Guid("bcc18b79-ba16-442f-80c4-8a59c30c463b"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IShellItemImageFactory
    {
        [PreserveSig] int GetImage(SIZE size, int flags, out IntPtr phbm);
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct SHFILEINFO
    {
        public IntPtr hIcon; public int iIcon; public uint dwAttributes;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string szDisplayName;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 80)] public string szTypeName;
    }
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct SHSTOCKICONINFO
    {
        public uint cbSize; public IntPtr hIcon; public int iSysImageIndex; public int iIcon;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string szPath;
    }
    [StructLayout(LayoutKind.Sequential)] struct ICONINFO { public bool fIcon; public int xHotspot, yHotspot; public IntPtr hbmMask, hbmColor; }
    [StructLayout(LayoutKind.Sequential)] struct BITMAP { public int bmType, bmWidth, bmHeight, bmWidthBytes; public ushort bmPlanes, bmBitsPixel; public IntPtr bmBits; }
    [StructLayout(LayoutKind.Sequential)]
    struct BITMAPINFOHEADER
    {
        public uint biSize; public int biWidth, biHeight; public ushort biPlanes, biBitCount;
        public uint biCompression, biSizeImage; public int biXPelsPerMeter, biYPelsPerMeter; public uint biClrUsed, biClrImportant;
    }

    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    static extern int SHCreateItemFromParsingName(string path, IntPtr pbc, ref Guid riid, [MarshalAs(UnmanagedType.Interface)] out object ppv);
    [DllImport("shell32.dll", CharSet = CharSet.Unicode)] static extern IntPtr SHGetFileInfoW(string path, uint attr, ref SHFILEINFO info, uint size, uint flags);
    [DllImport("shell32.dll")] static extern int SHGetStockIconInfo(int siid, uint flags, ref SHSTOCKICONINFO info);
    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    static extern int SHDefExtractIconW(string iconFile, int index, uint flags, out IntPtr large, out IntPtr small, uint size);
    [DllImport("user32.dll")] static extern bool DestroyIcon(IntPtr h);
    [DllImport("user32.dll")] static extern bool GetIconInfo(IntPtr h, out ICONINFO info);
    [DllImport("user32.dll")] static extern IntPtr GetDC(IntPtr h);
    [DllImport("user32.dll")] static extern int ReleaseDC(IntPtr h, IntPtr dc);
    [DllImport("gdi32.dll")] static extern bool DeleteObject(IntPtr h);
    [DllImport("gdi32.dll")] static extern int GetObject(IntPtr h, int size, ref BITMAP bm);
    [DllImport("gdi32.dll")] static extern int GetDIBits(IntPtr dc, IntPtr bmp, uint start, uint lines, byte[] bits, ref BITMAPINFOHEADER bi, uint usage);
}
