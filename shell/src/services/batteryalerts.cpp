// SPDX-License-Identifier: GPL-3.0-or-later
#include "batteryalerts.h"

#include "notifications.h"
#include "status.h"
#include "system.h"

#include <QLocale>

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
    connect(p, &PowerStatus::changed, this, [this, p] { if (!m_testing) update(p->percentage(), p->hasBattery(), p->pluggedIn()); });
    update(p->percentage(), p->hasBattery(), p->pluggedIn());
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
    if (m_saverAuto) {
        auto *pp = PowerProfiles::instance();
        if (pp->available() && pp->active() == QLatin1String("power-saver"))
            pp->setActive(m_saverBefore.isEmpty() ? QStringLiteral("balanced") : m_saverBefore);
        m_saverAuto = false;
    }
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
        if (m_last >= 0)
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
        return;
    }
    m_testing = true;
    update(percent, true, pluggedIn);
}

QString BatteryAlerts::testState() const
{
    return QStringLiteral("last=%1 saverAuto=%2 before=%3 set=%4 low=%5 reserve=%6 critical=%7 brightness=%8 profile=%9")
        .arg(m_last).arg(m_saverAuto).arg(m_brightnessBefore).arg(m_brightnessSet)
        .arg(m_notifiedLow).arg(m_notifiedReserve).arg(m_notifiedCritical)
        .arg(Brightness::instance()->percent()).arg(PowerProfiles::instance()->active());
}
