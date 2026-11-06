using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace FenestraIconExtractor;

public sealed record RefGlyph(string Name, string? Glyph, int? CodePoint, bool Verified);
public sealed record RefApp(string Name, string? Module, string? Family, string? Hint, string[] Paths, bool Verified);
public sealed record RefModule(string Name, string? Context, string? Module, int? Id, string? Path, bool Verified);
public sealed record RefBitmap(string Name, string? Origin, bool Verified);

/// <summary>The icons of design/reference/icons.json (table compiled into ReferenceIcons.g.cs):
/// Segoe Fluent glyphs as SVG, Store/system app logos, and the reference bitmaps that a documented
/// API can resolve. Every entry gets a status in an index file, so what was exported from an
/// unverified id or path can be checked on a real PC. Nothing is guessed silently.</summary>
public sealed partial class Exporter
{
    static readonly int[] AppSizes = { 256, 48, 32, 24, 16 };
    static readonly int[] BitmapSizes = { 16, 20, 24, 32, 48 };
    static readonly JsonSerializerOptions IndexJson = new()
    {
        WriteIndented = true,
        Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
    };

    void AddJson(string entry, JsonNode node) =>
        AddBytes(entry, Encoding.UTF8.GetBytes(node.ToJsonString(IndexJson) + "\n"));

    static JsonArray Arr(IEnumerable<string> items) => new(items.Select(i => (JsonNode)JsonValue.Create(i)!).ToArray());

    /// <summary>A path written as on a default install (C:\Windows, C:\Program Files...) on this PC.</summary>
    string Resolve(string path)
    {
        var p = Environment.ExpandEnvironmentVariables(path);
        (string From, string To)[] roots =
        {
            (@"C:\Windows", _win),
            (@"C:\Program Files (x86)", Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86)),
            (@"C:\Program Files", Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles)),
            (@"C:\ProgramData", Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData)),
        };
        foreach (var (from, to) in roots)
            if (!string.IsNullOrEmpty(to) && p.StartsWith(from + @"\", StringComparison.OrdinalIgnoreCase))
                return to + p[from.Length..];
        return p;
    }

    /// <summary>Resource candidates for a module under the Windows folder: SystemResources\X.mun first
    /// (where Windows 10 1903+ keeps the icons), then the file itself.</summary>
    string[] WithMun(string file)
    {
        var name = Path.GetFileName(file);
        return new[] { P("SystemResources", name + ".mun"), file };
    }

    void AddThemeIcon(IconGroup g, string context, string name, int[] sizes)
    {
        foreach (var size in sizes)
        {
            using var bmp = g.Render(size);
            var dir = $"{size}x{size}/{context}";
            _themeDirs.Add(dir);
            AddBytes($"icons/{IconTheme}/{dir}/{name}.png", IconCodec.ToPng(bmp));
        }
    }

    // --------------------------------------------------------------- glyphs ---
    void ExportGlyphs()
    {
        var path = FirstExisting(P("Fonts", "SegoeIcons.ttf"), P("Fonts", "segmdl2.ttf"));
        if (path == null) { Missing(@"Fonts\SegoeIcons.ttf (Segoe Fluent Icons) or Fonts\segmdl2.ttf"); return; }
        TrueTypeFont font;
        try
        {
            using var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
            var data = new byte[fs.Length];
            fs.ReadExactly(data);
            font = new TrueTypeFont(data);
        }
        catch (Exception e) when (e is InvalidDataException or NotSupportedException or IOException)
        {
            Missing($"{Path.GetFileName(path)}: {e.Message}");
            return;
        }
        Log($"  {Path.GetFileName(path)}: revision {font.Revision}, {font.CodePoints().Count} code points, {font.UnitsPerEm} units/em");
        var glyphs = new JsonObject();
        var missing = new List<string>();
        var reasons = new JsonObject();
        foreach (var g in ReferenceIcons.Glyphs)
        {
            if (g.CodePoint is not int cp)
            {
                missing.Add(g.Name);
                reasons[g.Name] = "no public code point (Windows draws something that is not in Microsoft's glyph table)";
                continue;
            }
            string? svg;
            try { svg = font.Svg(cp); }
            catch (InvalidDataException e) { svg = null; Log($"  {g.Name}: {e.Message}"); }
            if (svg == null)
            {
                missing.Add(g.Name);
                reasons[g.Name] = $"U+{cp:X4} is not in {Path.GetFileName(path)}";
                Missing($"glyph {g.Name} (U+{cp:X4} {g.Glyph})");
                continue;
            }
            AddBytes($"glyphs/{g.Name}.svg", Encoding.UTF8.GetBytes(svg));
            glyphs[g.Name] = new JsonObject
            {
                ["codepoint"] = $"U+{cp:X4}", ["glyph"] = g.Glyph, ["file"] = $"{g.Name}.svg", ["verified"] = g.Verified,
            };
        }
        int all = 0;
        if (_o.AllGlyphs)
        {
            foreach (var cp in font.CodePoints())
            {
                string? svg;
                try { svg = font.Svg(cp); } catch (InvalidDataException) { svg = null; }
                if (svg == null) continue;
                AddBytes($"glyphs/u/{cp:X4}.svg", Encoding.UTF8.GetBytes(svg));
                all++;
            }
            Log($"  --all-glyphs: {all} code points");
        }
        var index = new JsonObject
        {
            ["font"] = Path.GetFileName(path),
            ["font_revision"] = font.Revision,
            ["units_per_em"] = font.UnitsPerEm,
            ["baseline"] = font.Baseline,
            ["reference"] = "design/reference/icons.json" + (ReferenceIcons.SourceRevision.Length > 0 ? $" @ {ReferenceIcons.SourceRevision}" : ""),
            ["glyphs"] = glyphs,
            ["missing"] = Arr(missing),
            ["missing_reasons"] = reasons,
        };
        if (_o.AllGlyphs) index["all_glyphs"] = all;
        AddJson("glyphs/glyphs.json", index);
        Log($"  {glyphs.Count} of {ReferenceIcons.Glyphs.Length} named glyphs, {missing.Count} missing");
    }

    // ------------------------------------------------------------ app logos ---
    void ExportPackageLogos()
    {
        var report = new JsonObject();
        foreach (var app in ReferenceIcons.Apps)
        {
            JsonObject r;
            try { r = ExportReferenceApp(app); }
            catch (Exception e) when (e is IOException or UnauthorizedAccessException or System.Xml.XmlException or ExternalException or ArgumentException)
            {
                r = new JsonObject { ["status"] = "error", ["error"] = e.Message };
            }
            r["verified"] = app.Verified;
            r["module"] = app.Module;
            var status = (string?)r["status"];
            if (status is not ("exported" or "candidate")) Missing($"app logo {app.Name}: {status} {(string?)r["reason"] ?? (string?)r["error"] ?? ""}".TrimEnd());
            else if (!app.Verified) Log($"  {app.Name}: exported from an unverified source (check it): {(string?)r["source"]}");
            report[app.Name] = r;
        }
        AddJson("apps/apps.json", new JsonObject
        {
            ["reference"] = "design/reference/icons.json" + (ReferenceIcons.SourceRevision.Length > 0 ? $" @ {ReferenceIcons.SourceRevision}" : ""),
            ["theme"] = IconTheme,
            ["sizes"] = new JsonArray(AppSizes.Select(s => (JsonNode)JsonValue.Create(s)!).ToArray()),
            ["apps"] = report,
        });
    }

    string Status(bool verified) => verified ? "exported" : "candidate";

    JsonObject ExportReferenceApp(RefApp app)
    {
        // Logos the older steps already export.
        if (app.Family == "ImmersiveControlPanel")
            return Covered($"icons/{IconTheme}/48x48/apps/fenestra-settings.png", "App icons step (ImmersiveControlPanel logo)", app.Verified);
        if (app.Module == "SystemApps" && app.Family == null && app.Paths.Length > 0)
        {
            var p = app.Paths[0];
            if (p.Contains("WindowsLogo", StringComparison.OrdinalIgnoreCase))
                return Covered("assets/branding/start-button.svg", "Start button step", app.Verified);
            if (p.Contains("SearchIcon", StringComparison.OrdinalIgnoreCase))
                return Covered("assets/search/search.png", "Search icon step", app.Verified);
        }
        if (app.Module == "Exe") return ExportExeLogo(app);
        if (app.Family == null || !app.Family.Contains('_'))
            return new JsonObject { ["status"] = "unresolved", ["reason"] = "icons.json names no package family for it" };
        return ExportAppxLogo(app);
    }

    JsonObject Covered(string file, string step, bool verified) => _written.Contains(file)
        ? new JsonObject { ["status"] = Status(verified), ["file"] = file, ["source"] = step }
        : new JsonObject { ["status"] = "missing", ["reason"] = $"{step} did not export {file} (unticked or not found)" };

    JsonObject ExportExeLogo(RefApp app)
    {
        var cands = new List<string>();
        foreach (var raw in app.Paths)
        {
            var p = Resolve(raw);
            if (p.StartsWith(_win, StringComparison.OrdinalIgnoreCase)) cands.AddRange(WithMun(p));
            else cands.Add(p);
        }
        if (app.Name == "microsoft-edge") cands.AddRange(EdgePaths().OfType<string>());
        using var m = ResourceModule.Open(cands.ToArray());
        var g = m?.FirstGroup();
        if (m == null || g == null)
            return new JsonObject { ["status"] = "missing", ["reason"] = "not installed: " + string.Join(" | ", cands.Distinct()) };
        AddThemeIcon(g, "apps", app.Name, AppSizes);
        _themeDirs.Add("256x256/apps");
        AddRawGroup(m, g);
        return new JsonObject
        {
            ["status"] = Status(app.Verified), ["source"] = $"{m.Path} (first icon group, id {g.Id})",
            ["files"] = Arr(AppSizes.Select(s => $"icons/{IconTheme}/{s}x{s}/apps/{app.Name}.png")),
        };
    }

    JsonObject ExportAppxLogo(RefApp app)
    {
        var family = app.Family!;
        var folders = AppxLogos.PackageFolders(family);
        string how = "GetPackagesByPackageFamily";
        if (folders.Count == 0)
        {
            var sys = P("SystemApps", family);
            if (Directory.Exists(sys)) { folders.Add(sys); how = @"%WINDIR%\SystemApps"; }
        }
        if (folders.Count == 0)
            return new JsonObject { ["status"] = "missing", ["package_family"] = family, ["reason"] = "package family not installed for this user" };
        var main = folders.FirstOrDefault(f => File.Exists(Path.Combine(f, "AppxManifest.xml")));
        if (main == null)
            return new JsonObject { ["status"] = "missing", ["package_family"] = family, ["reason"] = "no AppxManifest.xml in " + folders[0] };
        var apps = AppxLogos.ReadManifest(Path.Combine(main, "AppxManifest.xml"));
        var chosen = AppxLogos.ChooseApp(apps, app.Hint);
        if (chosen?.Logo == null)
            return new JsonObject
            {
                ["status"] = "unresolved", ["package_family"] = family, ["hint"] = app.Hint,
                ["reason"] = app.Hint != null ? $"no application in the manifest matches \"{app.Hint}\"" : "the manifest has no app logo",
                ["applications"] = Arr(apps.Select(a => a.Id)),
            };

        // Qualified files of the logo resource, in the main package and its resource packages.
        var logoRel = chosen.Logo.Replace('/', '\\');
        var logoDir = Path.GetDirectoryName(logoRel) ?? "";
        var files = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var f in folders)
        {
            var dir = Path.Combine(f, logoDir);
            if (!Directory.Exists(dir)) continue;
            try
            {
                foreach (var file in Directory.EnumerateFiles(dir, "*", SearchOption.TopDirectoryOnly))
                    files.TryAdd(Path.GetFileName(file), file);
                foreach (var sub in Directory.EnumerateDirectories(dir))
                    foreach (var file in Directory.EnumerateFiles(sub, "*", SearchOption.TopDirectoryOnly))
                        files.TryAdd(Path.GetFileName(sub) + "\\" + Path.GetFileName(file), file);
            }
            catch (Exception e) when (e is UnauthorizedAccessException or IOException) { Log($"  {app.Name}: {e.Message}"); }
        }
        var variants = AppxLogos.Variants(logoRel, files.Keys).ToList();
        if (variants.Count == 0)
            return new JsonObject
            {
                ["status"] = "missing", ["package_family"] = family, ["app_id"] = chosen.Id, ["logo"] = chosen.Logo,
                ["reason"] = "no image file for the logo (only in resources.pri?)",
            };

        var used = new JsonObject();
        var light = new JsonObject();
        foreach (var size in AppSizes)
        {
            foreach (var isLight in new[] { false, true })
            {
                var v = AppxLogos.Pick(variants, size, isLight);
                if (v == null) continue;
                var src = files[v.File];
                using var img = LoadImage(src);
                using var bmp = img.Width == size && img.Height == size ? (Bitmap)img.Clone() : IconCodec.Scale(img, size);
                if (isLight)
                {
                    AddBytes($"apps/light/{size}x{size}/{app.Name}.png", IconCodec.ToPng(bmp));
                    light[size.ToString(System.Globalization.CultureInfo.InvariantCulture)] = v.File;
                }
                else
                {
                    _themeDirs.Add($"{size}x{size}/apps");
                    AddBytes($"icons/{IconTheme}/{size}x{size}/apps/{app.Name}.png", IconCodec.ToPng(bmp));
                    used[size.ToString(System.Globalization.CultureInfo.InvariantCulture)] = v.File;
                }
                AddFile($"raw/appx/{family}/{v.File.Replace('\\', '_')}", src);
            }
        }
        var r = new JsonObject
        {
            ["status"] = Status(app.Verified), ["package_family"] = family, ["found_with"] = how,
            ["app_id"] = chosen.Id, ["logo"] = chosen.Logo, ["source"] = $"{family}!{chosen.Id} {chosen.Logo}",
            ["variants_used"] = used,
        };
        if (app.Hint != null) r["hint"] = app.Hint;
        if (light.Count > 0) r["light_variants_used"] = light;
        return r;
    }

    // -------------------------------------------------------------- bitmaps ---
    enum BitmapApi { Stock, ThemePart }

    /// <summary>bitmaps[] entries a documented API can produce. Ids are the SHSTOCKICONID values and
    /// uxtheme part/state constants from the Windows SDK headers (shellapi.h, vssym32.h); whether
    /// Windows draws exactly this picture at the place seen in the screenshot is not verified, so the
    /// result is recorded as "candidate".</summary>
    static readonly (string Name, BitmapApi Api, string Symbol, int A, int B, string? ThemeClass)[] BitmapCandidates =
    {
        ("dialog-help", BitmapApi.Stock, "SIID_HELP", 23, 0, null),
        ("dialog-search", BitmapApi.Stock, "SIID_FIND", 22, 0, null),
        ("organize-delete", BitmapApi.Stock, "SIID_DELETE", 84, 0, null),
        ("organize-rename", BitmapApi.Stock, "SIID_RENAME", 83, 0, null),
        ("dialog-sort-arrow", BitmapApi.ThemePart, "HP_HEADERSORTARROW/HSAS_SORTEDUP", 4, 1, "Header"),
        ("dialog-size-grip", BitmapApi.ThemePart, "SP_GRIPPER", 3, 0, "Status"),
    };

    static readonly Dictionary<string, (string Status, string Note)> BitmapPolicy = new()
    {
        ["microsoft-account-logo"] = ("skipped", "brand logo: Fenestra neither reproduces nor exports it"),
        ["taskbar-task-view"] = ("substitute", "glyphs/task-view.svg (TaskView glyph)"),
        ["start-search-lens"] = ("substitute", "assets/search/search.png (taskbar search icon)"),
        ["dialog-back"] = ("substitute", "glyphs/go-previous.svg"),
        ["dialog-forward"] = ("substitute", "glyphs/go-next.svg"),
        ["dialog-up"] = ("substitute", "glyphs/go-up.svg"),
        ["dialog-refresh"] = ("substitute", "glyphs/view-refresh.svg"),
        ["dialog-preview-pane"] = ("substitute", "glyphs/view-dual.svg"),
        ["dialog-pinned"] = ("substitute", "glyphs/view-pin.svg"),
        ["dialog-view"] = ("substitute", "glyphs/view-list.svg"),
        ["organize-cut"] = ("substitute", "glyphs/edit-cut.svg"),
        ["organize-copy"] = ("substitute", "glyphs/edit-copy.svg"),
        ["organize-paste"] = ("substitute", "glyphs/edit-paste.svg"),
        ["organize-select-all"] = ("substitute", "glyphs/edit-select-all.svg"),
        ["organize-properties"] = ("substitute", "glyphs/document-properties.svg"),
        ["organize-close"] = ("substitute", "glyphs/window-close.svg"),
    };

    /// <summary>Modules searched with --probe-modules: every icon group at 32 px, so the ids of the
    /// unresolved bitmaps can be found by eye on a real PC and recorded in icons.json.</summary>
    string[][] ProbeModules() => new[]
    {
        WithMun(P("System32", "explorerframe.dll")), WithMun(P("System32", "shell32.dll")), WithMun(P("System32", "imageres.dll")),
        WithMun(P("System32", "compstui.dll")), WithMun(P("System32", "comctl32.dll")),
        new[] { Resolve(@"%LOCALAPPDATA%\Microsoft\OneDrive\OneDrive.exe"), Resolve(@"C:\Program Files\Microsoft OneDrive\OneDrive.exe") },
    };

    void ExportReferenceBitmaps()
    {
        var modules = new JsonObject();
        foreach (var m in ReferenceIcons.Modules)
        {
            JsonObject r;
            try { r = ExportReferenceModule(m); }
            catch (Exception e) when (e is IOException or UnauthorizedAccessException or ExternalException or ArgumentException)
            {
                r = new JsonObject { ["status"] = "error", ["error"] = e.Message };
            }
            r["verified"] = m.Verified;
            if ((string?)r["status"] is "missing" or "error") Missing($"{m.Name}: {(string?)r["reason"] ?? (string?)r["error"]}");
            else if (!m.Verified) Log($"  {m.Name}: exported from an unverified id/path (check it): {(string?)r["source"]}");
            modules[m.Name] = r;
        }

        var bitmaps = new JsonObject();
        foreach (var b in ReferenceIcons.Bitmaps)
        {
            JsonObject r;
            var cand = BitmapCandidates.FirstOrDefault(c => c.Name == b.Name);
            if (cand.Name != null)
            {
                try { r = cand.Api == BitmapApi.Stock ? ExportStockIcon(b.Name, cand.Symbol, cand.A) : ExportThemePart(b.Name, cand.ThemeClass!, cand.Symbol, cand.A, cand.B); }
                catch (Exception e) when (e is IOException or ExternalException or ArgumentException or EntryPointNotFoundException or DllNotFoundException)
                {
                    r = new JsonObject { ["status"] = "error", ["error"] = e.Message };
                }
                if ((string?)r["status"] == "candidate") Log($"  {b.Name}: candidate from {(string?)r["source"]} (check it)");
            }
            else if (BitmapPolicy.TryGetValue(b.Name, out var pol))
                r = new JsonObject { ["status"] = pol.Status, ["note"] = pol.Note };
            else
                r = new JsonObject { ["status"] = "unresolved", ["note"] = "no documented API or verified id; find it with --probe-modules" };
            r["verified"] = b.Verified;
            r["origin"] = b.Origin;
            bitmaps[b.Name] = r;
        }

        var index = new JsonObject
        {
            ["reference"] = "design/reference/icons.json" + (ReferenceIcons.SourceRevision.Length > 0 ? $" @ {ReferenceIcons.SourceRevision}" : ""),
            ["sizes"] = new JsonArray(BitmapSizes.Select(s => (JsonNode)JsonValue.Create(s)!).ToArray()),
            ["statuses"] = new JsonObject
            {
                ["exported"] = "verified source, exported",
                ["candidate"] = "exported from an unverified id, path or API mapping: compare it with Windows before relying on it",
                ["missing"] = "the source is not on this PC",
                ["unresolved"] = "no documented source known: nothing exported",
                ["substitute"] = "not exported; the file named in note stands in for it",
                ["skipped"] = "deliberately not exported",
            },
            ["modules"] = modules,
            ["bitmaps"] = bitmaps,
        };
        if (_o.ProbeModules) index["probe"] = ProbeAll();
        AddJson("bitmaps/bitmaps.json", index);
    }

    JsonObject ExportReferenceModule(RefModule m)
    {
        if (m.Module is "Imageres" or "Shell32" && m.Id is int id)
        {
            using var mod = OpenModule(m.Module == "Imageres" ? Src.Imageres : Src.Shell32);
            if (mod == null) return new JsonObject { ["status"] = "missing", ["reason"] = $"{m.Module} module not found" };
            var g = mod.Group(id);
            if (g == null) return new JsonObject { ["status"] = "missing", ["reason"] = $"{Path.GetFileName(mod.Path)} has no icon group {id}" };
            AddThemeIcon(g, m.Context ?? "places", m.Name, Sizes);
            AddRawGroup(mod, g);
            foreach (var s in BitmapSizes)
            {
                using var bmp = g.Render(s);
                AddBytes($"bitmaps/{s}x{s}/{m.Name}.png", IconCodec.ToPng(bmp));
            }
            return new JsonObject
            {
                ["status"] = Status(m.Verified), ["source"] = $"{Path.GetFileName(mod.Path)} icon group {id}",
                ["theme_file"] = $"icons/{IconTheme}/48x48/{m.Context}/{m.Name}.png",
            };
        }
        if (m.Module == "File" && m.Name == "avatar-default")
        {
            // Default account pictures: user.png (448 px) and user-32/-40/-48/-192.png.
            var dir = Resolve(@"C:\ProgramData\Microsoft\User Account Pictures");
            var found = new JsonArray();
            foreach (var f in new[] { "user.png", "user-32.png", "user-40.png", "user-48.png", "user-192.png" })
                if (AddFile($"assets/account/{f}", Path.Combine(dir, f))) found.Add(f);
            if (found.Count == 0) return new JsonObject { ["status"] = "missing", ["reason"] = $"no user*.png in {dir}" };
            var big = FirstExisting(Path.Combine(dir, "user.png"), Path.Combine(dir, "user-192.png"));
            foreach (var size in Sizes)
            {
                var exact = FirstExisting(Path.Combine(dir, $"user-{size}.png"));
                var src = exact ?? big ?? Path.Combine(dir, (string)found[0]!);
                using var img = LoadImage(src);
                using var bmp = img.Width == size && img.Height == size ? (Bitmap)img.Clone() : IconCodec.Scale(img, size);
                _themeDirs.Add($"{size}x{size}/status");
                AddBytes($"icons/{IconTheme}/{size}x{size}/status/avatar-default.png", IconCodec.ToPng(bmp));
            }
            return new JsonObject { ["status"] = Status(m.Verified), ["source"] = dir, ["files"] = found };
        }
        return new JsonObject { ["status"] = "unresolved", ["reason"] = $"module {m.Module} without id" };
    }

    // SHGetStockIconInfo(SHGSI_ICONLOCATION): module path + resource id, then the icon group itself
    // (all sizes, PNG frames kept) from the module, as for the theme icons.
    JsonObject ExportStockIcon(string name, string symbol, int siid)
    {
        var info = new SHSTOCKICONINFO { cbSize = (uint)Marshal.SizeOf<SHSTOCKICONINFO>() };
        int hr = SHGetStockIconInfo((uint)siid, 0 /* SHGSI_ICONLOCATION */, ref info);
        if (hr != 0 || string.IsNullOrEmpty(info.szPath))
            return new JsonObject { ["status"] = "missing", ["reason"] = $"SHGetStockIconInfo({symbol}) failed (0x{hr:X8})" };
        var path = Environment.ExpandEnvironmentVariables(info.szPath);
        var cands = path.StartsWith(_win, StringComparison.OrdinalIgnoreCase) ? WithMun(path) : new[] { path };
        using var m = ResourceModule.Open(cands);
        if (m == null) return new JsonObject { ["status"] = "missing", ["reason"] = $"cannot open {path}" };
        IconGroup? g;
        if (info.iIcon < 0) g = m.Group(-info.iIcon);
        else { var ids = m.GroupIds(); g = info.iIcon < ids.Count ? m.Group(ids[info.iIcon]) : null; }
        if (g == null) return new JsonObject { ["status"] = "missing", ["reason"] = $"{path},{info.iIcon}: no such icon group" };
        foreach (var s in BitmapSizes)
        {
            using var bmp = g.Render(s);
            AddBytes($"bitmaps/{s}x{s}/{name}.png", IconCodec.ToPng(bmp));
        }
        AddRawGroup(m, g);
        return new JsonObject
        {
            ["status"] = "candidate", ["api"] = "SHGetStockIconInfo", ["stock_icon"] = $"{symbol} ({siid})",
            ["source"] = $"{Path.GetFileName(m.Path)} icon group {g.Id} (stock icon {symbol}: {info.szPath},{info.iIcon})",
            ["files"] = Arr(BitmapSizes.Select(s => $"bitmaps/{s}x{s}/{name}.png")),
        };
    }

    // DrawThemeBackground of a visual-style part, once on black and once on white: the two results give
    // the colour and the alpha of each pixel whatever way the theme blends.
    JsonObject ExportThemePart(string name, string cls, string symbol, int part, int state)
    {
        IntPtr theme = OpenThemeData(IntPtr.Zero, cls);
        if (theme == IntPtr.Zero) return new JsonObject { ["status"] = "missing", ["reason"] = $"OpenThemeData({cls}) failed (classic theme?)" };
        try
        {
            if (GetThemePartSize(theme, IntPtr.Zero, part, state, IntPtr.Zero, 1 /* TS_TRUE */, out var sz) != 0 || sz.cx <= 0 || sz.cy <= 0)
                return new JsonObject { ["status"] = "missing", ["reason"] = $"{cls} part {symbol} has no size" };
            foreach (var s in BitmapSizes)
            {
                int w = Math.Min(sz.cx, s), h = Math.Min(sz.cy, s);
                var rect = new RECT { left = (s - w) / 2, top = (s - h) / 2, right = (s - w) / 2 + w, bottom = (s - h) / 2 + h };
                var black = DrawPart(theme, part, state, s, rect, 0x00000000);
                var white = DrawPart(theme, part, state, s, rect, 0x00FFFFFF);
                if (black == null || white == null) return new JsonObject { ["status"] = "missing", ["reason"] = "DrawThemeBackground failed" };
                using var bmp = new Bitmap(s, s, PixelFormat.Format32bppArgb);
                for (int y = 0; y < s; y++)
                    for (int x = 0; x < s; x++)
                    {
                        int i = (y * s + x) * 4;
                        int a = 255 - Math.Clamp(((white[i] - black[i]) + (white[i + 1] - black[i + 1]) + (white[i + 2] - black[i + 2])) / 3, 0, 255);
                        int U(int c) => a == 0 ? 0 : Math.Clamp(c * 255 / a, 0, 255);
                        bmp.SetPixel(x, y, Color.FromArgb(a, U(black[i + 2]), U(black[i + 1]), U(black[i])));
                    }
                AddBytes($"bitmaps/{s}x{s}/{name}.png", IconCodec.ToPng(bmp));
            }
            return new JsonObject
            {
                ["status"] = "candidate", ["api"] = "DrawThemeBackground",
                ["source"] = $"visual style class {cls}, {symbol} (part {part}, state {state}), true size {sz.cx}x{sz.cy}, centred",
                ["files"] = Arr(BitmapSizes.Select(s => $"bitmaps/{s}x{s}/{name}.png")),
            };
        }
        finally { CloseThemeData(theme); }
    }

    static byte[]? DrawPart(IntPtr theme, int part, int state, int size, RECT rect, uint background)
    {
        var bi = new BITMAPINFOHEADER { biSize = (uint)Marshal.SizeOf<BITMAPINFOHEADER>(), biWidth = size, biHeight = -size, biPlanes = 1, biBitCount = 32 };
        IntPtr dc = CreateCompatibleDC(IntPtr.Zero);
        if (dc == IntPtr.Zero) return null;
        IntPtr dib = CreateDIBSection(dc, ref bi, 0, out var bits, IntPtr.Zero, 0);
        if (dib == IntPtr.Zero) { DeleteDC(dc); return null; }
        IntPtr old = SelectObject(dc, dib);
        try
        {
            var px = new byte[size * size * 4];
            for (int i = 0; i < px.Length; i += 4) { px[i] = (byte)(background & 0xFF); px[i + 1] = (byte)((background >> 8) & 0xFF); px[i + 2] = (byte)((background >> 16) & 0xFF); px[i + 3] = 0; }
            Marshal.Copy(px, 0, bits, px.Length);
            if (DrawThemeBackground(theme, dc, part, state, ref rect, IntPtr.Zero) != 0) return null;
            GdiFlush();
            Marshal.Copy(bits, px, 0, px.Length);
            return px;
        }
        finally
        {
            SelectObject(dc, old);
            DeleteObject(dib);
            DeleteDC(dc);
        }
    }

    JsonObject ProbeAll()
    {
        var probe = new JsonObject();
        foreach (var cands in ProbeModules())
        {
            using var m = ResourceModule.Open(cands);
            if (m == null) { probe[Path.GetFileName(cands[^1])] = "not found"; continue; }
            var key = ModuleKey(m);
            int n = 0;
            foreach (var id in m.GroupIds())
            {
                var g = m.Group(id);
                if (g == null) continue;
                try
                {
                    using var bmp = g.Render(32);
                    AddBytes($"raw/probe/{key}/{id}.png", IconCodec.ToPng(bmp));
                    n++;
                }
                catch (Exception e) when (e is ArgumentException or ExternalException or InvalidOperationException or IndexOutOfRangeException) { }
            }
            probe[key] = n;
            Log($"  probe {Path.GetFileName(m.Path)}: {n} icon groups");
        }
        return probe;
    }

    // ------------------------------------------------------------ interop ---
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct SHSTOCKICONINFO
    {
        public uint cbSize;
        public IntPtr hIcon;
        public int iSysImageIndex;
        public int iIcon;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string szPath;
    }

    [StructLayout(LayoutKind.Sequential)] struct SIZE { public int cx, cy; }
    [StructLayout(LayoutKind.Sequential)] struct RECT { public int left, top, right, bottom; }
    [StructLayout(LayoutKind.Sequential)]
    struct BITMAPINFOHEADER
    {
        public uint biSize; public int biWidth, biHeight; public ushort biPlanes, biBitCount;
        public uint biCompression, biSizeImage; public int biXPelsPerMeter, biYPelsPerMeter; public uint biClrUsed, biClrImportant;
    }

    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    static extern int SHGetStockIconInfo(uint siid, uint uFlags, ref SHSTOCKICONINFO psii);
    [DllImport("uxtheme.dll", CharSet = CharSet.Unicode)]
    static extern IntPtr OpenThemeData(IntPtr hwnd, string classList);
    [DllImport("uxtheme.dll")]
    static extern int CloseThemeData(IntPtr theme);
    [DllImport("uxtheme.dll")]
    static extern int GetThemePartSize(IntPtr theme, IntPtr hdc, int part, int state, IntPtr rect, int eSize, out SIZE size);
    [DllImport("uxtheme.dll")]
    static extern int DrawThemeBackground(IntPtr theme, IntPtr hdc, int part, int state, ref RECT rect, IntPtr clip);
    [DllImport("gdi32.dll")] static extern IntPtr CreateCompatibleDC(IntPtr hdc);
    [DllImport("gdi32.dll")] static extern bool DeleteDC(IntPtr hdc);
    [DllImport("gdi32.dll")] static extern IntPtr CreateDIBSection(IntPtr hdc, ref BITMAPINFOHEADER bmi, uint usage, out IntPtr bits, IntPtr section, uint offset);
    [DllImport("gdi32.dll")] static extern IntPtr SelectObject(IntPtr hdc, IntPtr obj);
    [DllImport("gdi32.dll")] static extern bool DeleteObject(IntPtr obj);
    [DllImport("gdi32.dll")] static extern bool GdiFlush();
}
