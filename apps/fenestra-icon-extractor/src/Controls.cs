using System.ComponentModel;
using System.Drawing;
using System.Drawing.Drawing2D;

namespace FenestraIconExtractor;

interface IThemed { void ApplyTheme(Theme t); }

/// <summary>Base for owner-drawn Fluent controls: double buffered, DPI-aware helpers.</summary>
abstract class FluentControl : Control, IThemed
{
    protected Theme T = Theme.Current();
    protected bool Hover, Pressed;

    protected FluentControl()
    {
        SetStyle(ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer |
                 ControlStyles.ResizeRedraw | ControlStyles.SupportsTransparentBackColor | ControlStyles.Selectable, true);
        BackColor = Color.Transparent;
    }

    protected float S => DeviceDpi / 96f;

    public virtual void ApplyTheme(Theme t) { T = t; Invalidate(); }

    protected override void OnMouseEnter(EventArgs e) { Hover = true; Invalidate(); base.OnMouseEnter(e); }
    protected override void OnMouseLeave(EventArgs e) { Hover = Pressed = false; Invalidate(); base.OnMouseLeave(e); }
    protected override void OnMouseDown(MouseEventArgs e) { if (e.Button == MouseButtons.Left) { Pressed = true; Focus(); Invalidate(); } base.OnMouseDown(e); }
    protected override void OnMouseUp(MouseEventArgs e) { Pressed = false; Invalidate(); base.OnMouseUp(e); }
    protected override void OnGotFocus(EventArgs e) { Invalidate(); base.OnGotFocus(e); }
    protected override void OnLostFocus(EventArgs e) { Invalidate(); base.OnLostFocus(e); }
    protected override void OnEnabledChanged(EventArgs e) { Invalidate(); base.OnEnabledChanged(e); }
    protected override void OnTextChanged(EventArgs e) { Invalidate(); base.OnTextChanged(e); }

    protected void DrawFocus(Graphics g, RectangleF r, float radius)
    {
        if (!Focused || !ShowFocusCues) return;
        using var pen = new Pen(T.Text, 2 * S);
        using var p = Theme.Round(RectangleF.Inflate(r, 2 * S, 2 * S), radius + 2 * S);
        g.DrawPath(pen, p);
    }
}

/// <summary>Windows 11 check box with a title and a secondary description line.</summary>
sealed class FluentCheck : FluentControl
{
    bool _checked;
    public string Description { get; set; } = "";

    public event EventHandler? CheckedChanged;

    [DefaultValue(false)]
    public bool Checked
    {
        get => _checked;
        set { if (_checked != value) { _checked = value; Invalidate(); CheckedChanged?.Invoke(this, EventArgs.Empty); AccessibilityNotifyClients(AccessibleEvents.StateChange, -1); } }
    }

    public FluentCheck()
    {
        TabStop = true;
        Cursor = Cursors.Hand;
        AccessibleRole = AccessibleRole.CheckButton;
    }

    Font DescFont => _desc ??= new Font(Font.FontFamily, Font.SizeInPoints * 0.88f, FontStyle.Regular, GraphicsUnit.Point);
    Font? _desc;
    protected override void OnFontChanged(EventArgs e) { _desc?.Dispose(); _desc = null; base.OnFontChanged(e); }

    float Box => 20 * S;
    float Gap => 12 * S;

    const TextFormatFlags Flags = TextFormatFlags.WordBreak | TextFormatFlags.NoPrefix | TextFormatFlags.Left;

    public override Size GetPreferredSize(Size proposed)
    {
        int w = proposed.Width > 0 && proposed.Width < 10000 ? proposed.Width : Width;
        int textW = Math.Max(50, w - (int)(Box + Gap));
        int h = TextRenderer.MeasureText(Text, Font, new Size(textW, int.MaxValue), Flags).Height;
        if (Description.Length > 0)
            h += TextRenderer.MeasureText(Description, DescFont, new Size(textW, int.MaxValue), Flags).Height;
        return new Size(w, (int)Math.Max(h, Box) + (int)(10 * S));
    }

    protected override void OnSizeChanged(EventArgs e)
    {
        base.OnSizeChanged(e);
        var want = GetPreferredSize(new Size(Width, 0)).Height;
        if (Height != want) Height = want;
    }

    protected override void OnClick(EventArgs e) { if (Enabled) Checked = !Checked; base.OnClick(e); }
    protected override void OnKeyUp(KeyEventArgs e) { if (e.KeyCode == Keys.Space && Enabled) Checked = !Checked; base.OnKeyUp(e); }

    protected override void OnPaint(PaintEventArgs e)
    {
        var g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        float top = 5 * S + 1;
        var box = new RectangleF(1 * S, top, Box, Box);
        float r = 4 * S;
        var text = Enabled ? T.Text : Color.FromArgb(110, T.Text);
        using (var p = Theme.Round(box, r))
        {
            if (Checked)
            {
                var fill = !Enabled ? Color.FromArgb(110, T.Accent) : Hover ? T.AccentHover : T.Accent;
                using var b = new SolidBrush(fill);
                g.FillPath(b, p);
                using var pen = new Pen(T.OnAccent, 1.6f * S) { StartCap = LineCap.Round, EndCap = LineCap.Round, LineJoin = LineJoin.Round };
                g.DrawLines(pen, new[]
                {
                    new PointF(box.X + box.Width * 0.27f, box.Y + box.Height * 0.52f),
                    new PointF(box.X + box.Width * 0.43f, box.Y + box.Height * 0.68f),
                    new PointF(box.X + box.Width * 0.74f, box.Y + box.Height * 0.34f),
                });
            }
            else
            {
                using var b = new SolidBrush(Hover && Enabled ? T.ControlHover : T.Control);
                g.FillPath(b, p);
                using var pen = new Pen(Enabled ? T.Track : Color.FromArgb(90, T.Track), 1 * S);
                g.DrawPath(pen, p);
            }
        }
        DrawFocus(g, box, r);
        int x = (int)(Box + Gap);
        var tr = new Rectangle(x, (int)(4 * S), Width - x, Height);
        var titleH = TextRenderer.MeasureText(Text, Font, new Size(tr.Width, int.MaxValue), Flags).Height;
        TextRenderer.DrawText(g, Text, Font, tr, text, Flags);
        if (Description.Length > 0)
        {
            var dr = new Rectangle(x, tr.Y + titleH, tr.Width, Height - tr.Y - titleH);
            TextRenderer.DrawText(g, Description, DescFont, dr, Enabled ? T.SubText : Color.FromArgb(110, T.SubText), Flags);
        }
    }
}

/// <summary>Windows 11 push button; <see cref="Accent"/> makes it the filled primary button.</summary>
sealed class FluentButton : FluentControl, IButtonControl
{
    public bool Accent { get; set; }
    public DialogResult DialogResult { get; set; }

    public FluentButton()
    {
        TabStop = true;
        AccessibleRole = AccessibleRole.PushButton;
    }

    public void NotifyDefault(bool value) { }
    public void PerformClick() { if (Enabled) OnClick(EventArgs.Empty); }

    public override Size GetPreferredSize(Size proposed)
    {
        var t = TextRenderer.MeasureText(Text, Font);
        return new Size(Math.Max((int)(120 * S), t.Width + (int)(40 * S)), Math.Max((int)(32 * S), t.Height + (int)(14 * S)));
    }

    protected override void OnKeyUp(KeyEventArgs e)
    {
        if (e.KeyCode is Keys.Space or Keys.Enter) PerformClick();
        base.OnKeyUp(e);
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        var g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        var r = new RectangleF(2 * S, 2 * S, Width - 4 * S - 1, Height - 4 * S - 1);
        float rad = 4 * S;
        Color fill, fg, border;
        if (Accent)
        {
            fill = !Enabled ? Color.FromArgb(T.Dark ? 60 : 40, T.Text) : Pressed ? Theme.Blend(T.Accent, T.Background, 0.2) : Hover ? T.AccentHover : T.Accent;
            fg = !Enabled ? Color.FromArgb(T.Dark ? 130 : 160, T.Text) : T.OnAccent;
            border = fill;
        }
        else
        {
            fill = !Enabled ? T.Control : Pressed ? T.ControlPressed : Hover ? T.ControlHover : T.Control;
            fg = Enabled ? T.Text : Color.FromArgb(110, T.Text);
            border = T.ControlBorder;
        }
        using (var p = Theme.Round(r, rad))
        {
            using var b = new SolidBrush(fill);
            g.FillPath(b, p);
            using var pen = new Pen(border, 1);
            g.DrawPath(pen, p);
        }
        DrawFocus(g, r, rad);
        TextRenderer.DrawText(g, Text, Font, Rectangle.Round(r), fg,
            TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.NoPrefix | TextFormatFlags.SingleLine);
    }
}

/// <summary>Thin Windows 11 progress bar.</summary>
sealed class FluentProgress : FluentControl
{
    int _value;
    public int Value { get => _value; set { _value = Math.Clamp(value, 0, 100); Invalidate(); } }

    public FluentProgress() { TabStop = false; SetStyle(ControlStyles.Selectable, false); }

    protected override void OnPaint(PaintEventArgs e)
    {
        var g = e.Graphics;
        g.SmoothingMode = SmoothingMode.AntiAlias;
        float cy = Height / 2f;
        using (var pen = new Pen(T.Track, 1 * S))
            g.DrawLine(pen, 1.5f * S, cy, Width - 1.5f * S, cy);
        if (_value > 0)
        {
            float h = 3 * S;
            var r = new RectangleF(0, cy - h / 2, Math.Max(h, (Width - 1) * _value / 100f), h);
            using var p = Theme.Round(r, h / 2);
            using var b = new SolidBrush(T.Accent);
            g.FillPath(b, p);
        }
    }
}

/// <summary>Rounded "card" surface used to group settings.</summary>
sealed class Card : Panel, IThemed
{
    Theme _t = Theme.Current();

    public Card()
    {
        SetStyle(ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true);
    }

    public void ApplyTheme(Theme t) { _t = t; BackColor = t.Background; Invalidate(); }

    protected override void OnPaint(PaintEventArgs e)
    {
        var g = e.Graphics;
        g.Clear(_t.Background);
        g.SmoothingMode = SmoothingMode.AntiAlias;
        float s = DeviceDpi / 96f;
        using var p = Theme.Round(new RectangleF(0.5f, 0.5f, Width - 1.5f, Height - 1.5f), 7 * s);
        using var b = new SolidBrush(_t.Card);
        g.FillPath(b, p);
        using var pen = new Pen(_t.CardBorder, 1);
        g.DrawPath(pen, p);
    }

    protected override void OnControlAdded(ControlEventArgs e)
    {
        base.OnControlAdded(e);
        e.Control!.BackColor = _t.Card;
    }
}

/// <summary>Borderless TextBox inside a rounded Fluent field with an accent underline when focused.</summary>
sealed class FluentField : Panel, IThemed
{
    public TextBox Box { get; } = new() { BorderStyle = BorderStyle.None };
    Theme _t = Theme.Current();
    readonly bool _multiline;

    public FluentField(bool multiline = false)
    {
        _multiline = multiline;
        SetStyle(ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true);
        if (multiline)
        {
            Box.Multiline = true;
            Box.ReadOnly = true;
            Box.ScrollBars = ScrollBars.Vertical;
            Box.WordWrap = true;
        }
        Controls.Add(Box);
        Box.GotFocus += (_, _) => Invalidate();
        Box.LostFocus += (_, _) => Invalidate();
    }

    protected override void OnFontChanged(EventArgs e) { Box.Font = Font; base.OnFontChanged(e); LayoutBox(); }
    protected override void OnLayout(LayoutEventArgs e) { base.OnLayout(e); LayoutBox(); }

    void LayoutBox()
    {
        float s = DeviceDpi / 96f;
        int px = (int)(10 * s), py = (int)(6 * s);
        if (_multiline) Box.Bounds = new Rectangle(px, py, Width - 2 * px + (int)(4 * s), Height - 2 * py);
        else
        {
            int h = Box.PreferredHeight;
            Box.Bounds = new Rectangle(px, (Height - h) / 2, Width - 2 * px, h);
        }
    }

    public override Size GetPreferredSize(Size proposed) =>
        _multiline ? base.GetPreferredSize(proposed) : new Size(proposed.Width, Box.PreferredHeight + (int)(14 * DeviceDpi / 96f));

    [System.Runtime.InteropServices.DllImport("uxtheme.dll", CharSet = System.Runtime.InteropServices.CharSet.Unicode)]
    static extern int SetWindowTheme(IntPtr hwnd, string? app, string? idList);

    void ThemeScrollBar()
    {
        try { SetWindowTheme(Box.Handle, _t.Dark ? "DarkMode_Explorer" : "Explorer", null); }
        catch (Exception) { /* uxtheme unavailable */ }
    }

    protected override void OnHandleCreated(EventArgs e)
    {
        base.OnHandleCreated(e);
        if (_multiline) ThemeScrollBar();
    }

    public void ApplyTheme(Theme t)
    {
        _t = t;
        if (_multiline && Box.IsHandleCreated) ThemeScrollBar();
        BackColor = t.Background;
        Box.BackColor = _multiline ? t.Card : t.Control;
        Box.ForeColor = t.Text;
        Invalidate();
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        var g = e.Graphics;
        g.Clear(Parent?.BackColor ?? _t.Background);
        g.SmoothingMode = SmoothingMode.AntiAlias;
        float s = DeviceDpi / 96f;
        var r = new RectangleF(0.5f, 0.5f, Width - 1.5f, Height - 1.5f);
        using (var p = Theme.Round(r, 4 * s))
        {
            using var b = new SolidBrush(Box.BackColor);
            g.FillPath(b, p);
            using var pen = new Pen(_multiline ? _t.CardBorder : _t.ControlBorder, 1);
            g.DrawPath(pen, p);
        }
        if (!_multiline)
        {
            bool focus = Box.Focused;
            using var line = new Pen(focus ? _t.Accent : _t.Track, focus ? 2 * s : 1);
            float y = Height - (focus ? 1.5f * s : 1.5f);
            g.DrawLine(line, 4 * s, y, Width - 4 * s, y);
        }
    }
}
