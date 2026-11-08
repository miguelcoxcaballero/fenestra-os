// SPDX-License-Identifier: GPL-3.0-or-later
#include "lockosd.h"

#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>

namespace {
const QString s_name = QStringLiteral("org.kde.plasmashell");
const QString s_path = QStringLiteral("/org/kde/osdService");
}

LockOsd *LockOsd::instance()
{
    static LockOsd osd;
    return &osd;
}

LockOsd *LockOsd::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

LockOsd::LockOsd(QObject *parent)
    : QObject(parent)
{
    auto bus = QDBusConnection::sessionBus();
    // KWin's screen locker (ksld) implements org.freedesktop.ScreenSaver on the session bus.
    bus.connect(QStringLiteral("org.freedesktop.ScreenSaver"), QStringLiteral("/ScreenSaver"), QStringLiteral("org.freedesktop.ScreenSaver"),
                QStringLiteral("ActiveChanged"), this, SLOT(activeChanged(bool)));
    auto *watcher = new QDBusPendingCallWatcher(
        bus.asyncCall(QDBusMessage::createMethodCall(QStringLiteral("org.freedesktop.ScreenSaver"), QStringLiteral("/ScreenSaver"),
                                                     QStringLiteral("org.freedesktop.ScreenSaver"), QStringLiteral("GetActive"))),
        this);
    connect(watcher, &QDBusPendingCallWatcher::finished, this, [this](QDBusPendingCallWatcher *w) {
        QDBusPendingReply<bool> reply = *w;
        if (reply.isValid())
            setLocked(reply.value());
        w->deleteLater();
    });
}

void LockOsd::activeChanged(bool active)
{
    setLocked(active);
}

void LockOsd::setLocked(bool locked)
{
    if (m_locked == locked)
        return;
    m_locked = locked;
    auto bus = QDBusConnection::sessionBus();
    if (locked && !m_owned) {
        // Never take the name from a real plasmashell (a Plasma session on the same bus).
        if (!bus.interface()->isServiceRegistered(s_name).value()) {
            bus.registerObject(s_path, QStringLiteral("org.kde.osdService"), this, QDBusConnection::ExportAllSignals);
            m_owned = bus.registerService(s_name);
            if (!m_owned)
                bus.unregisterObject(s_path);
        }
    } else if (!locked && m_owned) {
        bus.unregisterService(s_name);
        bus.unregisterObject(s_path);
        m_owned = false;
    }
    Q_EMIT lockedChanged();
}

void LockOsd::progress(const QString &kind, int value)
{
    if (!m_owned)
        return;
    QString icon = QStringLiteral("fenestra-") + kind;
    if (kind == QLatin1String("volume") && value < 0)
        icon += QStringLiteral("-muted");
    Q_EMIT osdProgress(icon, std::max(0, value), 100, QString());
}

void LockOsd::text(const QString &kind, const QString &label, const QString &glyph, const QString &image)
{
    if (!m_owned)
        return;
    Q_EMIT osdText(QStringLiteral("fenestra-") + kind + QLatin1Char(':') + glyph + QLatin1Char(':') + image, label);
}
