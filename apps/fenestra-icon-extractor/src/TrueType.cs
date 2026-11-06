using System.Globalization;
using System.Text;

namespace FenestraIconExtractor;

/// <summary>
/// A minimal read-only TrueType (glyf) reader: head, maxp, hhea, hmtx, OS/2, cmap (formats 4 and 12),
/// loca and glyf, composite glyphs included. It turns glyph outlines into SVG path data in font
/// units, without hinting or rasterising, so the result is the same on every machine with the same
/// font file. No Windows APIs: the unit tests run it on Linux against free fonts.
/// </summary>
public sealed class TrueTypeFont
{
    public readonly record struct Point(double X, double Y, bool OnCurve);

    readonly byte[] _d;
    readonly Dictionary<string, (int Offset, int Length)> _tables = new(StringComparer.Ordinal);
    readonly Dictionary<int, int> _cmap = new();
    readonly int _locaFormat, _numHMetrics;

    public int UnitsPerEm { get; }
    public int GlyphCount { get; }
    public int Ascender { get; }
    public int Descender { get; }
    /// <summary>head.fontRevision as text, e.g. "1.37".</summary>
    public string Revision { get; }
    /// <summary>The cmap subtables used ("platform/encoding/format N").</summary>
    public List<string> CmapSubtables { get; } = new();
    /// <summary>Baseline position from the top of the em square (font units): the ascender, scaled
    /// into the em when ascender - descender differs from unitsPerEm.</summary>
    public int Baseline { get; }

    public static TrueTypeFont Load(string path) => new(File.ReadAllBytes(path));

    public TrueTypeFont(byte[] data, int fontIndex = 0)
    {
        _d = data;
        int dir = 0;
        if (Tag(0) == "ttcf")
        {
            int n = (int)U32(8);
            if (fontIndex < 0 || fontIndex >= n) throw new InvalidDataException("font index out of range");
            dir = (int)U32(12 + 4 * fontIndex);
        }
        uint version = U32(dir);
        if (version == 0x4F54544F) throw new NotSupportedException("CFF (OTTO) fonts have no glyf outlines");
        if (version != 0x00010000 && version != 0x74727565) throw new InvalidDataException("not a TrueType font");
        int numTables = U16(dir + 4);
        for (int i = 0; i < numTables; i++)
        {
            int r = dir + 12 + 16 * i;
            int off = (int)U32(r + 8), len = (int)U32(r + 12);
            if (off < 0 || len < 0 || (long)off + len > _d.Length) throw new InvalidDataException("table outside the file");
            _tables[Tag(r)] = (off, len);
        }
        foreach (var t in new[] { "head", "maxp", "hhea", "hmtx", "cmap", "loca", "glyf" })
            if (!_tables.ContainsKey(t)) throw new InvalidDataException($"missing '{t}' table");

        int head = _tables["head"].Offset;
        UnitsPerEm = U16(head + 18);
        if (UnitsPerEm < 16 || UnitsPerEm > 16384) throw new InvalidDataException("bad unitsPerEm");
        _locaFormat = S16(head + 50);
        uint rev = U32(head + 4);
        Revision = ((rev >> 16) + (rev & 0xFFFF) / 65536.0).ToString("0.###", CultureInfo.InvariantCulture);
        GlyphCount = U16(_tables["maxp"].Offset + 4);
        int hhea = _tables["hhea"].Offset;
        Ascender = S16(hhea + 4);
        Descender = S16(hhea + 6);
        _numHMetrics = Math.Max(1, U16(hhea + 34));
        int span = Ascender - Descender;
        Baseline = span > 0 && span != UnitsPerEm ? (int)Math.Round((double)UnitsPerEm * Ascender / span) : Ascender;
        ReadCmap();
    }

    // ------------------------------------------------------------- bytes ---
    int U16(int o) => o + 2 <= _d.Length ? (_d[o] << 8) | _d[o + 1] : throw new InvalidDataException("read past end");
    short S16(int o) => (short)U16(o);
    uint U32(int o) => o + 4 <= _d.Length ? (uint)((_d[o] << 24) | (_d[o + 1] << 16) | (_d[o + 2] << 8) | _d[o + 3]) : throw new InvalidDataException("read past end");
    string Tag(int o) => o + 4 <= _d.Length ? Encoding.ASCII.GetString(_d, o, 4) : "";

    // -------------------------------------------------------------- cmap ---
    void ReadCmap()
    {
        var (cmap, len) = _tables["cmap"];
        int n = U16(cmap + 2);
        // Preference: full Unicode (format 12) first, then BMP (format 4); symbol (3,0) last.
        var subtables = new List<(int Rank, int Offset)>();
        for (int i = 0; i < n; i++)
        {
            int r = cmap + 4 + 8 * i;
            int platform = U16(r), encoding = U16(r + 2);
            int off = cmap + (int)U32(r + 4);
            if (off + 2 > cmap + len) continue;
            int format = U16(off);
            int rank = (platform, encoding, format) switch
            {
                (3, 10, 12) => 0, (0, _, 12) => 1, (3, 1, 4) => 2, (0, _, 4) => 3, (3, 0, 4) => 4, _ => -1,
            };
            if (rank >= 0) { subtables.Add((rank, off)); CmapSubtables.Add($"{platform}/{encoding}/format {format}"); }
        }
        if (subtables.Count == 0) throw new InvalidDataException("no Unicode cmap subtable (format 4 or 12)");
        // Merge, best subtable last so its entries win.
        foreach (var (_, off) in subtables.OrderByDescending(s => s.Rank))
        {
            if (U16(off) == 12) ReadCmap12(off); else ReadCmap4(off);
        }
    }

    void ReadCmap4(int o)
    {
        int segX2 = U16(o + 6);
        int ends = o + 14, starts = ends + segX2 + 2, deltas = starts + segX2, ranges = deltas + segX2;
        for (int s = 0; s < segX2 / 2; s++)
        {
            int end = U16(ends + 2 * s), start = U16(starts + 2 * s);
            int delta = S16(deltas + 2 * s), rangeAt = ranges + 2 * s, range = U16(rangeAt);
            if (start > end) continue;
            for (int c = start; c <= end && c != 0xFFFF; c++)
            {
                int g;
                if (range == 0) g = (c + delta) & 0xFFFF;
                else
                {
                    int at = rangeAt + range + 2 * (c - start);
                    if (at + 2 > _d.Length) break;
                    g = U16(at);
                    if (g != 0) g = (g + delta) & 0xFFFF;
                }
                if (g != 0 && g < GlyphCount) _cmap[c] = g;
            }
        }
    }

    void ReadCmap12(int o)
    {
        uint groups = U32(o + 12);
        for (uint i = 0; i < groups && i < 1_000_000; i++)
        {
            int r = o + 16 + (int)(12 * i);
            uint start = U32(r), end = U32(r + 4), glyph = U32(r + 8);
            if (end < start || end > 0x10FFFF || end - start > 0x10FFFF) continue;
            for (uint c = start; c <= end; c++)
            {
                long g = glyph + (c - start);
                if (g != 0 && g < GlyphCount) _cmap[(int)c] = (int)g;
            }
        }
    }

    /// <summary>Glyph id for a Unicode code point, or 0 (.notdef) when the font has none.</summary>
    public int GlyphId(int codePoint) => _cmap.TryGetValue(codePoint, out var g) ? g : 0;

    /// <summary>Every mapped code point, ascending.</summary>
    public IReadOnlyList<int> CodePoints() => _cmap.Keys.OrderBy(c => c).ToList();

    public int AdvanceWidth(int glyph)
    {
        var (hmtx, len) = _tables["hmtx"];
        int i = Math.Min(glyph, _numHMetrics - 1);
        return 4 * i + 2 <= len ? U16(hmtx + 4 * i) : UnitsPerEm;
    }

    // -------------------------------------------------------------- glyf ---
    (int Offset, int Length) GlyphRange(int glyph)
    {
        if (glyph < 0 || glyph >= GlyphCount) return (0, 0);
        var (loca, len) = _tables["loca"];
        long a, b;
        if (_locaFormat == 0)
        {
            if (2 * glyph + 4 > len) return (0, 0);
            a = 2L * U16(loca + 2 * glyph); b = 2L * U16(loca + 2 * glyph + 2);
        }
        else
        {
            if (4 * glyph + 8 > len) return (0, 0);
            a = U32(loca + 4 * glyph); b = U32(loca + 4 * glyph + 4);
        }
        var (glyf, glen) = _tables["glyf"];
        if (b <= a || b > glen) return (0, 0);
        return (glyf + (int)a, (int)(b - a));
    }

    /// <summary>The outline of <paramref name="glyph"/>: closed contours of quadratic B-spline points,
    /// in font units (y up), composite glyphs resolved.</summary>
    public List<List<Point>> Contours(int glyph) => Contours(glyph, 0);

    List<List<Point>> Contours(int glyph, int depth)
    {
        var result = new List<List<Point>>();
        if (depth > 16) throw new InvalidDataException("composite glyphs nested too deeply");
        var (o, len) = GlyphRange(glyph);
        if (len < 10) return result;
        int end = o + len;
        int nContours = S16(o);
        if (nContours >= 0) return SimpleGlyph(o, end, nContours);

        int p = o + 10;
        const int ARGS_WORDS = 0x1, ARGS_XY = 0x2, SCALE = 0x8, MORE = 0x20, XY_SCALE = 0x40, TWO_BY_TWO = 0x80,
                  SCALED_OFFSET = 0x800, UNSCALED_OFFSET = 0x1000;
        int flags;
        do
        {
            if (p + 4 > end) break;
            flags = U16(p); int child = U16(p + 2); p += 4;
            int arg1, arg2;
            if ((flags & ARGS_WORDS) != 0)
            {
                arg1 = (flags & ARGS_XY) != 0 ? S16(p) : U16(p);
                arg2 = (flags & ARGS_XY) != 0 ? S16(p + 2) : U16(p + 2);
                p += 4;
            }
            else
            {
                arg1 = (flags & ARGS_XY) != 0 ? (sbyte)_d[p] : _d[p];
                arg2 = (flags & ARGS_XY) != 0 ? (sbyte)_d[p + 1] : _d[p + 1];
                p += 2;
            }
            double a = 1, b = 0, c = 0, dd = 1;
            if ((flags & SCALE) != 0) { a = dd = F2Dot14(p); p += 2; }
            else if ((flags & XY_SCALE) != 0) { a = F2Dot14(p); dd = F2Dot14(p + 2); p += 4; }
            else if ((flags & TWO_BY_TWO) != 0) { a = F2Dot14(p); b = F2Dot14(p + 2); c = F2Dot14(p + 4); dd = F2Dot14(p + 6); p += 8; }

            var parts = Contours(child, depth + 1);
            // x' = a*x + c*y + dx ; y' = b*x + d*y + dy
            List<List<Point>> moved = parts.Select(ct => ct.Select(q => new Point(a * q.X + c * q.Y, b * q.X + dd * q.Y, q.OnCurve)).ToList()).ToList();
            double dx, dy;
            if ((flags & ARGS_XY) != 0)
            {
                dx = arg1; dy = arg2;
                if ((flags & SCALED_OFFSET) != 0 && (flags & UNSCALED_OFFSET) == 0)
                {
                    (dx, dy) = (a * arg1 + c * arg2, b * arg1 + dd * arg2);
                }
            }
            else
            {
                // Point matching: child point arg2 is placed on parent point arg1.
                var parentPts = result.SelectMany(x => x).ToList();
                var childPts = moved.SelectMany(x => x).ToList();
                if (arg1 >= parentPts.Count || arg2 >= childPts.Count) { dx = dy = 0; }
                else { dx = parentPts[arg1].X - childPts[arg2].X; dy = parentPts[arg1].Y - childPts[arg2].Y; }
            }
            foreach (var ct in moved) result.Add(ct.Select(q => q with { X = q.X + dx, Y = q.Y + dy }).ToList());
        } while ((flags & MORE) != 0);
        return result;
    }

    double F2Dot14(int o) => S16(o) / 16384.0;

    List<List<Point>> SimpleGlyph(int o, int end, int nContours)
    {
        var result = new List<List<Point>>();
        if (nContours == 0) return result;
        int p = o + 10;
        var ends = new int[nContours];
        for (int i = 0; i < nContours; i++) { ends[i] = U16(p); p += 2; }
        int nPoints = ends[^1] + 1;
        if (nPoints <= 0 || nPoints > 65535) return result;
        int insLen = U16(p); p += 2 + insLen;
        var flags = new byte[nPoints];
        for (int i = 0; i < nPoints;)
        {
            if (p >= end) throw new InvalidDataException("glyph flags truncated");
            byte f = _d[p++];
            flags[i++] = f;
            if ((f & 8) != 0)
            {
                if (p >= end) throw new InvalidDataException("glyph flags truncated");
                int repeat = _d[p++];
                for (int k = 0; k < repeat && i < nPoints; k++) flags[i++] = f;
            }
        }
        var xs = new int[nPoints];
        var ys = new int[nPoints];
        int v = 0;
        for (int i = 0; i < nPoints; i++)
        {
            byte f = flags[i];
            if ((f & 2) != 0) { int dx = _d[p++]; v += (f & 16) != 0 ? dx : -dx; }
            else if ((f & 16) == 0) { v += S16(p); p += 2; }
            xs[i] = v;
        }
        v = 0;
        for (int i = 0; i < nPoints; i++)
        {
            byte f = flags[i];
            if ((f & 4) != 0) { int dy = _d[p++]; v += (f & 32) != 0 ? dy : -dy; }
            else if ((f & 32) == 0) { v += S16(p); p += 2; }
            ys[i] = v;
        }
        if (p > end) throw new InvalidDataException("glyph coordinates truncated");
        int startPt = 0;
        foreach (int e in ends)
        {
            if (e < startPt || e >= nPoints) throw new InvalidDataException("bad contour end point");
            var ct = new List<Point>(e - startPt + 1);
            for (int i = startPt; i <= e; i++) ct.Add(new Point(xs[i], ys[i], (flags[i] & 1) != 0));
            result.Add(ct);
            startPt = e + 1;
        }
        return result;
    }

    // --------------------------------------------------------------- SVG ---
    /// <summary>SVG path data for the glyph in an em-square coordinate system: x as in the font,
    /// y' = <see cref="Baseline"/> - y. Empty string for glyphs without outline (space).</summary>
    public string SvgPathData(int glyph) => SvgPathData(Contours(glyph), Baseline);

    public static string SvgPathData(List<List<Point>> contours, double baseline)
    {
        var sb = new StringBuilder();
        string N(double x) => Math.Round(x, 2).ToString("0.##", CultureInfo.InvariantCulture);
        string P(Point q) => N(q.X) + " " + N(baseline - q.Y);
        foreach (var raw in contours)
        {
            if (raw.Count < 2) continue;
            // Start at an on-curve point; when there is none, at the implied midpoint of the last
            // and first (off-curve) points.
            int first = raw.FindIndex(q => q.OnCurve);
            List<Point> pts;
            Point start;
            if (first >= 0)
            {
                pts = raw.Skip(first + 1).Concat(raw.Take(first)).ToList();
                start = raw[first];
            }
            else
            {
                pts = raw.ToList();
                start = Mid(raw[^1], raw[0]);
            }
            sb.Append('M').Append(P(start));
            Point? off = null;
            for (int i = 0; i <= pts.Count; i++)
            {
                var q = i < pts.Count ? pts[i] : start;   // back to the start point to close the contour
                bool closing = i == pts.Count;
                if (q.OnCurve)
                {
                    if (off is { } c) { sb.Append('Q').Append(P(c)).Append(' ').Append(P(q)); off = null; }
                    else if (!closing) sb.Append('L').Append(P(q));   // the closing line is drawn by Z
                }
                else
                {
                    if (off is { } c) sb.Append('Q').Append(P(c)).Append(' ').Append(P(Mid(c, q)));
                    off = q;
                }
            }
            sb.Append('Z');
        }
        return sb.ToString();
    }

    static Point Mid(Point a, Point b) => new((a.X + b.X) / 2, (a.Y + b.Y) / 2, true);

    /// <summary>A standalone SVG document for <paramref name="codePoint"/>, or null when the font has no
    /// glyph for it. The viewBox is the em square (unitsPerEm × unitsPerEm), the outline is filled with
    /// currentColor (non-zero rule, as TrueType rasterisers fill), and width/height are a size hint.</summary>
    public string? Svg(int codePoint, int sizeHint = 16)
    {
        int g = GlyphId(codePoint);
        if (g == 0) return null;
        string d = SvgPathData(g);
        if (d.Length == 0) return null;
        return "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 " + UnitsPerEm + " " + UnitsPerEm +
               "\" width=\"" + sizeHint + "\" height=\"" + sizeHint + "\">" +
               "<path fill=\"currentColor\" fill-rule=\"nonzero\" d=\"" + d + "\"/></svg>\n";
    }
}
