// SPDX-License-Identifier: GPL-3.0-or-later
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QGuiApplication>
#include <QStandardPaths>
#include <QTimer>
#include <QWindow>
#include <ctime>
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
    if (!locked)
        QTimer::singleShot(3000, this, &LockOsd::logUnlock);
    Q_EMIT lockedChanged();
}

namespace {
// The wall-clock time of boot as this process saw it when it started (realtime - boottime).
qint64 bootWallNow()
{
    timespec rt{}, boot{};
    clock_gettime(CLOCK_REALTIME, &rt);
    clock_gettime(CLOCK_BOOTTIME, &boot);
    return qint64(rt.tv_sec) - qint64(boot.tv_sec);
}
const qint64 s_bootWallAtStart = bootWallNow();
}

// One line per unlock in ~/.local/state/fenestra/unlock.log, 3 s after it: what the screen should
// show by then. If the desktop ever stays black after unlocking, this says which part was missing:
// KWin still locked, an output dimmed to nothing, the shell's windows not on screen, the clock moved.
void LockOsd::logUnlock()
{
    const auto bus = QDBusConnection::sessionBus();
    const QDBusReply<bool> active = bus.call(QDBusMessage::createMethodCall(QStringLiteral("org.freedesktop.ScreenSaver"), QStringLiteral("/ScreenSaver"),
                                                                            QStringLiteral("org.freedesktop.ScreenSaver"), QStringLiteral("GetActive")), QDBus::Block, 1000);
    int shown = 0, total = 0;
    for (QWindow *w : QGuiApplication::topLevelWindows()) {
        if (!w->isVisible())
            continue;
        ++total;
        shown += w->isExposed() ? 1 : 0;
    }
    // How far the wall clock moved since this process started (chrony stepping it at boot).
    timespec rt{}, mono{};
    clock_gettime(CLOCK_REALTIME, &rt);
    clock_gettime(CLOCK_BOOTTIME, &mono);
    const qint64 bootWall = qint64(rt.tv_sec) - qint64(mono.tv_sec);
    QString line = QStringLiteral("%1 uptime=%2s kwin-locked=%3 shell-windows=%4/%5-exposed clock-moved=%6s")
                       .arg(QDateTime::currentDateTime().toString(Qt::ISODate)).arg(mono.tv_sec)
                       .arg(active.isValid() ? (active.value() ? QStringLiteral("yes") : QStringLiteral("no")) : QStringLiteral("?"))
                       .arg(total).arg(shown).arg(bootWall - s_bootWallAtStart);
    // the panel's backlight (sysfs), as the brightness slider sets it
    const QDir backlights(QStringLiteral("/sys/class/backlight"));
    for (const QString &b : backlights.entryList(QDir::Dirs | QDir::NoDotAndDotDot)) {
        auto read = [&](const char *name) {
            QFile f(backlights.filePath(b) + QLatin1Char('/') + QLatin1String(name));
            return f.open(QIODevice::ReadOnly) ? QString::fromLatin1(f.readAll()).trimmed() : QStringLiteral("?");
        };
        line += QStringLiteral(" %1=%2/%3").arg(b, read("brightness"), read("max_brightness"));
    }
    const QString dir = QStandardPaths::writableLocation(QStandardPaths::GenericStateLocation) + QStringLiteral("/fenestra");
    QDir().mkpath(dir);
    QFile f(dir + QStringLiteral("/unlock.log"));
    QStringList lines;
    if (f.open(QIODevice::ReadOnly))
        lines = QString::fromUtf8(f.readAll()).split(QLatin1Char('\n'), Qt::SkipEmptyParts);
    f.close();
    lines.append(line);
    while (lines.size() > 200)
        lines.removeFirst();
    if (f.open(QIODevice::WriteOnly | QIODevice::Truncate))
        f.write((lines.join(QLatin1Char('\n')) + QLatin1Char('\n')).toUtf8());
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
