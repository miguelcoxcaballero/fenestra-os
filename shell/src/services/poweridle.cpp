// SPDX-License-Identifier: GPL-3.0-or-later
#include "poweridle.h"

#include "lockosd.h"

#include <KIdleTime>

#include <QDBusConnection>
#include <QDBusInterface>
#include <QDBusMessage>
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
constexpr uint kInterruptSession = 1; // PowerDevil's PolicyAgent::RequiredPolicy
constexpr uint kChangeScreenSettings = 4;
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
    schema = source ? g_settings_schema_source_lookup(source, "org.gnome.settings-daemon.plugins.power", TRUE) : nullptr;
    if (schema) {
        g_settings_schema_unref(schema);
        m_power = g_settings_new("org.gnome.settings-daemon.plugins.power");
        g_signal_connect(m_power, "changed::sleep-inactive-battery-timeout", G_CALLBACK(onDelayChanged), this);
        g_signal_connect(m_power, "changed::sleep-inactive-battery-type", G_CALLBACK(onDelayChanged), this);
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
    if (m_sleepTimeout >= 0) {
        KIdleTime::instance()->removeIdleTimeout(m_sleepTimeout);
        m_sleepTimeout = -1;
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
    int sleepMs = 0;
    if (m_power && m_sleepInhibitions.isEmpty()) {
        gchar *type = g_settings_get_string(m_power, "sleep-inactive-battery-type");
        if (qstrcmp(type, "suspend") == 0) {
            sleepMs = g_settings_get_int(m_power, "sleep-inactive-battery-timeout") * 1000;
        }
        g_free(type);
    }
    if (sleepMs > 0) {
        m_sleepTimeout = KIdleTime::instance()->addIdleTimeout(sleepMs);
    }
    qInfo().noquote() << "FENESTRA_POWERIDLE sleep-ms" << sleepMs << "battery" << m_onBattery << "locked" << LockOsd::instance()->locked() << "inhibitions"
                      << m_screenInhibitions.size() << "timeout-ms" << ms;
}

void PowerIdle::sleepIfQuiet()
{
    QProcess sinks;
    sinks.start(QStringLiteral("pactl"), {QStringLiteral("list"), QStringLiteral("short"), QStringLiteral("sinks")});
    if (sinks.waitForFinished(2000) && sinks.readAllStandardOutput().contains("RUNNING")) {
        qInfo("FENESTRA_POWERIDLE sound playing: no sleep");
        rearm(); // the idle timeout starts again
        return;
    }
    qInfo("FENESTRA_POWERIDLE sleep");
    QDBusMessage suspend = QDBusMessage::createMethodCall(QStringLiteral("org.freedesktop.login1"), QStringLiteral("/org/freedesktop/login1"),
                                                          QStringLiteral("org.freedesktop.login1.Manager"), QStringLiteral("Suspend"));
    suspend << false;
    QDBusConnection::systemBus().asyncCall(suspend);
}

void PowerIdle::timedOut(int id)
{
    if (id == m_sleepTimeout) {
        sleepIfQuiet();
        return;
    }
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
    }
    if (types & (kChangeScreenSettings | kInterruptSession)) {
        m_sleepInhibitions.insert(cookie);
        rearm();
    }
    return cookie;
}

void PowerIdle::ReleaseInhibition(uint cookie)
{
    const bool screen = m_screenInhibitions.remove(cookie);
    if (m_sleepInhibitions.remove(cookie) || screen) {
        rearm();
    }
}
