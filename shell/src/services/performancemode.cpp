// SPDX-License-Identifier: GPL-3.0-or-later
#include "performancemode.h"

#include "notifications.h"
#include "status.h"
#include "system.h"

#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QLocale>
#include <QSocketNotifier>
#include <QStandardPaths>

#include <fcntl.h>
#include <unistd.h>

namespace
{
QString readFile(const QString &path)
{
    QFile f(path);
    return f.open(QIODevice::ReadOnly) ? QString::fromLatin1(f.readAll()).trimmed() : QString();
}
qint64 now() { return QDateTime::currentMSecsSinceEpoch(); }
}

PerformanceMode *PerformanceMode::instance()
{
    static PerformanceMode mode;
    return &mode;
}

PerformanceMode *PerformanceMode::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

PerformanceMode::PerformanceMode(QObject *parent)
    : QObject(parent)
{
    // The class device names its driver; the legacy ACPI attribute is the one that is polled.
    const QDir classDir(QStringLiteral("/sys/class/platform-profile"));
    for (const QString &d : classDir.entryList(QDir::Dirs | QDir::NoDotAndDotDot)) {
        const QString base = classDir.filePath(d);
        if (QFileInfo::exists(base + QStringLiteral("/profile"))) {
            m_vendor = readFile(base + QStringLiteral("/name"));
            m_path = base + QStringLiteral("/profile");
            break;
        }
    }
    if (QFileInfo::exists(QStringLiteral("/sys/firmware/acpi/platform_profile")))
        m_path = QStringLiteral("/sys/firmware/acpi/platform_profile");
    if (m_path.isEmpty())
        return;
    m_profile = readFile(m_path);
    // sysfs_notify wakes poll() with POLLPRI on the attribute: a socket notifier of type Exception.
    m_fd = ::open(QFile::encodeName(m_path).constData(), O_RDONLY | O_CLOEXEC);
    if (m_fd >= 0) {
        char buf[64];
        (void)::read(m_fd, buf, sizeof buf); // arm the notification
        m_notifier = new QSocketNotifier(m_fd, QSocketNotifier::Exception, this);
        connect(m_notifier, &QSocketNotifier::activated, this, &PerformanceMode::readProfile);
    }
    // Plugging in / unplugging and power-mode changes make tuned rewrite the profile: not the key.
    connect(PowerStatus::instance(), &PowerStatus::changed, this, [this] {
        static bool plugged = PowerStatus::instance()->pluggedIn();
        if (PowerStatus::instance()->pluggedIn() != plugged) {
            plugged = PowerStatus::instance()->pluggedIn();
            m_quietUntil = now() + 4000;
        }
    });
    connect(PowerProfiles::instance(), &PowerProfiles::changed, this, [this] {
        static QString last = PowerProfiles::instance()->active();
        if (PowerProfiles::instance()->active() != last) {
            last = PowerProfiles::instance()->active();
            // tuned-ppd follows a key change too (platform profile first, then the power profile):
            // only a power-profile change that comes first silences the next platform change.
            if (now() - m_quietUntil > 1000)
                m_quietUntil = std::max(m_quietUntil, now() + 2000);
        }
    });
}

void PerformanceMode::readProfile()
{
    ::lseek(m_fd, 0, SEEK_SET);
    char buf[64] = {};
    const ssize_t n = ::read(m_fd, buf, sizeof buf - 1);
    const QString p = n > 0 ? QString::fromLatin1(buf, int(n)).trimmed() : QString();
    if (p.isEmpty() || p == m_profile)
        return;
    m_profile = p;
    Q_EMIT changed();
    if (now() >= m_quietUntil)
        notifyChange(p);
}

void PerformanceMode::notifyChange(const QString &profile)
{
    const bool es = QLocale().name().startsWith(QLatin1String("es"));
    const QString data = QStandardPaths::writableLocation(QStandardPaths::GenericDataLocation);
    QString app, title, icon;
    if (m_vendor == QLatin1String("samsung-galaxybook")) {
        // Samsung Settings' strings (its resources.pri) and icons (SamsungSettings/Resources).
        struct M { const char *id, *en, *es, *icon; };
        static const M modes[] = {
            {"low-power", "Silent", "Silencioso", "silent"},
            {"quiet", "Quiet", "Silencio", "fan_1"},
            {"balanced", "Optimised", "Optimizado", "optimised"},
            {"performance", "High performance", "Alto rendimiento", "high_performance"},
        };
        app = QStringLiteral("Samsung Settings");
        QString name = profile;
        for (const M &m : modes)
            if (profile == QLatin1String(m.id)) {
                name = es ? QString::fromUtf8(m.es) : QString::fromLatin1(m.en);
                const QString svg = data + QStringLiteral("/fenestra/oem/samsung/dark/%1.svg").arg(QLatin1String(m.icon));
                if (QFileInfo::exists(svg))
                    icon = svg;
            }
        title = (es ? QStringLiteral("Modo de rendimiento: ") : QStringLiteral("Performance mode: ")) + name;
        // The toast's header carries the app's own logo, as every Windows toast.
        const QString logo = data + QStringLiteral("/fenestra/oem/samsung/app.png");
        if (QFileInfo::exists(logo))
            icon = logo;
    } else {
        // Windows 11's power-mode names (Settings › System › Power & battery).
        const QString name = profile == QLatin1String("performance") ? (es ? QStringLiteral("Máximo rendimiento") : QStringLiteral("Best performance"))
                           : profile == QLatin1String("low-power") || profile == QLatin1String("quiet")
                                 ? (es ? QStringLiteral("Máxima eficiencia energética") : QStringLiteral("Best power efficiency"))
                                 : (es ? QStringLiteral("Equilibrado") : QStringLiteral("Balanced"));
        app = es ? QStringLiteral("Energía") : QStringLiteral("Power");
        title = (es ? QStringLiteral("Modo de energía: ") : QStringLiteral("Power mode: ")) + name;
    }
    if (icon.isEmpty())
        icon = QStringLiteral("battery-good-symbolic");
    // One notice at a time, as Windows replaces it while the key is pressed again.
    if (m_lastId)
        Notifications::instance()->CloseNotification(m_lastId);
    m_lastId = Notifications::instance()->notify(app, icon, title, QString());
}
