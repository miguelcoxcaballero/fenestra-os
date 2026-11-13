// SPDX-License-Identifier: GPL-3.0-or-later
#include "batteryalerts.h"

#include "notifications.h"
#include "status.h"
#include "system.h"

#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLocale>
#include <QProcess>
#include <QSettings>
#include <QTimer>
#include <QStandardPaths>

namespace
{
constexpr int kSaverLevel = 20, kLowLevel = 10, kReserveLevel = 7, kCriticalLevel = 5;
constexpr double kSaverDim = 0.70;    // Energy saver: brightness lowered by 30 %
constexpr double kCriticalDim = 0.70; // at the critical level, 30 % less again
bool spanish() { return QLocale().name().startsWith(QLatin1String("es")); }
}

BatteryAlerts *BatteryAlerts::instance()
{
    static BatteryAlerts alerts;
    return &alerts;
}

BatteryAlerts *BatteryAlerts::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

BatteryAlerts::BatteryAlerts(QObject *parent)
    : QObject(parent)
{
    auto *p = PowerStatus::instance();
    connect(p, &PowerStatus::changed, this, [this, p] {
        if (m_testing)
            return;
        update(p->percentage(), p->hasBattery(), p->pluggedIn());
        if (p->hasBattery())
            applyRefresh(!p->pluggedIn());
    });
    // Energy saver we turned on survives a restart of the shell (and of the PC: tuned keeps the
    // profile): without this note nobody would turn it off again and the PC would stay throttled.
    QSettings state(stateFile(), QSettings::IniFormat);
    if (state.value(QStringLiteral("Battery/SaverAuto"), false).toBool()) {
        m_saverAuto = true;
        m_saverBefore = state.value(QStringLiteral("Battery/SaverBefore")).toString();
        if (p->hasBattery() && !p->pluggedIn() && p->percentage() > kSaverLevel)
            leaveSaver();   // charged above the level while the shell was not looking
        else
            m_last = p->hasBattery() && !p->pluggedIn() ? p->percentage() : -2;
    }
    if (p->hasBattery())
        applyRefresh(!p->pluggedIn());
    update(p->percentage(), p->hasBattery(), p->pluggedIn());
}

QString BatteryAlerts::stateFile()
{
    return QStandardPaths::writableLocation(QStandardPaths::GenericStateLocation) + QStringLiteral("/fenestra/shell-state.conf");
}

void BatteryAlerts::rememberSaver()
{
    QSettings state(stateFile(), QSettings::IniFormat);
    state.setValue(QStringLiteral("Battery/SaverAuto"), m_saverAuto);
    state.setValue(QStringLiteral("Battery/SaverBefore"), m_saverBefore);
}

void BatteryAlerts::leaveSaver()
{
    if (!m_saverAuto)
        return;
    auto *pp = PowerProfiles::instance();
    // The profiles daemon answers a moment after the shell starts (later still at boot). Giving up
    // here, or reading an active profile that is not known yet, forgot the note while the PC was
    // still in power saver: it stayed throttled (turbo off) for good, plugged in or not. Wait for
    // the daemon's answer, however long it takes.
    if (!pp->available() || pp->active().isEmpty()) {
        if (!m_leavePending) {
            m_leavePending = true;
            connect(pp, &PowerProfiles::changed, this, [this] {
                if (m_leavePending)
                    leaveSaver();
            });
        }
        return;
    }
    m_leavePending = false;
    if (pp->active() == QLatin1String("power-saver"))
        pp->setActive(m_saverBefore.isEmpty() || m_saverBefore == QLatin1String("power-saver") ? QStringLiteral("balanced") : m_saverBefore);
    m_saverAuto = false;
    rememberSaver();
}

void BatteryAlerts::dimBy(double factor)
{
    auto *b = Brightness::instance();
    if (!b->available())
        return;
    const int now = b->percent();
    // The user moved the slider since our last change: dim from their value, restore to it.
    if (m_brightnessBefore < 0 || (m_brightnessSet >= 0 && now != m_brightnessSet))
        m_brightnessBefore = now;
    m_brightnessSet = std::max(1, int(now * factor + 0.5));
    b->setPercent(m_brightnessSet);
}

void BatteryAlerts::restore()
{
    leaveSaver();
    auto *b = Brightness::instance();
    // Give the brightness back only if nobody changed it meanwhile (as Windows on plugging in).
    if (m_brightnessBefore >= 0 && b->available() && b->percent() == m_brightnessSet)
        b->setPercent(m_brightnessBefore);
    m_brightnessBefore = m_brightnessSet = -1;
    m_notifiedLow = m_notifiedReserve = m_notifiedCritical = false;
}

void BatteryAlerts::update(int percent, bool hasBattery, bool pluggedIn)
{
    if (!hasBattery || pluggedIn) {
        if (m_last >= 0 || m_last == -2 || m_saverAuto)
            restore();
        m_last = -1;
        return;
    }
    const bool es = spanish();
    const int before = m_last < 0 ? 101 : m_last;   // a level first seen on battery counts as crossing
    m_last = percent;
    auto crossed = [&](int level) { return before > level && percent <= level; };
    auto *n = Notifications::instance();
    const QString app = es ? QStringLiteral("Batería") : QStringLiteral("Battery");

    if (crossed(kSaverLevel)) {
        auto *pp = PowerProfiles::instance();
        if (pp->available() && pp->active() != QLatin1String("power-saver")) {
            m_saverBefore = pp->active();
            pp->setActive(QStringLiteral("power-saver"));
            m_saverAuto = true;
            rememberSaver();
        }
        dimBy(kSaverDim);
    }
    if (percent <= kCriticalLevel && !m_notifiedCritical) {
        m_notifiedCritical = m_notifiedReserve = m_notifiedLow = true;
        dimBy(kCriticalDim);
        n->notify(app, QStringLiteral("battery-caution-symbolic"),
                  es ? QStringLiteral("La batería está muy baja") : QStringLiteral("Your battery is very low"),
                  es ? QStringLiteral("Conecta el equipo ahora. Queda un %1 %.").arg(percent)
                     : QStringLiteral("Plug in your PC now. %1% remaining.").arg(percent));
    } else if (percent <= kReserveLevel && !m_notifiedReserve) {
        m_notifiedReserve = m_notifiedLow = true;
        n->notify(app, QStringLiteral("battery-caution-symbolic"),
                  es ? QStringLiteral("La batería está muy baja") : QStringLiteral("Your battery is very low"),
                  es ? QStringLiteral("Está usando la energía de reserva. Conecta el equipo. Queda un %1 %.").arg(percent)
                     : QStringLiteral("You're running on reserve power. Plug in your PC. %1% remaining.").arg(percent));
    } else if (percent <= kLowLevel && !m_notifiedLow) {
        m_notifiedLow = true;
        n->notify(app, QStringLiteral("battery-low-symbolic"),
                  es ? QStringLiteral("La batería se está agotando") : QStringLiteral("Your battery is running low"),
                  es ? QStringLiteral("Es posible que quieras conectar el equipo. Queda un %1 %.").arg(percent)
                     : QStringLiteral("You might want to plug in your PC. %1% remaining.").arg(percent));
    }
}

void BatteryAlerts::testLevel(int percent, bool pluggedIn)
{
    if (percent < 0) {
        m_testing = false;
        auto *p = PowerStatus::instance();
        update(p->percentage(), p->hasBattery(), p->pluggedIn());
        if (p->hasBattery())
            applyRefresh(!p->pluggedIn());
        return;
    }
    m_testing = true;
    update(percent, true, pluggedIn);
    applyRefresh(!pluggedIn);
}

QString BatteryAlerts::testState() const
{
    return QStringLiteral("last=%1 saverAuto=%2 before=%3 set=%4 low=%5 reserve=%6 critical=%7 brightness=%8 profile=%9")
        .arg(m_last).arg(m_saverAuto).arg(m_brightnessBefore).arg(m_brightnessSet)
        .arg(m_notifiedLow).arg(m_notifiedReserve).arg(m_notifiedCritical)
        .arg(Brightness::instance()->percent()).arg(PowerProfiles::instance()->active());
}

void BatteryAlerts::applyRefresh(bool onBattery)
{
    const int want = onBattery ? 1 : 0;
    if (want == m_refreshState)
        return;
    const QSettings conf(QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation) + QStringLiteral("/fenestra/shell.conf"),
                         QSettings::IniFormat);
    if (!conf.value(QStringLiteral("Display/DynamicRefresh"), false).toBool())
        return;
    if (QStandardPaths::findExecutable(QStringLiteral("kscreen-doctor")).isEmpty())
        return;
    m_refreshState = want;
    auto *proc = new QProcess(this);
    connect(proc, &QProcess::finished, this, [this, proc, onBattery] {
        proc->deleteLater();
        const QJsonArray outputs = QJsonDocument::fromJson(proc->readAllStandardOutput()).object().value(QStringLiteral("outputs")).toArray();
        QStringList args;
        for (const QJsonValue &v : outputs) {
            const QJsonObject o = v.toObject();
            const QString name = o.value(QStringLiteral("name")).toString();
            const bool internal = name.startsWith(QLatin1String("eDP")) || name.startsWith(QLatin1String("LVDS")) || name.startsWith(QLatin1String("DSI"));
            if (!internal || !o.value(QStringLiteral("connected")).toBool() || !o.value(QStringLiteral("enabled")).toBool())
                continue;
            const QString currentId = o.value(QStringLiteral("currentModeId")).toString();
            const QJsonArray modes = o.value(QStringLiteral("modes")).toArray();
            QJsonObject current;
            for (const QJsonValue &m : modes)
                if (m.toObject().value(QStringLiteral("id")).toString() == currentId)
                    current = m.toObject();
            if (current.isEmpty())
                continue;
            const QJsonObject size = current.value(QStringLiteral("size")).toObject();
            // Same resolution: on battery the rate closest to 60 Hz (not below 59), on AC the highest.
            QString best;
            double bestRate = onBattery ? 1e9 : 0;
            for (const QJsonValue &m : modes) {
                const QJsonObject mo = m.toObject();
                if (mo.value(QStringLiteral("size")).toObject() != size)
                    continue;
                const double r = mo.value(QStringLiteral("refreshRate")).toDouble();
                if (onBattery ? (r >= 59.0 && r < bestRate) : (r > bestRate)) {
                    bestRate = r;
                    best = mo.value(QStringLiteral("id")).toString();
                }
            }
            if (!best.isEmpty() && best != currentId)
                args << QStringLiteral("output.%1.mode.%2").arg(name, best);
        }
        if (!args.isEmpty())
            QProcess::startDetached(QStringLiteral("kscreen-doctor"), args);
    });
    proc->start(QStringLiteral("kscreen-doctor"), {QStringLiteral("-j")});
}
