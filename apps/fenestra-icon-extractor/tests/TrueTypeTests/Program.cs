using System.Globalization;
using System.Text.Json;
using FenestraIconExtractor;
using Pt = FenestraIconExtractor.TrueTypeFont.Point;

// 1. Fixed cases of the contour -> path conversion (exact strings).
int failures = 0;
void Expect(string what, string got, string want)
{
    if (got == want) { Console.WriteLine($"ok   {what}"); return; }
    failures++;
    Console.WriteLine($"FAIL {what}\n     got  {got}\n     want {want}");
}
// A square of on-curve points: M, three L, Z (the closing line is implied by Z). y' = baseline - y.
Expect("square", TrueTypeFont.SvgPathData(new() { new() { new(0, 0, true), new(0, 100, true), new(100, 100, true), new(100, 0, true) } }, 100),
       "M0 100L0 0L100 0L100 100Z");
// On, off, on: one quadratic segment, then the closing line.
Expect("quad", TrueTypeFont.SvgPathData(new() { new() { new(0, 0, true), new(50, 100, false), new(100, 0, true) } }, 0),
       "M0 0Q50 -100 100 0Z");
// Two consecutive off-curve points: implied on-curve midpoint between them.
Expect("implied midpoint", TrueTypeFont.SvgPathData(new() { new() { new(0, 0, true), new(0, 100, false), new(100, 100, false), new(100, 0, true) } }, 0),
       "M0 0Q0 -100 50 -100Q100 -100 100 0Z");
// Only off-curve points (a TrueType "circle"): starts at the midpoint of the last and first points.
Expect("all off-curve", TrueTypeFont.SvgPathData(new() { new() { new(0, 50, false), new(50, 100, false), new(100, 50, false), new(50, 0, false) } }, 0),
       "M25 -25Q0 -50 25 -75Q50 -100 75 -75Q100 -50 75 -25Q50 0 25 -25Z");
// Contour starting off-curve: rotated to begin at its first on-curve point.
Expect("rotation", TrueTypeFont.SvgPathData(new() { new() { new(50, 100, false), new(100, 0, true), new(0, 0, true) } }, 0),
       "M100 0L0 0Q50 -100 100 0Z");

// 2. AppxManifest logo variants (qualifier parsing and choice).
var files = new[] { "AppList.png", "AppList.scale-100.png", "AppList.scale-200.png", "AppList.targetsize-16_altform-unplated.png",
                    "AppList.targetsize-24_altform-unplated.png", "AppList.targetsize-48_altform-unplated.png",
                    "AppList.targetsize-256_altform-unplated.png", "AppList.targetsize-48_altform-lightunplated.png",
                    "AppList.targetsize-48_contrast-black.png", "Other.targetsize-48.png" };
var variants = AppxLogos.Variants("AppList.png", files).ToList();
Expect("variants found", variants.Count.ToString(CultureInfo.InvariantCulture), "8");
Expect("pick 32 (smallest unplated >= 32)", AppxLogos.Pick(variants, 32, light: false)?.File ?? "-", "AppList.targetsize-48_altform-unplated.png");
Expect("pick 16 exact", AppxLogos.Pick(variants, 16, light: false)?.File ?? "-", "AppList.targetsize-16_altform-unplated.png");
Expect("pick 512 (largest unplated)", AppxLogos.Pick(variants, 512, light: false)?.File ?? "-", "AppList.targetsize-256_altform-unplated.png");
Expect("pick light 48", AppxLogos.Pick(variants, 48, light: true)?.File ?? "-", "AppList.targetsize-48_altform-lightunplated.png");
Expect("light 16 (from the 48 px light image)", AppxLogos.Pick(variants, 16, light: true)?.File ?? "-", "AppList.targetsize-48_altform-lightunplated.png");
Expect("no light in plated set", AppxLogos.Pick(AppxLogos.Variants("Logo.png", new[] { "Logo.scale-200.png" }).ToList(), 16, light: true)?.File ?? "-", "-");
var plated = AppxLogos.Variants("Assets\\Logo.png", new[] { "Logo.scale-100.png", "Logo.scale-200.png", "Logo.scale-400.png" }).ToList();
Expect("plated fallback: largest scale", AppxLogos.Pick(plated, 48, light: false)?.File ?? "-", "Logo.scale-400.png");
Expect("folder qualifier", AppxLogos.Variants("Assets\\Logo.png", new[] { "scale-200\\Logo.png", "targetsize-32_altform-unplated/Logo.png" })
       .Select(v => v.File).OrderBy(f => f).Aggregate((a, b) => a + "," + b), "scale-200\\Logo.png,targetsize-32_altform-unplated/Logo.png");

// 3. A real font: SVG files for the given code points plus a summary for the rendering comparison.
if (args.Length >= 2)
{
    var font = TrueTypeFont.Load(args[0]);
    Directory.CreateDirectory(args[1]);
    // "ALL": every code point of the font (what --all-glyphs does), otherwise the listed ones.
    var cps = args.Length == 3 && args[2] == "ALL" ? font.CodePoints().ToList()
        : args.Skip(2).Select(a => int.Parse(a.StartsWith("U+") ? a[2..] : a, NumberStyles.HexNumber)).ToList();
    var summary = new List<object>();
    foreach (var cp in cps)
    {
        int g = font.GlyphId(cp);
        var svg = font.Svg(cp, 64);
        if (svg != null) File.WriteAllText(Path.Combine(args[1], $"{cp:X4}.svg"), svg);
        summary.Add(new { cp = $"U+{cp:X4}", glyph = g, contours = g == 0 ? 0 : font.Contours(g).Count, svg = svg != null,
                          bytes = svg?.Length ?? 0 });
    }
    File.WriteAllText(Path.Combine(args[1], "summary.json"), JsonSerializer.Serialize(new
    {
        font = Path.GetFileName(args[0]), units_per_em = font.UnitsPerEm, ascender = font.Ascender, descender = font.Descender,
        baseline = font.Baseline, revision = font.Revision, glyphs = font.GlyphCount, mapped = font.CodePoints().Count,
        cmap = font.CmapSubtables, entries = summary,
    }, new JsonSerializerOptions { WriteIndented = true }));
    Console.WriteLine($"{Path.GetFileName(args[0])}: upem {font.UnitsPerEm}, baseline {font.Baseline}, {font.CodePoints().Count} code points, cmap {string.Join(", ", font.CmapSubtables)}; {summary.Count} SVGs in {args[1]}");
}
Console.WriteLine(failures == 0 ? "ALL PASS" : $"{failures} FAILED");
return failures == 0 ? 0 : 1;
