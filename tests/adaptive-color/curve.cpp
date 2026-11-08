// SPDX-License-Identifier: GPL-3.0-or-later
// Bench for Adaptive color's mapping and filter (shell/src/services/adaptivecolormodel.h).
//   curve table              Microsoft's sample output table vs ours: Fenestra adapts more (70 %, full
//                            strength in dim rooms), so it must be at least as warm as Windows (150 K
//                            slack) and at most 1000 K warmer; neutral light stays at 6500 K (exit 1 if not)
//   curve sweep              ambient 2700-6500 K (on the Planckian locus) x lux -> display K
//   curve follow             simulated scenes: step, strobe (light on/off every second), noise
//   curve live DIR SECONDS   read a real (or fake) IIO sensor every 2 s, log it (read-only)
// Build: g++ -std=c++20 -O2 -I shell/src/services tests/adaptive-color/curve.cpp -o curve
#include "adaptivecolormodel.h"

#include <chrono>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <functional>
#include <random>
#include <sys/resource.h>
#include <thread>

using namespace AdaptiveColorModel;

static int table()
{
    // learn.microsoft.com/windows-hardware/design/device-experiences/sensors-adaptive-color,
    // "Sample Output" (default settings): ACS x, y, lux -> display CCT.
    struct Row {
        double x, y, lux, ambientCct, displayCct;
    } rows[] = {
        {0.4593, 0.4107, 5, 2706, 5580},   {0.4593, 0.4107, 50, 2706, 5045}, {0.3805, 0.3767, 30, 4008, 5677},
        {0.3805, 0.3767, 100, 4008, 5032}, {0.3457, 0.3585, 50, 5002, 6067}, {0.3457, 0.3585, 500, 5002, 5675},
        {0.3127, 0.3290, 100, 6504, 6504}, {0.3127, 0.3290, 1000, 6504, 6504}, {0.3038, 0.3140, 500, 7194, 6831},
        {0.3038, 0.3140, 1200, 7194, 6504}, {0.2849, 0.2932, 700, 9224, 7632}, {0.2849, 0.2932, 1200, 9224, 6504},
    };
    int bad = 0;
    std::printf("%-8s %-8s %6s %8s | %10s %10s %7s\n", "x", "y", "lux", "ambient", "windows", "fenestra", "delta");
    for (const Row &r : rows) {
        const double ours = targetTemperature({r.x, r.y}, r.lux);
        // KWin cannot go above the panel's 6500 K: compare with Windows clamped the same way.
        const double win = std::min(r.displayCct, 6500.0);
        const double d = ours - win;
        const bool ok = d <= 150 && d >= -1000;
        bad += !ok;
        std::printf("%-8.4f %-8.4f %6.0f %8.0f | %10.0f %10.0f %+7.0f %s\n", r.x, r.y, r.lux, r.ambientCct, r.displayCct, ours, d,
                    ok ? "" : "  <-- off");
    }
    std::printf("%s\n", bad ? "FAIL" : "PASS (as warm as Windows or up to 1000 K warmer, above 6500 K clamped)");
    return bad ? 1 : 0;
}

static int sweep()
{
    const double luxes[] = {0, 10, 30, 50, 100, 300, 600, 900, 1200};
    std::printf("ambient");
    for (double l : luxes)
        std::printf(" %6.0flx", l);
    std::printf("\n");
    for (int k = 2700; k <= 6500; k += 200) {
        std::printf("%6dK", k);
        for (double l : luxes)
            std::printf(" %7.0f", targetTemperature(xyFromCct(k), l));
        std::printf("\n");
    }
    return 0;
}

// Simulated scenes, 2 s sampling, 0.5 s output ticks quantised to 100 K (what the shell sends
// KWin). Prints the applied temperature and the largest step between two ticks.
static int follow()
{
    struct Scene {
        const char *name;
        double (*cct)(double t);
        double (*lux)(double t);
    } scenes[] = {
        {"office 5000K -> warm lamp 2700K at t=20s", [](double t) { return t < 20 ? 5000.0 : 2700.0; }, [](double) { return 300.0; }},
        {"strobe: 2700K lamp switched on/off at random, about every second, over 5000K office",
         [](double t) { return ((unsigned(t) * 2654435761u) >> 31) ? 2700.0 : 5000.0; }, [](double) { return 300.0; }},
        {"daylight 6500K, lights off at t=20s (5 lx)", [](double) { return 6500.0; }, [](double t) { return t < 20 ? 400.0 : 5.0; }},
    };
    std::mt19937 rng(1);
    std::normal_distribution<double> noise(0.0, 0.004); // sensor xy noise (~0.025 HLK limit / 6)
    for (const Scene &s : scenes) {
        Follower f(6500);
        std::printf("\n# %s\n# t(s)  sensorK  goalK  appliedK\n", s.name);
        int last = 6500, maxStep = 0, changes = 0;
        bool first = true;
        for (double t = 0; t <= 60.0 + 1e-9; t += 0.5) {
            if (std::fmod(t, 2.0) < 1e-9) {
                Xy a = xyFromCct(s.cct(t));
                a.x += noise(rng);
                a.y += noise(rng);
                const double target = targetTemperature(a, s.lux(t));
                if (first)
                    f.reset(target, t, 2.0);
                else
                    f.addSample(target, t);
                first = false;
                std::printf("%5.1f  %7.0f  %5.0f", t, cctFromXy(a), f.goalKelvin());
            } else {
                std::printf("%5.1f  %7s  %5s", t, "", "");
            }
            const int applied = int(std::lround(f.currentKelvin(t) / 100.0) * 100);
            maxStep = std::max(maxStep, std::abs(applied - last));
            changes += applied != last;
            last = applied;
            std::printf("  %6d\n", applied);
        }
        std::printf("# largest step between 0.5 s ticks: %d K, changes: %d\n", maxStep, changes);
    }
    return 0;
}

static double cpuSeconds()
{
    rusage u{};
    getrusage(RUSAGE_SELF, &u);
    return u.ru_utime.tv_sec + u.ru_utime.tv_usec / 1e6 + u.ru_stime.tv_sec + u.ru_stime.tv_usec / 1e6;
}

static int live(const char *dir, int seconds)
{
    const std::string path = AlsSysfs::find(dir);
    AlsSysfs als;
    if (path.empty() || !als.open(path)) {
        std::fprintf(stderr, "no colour-capable IIO light sensor in %s\n", dir);
        return 2;
    }
    std::printf("# sensor %s (chromaticity: %s)\n# time      x      y      sensorK     lux   targetK  read-ms\n", path.c_str(),
                als.hasChromaticity() ? "yes" : "no, CCT only");
    const auto t0 = std::chrono::steady_clock::now();
    const double cpu0 = cpuSeconds();
    double readMs = 0;
    int n = 0;
    while (std::chrono::steady_clock::now() - t0 < std::chrono::seconds(seconds)) {
        const auto r0 = std::chrono::steady_clock::now();
        const AlsSysfs::Sample s = als.read();
        const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - r0).count();
        readMs += ms;
        ++n;
        const Xy xy = s.hasXy ? s.xy : s.hasCct ? xyFromCct(s.cct) : kD65;
        const double target = targetTemperature(xy, s.hasLux ? s.lux : 300);
        char ts[16];
        const std::time_t now = std::time(nullptr);
        std::strftime(ts, sizeof ts, "%H:%M:%S", std::localtime(&now));
        std::printf("%s  %.4f %.4f  %7.0f  %8.2f  %7.0f  %6.1f\n", ts, xy.x, xy.y, s.hasCct ? s.cct : cctFromXy(xy), s.lux, target, ms);
        std::fflush(stdout);
        std::this_thread::sleep_for(std::chrono::seconds(2));
    }
    const double wall = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    std::printf("# %d samples, mean read %.1f ms (blocked, not CPU), CPU %.3f s in %.0f s = %.4f %%\n", n, readMs / n,
                cpuSeconds() - cpu0, wall, 100.0 * (cpuSeconds() - cpu0) / wall);
    return 0;
}

int main(int argc, char **argv)
{
    const char *mode = argc > 1 ? argv[1] : "table";
    if (!std::strcmp(mode, "table"))
        return table();
    if (!std::strcmp(mode, "sweep"))
        return sweep();
    if (!std::strcmp(mode, "follow"))
        return follow();
    if (!std::strcmp(mode, "live"))
        return live(argc > 2 ? argv[2] : "/sys/bus/iio/devices", argc > 3 ? std::atoi(argv[3]) : 60);
    std::fprintf(stderr, "usage: %s table|sweep|follow|live [DIR [SECONDS]]\n", argv[0]);
    return 2;
}
