using System.Runtime.InteropServices;
using System.Text.RegularExpressions;
using System.Xml.Linq;

namespace FenestraIconExtractor;

/// <summary>
/// Store and system app logos: the package of a family installed for the current user, the logo
/// its AppxManifest.xml names (VisualElements/@Square44x44Logo, a resource base name) and the
/// qualified files on disk ("AppList.targetsize-48_altform-unplated.png", "scale-200\AppList.png", ...).
/// The variant parsing and choice are pure functions (tested on Linux); the lookup uses the
/// documented Win32 packaging APIs GetPackagesByPackageFamily and GetPackagePathByFullName.
/// </summary>
public static class AppxLogos
{
    /// <summary>One qualified file of a logo resource. <see cref="File"/> is relative to the logo's folder.</summary>
    public sealed record Variant(string File, int? TargetSize, int? Scale, bool Unplated, bool Light);

    static readonly Regex QualRx = new(@"^(?<k>[a-z]+)-(?<v>[a-z0-9]+)$", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);

    /// <summary>The variants of <paramref name="logo"/> (e.g. "Assets\AppList.png") among
    /// <paramref name="files"/> (paths relative to the logo's folder, '\' or '/'). High-contrast
    /// variants are left out.</summary>
    public static IEnumerable<Variant> Variants(string logo, IEnumerable<string> files)
    {
        var name = logo.Replace('\\', '/').Split('/')[^1];
        var stem = Path.GetFileNameWithoutExtension(name);
        var ext = Path.GetExtension(name);
        foreach (var f in files)
        {
            var parts = f.Replace('\\', '/').Split('/');
            string? quals;
            if (parts.Length == 1)
            {
                var n = parts[0];
                if (n.Equals(name, StringComparison.OrdinalIgnoreCase)) quals = "";
                else if (n.StartsWith(stem + ".", StringComparison.OrdinalIgnoreCase) && n.EndsWith(ext, StringComparison.OrdinalIgnoreCase)
                         && n.Length > stem.Length + 1 + ext.Length)
                    quals = n[(stem.Length + 1)..^ext.Length];
                else continue;
            }
            else if (parts.Length == 2 && parts[1].Equals(name, StringComparison.OrdinalIgnoreCase)) quals = parts[0];
            else continue;
            var v = Parse(f, quals);
            if (v != null) yield return v;
        }
    }

    static Variant? Parse(string file, string quals)
    {
        int? target = null, scale = null;
        bool unplated = false, light = false;
        if (quals.Length > 0)
        {
            foreach (var q in quals.Split('_'))
            {
                var m = QualRx.Match(q);
                if (!m.Success) return null;     // something else that happens to share the stem
                var k = m.Groups["k"].Value.ToLowerInvariant();
                var val = m.Groups["v"].Value.ToLowerInvariant();
                switch (k)
                {
                    case "contrast": return null;
                    case "targetsize" when int.TryParse(val, out var t): target = t; break;
                    case "scale" when int.TryParse(val, out var s): scale = s; break;
                    case "altform":
                        if (val == "unplated") unplated = true;
                        else if (val == "lightunplated") { unplated = true; light = true; }
                        else return null;          // altform-colorful, -fullcolor...: not the app list logo
                        break;
                    case "theme": if (val == "light") light = true; break;
                    default: break;                // lang-xx, dxfeaturelevel...: harmless
                }
            }
        }
        return new Variant(file, target, scale, unplated, light);
    }

    /// <summary>The variant to render at <paramref name="size"/> px: an unplated targetsize image (the
    /// smallest that is at least <paramref name="size"/>, else the largest), then a plated targetsize
    /// image, then the largest scale-N image. With <paramref name="light"/> only light-theme
    /// variants count (null when there is none).</summary>
    public static Variant? Pick(IReadOnlyList<Variant> variants, int size, bool light)
    {
        static Variant? BySize(IEnumerable<Variant> vs, int size)
        {
            var list = vs.Where(v => v.TargetSize != null).ToList();
            if (list.Count == 0) return null;
            return list.Where(v => v.TargetSize >= size).OrderBy(v => v.TargetSize).FirstOrDefault()
                   ?? list.OrderByDescending(v => v.TargetSize).First();
        }
        var pool = variants.Where(v => v.Light == light).ToList();
        return BySize(pool.Where(v => v.Unplated), size)
               ?? BySize(pool.Where(v => !v.Unplated), size)
               ?? (light ? null : pool.Where(v => v.TargetSize == null).OrderByDescending(v => v.Scale ?? 100).FirstOrDefault());
    }

    // ----------------------------------------------------------- manifest ---
    public sealed record AppEntry(string Id, string? Executable, string? DisplayName, string? Logo, bool InAppList);

    /// <summary>The applications of an AppxManifest.xml with their app list logo attribute.</summary>
    public static List<AppEntry> ReadManifest(string manifestPath)
    {
        var doc = XDocument.Load(manifestPath, LoadOptions.None);
        var apps = new List<AppEntry>();
        string? storeLogo = doc.Descendants().FirstOrDefault(e => e.Name.LocalName == "Properties")?
            .Elements().FirstOrDefault(e => e.Name.LocalName == "Logo")?.Value;
        foreach (var app in doc.Descendants().Where(e => e.Name.LocalName == "Application"))
        {
            var ve = app.Descendants().FirstOrDefault(e => e.Name.LocalName == "VisualElements");
            string? A(XElement? e, string n) => e?.Attributes().FirstOrDefault(a => a.Name.LocalName == n)?.Value;
            var logo = A(ve, "Square44x44Logo") ?? A(ve, "Square30x30Logo") ?? A(ve, "Square150x150Logo") ?? storeLogo;
            apps.Add(new AppEntry(A(app, "Id") ?? "", A(app, "Executable"), A(ve, "DisplayName"), logo,
                                  !string.Equals(A(ve, "AppListEntry"), "none", StringComparison.OrdinalIgnoreCase)));
        }
        return apps;
    }

    static string Squash(string? s) => s == null ? "" : Regex.Replace(s.ToLowerInvariant(), "[^a-z0-9]", "");

    /// <summary>The application a hint such as "Get Started" names (matched against Id, Executable
    /// and DisplayName); without a hint the first one shown in the app list. Null when a hint
    /// matches nothing: the caller reports it instead of guessing.</summary>
    public static AppEntry? ChooseApp(IReadOnlyList<AppEntry> apps, string? hint)
    {
        var withLogo = apps.Where(a => !string.IsNullOrEmpty(a.Logo)).ToList();
        if (string.IsNullOrWhiteSpace(hint))
            return withLogo.FirstOrDefault(a => a.InAppList) ?? withLogo.FirstOrDefault();
        var h = Squash(hint);
        return withLogo.FirstOrDefault(a => Squash(a.Id) == h)
               ?? withLogo.FirstOrDefault(a => Squash(a.Id).Contains(h) || Squash(a.DisplayName).Contains(h)
                                               || Squash(Path.GetFileNameWithoutExtension(a.Executable)).Contains(h));
    }

    // ----------------------------------------------------------- packages ---
    const int ERROR_SUCCESS = 0, ERROR_INSUFFICIENT_BUFFER = 122;

    /// <summary>Install folders of every package of <paramref name="family"/> registered for the
    /// current user (the main package first, then resource packages), or an empty list.</summary>
    public static List<string> PackageFolders(string family)
    {
        var result = new List<string>();
        if (!OperatingSystem.IsWindowsVersionAtLeast(6, 3)) return result;
        try
        {
            uint count = 0, len = 0;
            int rc = GetPackagesByPackageFamily(family, ref count, IntPtr.Zero, ref len, IntPtr.Zero);
            if (rc != ERROR_INSUFFICIENT_BUFFER || count == 0) return result;
            IntPtr names = Marshal.AllocHGlobal((int)count * IntPtr.Size);
            IntPtr buf = Marshal.AllocHGlobal((int)len * 2);
            try
            {
                rc = GetPackagesByPackageFamily(family, ref count, names, ref len, buf);
                if (rc != ERROR_SUCCESS) return result;
                var full = new List<string>();
                for (int i = 0; i < count; i++)
                    if (Marshal.PtrToStringUni(Marshal.ReadIntPtr(names, i * IntPtr.Size)) is { Length: > 0 } s) full.Add(s);
                // Resource packages ("..._neutral_split.scale-200_...", "...~_...") after the main one.
                foreach (var fn in full.OrderBy(f => f.Contains("_split.", StringComparison.OrdinalIgnoreCase) || f.Contains('~') ? 1 : 0))
                {
                    uint plen = 0;
                    if (GetPackagePathByFullName(fn, ref plen, null) != ERROR_INSUFFICIENT_BUFFER || plen == 0) continue;
                    var path = new char[plen];
                    if (GetPackagePathByFullName(fn, ref plen, path) != ERROR_SUCCESS) continue;
                    var p = new string(path, 0, (int)Math.Max(0, plen - 1)).TrimEnd('\0');
                    if (Directory.Exists(p)) result.Add(p);
                }
            }
            finally
            {
                Marshal.FreeHGlobal(names);
                Marshal.FreeHGlobal(buf);
            }
        }
        catch (Exception e) when (e is EntryPointNotFoundException or DllNotFoundException or MarshalDirectiveException)
        {
            // Older Windows or Wine without the packaging APIs: the caller falls back to SystemApps.
        }
        return result;
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, ExactSpelling = true)]
    static extern int GetPackagesByPackageFamily(string packageFamilyName, ref uint count, IntPtr packageFullNames, ref uint bufferLength, IntPtr buffer);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, ExactSpelling = true)]
    static extern int GetPackagePathByFullName(string packageFullName, ref uint pathLength, [Out] char[]? path);
}
