using System.IO.Compression;
using System.Text;
using System.Text.RegularExpressions;

namespace FenestraIconExtractor;

/// <summary>
/// The weather condition icons of the taskbar weather button and the Widgets board.
///
/// Windows does not install them: Widgets (MicrosoftWindows.Client.WebExperience) shows the icon
/// for the current condition from its web content, which loads
/// <c>…/weather/Icons/taskbar_v10/Condition_Card/&lt;Name&gt;.svg</c> and keeps it in the WebView2 HTTP
/// cache of the package (<c>%LOCALAPPDATA%\Packages\MicrosoftWindows.Client.WebExperience_cw5n1h2txyewy\
/// LocalState\EBWebView\Default\Cache\Cache_Data</c>, Chromium "blockfile" format). The extractor reads
/// every condition icon found in that cache (and Edge's). With <c>--weather-download</c> it also asks
/// the same address Widgets uses for the conditions this PC has not shown yet (opt-in: the only
/// network access of the extractor). Names and sky codes below are the ones Windows' own Widgets
/// code maps conditions to (no artwork).
/// </summary>
public static class WeatherIcons
{
    public const string Base = "https://assets.msn.com/weathermapdata/1/static/weather/Icons/taskbar_v10/Condition_Card/";

    /// <summary>Widgets' sky code -> icon name (weather-card web component, Windows 11 24H2).</summary>
    public static readonly Dictionary<int, string> SkyCodes = new()
    {
        [1] = "SunnyDayV3", [2] = "MostlySunnyDay", [3] = "PartlyCloudyDayV3", [4] = "MostlyCloudyDayV2", [5] = "CloudyV3",
        [6] = "BlowingHailV2", [7] = "BlowingSnowV2", [8] = "LightRainV2", [9] = "FogV2", [10] = "FreezingRainV2",
        [12] = "Haze", [13] = "HeavyDrizzle", [14] = "ModerateRainV2", [15] = "HeavySnowV2", [16] = "IcePellets",
        [17] = "LightRainShowerDay", [19] = "LightRainV3", [20] = "LightSnowV2", [23] = "HeavyDrizzle", [24] = "RainSnowV2",
        [25] = "Snow", [26] = "SnowShowersDayV2", [27] = "ThunderstormsV2", [28] = "ClearNightV3", [29] = "MostlyClearNight",
        [30] = "PartlyCloudyNightV2", [31] = "MostlyCloudyNightV2", [39] = "Fair", [40] = "HeavyDrizzle", [43] = "IcePelletsV2",
        [44] = "LightRainShowerNight", [50] = "RainShowersNightV2", [52] = "Snow", [53] = "N422Snow", [54] = "HazySmokeV2",
        [55] = "Dust1", [56] = "ThunderstormsV2", [57] = "Haze", [58] = "FogV2", [59] = "WindyV2", [65] = "HailDayV2",
        [66] = "HailNightV2", [73] = "HailDayV2", [74] = "HailNightV2", [77] = "RainSnowV2", [78] = "RainSnowShowersNightV2",
        [79] = "RainShowersDayV2", [81] = "LightSnowShowersDay", [82] = "LightSnowShowersNight", [89] = "HazySmokeV2",
        [90] = "HazeSmokeNightV2_106", [91] = "WindyV2",
    };

    /// <summary>Icon names of Widgets' symbol map (day/night variants of showers and storms).</summary>
    public static readonly string[] SymbolNames =
    {
        "D200PartlySunnyV2", "D210LightRainShowersV2", "D211LightRainSowShowersV2", "D212LightSnowShowersV2",
        "D221RainSnowShowersV2", "D240TstormsV2", "D310LightRainShowersV2", "D311LightRainSnowShowersV2",
        "D321RainSnowShowersV2", "D340TstormsV2", "N210LightRainShowersV2", "N211LightRainSnowShowersV2",
        "N212LightSnowShowersV2", "N221RainSnowShowersV2", "N222SnowShowersV2", "N240TstormsV2", "N310LightRainShowersV2",
        "N311LightRainSnowShowersV2", "N321RainSnowShowersV2", "N322SnowShowersV2", "N340TstormsV2", "N422SnowV2",
        "Hazy-Night",
    };

    public static IEnumerable<string> AllNames() => SkyCodes.Values.Concat(SymbolNames).Distinct(StringComparer.Ordinal).OrderBy(n => n, StringComparer.Ordinal);

    static readonly Regex NameRx = new(@"^[A-Za-z0-9_-]{1,64}$", RegexOptions.CultureInvariant);
    public static bool ValidName(string n) => NameRx.IsMatch(n);

    /// <summary>WebView2/Edge cache folders of this user that can hold Widgets content.</summary>
    public static IEnumerable<string> CacheDirs()
    {
        var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        var roots = new[]
        {
            Path.Combine(local, "Packages", "MicrosoftWindows.Client.WebExperience_cw5n1h2txyewy", "LocalState", "EBWebView"),
            Path.Combine(local, "Microsoft", "Edge", "User Data"),
        };
        foreach (var root in roots)
        {
            if (!Directory.Exists(root)) continue;
            IEnumerable<string> profiles;
            try { profiles = Directory.EnumerateDirectories(root).ToList(); }
            catch (Exception) { continue; }
            foreach (var p in profiles)
            {
                var d = Path.Combine(p, "Cache", "Cache_Data");
                if (File.Exists(Path.Combine(d, "data_1"))) yield return d;
            }
        }
    }

    /// <summary>Entries of a Chromium blockfile cache whose key matches <paramref name="keyFilter"/>:
    /// (key, decoded body). Read-only; files are opened shared because the browser may be running.</summary>
    public static IEnumerable<(string Key, byte[] Body)> ReadCache(string dir, Func<string, bool> keyFilter)
    {
        var files = new Dictionary<int, byte[]>();
        byte[] Block(int n)
        {
            if (!files.TryGetValue(n, out var d)) files[n] = d = ReadShared(Path.Combine(dir, $"data_{n}"));
            return d;
        }
        byte[] Read(uint addr, int size)
        {
            if ((addr & 0x80000000) == 0 || size <= 0) return Array.Empty<byte>();
            int type = (int)((addr >> 28) & 7);
            if (type == 0)
            {
                var f = ReadShared(Path.Combine(dir, $"f_{addr & 0x0fffffff:x6}"));
                return f.Length > size ? f[..size] : f;
            }
            int bs = type switch { 1 => 36, 2 => 256, 3 => 1024, 4 => 4096, _ => 0 };
            if (bs == 0) return Array.Empty<byte>();
            var data = Block((int)((addr >> 16) & 0xff));
            long start = 8192 + (long)(addr & 0xffff) * bs;
            if (start >= data.Length) return Array.Empty<byte>();
            return data[(int)start..(int)Math.Min(data.Length, start + size)];
        }
        byte[]? d1 = null;
        try { d1 = Block(1); } catch (IOException) { }
        if (d1 == null) yield break;
        for (int off = 8192; off + 256 <= d1.Length; off += 256)
        {
            int keyLen = BitConverter.ToInt32(d1, off + 32);
            if (keyLen <= 0 || keyLen > 8192) continue;
            string key;
            if (keyLen < 256 - 96) key = Encoding.Latin1.GetString(d1, off + 96, keyLen);
            else
            {
                uint longKey = BitConverter.ToUInt32(d1, off + 36);
                if (longKey == 0) continue;
                key = Encoding.Latin1.GetString(Read(longKey, keyLen));
            }
            if (!keyFilter(key)) continue;
            int hdrSize = BitConverter.ToInt32(d1, off + 40), bodySize = BitConverter.ToInt32(d1, off + 44);
            uint hdrAddr = BitConverter.ToUInt32(d1, off + 56), bodyAddr = BitConverter.ToUInt32(d1, off + 60);
            byte[] body;
            try
            {
                body = Read(bodyAddr, bodySize);
                var hdr = Encoding.Latin1.GetString(Read(hdrAddr, hdrSize));
                var enc = Regex.Match(hdr, @"content-encoding:\s*(\w+)", RegexOptions.IgnoreCase);
                if (enc.Success) body = Decode(body, enc.Groups[1].Value.ToLowerInvariant());
            }
            catch (Exception) { continue; }
            if (body.Length > 0) yield return (key, body);
        }
    }

    static byte[] Decode(byte[] body, string encoding)
    {
        using var input = new MemoryStream(body);
        using Stream s = encoding switch
        {
            "br" => new BrotliStream(input, CompressionMode.Decompress),
            "gzip" => new GZipStream(input, CompressionMode.Decompress),
            "deflate" => new ZLibStream(input, CompressionMode.Decompress),
            _ => input,
        };
        using var ms = new MemoryStream();
        s.CopyTo(ms);
        return ms.ToArray();
    }

    static byte[] ReadShared(string path)
    {
        using var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
        var data = new byte[fs.Length];
        fs.ReadExactly(data);
        return data;
    }

    public static bool LooksLikeSvg(byte[] data)
    {
        var head = Encoding.UTF8.GetString(data, 0, Math.Min(data.Length, 512)).TrimStart('﻿', ' ', '\r', '\n', '\t');
        return head.StartsWith("<svg", StringComparison.Ordinal) || (head.StartsWith("<?xml", StringComparison.Ordinal) && head.Contains("<svg"));
    }
}
