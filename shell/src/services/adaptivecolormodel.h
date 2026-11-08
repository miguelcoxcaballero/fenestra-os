// SPDX-License-Identifier: GPL-3.0-or-later
// Adaptive color: the display white point that matches the ambient light (no Qt, testable alone:
// tests/adaptive-color/curve.cpp). Windows' Display Enhancement Service algorithm, as Microsoft
// documents it for OEMs ("Adaptive Color", learn.microsoft.com/windows-hardware/design/
// device-experiences/sensors-adaptive-color), with its defaults:
//   1. strength S = 50 % (DefaultAdaptiveColorAdaptationStrength; Windows 11 has no slider)
//      x the lux-based strength SL (LuxBasedStrengthAdaptationLut: 0.5 up to 50 lx, rising to
//      1.0 at 100 lx, 1.0 up to 600 lx, then falling: at 1200 lx the display stays at D65);
//   2. adapted white point = D65 + S x (ambient CIE xy - D65);
//   3. clamped to the white-point range (Windows keeps it between about 5000 K and the panel's
//      own white; KWin's colour temperature cannot go above 6500 K anyway);
//   4. below 50 lx (WhitePointMappingLowLightLuxLevel of Microsoft's sample table) the colour
//      reading is noisy: weighted towards the "low lux" white point, D65 + S x (D50 - D65)
//      (about 5650 K), by lux / 50.
// The result is a correlated colour temperature for KWin's Night light pipeline (blackbody
// channel factors). Blending is done in mireds (1e6 / K), where equal steps look equal.
#pragma once

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <deque>
#include <dirent.h>
#include <fcntl.h>
#include <string>
#include <unistd.h>
#include <vector>

namespace AdaptiveColorModel
{

struct Xy {
    double x = 0, y = 0;
};

inline constexpr Xy kD65{0.31271, 0.32902};
inline constexpr Xy kD50{0.34567, 0.35850};
inline constexpr double kStrength = 0.5;     // Windows 11's fixed 50 %
inline constexpr double kLowLightLux = 50.0;
inline constexpr int kMinTemperature = 5000; // warmest Adaptive color goes (Night light goes further)
inline constexpr int kMaxTemperature = 6500; // the panel's own white (KWin's maximum)

inline double mired(double kelvin) { return 1e6 / kelvin; }
inline double kelvin(double mireds) { return 1e6 / mireds; }

// McCamy's approximation of the correlated colour temperature of a CIE 1931 xy chromaticity
// (good to a few kelvin between 2800 K and 10000 K, the range that matters here).
inline double cctFromXy(Xy c)
{
    const double n = (c.x - 0.3320) / (0.1858 - c.y);
    return 449.0 * n * n * n + 3525.0 * n * n + 6823.3 * n + 5520.33;
}

// Chromaticity of a Planckian (blackbody) radiator, Kim et al. cubic spline (1667 K - 25000 K):
// for sensors that report only a colour temperature.
inline Xy xyFromCct(double t)
{
    t = std::clamp(t, 1667.0, 25000.0);
    const double t2 = t * t, t3 = t2 * t;
    const double x = t <= 4000 ? -0.2661239e9 / t3 - 0.2343589e6 / t2 + 0.8776956e3 / t + 0.179910
                               : -3.0258469e9 / t3 + 2.1070379e6 / t2 + 0.2226347e3 / t + 0.240390;
    const double x2 = x * x, x3 = x2 * x;
    double y;
    if (t <= 2222)
        y = -1.1063814 * x3 - 1.34811020 * x2 + 2.18555832 * x - 0.20219683;
    else if (t <= 4000)
        y = -0.9549476 * x3 - 1.37418593 * x2 + 2.09137015 * x - 0.16748867;
    else
        y = 3.0817580 * x3 - 5.87338670 * x2 + 3.75112997 * x - 0.37001483;
    return {x, y};
}

// SL: Windows' LuxBasedStrengthAdaptationLut (0:0.5, 50:0.5, 60:0.6 ... 100:1.0, 600:1.0,
// 650:0.9958 ...) and its sample table, where 1200 lx ambient leaves the display at D65.
inline double luxStrength(double lux)
{
    if (lux <= 50)
        return 0.5;
    if (lux <= 100)
        return 0.5 + (lux - 50) / 100.0;
    if (lux <= 600)
        return 1.0;
    const double t = (lux - 600) / 600.0;
    return std::max(0.0, 1.0 - t * t);
}

// A plausible ambient chromaticity (rejects 0/0 in the dark, saturated coloured lamps
// beyond what the clamp would keep anyway are still accepted).
inline bool plausible(Xy c)
{
    return c.x > 0.2 && c.x < 0.6 && c.y > 0.2 && c.y < 0.5;
}

// Target display colour temperature (K) for an ambient chromaticity and illuminance.
// `cap` is the user's own daytime temperature (6500 K unless they lowered it).
inline double targetTemperature(Xy ambient, double lux, int cap = kMaxTemperature)
{
    const double maxT = std::min(cap, kMaxTemperature);
    const double minT = std::min<double>(kMinTemperature, maxT);
    lux = std::max(0.0, lux);
    const double s = kStrength * luxStrength(lux);
    const Xy adapted{kD65.x + s * (ambient.x - kD65.x), kD65.y + s * (ambient.y - kD65.y)};
    double m = mired(std::clamp(cctFromXy(adapted), minT, maxT));
    if (lux < kLowLightLux) {
        const Xy low{kD65.x + kStrength * (kD50.x - kD65.x), kD65.y + kStrength * (kD50.y - kD65.y)};
        const double mLow = mired(std::clamp(cctFromXy(low), minT, maxT));
        const double w = lux / kLowLightLux;
        m = w * m + (1 - w) * mLow;
    }
    return kelvin(m);
}

// Slow, flicker-free following of the target ("slow, non-distracting colour transitions" and
// "hysteresis to prevent excessively frequent white point adjustments"):
//  - the light must have settled (the last samples agree) before the screen follows it, at their
//    trimmed mean: a light switched on and off every second or a passing shadow never reaches
//    the screen (Windows' strobe test);
//  - a new goal only when that level leaves a deadband of kDeadbandMired around the current
//    goal (about 130 K at 5700 K), so sensor noise never moves the screen; going back the other
//    way within a minute needs kReversalMired;
//  - transitions in mireds with an ease-in-out curve, lasting kSecondsPerMired per mired
//    (D65 -> D50, 46 mireds, about 12-14 s as Windows' 12.76 s), between kMinSeconds and
//    kMaxSeconds.
class Follower
{
public:
    static constexpr int kWindow = 7;
    static constexpr int kSettle = 4;
    static constexpr double kSettledMired = 8.0;
    static constexpr double kDeadbandMired = 4.0;
    static constexpr double kReversalMired = 8.0;
    static constexpr double kReversalSeconds = 60.0;
    static constexpr double kSecondsPerMired = 0.28;
    static constexpr double kMinSeconds = 2.0;
    static constexpr double kMaxSeconds = 20.0;

    explicit Follower(double startKelvin = kMaxTemperature)
        : m_from(mired(startKelvin))
        , m_goal(m_from)
    {
    }

    // A new sample (target in K) at time `now` (s). Returns true when a new transition starts.
    bool addSample(double targetKelvin, double now)
    {
        m_window.push_back(mired(targetKelvin));
        while (int(m_window.size()) > kWindow)
            m_window.pop_front();
        // The light must have settled: the last kSettle samples (8 s) agree within kSettledMired,
        // and the screen goes to their trimmed mean. A step back the other way within a minute of
        // a move needs the whole window (14 s) to agree and twice the change, so a light that
        // keeps flicking on and off holds the screen still instead of swinging it.
        auto settledLevel = [this](int n, double &level) {
            if (int(m_window.size()) < n)
                return false;
            std::vector<double> last(m_window.end() - n, m_window.end());
            std::sort(last.begin(), last.end());
            if (last.back() - last.front() > kSettledMired)
                return false;
            level = 0;
            for (size_t i = 1; i + 1 < last.size(); ++i)
                level += last[i];
            level /= double(last.size() - 2);
            return true;
        };
        double level = 0;
        if (!settledLevel(kSettle, level))
            return false;
        double delta = level - m_goal;
        const bool reversal = m_lastDirection != 0 && (delta > 0) != (m_lastDirection > 0)
            && now - (m_start + m_duration) < kReversalSeconds;
        if (reversal) {
            if (!settledLevel(kWindow, level))
                return false;
            delta = level - m_goal;
        }
        if (std::abs(delta) < (reversal ? kReversalMired : kDeadbandMired))
            return false;
        m_lastDirection = delta > 0 ? 1 : -1;
        startTransition(level, now, std::clamp(std::abs(level - current(now)) * kSecondsPerMired, kMinSeconds, kMaxSeconds));
        return true;
    }

    // Jump straight to a goal (first sample, after the lid opens or the screen unlocks: Windows
    // adapts within a second), forgetting older samples.
    void reset(double targetKelvin, double now, double seconds)
    {
        m_window.assign(1, mired(targetKelvin));
        m_lastDirection = 0;
        startTransition(mired(targetKelvin), now, seconds);
    }

    // Go to a fixed temperature (turning the feature off), keeping no samples.
    void goTo(double targetKelvin, double now, double seconds)
    {
        m_window.clear();
        m_lastDirection = 0;
        startTransition(mired(targetKelvin), now, seconds);
    }

    double current(double now) const
    {
        if (now >= m_start + m_duration || m_duration <= 0)
            return m_goal;
        const double t = std::clamp((now - m_start) / m_duration, 0.0, 1.0);
        const double e = t * t * (3 - 2 * t); // smoothstep: accelerates, then decelerates
        return m_from + (m_goal - m_from) * e;
    }
    double currentKelvin(double now) const { return kelvin(current(now)); }
    double goalKelvin() const { return kelvin(m_goal); }
    bool moving(double now) const { return now < m_start + m_duration; }

private:
    void startTransition(double goal, double now, double seconds)
    {
        m_from = current(now);
        m_goal = goal;
        m_start = now;
        m_duration = seconds;
    }

    std::deque<double> m_window;
    double m_from, m_goal;
    double m_start = 0, m_duration = 0;
    int m_lastDirection = 0;
};

// An IIO ambient light sensor that reports colour (HID sensor hub "als", and any other driver
// exposing in_chromaticity_x/y or in_colortemp): /sys/bus/iio/devices/iio:deviceN. The files
// stay open and are re-read with pread(), which makes the driver fetch a fresh report (a HID
// sensor answers in about 100 ms: read it off the GUI thread). Value = (raw + offset) x scale.
class AlsSysfs
{
public:
    struct Sample {
        bool hasXy = false, hasCct = false, hasLux = false;
        Xy xy;
        double cct = 0, lux = 0;
    };

    AlsSysfs() = default;
    AlsSysfs(const AlsSysfs &) = delete;
    AlsSysfs &operator=(const AlsSysfs &) = delete;
    ~AlsSysfs() { close(); }

    // The first colour-capable device under `root` (or `root` itself when it is a device).
    static std::string find(const std::string &root = "/sys/bus/iio/devices")
    {
        auto colour = [](const std::string &dir) {
            return (exists(dir + "/in_chromaticity_x_raw") && exists(dir + "/in_chromaticity_y_raw"))
                || exists(dir + "/in_colortemp_raw") || exists(dir + "/in_colortemp_input");
        };
        if (colour(root))
            return root;
        std::vector<std::string> names;
        if (DIR *d = opendir(root.c_str())) {
            while (dirent *e = readdir(d)) {
                if (std::string(e->d_name).rfind("iio:device", 0) == 0)
                    names.push_back(e->d_name);
            }
            closedir(d);
        }
        std::sort(names.begin(), names.end());
        for (const auto &n : names) {
            if (colour(root + "/" + n))
                return root + "/" + n;
        }
        return {};
    }

    bool open(const std::string &dir)
    {
        close();
        m_dir = dir;
        m_x = Channel(dir, "chromaticity_x");
        m_y = Channel(dir, "chromaticity_y");
        m_cct = Channel(dir, "colortemp");
        m_lux = Channel(dir, "illuminance");
        return (m_x.fd >= 0 && m_y.fd >= 0) || m_cct.fd >= 0;
    }
    void close()
    {
        for (Channel *c : {&m_x, &m_y, &m_cct, &m_lux})
            c->close();
    }
    const std::string &dir() const { return m_dir; }
    bool hasChromaticity() const { return m_x.fd >= 0 && m_y.fd >= 0; }

    Sample read()
    {
        Sample s;
        double x = 0, y = 0;
        if (hasChromaticity() && m_x.read(x) && m_y.read(y)) {
            s.xy = {x, y};
            s.hasXy = plausible(s.xy);
        }
        // The sensor's own CCT only when there is no usable chromaticity (saves a HID report).
        if (!s.hasXy && m_cct.fd >= 0 && m_cct.read(s.cct))
            s.hasCct = s.cct >= 1000 && s.cct <= 25000;
        s.hasLux = m_lux.fd >= 0 && m_lux.read(s.lux) && s.lux >= 0;
        return s;
    }

private:
    static bool exists(const std::string &p) { return access(p.c_str(), R_OK) == 0; }
    static bool readNumber(const std::string &p, double &v)
    {
        const int fd = ::open(p.c_str(), O_RDONLY | O_CLOEXEC);
        if (fd < 0)
            return false;
        char buf[64];
        const ssize_t n = ::pread(fd, buf, sizeof buf - 1, 0);
        ::close(fd);
        if (n <= 0)
            return false;
        buf[n] = 0;
        char *end = nullptr;
        v = std::strtod(buf, &end);
        return end != buf;
    }

    struct Channel {
        int fd = -1;
        double scale = 1, offset = 0;
        Channel() = default;
        Channel(const std::string &dir, const std::string &name)
        {
            // _input is already in units; _raw needs the channel's (or the shared) scale/offset.
            std::string base = dir + "/in_" + name;
            fd = ::open((base + "_input").c_str(), O_RDONLY | O_CLOEXEC);
            if (fd >= 0)
                return;
            fd = ::open((base + "_raw").c_str(), O_RDONLY | O_CLOEXEC);
            if (fd < 0)
                return;
            // in_chromaticity_x_raw shares in_chromaticity_scale with y (IIO's shared_by_type).
            const std::string shared = dir + "/in_" + name.substr(0, name.find('_'));
            if (!readNumber(base + "_scale", scale) && !readNumber(shared + "_scale", scale))
                scale = 1;
            if (!readNumber(base + "_offset", offset) && !readNumber(shared + "_offset", offset))
                offset = 0;
        }
        Channel(Channel &&o) noexcept { *this = std::move(o); }
        Channel &operator=(Channel &&o) noexcept
        {
            if (this != &o) {
                close();
                fd = o.fd;
                scale = o.scale;
                offset = o.offset;
                o.fd = -1;
            }
            return *this;
        }
        ~Channel() { close(); }
        void close()
        {
            if (fd >= 0)
                ::close(fd);
            fd = -1;
        }
        bool read(double &v) const
        {
            char buf[64];
            const ssize_t n = ::pread(fd, buf, sizeof buf - 1, 0);
            if (n <= 0)
                return false;
            buf[n] = 0;
            char *end = nullptr;
            const double raw = std::strtod(buf, &end);
            if (end == buf)
                return false;
            v = (raw + offset) * scale;
            return std::isfinite(v);
        }
    };

    std::string m_dir;
    Channel m_x, m_y, m_cct, m_lux;
};

} // namespace AdaptiveColorModel
