// SPDX-License-Identifier: GPL-3.0-or-later
#include "adaptivecolor.h"

#include "shellsettings.h"

#include <KConfigGroup>
#include <KConfigWatcher>
#include <KSharedConfig>

#include <QCoreApplication>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusServiceWatcher>
#include <QDBusVariant>
#include <QLoggingCategory>

using namespace AdaptiveColorModel;

Q_LOGGING_CATEGORY(lcAdaptive, "fenestra.adaptivecolor", QtWarningMsg)

namespace
{
const QString kKWin = QStringLiteral("org.kde.KWin");
const QString kNightLightPath = QStringLiteral("/org/kde/KWin/NightLight");
const QString kNightLightIface = QStringLiteral("org.kde.KWin.NightLight");
const QString kProps = QStringLiteral("org.freedesktop.DBus.Properties");
const QString kLogin1 = QStringLiteral("org.freedesktop.login1");
const QString kLogin1Path = QStringLiteral("/org/freedesktop/login1");
const QString kLogin1Manager = QStringLiteral("org.freedesktop.login1.Manager");
const QString kNightColor = QStringLiteral("NightColor");
const char kDayKey[] = "DayTemperature";
// What Fenestra wrote, and the user's own value before it: KWin ignores unknown keys.
const char kOursKey[] = "X-Fenestra-AdaptiveColor";
const char kBaseKey[] = "X-Fenestra-DayTemperature";

constexpr int kStepK = 100;            // KWin ramps each step in 50 K steps of its own
constexpr int kTickMs = 500;           // Windows' ColorTransitionMinTransitionTime is 300 ms
constexpr int kKeepAliveMs = 8000;     // KWin ends a preview after 15 s
constexpr double kResumeAfter = 15.0;  // Windows: lid open within 15 s keeps the last white point
constexpr double kQuickSeconds = 1.5;  // ... after longer, the new white point within ~1 s
constexpr double kStartSeconds = 2.0;  // turning the feature on: quick, but subtle

int quantise(double k)
{
    return std::clamp(int(std::lround(k / kStepK)) * kStepK, 1000, kMaxTemperature);
}

KConfigGroup nightColor()
{
    auto cfg = KSharedConfig::openConfig(QStringLiteral("kwinrc"));
    return cfg->group(kNightColor);
}
}

// ---- sensor thread ----------------------------------------------------------------------------
AlsWorker::AlsWorker(const QString &dir)
    : m_dir(dir)
{
}

void AlsWorker::sample()
{
    if (!m_als) {
        m_als = std::make_unique<AlsSysfs>();
        if (!m_als->open(m_dir.toStdString()))
            qCWarning(lcAdaptive) << "cannot open the light sensor" << m_dir;
    }
    const AlsSysfs::Sample s = m_als->read();
    Q_EMIT sampled(s.hasXy, s.xy.x, s.xy.y, s.hasCct, s.cct, s.hasLux, s.lux);
}

// ---- service ----------------------------------------------------------------------------------
AdaptiveColor *AdaptiveColor::instance()
{
    static auto *s = new AdaptiveColor; // lives as long as the shell (its thread stops on quit)
    return s;
}

AdaptiveColor *AdaptiveColor::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

AdaptiveColor::AdaptiveColor(QObject *parent)
    : QObject(parent)
{
    m_clock.start();
    const QByteArray fake = qgetenv("FENESTRA_ALS_PATH");
    m_sensorDir = QString::fromStdString(AlsSysfs::find(fake.isEmpty() ? std::string("/sys/bus/iio/devices") : fake.toStdString()));
    if (m_sensorDir.isEmpty()) {
        qCInfo(lcAdaptive) << "no ambient light sensor with colour: Adaptive color unavailable";
        return;
    }
    qCInfo(lcAdaptive) << "colour light sensor" << m_sensorDir;

    m_worker = new AlsWorker(m_sensorDir);
    m_worker->moveToThread(&m_thread);
    connect(&m_thread, &QThread::finished, m_worker, &QObject::deleteLater);
    connect(m_worker, &AlsWorker::sampled, this, &AdaptiveColor::onSample, Qt::QueuedConnection);
    m_thread.setObjectName(QStringLiteral("adaptive-color"));
    m_thread.start(QThread::LowPriority);

    bool ok = false;
    const int interval = qEnvironmentVariableIntValue("FENESTRA_ADAPTIVE_COLOR_INTERVAL_MS", &ok);
    m_sampleTimer.setInterval(ok && interval >= 100 ? interval : 2000);
    m_sampleTimer.setTimerType(Qt::CoarseTimer);
    connect(&m_sampleTimer, &QTimer::timeout, this, [this] {
        if (m_sampleInFlight)
            return;
        m_sampleInFlight = true;
        QMetaObject::invokeMethod(m_worker, &AlsWorker::sample, Qt::QueuedConnection);
    });
    m_tickTimer.setInterval(kTickMs);
    connect(&m_tickTimer, &QTimer::timeout, this, &AdaptiveColor::tick);
    m_keepAlive.setInterval(kKeepAliveMs);
    m_keepAlive.setTimerType(Qt::CoarseTimer);
    connect(&m_keepAlive, &QTimer::timeout, this, [this] {
        if (m_previewing)
            preview(m_sentK);
    });

    // The user's (or KDE's) own DayTemperature, and leftovers of a shell that did not exit.
    readKWinConfig();
    m_follower = Follower(m_wroteDay ? nightColor().readEntry(kDayKey, kMaxTemperature) : kMaxTemperature);
    auto watcher = KConfigWatcher::create(KSharedConfig::openConfig(QStringLiteral("kwinrc")));
    connect(watcher.data(), &KConfigWatcher::configChanged, this, [this](const KConfigGroup &group) {
        if (group.name() != kNightColor)
            return;
        const int day = std::clamp(group.readEntry(kDayKey, kMaxTemperature), 1000, kMaxTemperature);
        if (m_wroteDay ? day != m_sentK : day != m_baseDay) {
            // Someone else (KDE's Night light page) set the day temperature: that is the cap now.
            m_baseDay = day;
            m_wroteDay = false;
            m_sentK = 0;
            qCInfo(lcAdaptive) << "day temperature set elsewhere:" << day;
            update();
        }
    });
    static KConfigWatcher::Ptr keep;
    keep = watcher;

    connect(ShellSettings::instance(), &ShellSettings::fileChanged, this, &AdaptiveColor::readSetting);

    auto bus = QDBusConnection::sessionBus();
    bus.connect(kKWin, kNightLightPath, kProps, QStringLiteral("PropertiesChanged"), this,
                SLOT(onNightLightProps(QString, QVariantMap, QStringList)));
    bus.connect(QStringLiteral("org.freedesktop.ScreenSaver"), QStringLiteral("/ScreenSaver"), QStringLiteral("org.freedesktop.ScreenSaver"),
                QStringLiteral("ActiveChanged"), this, SLOT(onScreenSaver(bool)));
    m_kwinWatcher = new QDBusServiceWatcher(kKWin, bus, QDBusServiceWatcher::WatchForRegistration | QDBusServiceWatcher::WatchForUnregistration, this);
    connect(m_kwinWatcher, &QDBusServiceWatcher::serviceRegistered, this, [this] {
        m_previewing = false; // a new KWin has no preview of ours
        m_sentK = 0;
        queryNightLight();
    });
    connect(m_kwinWatcher, &QDBusServiceWatcher::serviceUnregistered, this, [this] {
        m_kwin = false;
        m_previewing = false;
        update();
    });
    auto sys = QDBusConnection::systemBus();
    sys.connect(kLogin1, kLogin1Path, kProps, QStringLiteral("PropertiesChanged"), this,
                SLOT(onLogindProps(QString, QVariantMap, QStringList)));
    sys.connect(kLogin1, kLogin1Path, kLogin1Manager, QStringLiteral("PrepareForSleep"), this, SLOT(onPrepareForSleep(bool)));

    auto *saver = new QDBusPendingCallWatcher(
        bus.asyncCall(QDBusMessage::createMethodCall(QStringLiteral("org.freedesktop.ScreenSaver"), QStringLiteral("/ScreenSaver"),
                                                     QStringLiteral("org.freedesktop.ScreenSaver"), QStringLiteral("GetActive"))),
        this);
    connect(saver, &QDBusPendingCallWatcher::finished, this, [this](QDBusPendingCallWatcher *w) {
        QDBusPendingReply<bool> r = *w;
        if (r.isValid())
            onScreenSaver(r.value());
        w->deleteLater();
    });
    QDBusMessage lid = QDBusMessage::createMethodCall(kLogin1, kLogin1Path, kProps, QStringLiteral("Get"));
    lid.setArguments({kLogin1Manager, QStringLiteral("LidClosed")});
    auto *lidCall = new QDBusPendingCallWatcher(sys.asyncCall(lid), this);
    connect(lidCall, &QDBusPendingCallWatcher::finished, this, [this](QDBusPendingCallWatcher *w) {
        QDBusPendingReply<QDBusVariant> r = *w;
        if (r.isValid())
            onLid(r.value().variant().toBool());
        w->deleteLater();
    });

    connect(qApp, &QCoreApplication::aboutToQuit, this, [this] {
        m_quitting = true;
        m_sampleTimer.stop();
        m_tickTimer.stop();
        m_keepAlive.stop();
        restore();
        m_thread.quit();
        m_thread.wait(1000);
    });

    readSetting();
    queryNightLight();
}

AdaptiveColor::~AdaptiveColor()
{
    m_thread.quit();
    m_thread.wait(1000);
}

void AdaptiveColor::readSetting()
{
    const bool on = ShellSettings::instance()->value(QStringLiteral("Display/AdaptiveColor"), true).toBool();
    if (on == m_enabled)
        return;
    m_enabled = on;
    qCInfo(lcAdaptive) << (on ? "on" : "off");
    if (on)
        m_fresh = true;
    update();
    Q_EMIT changed();
}

void AdaptiveColor::readKWinConfig()
{
    KSharedConfig::openConfig(QStringLiteral("kwinrc"))->reparseConfiguration();
    const KConfigGroup g = nightColor();
    const int day = std::clamp(g.readEntry(kDayKey, kMaxTemperature), 1000, kMaxTemperature);
    const int ours = g.readEntry(kOursKey, 0);
    if (ours != 0 && ours == day) {
        // Left by a shell that did not exit cleanly: carry on from there.
        m_baseDay = std::clamp(g.readEntry(kBaseKey, kMaxTemperature), 1000, kMaxTemperature);
        m_wroteDay = true;
        m_sentK = day;
        m_appliedK = day;
    } else {
        m_baseDay = day;
        m_wroteDay = false;
    }
}

void AdaptiveColor::queryNightLight()
{
    QDBusMessage m = QDBusMessage::createMethodCall(kKWin, kNightLightPath, kProps, QStringLiteral("GetAll"));
    m.setArguments({kNightLightIface});
    auto *w = new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(m), this);
    connect(w, &QDBusPendingCallWatcher::finished, this, [this](QDBusPendingCallWatcher *w) {
        QDBusPendingReply<QVariantMap> r = *w;
        w->deleteLater();
        if (!r.isValid()) {
            qCInfo(lcAdaptive) << "KWin Night light not reachable:" << r.error().message();
            m_kwin = false;
            update();
            return;
        }
        m_kwin = true;
        nightLightChanged(r.value());
    });
}

void AdaptiveColor::onNightLightProps(const QString &iface, const QVariantMap &props, const QStringList &)
{
    if (iface == kNightLightIface)
        nightLightChanged(props);
}

void AdaptiveColor::nightLightChanged(const QVariantMap &props)
{
    bool relevant = false;
    auto take = [&](const char *key, bool &field) {
        const auto it = props.constFind(QLatin1String(key));
        if (it != props.constEnd() && it->toBool() != field) {
            field = it->toBool();
            relevant = true;
        }
    };
    take("running", m_nlRunning);
    take("inhibited", m_nlInhibited);
    take("daylight", m_nlDaylight);
    if (relevant || m_output == Output::None) {
        qCInfo(lcAdaptive) << "Night light running" << m_nlRunning << "inhibited" << m_nlInhibited << "daylight" << m_nlDaylight;
        update();
    }
}

void AdaptiveColor::onScreenSaver(bool active)
{
    if (active == m_locked)
        return;
    m_locked = active;
    update();
}

void AdaptiveColor::onLid(bool closed)
{
    if (closed == m_lidClosed)
        return;
    m_lidClosed = closed;
    update();
}

void AdaptiveColor::onLogindProps(const QString &iface, const QVariantMap &props, const QStringList &)
{
    if (iface == kLogin1Manager && props.contains(QStringLiteral("LidClosed")))
        onLid(props.value(QStringLiteral("LidClosed")).toBool());
}

void AdaptiveColor::onPrepareForSleep(bool sleeping)
{
    if (sleeping) {
        m_sampleTimer.stop();
        if (m_pausedAt < 0)
            m_pausedAt = now();
        return;
    }
    // Back from suspend: new place, new light. Adapt quickly, as Windows on lid open.
    m_fresh = true;
    m_sampleTimer.stop(); // update() restarts it with a sample right away
    update();
}

AdaptiveColor::Output AdaptiveColor::output() const
{
    if (!available() || !m_enabled || !m_kwin || m_nlInhibited)
        return Output::None;
    if (m_nlRunning)
        return m_nlDaylight ? Output::DayTemperature : Output::Hold;
    return Output::Preview;
}

bool AdaptiveColor::sampling() const
{
    const Output o = output();
    return (o == Output::DayTemperature || o == Output::Preview) && !m_locked && !m_lidClosed;
}

void AdaptiveColor::update()
{
    if (!available())
        return;
    const Output o = output();
    if (o != m_output) {
        qCInfo(lcAdaptive) << "output" << int(m_output) << "->" << int(o);
        if (m_output == Output::Preview && m_previewing)
            stopPreview();
        if (o == Output::None) {
            restore();
            m_follower.goTo(m_baseDay, now(), 0);
            m_appliedK = kMaxTemperature;
            m_fresh = true;
            Q_EMIT changed();
        }
        m_sentK = m_wroteDay && o == Output::DayTemperature ? m_sentK : 0;
        m_output = o;
    }

    if (sampling()) {
        if (!m_sampleTimer.isActive()) {
            if (m_pausedAt >= 0 && now() - m_pausedAt > kResumeAfter)
                m_fresh = true;
            m_pausedAt = -1;
            m_sampleTimer.start();
            if (!m_sampleInFlight) {
                m_sampleInFlight = true;
                QMetaObject::invokeMethod(m_worker, &AlsWorker::sample, Qt::QueuedConnection);
            }
        }
    } else if (m_sampleTimer.isActive()) {
        m_sampleTimer.stop();
        m_pausedAt = now();
    }

    if (o == Output::DayTemperature || o == Output::Preview) {
        if (!m_fresh)
            apply(quantise(m_follower.currentKelvin(now())));
        if (m_follower.moving(now()) && !m_tickTimer.isActive())
            m_tickTimer.start();
    } else {
        m_tickTimer.stop();
    }
    if (m_previewing != m_keepAlive.isActive())
        m_previewing ? m_keepAlive.start() : m_keepAlive.stop();
}

void AdaptiveColor::onSample(bool hasXy, double x, double y, bool hasCct, double cct, bool hasLux, double lux)
{
    m_sampleInFlight = false;
    if (!sampling())
        return;
    if (hasXy) {
        m_ambient = {x, y};
        m_haveAmbient = true;
    } else if (hasCct) {
        m_ambient = xyFromCct(cct);
        m_haveAmbient = true;
    }
    // No colour reading yet (dark, or a sensor that only woke up): the low-light white point
    // still applies through the lux weighting; without lux at all, as indoor light.
    const double l = hasLux ? lux : 300.0;
    const double target = targetTemperature(m_haveAmbient ? m_ambient : kD65, l, m_baseDay);
    m_ambientK = m_haveAmbient ? int(std::lround(hasCct && !hasXy ? cct : cctFromXy(m_ambient))) : 0;
    m_lux = l;
    qCDebug(lcAdaptive).nospace() << "sample xy " << (hasXy ? x : 0) << "," << (hasXy ? y : 0) << " cct " << (hasCct ? cct : 0) << " lux "
                                  << (hasLux ? lux : -1) << " -> ambient " << m_ambientK << " K, target " << int(target) << " K";
    const double t = now();
    if (m_fresh) {
        m_follower.reset(target, t, m_appliedK == kMaxTemperature && m_sentK == 0 ? kStartSeconds : kQuickSeconds);
        m_fresh = false;
        qCInfo(lcAdaptive) << "adapting to" << int(target) << "K (ambient" << m_ambientK << "K," << l << "lx)";
    } else if (m_follower.addSample(target, t)) {
        qCInfo(lcAdaptive) << "transition to" << int(m_follower.goalKelvin()) << "K (ambient" << m_ambientK << "K," << l << "lx)";
    }
    if (m_follower.moving(t) && !m_tickTimer.isActive())
        m_tickTimer.start();
    tick();
    Q_EMIT changed();
}

void AdaptiveColor::tick()
{
    const double t = now();
    apply(quantise(m_follower.currentKelvin(t)));
    if (!m_follower.moving(t))
        m_tickTimer.stop();
}

void AdaptiveColor::apply(int kelvin)
{
    kelvin = std::min(kelvin, m_baseDay);
    switch (m_output) {
    case Output::DayTemperature:
        if (kelvin != m_sentK) {
            writeDayTemperature(kelvin);
            m_sentK = kelvin;
        }
        break;
    case Output::Preview:
        if (kelvin >= kMaxTemperature) {
            if (m_previewing)
                stopPreview();
        } else if (kelvin != m_sentK || !m_previewing) {
            preview(kelvin);
        }
        m_sentK = kelvin;
        break;
    case Output::None:
    case Output::Hold:
        return;
    }
    if (m_previewing != m_keepAlive.isActive())
        m_previewing ? m_keepAlive.start() : m_keepAlive.stop();
    if (kelvin != m_appliedK) {
        m_appliedK = kelvin;
        qCDebug(lcAdaptive) << "applied" << kelvin << "K via" << (m_output == Output::Preview ? "preview" : "DayTemperature");
        Q_EMIT changed();
    }
}

void AdaptiveColor::writeDayTemperature(int kelvin)
{
    KConfigGroup g = nightColor();
    g.writeEntry(kBaseKey, m_baseDay);
    g.writeEntry(kOursKey, kelvin);
    // KConfig::Notify: KWin's config watcher reconfigures Night light, which ramps there.
    g.writeEntry(kDayKey, kelvin, KConfig::Notify);
    g.sync();
    m_wroteDay = true;
}

void AdaptiveColor::restore()
{
    if (m_previewing)
        stopPreview();
    if (m_wroteDay) {
        KConfigGroup g = nightColor();
        if (m_baseDay >= kMaxTemperature)
            g.deleteEntry(kDayKey, KConfig::Notify);
        else
            g.writeEntry(kDayKey, m_baseDay, KConfig::Notify);
        g.deleteEntry(kOursKey);
        g.deleteEntry(kBaseKey);
        g.sync();
        m_wroteDay = false;
    }
    m_sentK = 0;
}

void AdaptiveColor::preview(int kelvin)
{
    QDBusMessage m = QDBusMessage::createMethodCall(kKWin, kNightLightPath, kNightLightIface, QStringLiteral("preview"));
    m.setArguments({uint(kelvin)});
    QDBusConnection::sessionBus().send(m);
    m_previewing = true;
}

void AdaptiveColor::stopPreview()
{
    QDBusMessage m = QDBusMessage::createMethodCall(kKWin, kNightLightPath, kNightLightIface, QStringLiteral("stopPreview"));
    // Blocking on quit, so the message leaves before the connection closes.
    if (m_quitting)
        QDBusConnection::sessionBus().call(m, QDBus::Block, 500);
    else
        QDBusConnection::sessionBus().send(m);
    m_previewing = false;
}
