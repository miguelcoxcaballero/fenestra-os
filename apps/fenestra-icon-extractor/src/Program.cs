using System.Runtime.InteropServices;

namespace FenestraIconExtractor;

static class Program
{
    const string Usage =
        "FenestraIconExtractor.exe [--export PACK.zip] [--no-fonts] [--no-cursors] [--no-icons] [--no-folders]\n" +
        "                          [--no-taskbar] [--no-apps] [--no-battery] [--wallpapers] [--log FILE]\n" +
        "                          [--no-glyphs] [--all-glyphs] [--no-package-logos] [--no-bitmaps] [--probe-modules]\n" +
        "Without --export the window opens. Windows is only read; only PACK.zip is written.";

    [STAThread]
    static int Main(string[] args)
    {
        if (args.Length >= 2 && args[0] == "--screenshot") return Screenshot(args[1], args.Length >= 3 ? args[2] : null);
        if (args.Length > 0) return RunCli(args);
        ApplicationConfiguration.Initialize();
        Application.Run(new MainForm());
        return 0;
    }

    [DllImport("kernel32.dll")]
    static extern bool AttachConsole(int pid);

    /// <summary>Test hook: renders the window (optionally after an export to <paramref name="exportTo"/>) to a PNG.</summary>
    static int Screenshot(string png, string? exportTo)
    {
        ApplicationConfiguration.Initialize();
        using var f = new MainForm();
        f.Shown += async (_, _) =>
        {
            await Task.Delay(800);
            if (exportTo != null) await f.ExportForTest(exportTo);
            await Task.Delay(500);
            using var bmp = new System.Drawing.Bitmap(f.ClientSize.Width, f.ClientSize.Height);
            using (var g = System.Drawing.Graphics.FromImage(bmp))
            {
                g.Clear(f.BackColor);
                foreach (Control c in f.Controls.Cast<Control>().Reverse()) Capture(c, g, c.Location);
            }
            bmp.Save(png, System.Drawing.Imaging.ImageFormat.Png);
            f.Close();
        };
        Application.Run(f);
        return 0;
    }

    static void Capture(Control c, System.Drawing.Graphics g, System.Drawing.Point at)
    {
        if (!c.Visible || c.Width <= 0 || c.Height <= 0) return;
        using (var b = new System.Drawing.Bitmap(c.Width, c.Height))
        {
            c.DrawToBitmap(b, new System.Drawing.Rectangle(0, 0, c.Width, c.Height));
            g.DrawImage(b, at);
        }
        foreach (Control k in c.Controls.Cast<Control>().Reverse())
            Capture(k, g, new System.Drawing.Point(at.X + k.Left, at.Y + k.Top));
    }

    /// <summary>Headless export for scripted runs (and automated tests).</summary>
    static int RunCli(string[] args)
    {
        AttachConsole(-1);
        var o = new ExportOptions();
        string? logFile = null;
        bool export = false;
        for (int i = 0; i < args.Length; i++)
        {
            switch (args[i].ToLowerInvariant())
            {
                case "--export" when i + 1 < args.Length: o.Destination = args[++i]; export = true; break;
                case "--log" when i + 1 < args.Length: logFile = args[++i]; break;
                case "--no-fonts": o.Fonts = false; break;
                case "--no-cursors": o.Cursors = false; break;
                case "--no-icons": o.SystemIcons = false; break;
                case "--no-folders": o.FolderIcons = false; break;
                case "--no-taskbar": o.Taskbar = false; break;
                case "--no-apps": o.AppIcons = false; break;
                case "--no-battery": o.Battery = false; break;
                case "--wallpapers": o.Wallpapers = true; break;
                case "--no-glyphs": o.Glyphs = false; break;
                case "--all-glyphs": o.AllGlyphs = true; break;
                case "--no-package-logos": o.PackageLogos = false; break;
                case "--no-bitmaps": o.ReferenceBitmaps = false; break;
                case "--probe-modules": o.ProbeModules = true; break;
                default: Console.WriteLine(Usage); return 2;
            }
        }
        if (!export) { Console.WriteLine(Usage); return 2; }
        using var log = logFile != null ? new StreamWriter(logFile, append: false) { AutoFlush = true } : null;
        void Write(string s) { Console.WriteLine(s); log?.WriteLine(s); }
        var progress = new SyncProgress(p => { if (p.Message != null) Write(p.Message); });
        try
        {
            var r = new Exporter(o, progress).Run();
            Write($"OK files={r.Files} bytes={r.Bytes} missing={r.Missing} path={r.Path}");
            return 0;
        }
        catch (Exception e)
        {
            Write("FAILED: " + e);
            return 1;
        }
    }

    sealed class SyncProgress(Action<ExportProgress> a) : IProgress<ExportProgress>
    {
        public void Report(ExportProgress value) => a(value);
    }
}
