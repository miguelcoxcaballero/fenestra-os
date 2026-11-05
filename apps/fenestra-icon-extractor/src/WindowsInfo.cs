using System.Drawing;
using System.Globalization;
using Microsoft.Win32;

namespace FenestraIconExtractor;

/// <summary>Read-only facts about this Windows installation (registry + well-known folders).</summary>
static class WindowsInfo
{
    public static string WindowsDir =>
        Environment.GetFolderPath(Environment.SpecialFolder.Windows) is { Length: > 0 } w ? w : @"C:\Windows";

    static object? Reg(RegistryKey root, string key, string value)
    {
        try
        {
            using var k = root.OpenSubKey(key, false);
            return k?.GetValue(value);
        }
        catch (Exception) { return null; }
    }

    public static string? RegString(RegistryKey root, string key, string value) => Reg(root, key, value) as string;

    const string CurrentVersion = @"SOFTWARE\Microsoft\Windows NT\CurrentVersion";

    public static string Build
    {
        get
        {
            var build = RegString(Registry.LocalMachine, CurrentVersion, "CurrentBuildNumber")
                        ?? RegString(Registry.LocalMachine, CurrentVersion, "CurrentBuild")
                        ?? Environment.OSVersion.Version.Build.ToString(CultureInfo.InvariantCulture);
            return Reg(Registry.LocalMachine, CurrentVersion, "UBR") is int ubr ? $"{build}.{ubr}" : build;
        }
    }

    public static int BuildNumber => int.TryParse(Build.Split('.')[0], out var b) ? b : 0;

    /// <summary>ProductName still says "Windows 10" on Windows 11, so decide by build number.</summary>
    public static string OsName => BuildNumber >= 22000 ? "Windows 11" : BuildNumber > 0 ? "Windows 10" : "Windows";

    public static string? Edition => RegString(Registry.LocalMachine, CurrentVersion, "EditionID");
    public static string? DisplayVersion => RegString(Registry.LocalMachine, CurrentVersion, "DisplayVersion");

    public static string Locale
    {
        get
        {
            var ui = CultureInfo.CurrentUICulture.Name;
            if (!string.IsNullOrEmpty(ui)) return ui;
            return RegString(Registry.CurrentUser, @"Control Panel\International", "LocaleName") ?? "en-US";
        }
    }

    public static bool AppsUseLightTheme =>
        Reg(Registry.CurrentUser, @"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "AppsUseLightTheme") is not int v || v != 0;

    /// <summary>The accent colour the user chose (DWM AccentColor is 0xAABBGGRR).</summary>
    public static Color Accent
    {
        get
        {
            if (Reg(Registry.CurrentUser, @"Software\Microsoft\Windows\DWM", "AccentColor") is int abgr)
            {
                uint v = unchecked((uint)abgr);
                return Color.FromArgb((int)(v & 0xFF), (int)((v >> 8) & 0xFF), (int)((v >> 16) & 0xFF));
            }
            var pal = Palette;
            if (pal != null) return pal[3];
            if (Reg(Registry.CurrentUser, @"Software\Microsoft\Windows\DWM", "ColorizationColor") is int argb)
                return Color.FromArgb(255, Color.FromArgb(argb));
            return Color.FromArgb(0x00, 0x78, 0xD4);
        }
    }

    /// <summary>Explorer\Accent AccentPalette: 8 RGBA colours, light3..base(3)..dark3.</summary>
    public static Color[]? Palette
    {
        get
        {
            if (Reg(Registry.CurrentUser, @"Software\Microsoft\Windows\CurrentVersion\Explorer\Accent", "AccentPalette") is byte[] p && p.Length >= 32)
            {
                var c = new Color[8];
                for (int i = 0; i < 8; i++) c[i] = Color.FromArgb(p[4 * i], p[4 * i + 1], p[4 * i + 2]);
                return c;
            }
            return null;
        }
    }

    public static string Hex(Color c) => $"#{c.R:X2}{c.G:X2}{c.B:X2}";

    public static string? CursorSchemeName => RegString(Registry.CurrentUser, @"Control Panel\Cursors", "");

    /// <summary>HKCU\Control Panel\Cursors role -> file. Empty values mean the Windows default.</summary>
    public static Dictionary<string, string> CursorScheme()
    {
        var result = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        try
        {
            using var k = Registry.CurrentUser.OpenSubKey(@"Control Panel\Cursors", false);
            if (k == null) return result;
            foreach (var name in k.GetValueNames())
            {
                if (string.IsNullOrEmpty(name) || name == "Scheme Source" || name == "CursorBaseSize") continue;
                if (k.GetValue(name, null, RegistryValueOptions.DoNotExpandEnvironmentNames) is string s)
                    result[name] = s;
            }
        }
        catch (Exception) { }
        return result;
    }

    public static string? WallpaperPath => RegString(Registry.CurrentUser, @"Control Panel\Desktop", "WallPaper");

    public static string? LockScreenPath =>
        RegString(Registry.LocalMachine, @"SOFTWARE\Microsoft\Windows\CurrentVersion\PersonalizationCSP", "LockScreenImagePath")
        ?? RegString(Registry.LocalMachine, @"SOFTWARE\Policies\Microsoft\Windows\Personalization", "LockScreenImage");
}
