using System.Diagnostics;
using System.Drawing;
using Microsoft.Win32;

namespace FenestraIconExtractor;

sealed class MainForm : Form
{
    readonly Label _title = new() { Text = "Fenestra Icon Extractor", AutoSize = false };
    readonly Label _intro = new()
    {
        AutoSize = false,
        Text = "Exports the fonts, cursors and system icons of this Windows installation into a Fenestra icon pack " +
               "(.zip), so Fenestra OS can look like your own Windows. Import the pack in Fenestra OS. " +
               "Nothing is uploaded and nothing on this PC is changed: Windows is only read.",
    };
    readonly Label _whatHeader = new() { Text = "What to export", AutoSize = false };
    readonly Card _card = new();
    readonly FluentCheck _fonts = Check("Fonts", "Segoe UI, Segoe UI Variable, Segoe Fluent Icons and Consolas", true);
    readonly FluentCheck _cursors = Check("Mouse pointers", "Windows Aero cursors and your current pointer scheme", true);
    readonly FluentCheck _icons = Check("System icons", "Folders, This PC, drives, Recycle Bin and file types, as an icon theme", true);
    readonly FluentCheck _folders = Check("File Explorer folder icons", "Empty and full folder artwork", true);
    readonly FluentCheck _taskbar = Check("Start button and Search icon", "The Windows logo and the colour taskbar search icon", true);
    readonly FluentCheck _apps = Check("App icons", "Settings, Task Manager and File Explorer", true);
    readonly FluentCheck _battery = Check("Battery glyphs", "The taskbar battery icon font (Sysbatt.ttf)", true);
    readonly FluentCheck _wall = Check("Wallpaper and lock screen picture", "Your current desktop background and lock screen image", false);
    readonly Label _destHeader = new() { Text = "Save the pack to", AutoSize = false };
    readonly FluentField _dest = new();
    readonly FluentButton _browse = new() { Text = "Browse…" };
    readonly FluentProgress _progress = new();
    readonly Label _status = new() { AutoSize = false, Text = "Ready." };
    readonly FluentField _log = new(multiline: true);
    readonly Label _legal = new()
    {
        AutoSize = false,
        Text = "For use with your own Windows licence. Don't redistribute the exported pack.",
    };
    readonly FluentButton _open = new() { Text = "Open folder", Enabled = false };
    readonly FluentButton _export = new() { Text = "Export", Accent = true };
    FluentCheck[] Checks => new[] { _fonts, _cursors, _icons, _folders, _taskbar, _apps, _battery, _wall };

    Theme _theme = Theme.Current();
    string? _lastZip;
    bool _busy;

    static FluentCheck Check(string title, string desc, bool on) => new() { Text = title, Description = desc, Checked = on };

    public MainForm()
    {
        Text = "Fenestra Icon Extractor";
        AutoScaleMode = AutoScaleMode.None; // layout is computed from DeviceDpi below
        StartPosition = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.Sizable;
        MaximizeBox = true;
        AutoScroll = true;
        DoubleBuffered = true;
        try { if (Environment.ProcessPath is { } exe) Icon = Icon.ExtractAssociatedIcon(exe); } catch (Exception) { }

        _card.Controls.AddRange(Checks);
        _dest.Box.Text = ExportOptions.DefaultDestination;
        _dest.Box.AccessibleName = "Destination file";
        _log.Box.AccessibleName = "Export log";
        Controls.AddRange(new Control[] { _title, _intro, _whatHeader, _card, _destHeader, _dest, _browse, _progress, _status, _log, _legal, _open, _export });
        AcceptButton = _export;

        _browse.Click += (_, _) => Browse();
        _export.Click += async (_, _) => await ExportAsync();
        _open.Click += (_, _) => OpenFolder();
        SystemEvents.UserPreferenceChanged += OnUserPreferenceChanged;

        ApplyFonts();
        ApplyTheme(Theme.Current());
        SetInitialSize();
    }

    protected override void Dispose(bool disposing)
    {
        if (disposing) SystemEvents.UserPreferenceChanged -= OnUserPreferenceChanged;
        base.Dispose(disposing);
    }

    float S => DeviceDpi / 96f;

    void ApplyFonts()
    {
        Font = Theme.UiFont(10.5f);
        _title.Font = Theme.UiFont(20f, FontStyle.Bold, display: true);
        _whatHeader.Font = _destHeader.Font = Theme.UiFont(10.5f, FontStyle.Bold);
        foreach (var c in Checks) c.Font = Font;
        _legal.Font = _status.Font = Theme.UiFont(9f);
        _log.Font = Theme.UiFont(9f);
    }

    void ApplyTheme(Theme t)
    {
        _theme = t;
        BackColor = t.Background;
        ForeColor = t.Text;
        foreach (Control c in Controls)
        {
            if (c is Label l) { l.BackColor = t.Background; l.ForeColor = t.Text; }
            if (c is IThemed th) th.ApplyTheme(t);
        }
        _intro.ForeColor = _legal.ForeColor = _status.ForeColor = t.SubText;
        foreach (var c in Checks) { c.ApplyTheme(t); c.BackColor = t.Card; }
        if (IsHandleCreated) Theme.ApplyFrame(Handle, t.Dark);
        Invalidate(true);
    }

    void OnUserPreferenceChanged(object? sender, UserPreferenceChangedEventArgs e)
    {
        if (e.Category is UserPreferenceCategory.General or UserPreferenceCategory.Color or UserPreferenceCategory.VisualStyle)
        {
            if (IsHandleCreated) BeginInvoke(() => ApplyTheme(Theme.Current()));
        }
    }

    protected override void OnHandleCreated(EventArgs e)
    {
        base.OnHandleCreated(e);
        Theme.ApplyFrame(Handle, _theme.Dark);
    }

    protected override void OnDpiChanged(DpiChangedEventArgs e)
    {
        base.OnDpiChanged(e);
        ApplyFonts();
        PerformLayout();
    }

    void SetInitialSize()
    {
        int w = (int)(700 * S);
        int h = LayoutAll(w, apply: false);
        var screen = Screen.FromPoint(Cursor.Position).WorkingArea;
        ClientSize = new Size(Math.Min(w, screen.Width - 40), Math.Min(h, screen.Height - 60));
        MinimumSize = new Size((int)(520 * S), (int)(420 * S));
    }

    protected override void OnLayout(LayoutEventArgs e)
    {
        base.OnLayout(e);
        if (_title != null) LayoutAll(ClientSize.Width - (VerticalScroll.Visible ? SystemInformation.VerticalScrollBarWidth : 0), apply: true);
    }

    static int TextHeight(Label l, int width) =>
        TextRenderer.MeasureText(l.Text, l.Font, new Size(width, int.MaxValue), TextFormatFlags.WordBreak | TextFormatFlags.NoPrefix).Height;

    /// <summary>Stacks everything in a single column; returns the total height.</summary>
    int LayoutAll(int width, bool apply)
    {
        int m = (int)(28 * S), gap = (int)(8 * S), y = (int)(20 * S) + AutoScrollPosition.Y;
        int inner = Math.Max(200, width - 2 * m);
        void Place(Control c, int x, int top, int w, int h) { if (apply) c.Bounds = new Rectangle(x, top, w, h); }
        void Text(Label l, int extra = 0)
        {
            int h = TextHeight(l, inner);
            Place(l, m, y, inner, h);
            y += h + extra;
        }
        Text(_title, (int)(4 * S));
        Text(_intro, (int)(18 * S));
        Text(_whatHeader, gap);

        int pad = (int)(16 * S), cy = (int)(10 * S);
        int checkW = inner - 2 * pad;
        foreach (var c in Checks)
        {
            int h = c.GetPreferredSize(new Size(checkW, 0)).Height;
            if (apply) c.Bounds = new Rectangle(pad, cy, checkW, h);
            cy += h + (int)(2 * S);
        }
        cy += (int)(8 * S);
        Place(_card, m, y, inner, cy);
        y += cy + (int)(18 * S);

        Text(_destHeader, gap);
        var bsz = _browse.GetPreferredSize(Size.Empty);
        int fh = Math.Max(bsz.Height, _dest.GetPreferredSize(new Size(inner, 0)).Height);
        Place(_dest, m, y, inner - bsz.Width - gap, fh);
        Place(_browse, m + inner - bsz.Width, y, bsz.Width, fh);
        y += fh + (int)(18 * S);

        Place(_progress, m, y, inner, (int)(8 * S));
        y += (int)(12 * S);
        Text(_status, (int)(6 * S));
        int lh = (int)(120 * S);
        Place(_log, m, y, inner, lh);
        y += lh + (int)(18 * S);

        var esz = _export.GetPreferredSize(Size.Empty);
        var osz = _open.GetPreferredSize(Size.Empty);
        int bw = esz.Width + osz.Width + gap;
        int legalW = Math.Max(120, inner - bw - 2 * gap);
        int legalH = TextRenderer.MeasureText(_legal.Text, _legal.Font, new Size(legalW, int.MaxValue), TextFormatFlags.WordBreak).Height;
        int rowH = Math.Max(esz.Height, legalH);
        Place(_legal, m, y + (rowH - legalH) / 2, legalW, legalH);
        Place(_open, m + inner - bw, y + (rowH - osz.Height) / 2, osz.Width, osz.Height);
        Place(_export, m + inner - esz.Width, y + (rowH - esz.Height) / 2, esz.Width, esz.Height);
        y += rowH + (int)(22 * S);
        return y - AutoScrollPosition.Y;
    }

    void Browse()
    {
        using var dlg = new SaveFileDialog
        {
            Title = "Save Fenestra icon pack",
            Filter = "Fenestra icon pack (*.zip)|*.zip",
            DefaultExt = "zip",
            AddExtension = true,
            OverwritePrompt = true,
        };
        try
        {
            var cur = _dest.Box.Text.Trim();
            dlg.FileName = Path.GetFileName(cur);
            var dir = Path.GetDirectoryName(cur);
            if (!string.IsNullOrEmpty(dir) && Directory.Exists(dir)) dlg.InitialDirectory = dir;
        }
        catch (Exception) { }
        if (dlg.ShowDialog(this) == DialogResult.OK) _dest.Box.Text = dlg.FileName;
    }

    void Log(string line)
    {
        _log.Box.AppendText((_log.Box.TextLength > 0 ? Environment.NewLine : "") + line);
    }

    void SetBusy(bool busy)
    {
        _busy = busy;
        _export.Enabled = _browse.Enabled = !busy;
        _dest.Box.ReadOnly = busy;
        foreach (var c in Checks) c.Enabled = !busy;
        UseWaitCursor = busy;
    }

    internal Task ExportForTest(string dest)
    {
        if (File.Exists(dest)) File.Delete(dest);
        _dest.Box.Text = dest;
        return ExportAsync();
    }

    async Task ExportAsync()
    {
        if (_busy) return;
        var dest = _dest.Box.Text.Trim().Trim('"');
        if (dest.Length == 0) { Browse(); return; }
        if (!dest.EndsWith(".zip", StringComparison.OrdinalIgnoreCase)) dest += ".zip";
        try { dest = Path.GetFullPath(Environment.ExpandEnvironmentVariables(dest)); }
        catch (Exception) { MessageBox.Show(this, "That isn't a valid file path.", Text, MessageBoxButtons.OK, MessageBoxIcon.Warning); return; }
        if (!Checks.Any(c => c.Checked)) { MessageBox.Show(this, "Choose at least one thing to export.", Text, MessageBoxButtons.OK, MessageBoxIcon.Information); return; }
        if (File.Exists(dest) && MessageBox.Show(this, $"{Path.GetFileName(dest)} already exists. Replace it?", Text,
                MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes) return;
        _dest.Box.Text = dest;

        var opts = new ExportOptions
        {
            Fonts = _fonts.Checked, Cursors = _cursors.Checked, SystemIcons = _icons.Checked, FolderIcons = _folders.Checked,
            Taskbar = _taskbar.Checked, AppIcons = _apps.Checked, Battery = _battery.Checked, Wallpapers = _wall.Checked,
            Destination = dest,
        };
        SetBusy(true);
        _open.Enabled = false;
        _log.Box.Clear();
        _progress.Value = 0;
        _status.Text = "Exporting…";
        var progress = new Progress<ExportProgress>(p =>
        {
            if (p.Percent >= 0) { _progress.Value = p.Percent; if (p.Message != null) _status.Text = p.Message; }
            if (p.Message != null) Log(p.Message);
        });
        try
        {
            var r = await Task.Run(() => new Exporter(opts, progress).Run());
            await Task.Yield();
            _progress.Value = 100;
            _lastZip = r.Path;
            _status.Text = r.Missing == 0
                ? $"Done. {r.Files} files, {r.Bytes / 1048576.0:0.0} MB."
                : $"Done. {r.Files} files, {r.Bytes / 1048576.0:0.0} MB ({r.Missing} items not found on this PC).";
            _open.Enabled = true;
            _open.Focus();
        }
        catch (Exception ex)
        {
            _progress.Value = 0;
            _status.Text = "Export failed.";
            Log("Export failed: " + ex.Message);
            MessageBox.Show(this, "The export failed:\n\n" + ex.Message, Text, MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
        finally
        {
            SetBusy(false);
        }
    }

    void OpenFolder()
    {
        if (_lastZip == null) return;
        try
        {
            if (File.Exists(_lastZip))
                Process.Start(new ProcessStartInfo("explorer.exe", $"/select,\"{_lastZip}\"") { UseShellExecute = false });
            else if (Path.GetDirectoryName(_lastZip) is { } dir)
                Process.Start(new ProcessStartInfo(dir) { UseShellExecute = true });
        }
        catch (Exception ex) { Log("Could not open the folder: " + ex.Message); }
    }
}
