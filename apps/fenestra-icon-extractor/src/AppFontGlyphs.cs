namespace FenestraIconExtractor;

/// <summary>
/// Icon fonts that Windows apps carry in their own packages (Paint, Snipping Tool, Settings, Store,
/// Weather), and the icons.json glyphs that have no Segoe Fluent Icons code point but are drawn from
/// one of them. Names, file names and code points only: no outlines. The code points were found by
/// shape on the Windows 11 reference screenshots (normalised correlation of the ink, ≥ 0.9 except the
/// ones marked unverified) and checked by eye; see docs/ICON-PACK-FORMAT.md.
/// </summary>
public static class AppFontGlyphs
{
    public sealed record AppFont(string File, string? Family, string[] Fallbacks);

    public static readonly AppFont[] Fonts =
    {
        new("PaintIcons.ttf", "Microsoft.Paint_8wekyb3d8bbwe", System.Array.Empty<string>()),
        new("SnSkFluent.ttf", "Microsoft.ScreenSketch_8wekyb3d8bbwe", System.Array.Empty<string>()),
        new("SettingsIcons.ttf", null, new[]
        {
            @"SystemApps\MicrosoftWindows.Client.Core_cw5n1h2txyewy\ValueBanner\Assets\Fonts\SettingsIcons.ttf",
            @"SystemApps\MicrosoftWindows.Client.CBS_cw5n1h2txyewy\VisualAssist\Assets\Fonts\SettingsIcons.ttf",
        }),
        new("StoreIcons.ttf", "Microsoft.WindowsStore_8wekyb3d8bbwe", new[]
        {
            @"SystemApps\MicrosoftWindows.Client.CBS_cw5n1h2txyewy\WindowsBackup\Assets\StoreIcons.ttf",
        }),
        new("WeatherColorIcons.ttf", "Microsoft.BingWeather_8wekyb3d8bbwe", System.Array.Empty<string>()),
        new("Sysbatt.ttf", null, new[] { @"SystemApps\MicrosoftWindows.Client.Core_cw5n1h2txyewy\SystemTray\Assets\Sysbatt.ttf" }),
    };

    /// <summary>icons.json glyph name -> (font file, code point, verified).</summary>
    public static readonly Dictionary<string, (string Font, int CodePoint, bool Verified)> Glyphs = new()
    {
        ["document-edit"] = ("SnSkFluent.ttf", 0xEF77, true),
        ["edit-select-invert"] = ("PaintIcons.ttf", 0xE65E, true),
        ["document-import"] = ("PaintIcons.ttf", 0xE89D, true),
        ["image-properties"] = ("PaintIcons.ttf", 0xF3F0, true),
        ["edit-copy-layers"] = ("PaintIcons.ttf", 0xF194, true),
        ["view-thumbnail"] = ("PaintIcons.ttf", 0xE661, true),
        ["object-rotate-right"] = ("PaintIcons.ttf", 0xE663, true),
        ["object-rotate-left"] = ("PaintIcons.ttf", 0xE662, true),
        ["object-rotate-180"] = ("PaintIcons.ttf", 0xE664, true),
        ["object-flip-vertical"] = ("PaintIcons.ttf", 0xE300, true),
        ["object-flip-horizontal"] = ("PaintIcons.ttf", 0xEF33, true),
        ["image-creator"] = ("PaintIcons.ttf", 0xE344, true),
        ["generative-erase"] = ("PaintIcons.ttf", 0xE342, true),
        ["shape-outline"] = ("PaintIcons.ttf", 0xE666, true),
        ["shape-fill"] = ("PaintIcons.ttf", 0xF42B, true),
        ["zoom-fit-window"] = ("PaintIcons.ttf", 0xE45E, true),
        ["shape-line"] = ("SnSkFluent.ttf", 0xF4FC, false),
        ["shape-rounded-rectangle"] = ("SegoeIcons.ttf", 0xE71A, false),
        ["cursor-position"] = ("SettingsIcons.ttf", 0xE3B3, false),
        ["apps-default"] = ("SettingsIcons.ttf", 0xE42A, true),
        ["apps-for-websites"] = ("SettingsIcons.ttf", 0xF6AB, true),
        ["windows-backup-symbolic"] = ("SettingsIcons.ttf", 0xEE6E, true),
        ["display-hdr"] = ("SettingsIcons.ttf", 0xEA7F, true),
        ["notifications-scheduled"] = ("SettingsIcons.ttf", 0xECC1, true),
        ["theme-mode"] = ("SettingsIcons.ttf", 0xE795, true),
        ["desktop-icons-settings"] = ("SettingsIcons.ttf", 0xE328, true),
        ["view-apps-filled"] = ("StoreIcons.ttf", 0xE635, true),
        ["applications-games-filled"] = ("StoreIcons.ttf", 0xE637, true),
    };

    /// <summary>Why the remaining icons.json glyphs are not exported.</summary>
    public static string Unresolved(string name) => name.StartsWith("shape-", StringComparison.Ordinal)
        ? "Paint draws its shape gallery as vector shapes, not from a font (no glyph in PaintIcons.ttf or SegoeIcons.ttf)"
        : "no glyph of SegoeIcons.ttf, PaintIcons.ttf, SnSkFluent.ttf, SettingsIcons.ttf or StoreIcons.ttf matches the reference shape";

    /// <summary>Where <paramref name="font"/> is on this PC (registered package of the family, then the fallbacks).</summary>
    public static string? Locate(AppFont font, string windowsDir)
    {
        if (font.Family != null)
        {
            foreach (var dir in AppxLogos.PackageFolders(font.Family))
            {
                try
                {
                    var hit = Directory.EnumerateFiles(dir, font.File, SearchOption.AllDirectories).OrderBy(f => f.Length).FirstOrDefault();
                    if (hit != null) return hit;
                }
                catch (Exception) { /* access denied in a subfolder */ }
            }
        }
        foreach (var rel in font.Fallbacks)
        {
            var p = Path.Combine(windowsDir, rel);
            if (File.Exists(p)) return p;
        }
        return null;
    }
}
