// SPDX-License-Identifier: GPL-3.0-or-later
#include "poweridle.h"

#include "lockosd.h"

#include <KIdleTime>

#include <QDBusConnection>
#include <QDBusInterface>
#include <QDBusReply>
#include <QDebug>
#include <QProcess>

// GLib uses "signals" as a struct member name; Qt defines it as a macro.
#pragma push_macro("signals")
#undef signals
#include <gio/gio.h>
#pragma pop_macro("signals")

namespace
{
constexpr int kLockedMs = 60 * 1000; // Windows' console lock display-off timeout
constexpr uint kChangeScreenSettings = 4; // PowerDevil's PolicyAgent::RequiredPolicy
const QString s_agent = QStringLiteral("org.kde.Solid.PowerManagement.PolicyAgent");
const QString s_upower = QStringLiteral("org.freedesktop.UPower");
const QString s_upowerPath = QStringLiteral("/org/freedesktop/UPower");
}

PowerIdle *PowerIdle::instance()
{
    static auto *idle = new PowerIdle;
    return idle;
}

PowerIdle::PowerIdle(QObject *parent)
    : QObject(parent)
    , m_testBattery(qEnvironmentVariableIntValue("FENESTRA_TEST_ON_BATTERY") == 1) // benches have no UPower
{
    GSettingsSchemaSource *source = g_settings_schema_source_get_default();
    GSettingsSchema *schema = source ? g_settings_schema_source_lookup(source, "org.gnome.desktop.session", TRUE) : nullptr;
    if (schema) {
        g_settings_schema_unref(schema);
        m_settings = g_settings_new("org.gnome.desktop.session");
        g_signal_connect(m_settings, "changed::idle-delay", G_CALLBACK(onDelayChanged), this);
    }

    auto session = QDBusConnection::sessionBus();
    // Never in the way of a real PowerDevil (a Plasma session on the same bus).
    session.registerObject(QStringLiteral("/org/kde/Solid/PowerManagement/PolicyAgent"), s_agent, this, QDBusConnection::ExportScriptableSlots);
    session.registerService(s_agent);

    QDBusConnection::systemBus().connect(s_upower, s_upowerPath, QStringLiteral("org.freedesktop.DBus.Properties"),
                                         QStringLiteral("PropertiesChanged"), this, SLOT(batteryChanged()));
    connect(LockOsd::instance(), &LockOsd::lockedChanged, this, &PowerIdle::rearm);
    connect(KIdleTime::instance(), &KIdleTime::timeoutReached, this, [this](int id, int) {
        timedOut(id);
    });
    batteryChanged();
}

void PowerIdle::onDelayChanged(GSettings *, const char *, void *self)
{
    static_cast<PowerIdle *>(self)->rearm();
}

void PowerIdle::batteryChanged()
{
    bool onBattery = m_testBattery;
    if (!m_testBattery) {
        QDBusInterface upower(s_upower, s_upowerPath, s_upower, QDBusConnection::systemBus());
        onBattery = upower.isValid() && upower.property("OnBattery").toBool();
    }
    m_onBattery = onBattery;
    rearm();
}

void PowerIdle::rearm()
{
    if (m_timeout >= 0) {
        KIdleTime::instance()->removeIdleTimeout(m_timeout);
        m_timeout = -1;
    }
    if (!m_onBattery) {
        return;
    }
    int ms = 0;
    if (LockOsd::instance()->locked()) {
        ms = kLockedMs;
    } else if (m_settings && m_screenInhibitions.isEmpty()) {
        ms = int(g_settings_get_uint(m_settings, "idle-delay")) * 1000;
    }
    if (ms > 0) {
        m_timeout = KIdleTime::instance()->addIdleTimeout(ms);
    }
    qInfo().noquote() << "FENESTRA_POWERIDLE battery" << m_onBattery << "locked" << LockOsd::instance()->locked() << "inhibitions"
                      << m_screenInhibitions.size() << "timeout-ms" << ms;
}

void PowerIdle::timedOut(int id)
{
    if (id != m_timeout) {
        return;
    }
    qInfo("FENESTRA_POWERIDLE screen off");
    QProcess::startDetached(QStringLiteral("kscreen-doctor"), {QStringLiteral("--dpms"), QStringLiteral("off")});
}

uint PowerIdle::AddInhibition(uint types, const QString &appName, const QString &reason)
{
    Q_UNUSED(appName)
    Q_UNUSED(reason)
    const uint cookie = m_nextCookie++;
    if (types & kChangeScreenSettings) {
        m_screenInhibitions.insert(cookie);
        rearm();
    }
    return cookie;
}

void PowerIdle::ReleaseInhibition(uint cookie)
{
    if (m_screenInhibitions.remove(cookie)) {
        rearm();
    }
}
