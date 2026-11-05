using System.Drawing;
using System.Drawing.Drawing2D;
using System.Runtime.InteropServices;

namespace FenestraIconExtractor;

/// <summary>Windows 11 colours for light and dark mode, following the system setting and accent.</summary>
sealed class Theme
{
    public bool Dark { get; init; }
    public Color Background { get; init; }
    public Color Card { get; init; }
    public Color CardBorder { get; init; }
    public Color Text { get; init; }
    public Color SubText { get; init; }
    public Color Control { get; init; }
    public Color ControlHover { get; init; }
    public Color ControlPressed { get; init; }
    public Color ControlBorder { get; init; }
    public Color Accent { get; init; }
    public Color AccentHover { get; init; }
    public Color OnAccent { get; init; }
    public Color Track { get; init; }

    public static Theme Current()
    {
        bool dark = !WindowsInfo.AppsUseLightTheme;
        var pal = WindowsInfo.Palette;
        var baseAccent = WindowsInfo.Accent;
        // Windows uses AccentDark1 on light surfaces and AccentLight2 on dark ones.
        var accent = pal != null ? (dark ? pal[1] : pal[4])
                   : dark ? Blend(baseAccent, Color.White, 0.45) : Blend(baseAccent, Color.Black, 0.15);
        var hover = pal != null ? (dark ? pal[2] : pal[5]) : Blend(accent, dark ? Color.Black : Color.White, 0.1);
        return dark
            ? new Theme
            {
                Dark = true, Background = C(0x202020), Card = C(0x2B2B2B), CardBorder = C(0x1C1C1C),
                Text = C(0xFFFFFF), SubText = C(0xCFCFCF), Control = C(0x373737), ControlHover = C(0x3D3D3D),
                ControlPressed = C(0x323232), ControlBorder = C(0x444444), Accent = accent, AccentHover = hover,
                OnAccent = Color.Black, Track = C(0x9A9A9A),
            }
            : new Theme
            {
                Dark = false, Background = C(0xF3F3F3), Card = C(0xFBFBFB), CardBorder = C(0xE5E5E5),
                Text = C(0x1B1B1B), SubText = C(0x5F5F5F), Control = C(0xFEFEFE), ControlHover = C(0xF6F6F6),
                ControlPressed = C(0xF0F0F0), ControlBorder = C(0xD5D5D5), Accent = accent, AccentHover = hover,
                OnAccent = Color.White, Track = C(0x8A8A8A),
            };
    }

    static Color C(int rgb) => Color.FromArgb((rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF);

    public static Color Blend(Color a, Color b, double t) => Color.FromArgb(
        (int)(a.R + (b.R - a.R) * t), (int)(a.G + (b.G - a.G) * t), (int)(a.B + (b.B - a.B) * t));

    public static GraphicsPath Round(RectangleF r, float radius)
    {
        var p = new GraphicsPath();
        float d = Math.Min(radius * 2, Math.Min(r.Width, r.Height));
        if (d <= 0) { p.AddRectangle(r); return p; }
        p.AddArc(r.X, r.Y, d, d, 180, 90);
        p.AddArc(r.Right - d, r.Y, d, d, 270, 90);
        p.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
        p.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
        p.CloseFigure();
        return p;
    }

    public static Font UiFont(float size, FontStyle style = FontStyle.Regular, bool display = false)
    {
        foreach (var name in new[] { display ? "Segoe UI Variable Display" : "Segoe UI Variable Text", "Segoe UI" })
        {
            var f = new Font(name, size, style, GraphicsUnit.Point);
            if (f.Name == name) return f;
            f.Dispose();
        }
        return new Font(FontFamily.GenericSansSerif, size, style, GraphicsUnit.Point);
    }

    // ------------------------------------------------------------ DWM frame ---
    [DllImport("dwmapi.dll")]
    static extern int DwmSetWindowAttribute(IntPtr hwnd, int attr, ref int value, int size);

    const int DWMWA_USE_IMMERSIVE_DARK_MODE = 20;
    const int DWMWA_WINDOW_CORNER_PREFERENCE = 33;
    const int DWMWA_SYSTEMBACKDROP_TYPE = 38;

    /// <summary>Dark title bar, rounded corners and the Mica backdrop (Windows 11 22H2+).
    /// Silently does nothing on systems without these attributes.</summary>
    public static void ApplyFrame(IntPtr hwnd, bool dark)
    {
        try
        {
            int on = dark ? 1 : 0;
            DwmSetWindowAttribute(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ref on, sizeof(int));
            int round = 2;
            DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ref round, sizeof(int));
            int mica = 2;
            DwmSetWindowAttribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE, ref mica, sizeof(int));
        }
        catch (Exception) { /* dwmapi missing (e.g. Wine without DWM) */ }
    }
}
