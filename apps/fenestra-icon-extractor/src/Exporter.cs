using System.Drawing;
using System.IO.Compression;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace FenestraIconExtractor;

public sealed class ExportOptions
{
    public bool Fonts { get; set; } = true;
    public bool Cursors { get; set; } = true;
    public bool SystemIcons { get; set; } = true;
    public bool FolderIcons { get; set; } = true;
    public bool Taskbar { get; set; } = true;
    public bool AppIcons { get; set; } = true;
    public bool Battery { get; set; } = true;
    public bool Wallpapers { get; set; }
    public string Destination { get; set; } = DefaultDestination;

    public static string DefaultDestination =>
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "Fenestra-Windows-icons.zip");
}

public readonly record struct ExportProgress(int Percent, string? Message);

public sealed record ExportResult(int Files, long Bytes, int Missing, string Path);

/// <summary>
/// Builds a Fenestra icon pack (docs/ICON-PACK-FORMAT.md). Windows is only read; the only
/// file written is the destination .zip (via a temporary ".partial" file next to it).
/// </summary>
public sealed class Exporter
{
    public const string Version = "1.1.0";
    public const string IconTheme = "Fenestra-Windows";
    public const string CursorTheme = "Fenestra-Windows-Cursors";
    static readonly int[] Sizes = { 256, 48, 32, 16 };

    static readonly string[] FontFiles =
    {
        "segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf", "segoeuiz.ttf", "segoeuil.ttf", "segoeuisl.ttf",
        "seguisb.ttf", "seguisbi.ttf", "seguili.ttf", "seguibl.ttf", "seguibli.ttf",
        "SegUIVar.ttf", "SegoeIcons.ttf", "consola.ttf", "consolab.ttf", "consolai.ttf", "consolaz.ttf",
    };

    // Windows defaults for HKCU\Control Panel\Cursors roles left empty (= "Windows Default").
    static readonly Dictionary<string, string> DefaultCursors = new(StringComparer.OrdinalIgnoreCase)
    {
        ["Arrow"] = "aero_arrow.cur", ["Help"] = "aero_helpsel.cur", ["AppStarting"] = "aero_working.ani",
        ["Wait"] = "aero_busy.ani", ["NWPen"] = "aero_pen.cur", ["No"] = "aero_unavail.cur",
        ["SizeNS"] = "aero_ns.cur", ["SizeWE"] = "aero_ew.cur", ["SizeNWSE"] = "aero_nwse.cur",
        ["SizeNESW"] = "aero_nesw.cur", ["SizeAll"] = "aero_move.cur", ["UpArrow"] = "aero_up.cur",
        ["Hand"] = "aero_link.cur", ["Pin"] = "aero_pin.cur", ["Person"] = "aero_person.cur",
        ["IBeam"] = "beam_r.cur", ["Crosshair"] = "cross_r.cur",
    };

    enum Src { Imageres, Shell32, Edge }

    /// <summary>freedesktop icon name -> (context dir, source module, icon group id).</summary>
    static readonly (string Name, string Context, Src Module, object Id)[] ThemeIcons =
    {
        ("folder", "places", Src.Imageres, 3),
        ("inode-directory", "places", Src.Imageres, 3),
        ("folder-open", "places", Src.Imageres, 4),
        ("folder-documents", "places", Src.Imageres, 112),
        ("folder-pictures", "places", Src.Imageres, 113),
        ("folder-music", "places", Src.Imageres, 108),
        ("folder-videos", "places", Src.Imageres, 189),
        ("folder-download", "places", Src.Imageres, 184),
        ("user-desktop", "places", Src.Imageres, 183),
        ("folder-publicshare", "places", Src.Imageres, 178),
        ("folder-remote", "places", Src.Imageres, 73),
        ("folder-recent", "places", Src.Imageres, 117),
        ("user-trash", "places", Src.Imageres, 55),
        ("user-trash-full", "places", Src.Imageres, 54),
        ("network-workgroup", "places", Src.Imageres, 25),
        ("computer", "devices", Src.Imageres, 109),
        ("video-display", "devices", Src.Imageres, 109),
        ("drive-harddisk", "devices", Src.Imageres, 32),
        ("drive-harddisk-system", "devices", Src.Imageres, 36),
        ("drive-removable-media", "devices", Src.Imageres, 35),
        ("drive-optical", "devices", Src.Imageres, 30),
        ("media-optical", "devices", Src.Imageres, 61),
        ("media-flash", "devices", Src.Imageres, 60),
        ("printer", "devices", Src.Imageres, 51),
        ("camera-photo", "devices", Src.Imageres, 57),
        ("input-keyboard", "devices", Src.Imageres, 182),
        ("scanner", "devices", Src.Imageres, 95),
        ("phone", "devices", Src.Imageres, 47),
        ("text-x-generic", "mimetypes", Src.Imageres, 102),
        ("image-x-generic", "mimetypes", Src.Imageres, 70),
        ("audio-x-generic", "mimetypes", Src.Imageres, 131),
        ("video-x-generic", "mimetypes", Src.Imageres, 133),
        ("application-x-executable", "mimetypes", Src.Imageres, 15),
        ("application-x-generic", "mimetypes", Src.Imageres, 2),
        ("unknown", "mimetypes", Src.Imageres, 2),
        ("package-x-generic", "mimetypes", Src.Imageres, 174),
        ("application-zip", "mimetypes", Src.Imageres, 174),
        ("font-x-generic", "mimetypes", Src.Imageres, 124),
        ("x-office-document", "mimetypes", Src.Imageres, 90),
        ("text-x-script", "mimetypes", Src.Imageres, 67),
        ("application-pdf", "mimetypes", Src.Edge, "IDR_X007_PDF_DOC"),
        ("text-html", "mimetypes", Src.Edge, "IDR_X006_HTML_DOC"),
        ("system-search", "actions", Src.Shell32, 23),
        ("help-browser", "apps", Src.Shell32, 24),
    };

    readonly ExportOptions _o;
    readonly IProgress<ExportProgress> _progress;
    readonly string _win = WindowsInfo.WindowsDir;
    readonly HashSet<string> _written = new(StringComparer.OrdinalIgnoreCase);
    readonly HashSet<string> _themeDirs = new();
    readonly JsonObject _extra = new();
    ZipArchive _zip = null!;
    long _bytes;
    int _missing;

    public Exporter(ExportOptions options, IProgress<ExportProgress> progress)
    {
        _o = options;
        _progress = progress;
    }

    void Log(string msg) => _progress.Report(new ExportProgress(-1, msg));
    void Missing(string what) { _missing++; Log($"  not found: {what}"); }

    public ExportResult Run(CancellationToken ct = default)
    {
        var dest = Path.GetFullPath(_o.Destination);
        Directory.CreateDirectory(Path.GetDirectoryName(dest)!);
        var tmp = dest + ".partial";
        Log($"{WindowsInfo.OsName} build {WindowsInfo.Build}, {WindowsInfo.Locale}, accent {WindowsInfo.Hex(WindowsInfo.Accent)}");
        Log($"Windows folder: {_win}");
        var steps = new List<(string Title, Action Run)>();
        if (_o.Fonts) steps.Add(("Fonts", ExportFonts));
        if (_o.Cursors) steps.Add(("Cursors", ExportCursors));
        if (_o.SystemIcons) steps.Add(("File type icons", ExportFileTypeIcons));
        if (_o.SystemIcons) steps.Add(("System icons", ExportSystemIcons));
        if (_o.FolderIcons) steps.Add(("Explorer folder icons", ExportFolderIcons));
        if (_o.Taskbar) steps.Add(("Start button and Search icon", ExportTaskbar));
        if (_o.AppIcons) steps.Add(("App icons", ExportAppIcons));
        if (_o.Battery) steps.Add(("Battery glyphs", ExportBattery));
        if (_o.Wallpapers) steps.Add(("Wallpaper and lock screen", ExportWallpapers));
        try
        {
            using (var fs = new FileStream(tmp, FileMode.Create, FileAccess.ReadWrite, FileShare.None))
            using (_zip = new ZipArchive(fs, ZipArchiveMode.Create, leaveOpen: false, Encoding.UTF8))
            {
                for (int i = 0; i < steps.Count; i++)
                {
                    ct.ThrowIfCancellationRequested();
                    _progress.Report(new ExportProgress(i * 100 / (steps.Count + 1), steps[i].Title));
                    int before = _written.Count;
                    try { steps[i].Run(); }
                    catch (Exception e) when (e is not OperationCanceledException)
                    {
                        Log($"  error: {e.Message}");
                    }
                    Log($"  {_written.Count - before} files");
                }
                if (_themeDirs.Count > 0) WriteIndexTheme();
                WriteManifest();
            }
            File.Move(tmp, dest, overwrite: true);
        }
        catch
        {
            try { File.Delete(tmp); } catch (Exception) { }
            throw;
        }
        _progress.Report(new ExportProgress(100, $"Saved {_written.Count} files ({_bytes / 1048576.0:0.0} MB) to {dest}"));
        return new ExportResult(_written.Count, new FileInfo(dest).Length, _missing, dest);
    }

    // ------------------------------------------------------------------ zip ---
    void AddBytes(string entry, byte[] data)
    {
        entry = entry.Replace('\\', '/');
        if (entry.StartsWith('/') || entry.Split('/').Contains("..")) throw new InvalidOperationException(entry);
        if (!_written.Add(entry)) return;
        bool packed = entry.EndsWith(".png", StringComparison.OrdinalIgnoreCase) || entry.EndsWith(".jpg", StringComparison.OrdinalIgnoreCase);
        var e = _zip.CreateEntry(entry, packed ? CompressionLevel.Fastest : CompressionLevel.Optimal);
        using (var s = e.Open()) s.Write(data, 0, data.Length);
        _bytes += data.Length;
    }

    bool AddFile(string entry, string? src)
    {
        if (src == null || !File.Exists(src)) return false;
        byte[] data;
        using (var fs = new FileStream(src, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
        {
            data = new byte[fs.Length];
            fs.ReadExactly(data);
        }
        AddBytes(entry, data);
        return true;
    }

    string P(params string[] parts) => Path.Combine(new[] { _win }.Concat(parts).ToArray());

    static string? FirstExisting(params string?[] paths) => paths.FirstOrDefault(p => p != null && File.Exists(p));

    // ---------------------------------------------------------------- fonts ---
    void ExportFonts()
    {
        foreach (var f in FontFiles)
        {
            if (!AddFile($"fonts/{f}", P("Fonts", f)) && f is "segoeui.ttf" or "SegUIVar.ttf" or "SegoeIcons.ttf" or "consola.ttf")
                Missing($@"Fonts\{f}");
        }
    }

    // -------------------------------------------------------------- cursors ---
    void ExportCursors()
    {
        var dir = P("Cursors");
        if (!Directory.Exists(dir)) { Missing(@"Cursors folder"); return; }
        foreach (var f in Directory.EnumerateFiles(dir).OrderBy(f => f, StringComparer.OrdinalIgnoreCase))
        {
            var name = Path.GetFileName(f);
            var ext = Path.GetExtension(name).ToLowerInvariant();
            if (ext is not (".cur" or ".ani")) continue;
            var lower = name.ToLowerInvariant();
            if (lower.StartsWith("aero_") || lower.StartsWith("beam_") || lower.StartsWith("cross_"))
                AddFile($"cursors/{lower}", f);
        }
        // The user's current scheme (may point at files outside C:\Windows\Cursors).
        var scheme = WindowsInfo.CursorScheme();
        var roles = new JsonObject();
        foreach (var (role, def) in DefaultCursors)
        {
            scheme.TryGetValue(role, out var value);
            string? file = null;
            if (!string.IsNullOrWhiteSpace(value))
            {
                var path = Environment.ExpandEnvironmentVariables(value);
                if (!Path.IsPathRooted(path)) path = Path.Combine(dir, path);
                if (File.Exists(path))
                {
                    var name = Path.GetFileName(path).ToLowerInvariant();
                    if (_written.Contains($"cursors/{name}") && !Path.GetDirectoryName(path)!.Equals(dir, StringComparison.OrdinalIgnoreCase))
                        name = "scheme-" + name;
                    AddFile($"cursors/{name}", path);
                    file = name;
                }
            }
            if (file == null && _written.Contains($"cursors/{def}")) file = def;
            if (file != null) roles[role] = file;
        }
        _extra["cursor_scheme"] = new JsonObject
        {
            ["name"] = WindowsInfo.CursorSchemeName ?? "Windows Default",
            ["roles"] = roles,
        };
    }

    // --------------------------------------------------------- system icons ---
    ResourceModule? OpenModule(Src s) => s switch
    {
        Src.Imageres => ResourceModule.Open(P("SystemResources", "imageres.dll.mun"), P("System32", "imageres.dll")),
        Src.Shell32 => ResourceModule.Open(P("SystemResources", "shell32.dll.mun"), P("System32", "shell32.dll")),
        Src.Edge => ResourceModule.Open(EdgePaths()),
        _ => null,
    };

    static string?[] EdgePaths()
    {
        var pf86 = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86);
        var pf = Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles);
        return new[] { pf86, pf }.Where(p => !string.IsNullOrEmpty(p))
            .Select(p => Path.Combine(p, "Microsoft", "Edge", "Application", "msedge.exe")).ToArray();
    }

    static string ModuleKey(ResourceModule m)
    {
        var n = Path.GetFileName(m.Path).ToLowerInvariant();
        foreach (var suffix in new[] { ".dll.mun", ".exe.mun", ".dll", ".exe", ".mun" })
            if (n.EndsWith(suffix)) return n[..^suffix.Length];
        return n;
    }

    void AddThemeIcon(IconGroup g, string context, string name)
    {
        foreach (var size in Sizes)
        {
            using var bmp = g.Render(size);
            var dir = $"{size}x{size}/{context}";
            _themeDirs.Add(dir);
            AddBytes($"icons/{IconTheme}/{dir}/{name}.png", IconCodec.ToPng(bmp));
        }
    }

    void AddRawGroup(ResourceModule m, IconGroup g) =>
        AddBytes($"raw/icons/{ModuleKey(m)}/{g.Id}.ico", g.ToIco());

    void ExportSystemIcons()
    {
        var modules = new Dictionary<Src, ResourceModule?>();
        try
        {
            int done = 0;
            foreach (var (name, context, src, id) in ThemeIcons)
            {
                if (!modules.TryGetValue(src, out var m)) modules[src] = m = OpenModule(src);
                done++;
                if (m == null) { Missing($"{src} icons (for {name})"); continue; }
                var g = m.Group(id);
                if (g == null) { Missing($"{Path.GetFileName(m.Path)} icon {id} ({name})"); continue; }
                AddThemeIcon(g, context, name);
                AddRawGroup(m, g);
                if (done % 6 == 0) Log($"  {done}/{ThemeIcons.Length} icons");
            }
        }
        finally
        {
            foreach (var m in modules.Values) m?.Dispose();
        }
    }

    // Before ExportSystemIcons: the per-type icons win over its generic mimetype ones.
    void ExportFileTypeIcons()
    {
        foreach (var (ext, names) in FileTypeIcons.Map)
        {
            foreach (var size in Sizes)
            {
                byte[]? png;
                try { png = FileTypeIcons.Png(ext, size); }
                catch (Exception e) { Log($"  {ext}: {e.Message}"); png = null; }
                if (png == null) { Missing($"{ext} icon ({size} px)"); continue; }
                var dir = $"{size}x{size}/mimetypes";
                _themeDirs.Add(dir);
                foreach (var name in names)
                    AddBytes($"icons/{IconTheme}/{dir}/{name}.png", png);
            }
        }
    }

    void ExportFolderIcons()
    {
        using var m = OpenModule(Src.Imageres);
        if (m == null) { Missing("imageres.dll.mun"); return; }
        var empty = m.Group(3);
        if (empty == null) Missing("imageres icon 3 (empty folder)");
        else
        {
            using var bmp = empty.Render(Math.Min(256, empty.LargestSize));
            AddBytes("assets/folders/folder-empty.png", IconCodec.ToPng(bmp));
            AddRawGroup(m, empty);
        }
        // Group 162 is Explorer's "folder with content" art: back flap, a thin sliver of paper and the
        // front flap. Explorer adds the content preview at run time, so on its own it looks almost
        // empty. Compose the white sheet between the flaps, the way a non-empty folder looks.
        var full = m.Group(162);
        if (full == null) { Missing("imageres icon 162 (full folder)"); return; }
        using (var bmp = full.Render(Math.Min(256, full.LargestSize)))
        {
            using var composed = FolderArt.AddSheet(bmp);
            if (composed == null) Log("  full folder: unexpected artwork, exported as is");
            AddBytes("assets/folders/folder-full.png", IconCodec.ToPng(composed ?? bmp));
        }
        AddRawGroup(m, full);
    }

    // -------------------------------------------------------------- taskbar ---
    void ExportTaskbar()
    {
        var core = P("SystemApps", "MicrosoftWindows.Client.Core_cw5n1h2txyewy");
        var logo = FirstExisting(Path.Combine(core, "Icons", "WindowsLogo.svg"));
        if (logo == null && Directory.Exists(core))
        {
            try
            {
                logo = Directory.EnumerateFiles(core, "WindowsLogo.svg", SearchOption.AllDirectories)
                    .OrderBy(f => f.Length).FirstOrDefault();
            }
            catch (Exception) { /* access denied in some subfolders */ }
        }
        if (!AddFile("assets/branding/start-button.svg", logo)) Missing(@"SystemApps\MicrosoftWindows.Client.Core_cw5n1h2txyewy\Icons\WindowsLogo.svg");

        string? search = null;
        var shared = P("SystemApps", "Shared");
        foreach (var scale in new[] { "400", "200", "100" })
        {
            var d = Path.Combine(shared, $"SearchIconOnDark.scale-{scale}");
            if (!Directory.Exists(d)) continue;
            search = Directory.EnumerateFiles(d, "*.png", SearchOption.AllDirectories)
                .OrderBy(f => f, StringComparer.OrdinalIgnoreCase).FirstOrDefault();
            if (search != null) break;
        }
        if (!AddFile("assets/search/search.png", search)) Missing(@"SystemApps\Shared\SearchIconOnDark.scale-*\*.png");
    }

    // ------------------------------------------------------------ app icons ---
    void ExportAppIcons()
    {
        ExportSettingsIcon();

        AppIcon(new[] { P("explorer.exe") }, "File Explorer", "system-file-manager", "org.gnome.Nautilus", "fenestra-file-explorer");
        AppIcon(new[] { P("SystemResources", "Taskmgr.exe.mun"), P("System32", "Taskmgr.exe") }, "Task Manager",
                "org.fenestra.TaskManager", "utilities-system-monitor", "fenestra-taskmgr");
    }

    /// <summary>Settings app logo. File names differ between builds, so rank every logo*.png in
    /// ImmersiveControlPanel\images (unplated, then targetsize, then pixel size; never high-contrast),
    /// falling back to SystemSettings.exe's own icon.</summary>
    void ExportSettingsIcon()
    {
        var images = P("ImmersiveControlPanel", "images");
        var cands = new List<(string Path, bool Unplated, bool Target, int Size)>();
        if (Directory.Exists(images))
        {
            foreach (var f in Directory.EnumerateFiles(images, "logo*.png", SearchOption.TopDirectoryOnly))
            {
                var n = Path.GetFileName(f).ToLowerInvariant();
                if (n.Contains("contrast")) continue;
                int size = 0;
                try { using var im = LoadImage(f); size = Math.Min(im.Width, im.Height); } catch (Exception) { continue; }
                cands.Add((f, n.Contains("unplated"), n.Contains("targetsize"), size));
            }
        }
        var best = cands.OrderByDescending(c => c.Unplated).ThenByDescending(c => c.Size).ThenByDescending(c => c.Target).FirstOrDefault();
        IconGroup? exeIcon = null;
        ResourceModule? exe = null;
        try
        {
            if (best.Path == null || best.Size < 48)
            {
                exe = ResourceModule.Open(P("SystemResources", "SystemSettings.exe.mun"), P("ImmersiveControlPanel", "SystemSettings.exe"));
                exeIcon = exe?.FirstGroup();
            }
            if (best.Path == null && exeIcon == null) { Missing(@"Settings logo (ImmersiveControlPanel\images\logo*.png or SystemSettings.exe)"); return; }
            bool usePng = best.Path != null && (best.Size >= 48 || exeIcon == null);
            Log(usePng ? $"  Settings logo: {Path.GetFileName(best.Path)} ({best.Size} px)" : "  Settings logo: SystemSettings.exe icon");

            Bitmap Render(int size)
            {
                if (!usePng) return exeIcon!.Render(size);
                var exact = cands.FirstOrDefault(c => c.Unplated && c.Size == size).Path;
                using var src = LoadImage(exact ?? best.Path!);
                return src.Width == size && src.Height == size ? (Bitmap)src.Clone() : IconCodec.Scale(src, size);
            }
            using (var big = Render(256)) AddBytes("assets/branding/settings.png", IconCodec.ToPng(big));
            foreach (var size in Sizes)
            {
                _themeDirs.Add($"{size}x{size}/apps");
                using var bmp = Render(size);
                AddBytes($"icons/{IconTheme}/{size}x{size}/apps/fenestra-settings.png", IconCodec.ToPng(bmp));
            }
            if (exe != null && exeIcon != null) AddRawGroup(exe, exeIcon);
        }
        finally { exe?.Dispose(); }
    }

    static Bitmap LoadImage(string path)
    {
        using var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
        using var ms = new MemoryStream();
        fs.CopyTo(ms);
        ms.Position = 0;
        using var img = new Bitmap(ms);
        return img.Clone(new Rectangle(0, 0, img.Width, img.Height), System.Drawing.Imaging.PixelFormat.Format32bppArgb);
    }

    void AppIcon(string[] candidates, string label, params string[] names)
    {
        using var m = ResourceModule.Open(candidates);
        var g = m?.FirstGroup();
        if (m == null || g == null) { Missing($"{label} icon ({Path.GetFileName(candidates[^1])})"); return; }
        foreach (var n in names) AddThemeIcon(g, "apps", n);
        AddRawGroup(m, g);
    }

    // -------------------------------------------------------------- battery ---
    void ExportBattery()
    {
        var src = FirstExisting(
            P("SystemApps", "MicrosoftWindows.Client.Core_cw5n1h2txyewy", "SystemTray", "Assets", "Sysbatt.ttf"),
            P("SystemResources", "Windows.UI.ControlCenter", "Assets", "Sysbatt.ttf"),
            P("SystemApps", "Microsoft.LockApp_cw5n1h2txyewy", "Assets", "Sysbatt.ttf"));
        if (!AddFile("raw/Sysbatt.ttf", src)) Missing("Sysbatt.ttf");
    }

    // ----------------------------------------------------------- wallpapers ---
    static string ImageExt(string path)
    {
        var head = new byte[8];
        using (var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
            fs.ReadAtLeast(head, head.Length, throwOnEndOfStream: false);
        if (head[0] == 0x89 && head[1] == 0x50) return ".png";
        if (head[0] == 0x42 && head[1] == 0x4D) return ".bmp";
        if (head[0] == 0xFF && head[1] == 0xD8) return ".jpg";
        var e = Path.GetExtension(path).ToLowerInvariant();
        return e is ".jpg" or ".jpeg" or ".png" or ".bmp" or ".webp" ? e : ".jpg";
    }

    void ExportWallpapers()
    {
        var appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
        var desk = FirstExisting(WindowsInfo.WallpaperPath is { Length: > 0 } w ? Environment.ExpandEnvironmentVariables(w) : null,
                                 Path.Combine(appData, "Microsoft", "Windows", "Themes", "TranscodedWallpaper"));
        if (desk != null) AddFile($"assets/wallpapers/windows-desktop{ImageExt(desk)}", desk);
        else Missing("desktop wallpaper (a solid colour or slideshow has no single image)");

        var lockPath = WindowsInfo.LockScreenPath is { Length: > 0 } l ? Environment.ExpandEnvironmentVariables(l) : null;
        var lockImg = FirstExisting(lockPath, P("Web", "Screen", "img100.jpg"));
        if (lockImg != null)
        {
            if (lockImg != lockPath) Log("  lock screen: personal lock screen pictures are private to Windows; using the default image");
            AddFile($"assets/wallpapers/windows-lockscreen{ImageExt(lockImg)}", lockImg);
        }
        else Missing("lock screen image");
    }

    // ------------------------------------------------------------ metadata ---
    void WriteIndexTheme()
    {
        var dirs = _themeDirs.OrderByDescending(d => int.Parse(d.Split('x')[0])).ThenBy(d => d, StringComparer.Ordinal).ToList();
        var sb = new StringBuilder();
        sb.Append("[Icon Theme]\n");
        sb.Append($"Name={IconTheme}\n");
        sb.Append("Comment=Icons exported from your own Windows installation by Fenestra Icon Extractor\n");
        sb.Append("Inherits=Fenestra,Win11,Adwaita,hicolor\n");
        sb.Append("Example=folder\n");
        sb.Append($"Directories={string.Join(',', dirs)}\n");
        foreach (var d in dirs)
        {
            var size = d.Split('x')[0];
            var ctx = d.Split('/')[1] switch
            {
                "places" => "Places", "devices" => "Devices", "mimetypes" => "MimeTypes",
                "apps" => "Applications", "actions" => "Actions", _ => "Status",
            };
            sb.Append($"\n[{d}]\nSize={size}\nContext={ctx}\nType=Fixed\n");
        }
        AddBytes($"icons/{IconTheme}/index.theme", Encoding.UTF8.GetBytes(sb.ToString()));
    }

    void WriteManifest()
    {
        var tops = new[] { "fonts", "cursors", "assets", "icons", "raw" }
            .Where(t => _written.Any(w => w.StartsWith(t + "/", StringComparison.Ordinal))).ToList();
        var os = WindowsInfo.OsName;
        var source = new JsonObject { ["os"] = os, ["build"] = WindowsInfo.Build, ["locale"] = WindowsInfo.Locale };
        if (WindowsInfo.DisplayVersion is { } dv) source["version"] = dv;
        if (WindowsInfo.Edition is { } ed) source["edition"] = ed;
        var m = new JsonObject
        {
            ["format"] = "fenestra-icon-pack",
            ["version"] = 1,
            ["id"] = os == "Windows 10" ? "windows-10-user-export" : "windows-11-user-export",
            ["name"] = $"{os} (exported from my PC)",
            ["generator"] = $"Fenestra Icon Extractor {Version}",
            ["source"] = source,
            ["created"] = DateTime.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'", System.Globalization.CultureInfo.InvariantCulture),
            ["contents"] = new JsonArray(tops.Select(t => (JsonNode)JsonValue.Create(t)!).ToArray()),
        };
        if (tops.Contains("icons")) m["icon_theme"] = IconTheme;
        if (tops.Contains("cursors")) m["cursor_theme"] = CursorTheme;
        m["accent"] = WindowsInfo.Hex(WindowsInfo.Accent);
        m["licence_note"] = "Personal export of files from the user's own Windows licence. Do not redistribute.";
        foreach (var (k, v) in _extra.ToList())
        {
            _extra.Remove(k);
            m[k] = v;
        }
        var json = m.ToJsonString(new JsonSerializerOptions { WriteIndented = true, Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping });
        AddBytes("fenestra-pack.json", Encoding.UTF8.GetBytes(json + "\n"));
    }
}
