// SPDX-License-Identifier: GPL-3.0-or-later
// Adaptive color (Windows 11: Settings > System > Display > Brightness & color > "Adaptive
// color"): the white point of the screen follows the colour of the ambient light, read from an
// ambient light sensor that reports colour (any laptop whose IIO light sensor has
// in_chromaticity_x/y or in_colortemp: Samsung Galaxy Book, Surface, ThinkPad X1...).
// The mapping and the filter are Windows' (adaptivecolormodel.h).
//
// Sensor: sysfs, one sample every 2 s on a worker thread (a HID sensor takes ~100 ms per
// attribute, asleep); iio-sensor-proxy's D-Bus API has no colour. Stops while the screen is
// locked, the lid is closed, Night light owns the screen, or the feature is off.
//
// Output: KWin's Night light pipeline (blackbody channel factors on every output, in the
// colour pipeline / CRTC: no repaint cost, no flicker):
//   - Night light on, daytime: kwinrc [NightColor] DayTemperature = the adapted temperature.
//     KWin uses it as the day end of its schedule, so at night Night light's own temperature
//     applies and the evening/morning transitions blend from and to the adapted white.
//   - Night light on, night (or Constant mode): Night light wins, Adaptive color holds.
//   - Night light off: org.kde.KWin.NightLight.preview(temperature), renewed every 8 s (KWin
//     drops a preview after 15 s, so a dead shell leaves no tint behind); kwinrc is not touched.
//   - Night light suspended (inhibited: "colour-accurate" request): nothing applies.
// The user's own DayTemperature (if they lowered it) is the cap and is restored on exit or
// when the feature is turned off.
//   shell.conf [Display] AdaptiveColor=true|false (Settings > System > Display), default on.
//   FENESTRA_ALS_PATH: sensor directory (fake sysfs tree for tests).
//   QT_LOGGING_RULES="fenestra.adaptivecolor.debug=true": log every sample.
#pragma once

#include <QElapsedTimer>
#include <QObject>
#include <QQmlEngine>
#include <QThread>
#include <QTimer>

#include <memory>

#include "adaptivecolormodel.h"

class QDBusServiceWatcher;

// Reads the sensor on its own thread (blocking sysfs reads never touch the GUI thread).
class AlsWorker : public QObject
{
    Q_OBJECT
public:
    explicit AlsWorker(const QString &dir);
public Q_SLOTS:
    void sample();
Q_SIGNALS:
    void sampled(bool hasXy, double x, double y, bool hasCct, double cct, bool hasLux, double lux);

private:
    QString m_dir;
    std::unique_ptr<AdaptiveColorModel::AlsSysfs> m_als;
};

class AdaptiveColor : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(bool available READ available CONSTANT)
    Q_PROPERTY(bool enabled READ enabled NOTIFY changed)
    // What the sensor sees and what the screen gets (K, 0 when unknown).
    Q_PROPERTY(int ambientTemperature READ ambientTemperature NOTIFY changed)
    Q_PROPERTY(double illuminance READ illuminance NOTIFY changed)
    Q_PROPERTY(int temperature READ temperature NOTIFY changed)
public:
    static AdaptiveColor *instance();
    static AdaptiveColor *create(QQmlEngine *, QJSEngine *);
    ~AdaptiveColor() override;

    bool available() const { return !m_sensorDir.isEmpty(); }
    bool enabled() const { return m_enabled; }
    int ambientTemperature() const { return m_ambientK; }
    double illuminance() const { return m_lux; }
    int temperature() const { return m_appliedK; }

Q_SIGNALS:
    void changed();

private Q_SLOTS:
    void onNightLightProps(const QString &iface, const QVariantMap &props, const QStringList &invalidated);
    void onLogindProps(const QString &iface, const QVariantMap &props, const QStringList &invalidated);
    void onScreenSaver(bool active);
    void onPrepareForSleep(bool sleeping);

private:
    enum class Output { None, DayTemperature, Preview, Hold };

    explicit AdaptiveColor(QObject *parent = nullptr);
    void readSetting();
    void readKWinConfig();
    void queryNightLight();
    void nightLightChanged(const QVariantMap &props);
    void onLid(bool closed);
    void onSample(bool hasXy, double x, double y, bool hasCct, double cct, bool hasLux, double lux);
    void update();          // re-evaluates what runs (sampling, output path)
    void tick();            // one step of the transition
    void apply(int kelvin); // sends a temperature down the current output path
    void restore();         // gives the screen back (user's DayTemperature, no preview)
    void writeDayTemperature(int kelvin);
    void preview(int kelvin);
    void stopPreview();
    Output output() const;
    bool sampling() const;
    double now() const { return m_clock.elapsed() / 1000.0; }

    QString m_sensorDir;
    QThread m_thread;
    AlsWorker *m_worker = nullptr;
    QTimer m_sampleTimer, m_tickTimer, m_keepAlive;
    QElapsedTimer m_clock;
    QDBusServiceWatcher *m_kwinWatcher = nullptr;
    AdaptiveColorModel::Follower m_follower;

    bool m_enabled = false;
    bool m_locked = false, m_lidClosed = false;
    bool m_kwin = false;            // org.kde.KWin.NightLight answered
    bool m_nlRunning = false, m_nlInhibited = false, m_nlDaylight = true;
    bool m_fresh = true;            // next sample starts a quick transition (start, unlock, lid open)
    bool m_sampleInFlight = false;
    bool m_previewing = false;
    bool m_quitting = false;
    bool m_wroteDay = false;        // DayTemperature currently holds our value
    double m_pausedAt = -1;
    int m_baseDay = AdaptiveColorModel::kMaxTemperature; // the user's own DayTemperature
    int m_appliedK = AdaptiveColorModel::kMaxTemperature;
    int m_sentK = 0;                // last value sent down the output path
    int m_lastDay = 0;              // last DayTemperature written to kwinrc
    bool m_nlKnown = false;         // Night light's state was read once
    int m_ambientK = 0;
    double m_lux = 0;
    AdaptiveColorModel::Xy m_ambient = AdaptiveColorModel::kD65;
    bool m_haveAmbient = false;
    Output m_output = Output::None;
};
