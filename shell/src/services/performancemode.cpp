// SPDX-License-Identifier: GPL-3.0-or-later
#include "performancemode.h"

#include "status.h"
#include "system.h"

#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLocale>
#include <QSocketNotifier>
#include <QStandardPaths>
#include <QUrl>

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
    // Benches without the hardware (tests/shell-kwin): FENESTRA_FAKE_PLATFORM_PROFILE=<driver>.
    if (qEnvironmentVariableIsSet("FENESTRA_FAKE_PLATFORM_PROFILE")) {
        m_vendor = qEnvironmentVariable("FENESTRA_FAKE_PLATFORM_PROFILE");
        return;
    }
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
        Q_EMIT keyChanged(p);
}

namespace SamsungOsd
{
QString dir()
{
    return QStandardPaths::writableLocation(QStandardPaths::GenericDataLocation) + QStringLiteral("/fenestra/oem/samsung/osd");
}

QString text(const QString &key, const char *en, const char *es)
{
    static const QJsonObject all = [] {
        QFile f(dir() + QStringLiteral("/strings.json"));
        return f.open(QIODevice::ReadOnly) ? QJsonDocument::fromJson(f.readAll()).object() : QJsonObject();
    }();
    // The OSD's own languages: es-ES, en-GB, en-US… (the locale's exact name, then any of its language).
    const QString name = QLocale().name().replace(QLatin1Char('_'), QLatin1Char('-'));
    QString v = all.value(name).toObject().value(key).toString();
    if (v.isEmpty()) {
        const QString lang = name.section(QLatin1Char('-'), 0, 0);
        for (auto it = all.begin(); it != all.end() && v.isEmpty(); ++it)
            if (it.key().section(QLatin1Char('-'), 0, 0) == lang)
                v = it.value().toObject().value(key).toString();
    }
    if (v.isEmpty())
        v = QString::fromUtf8(name.startsWith(QLatin1String("es")) ? es : en);
    return v;
}

QString picture(const QString &name, bool dark)
{
    const QString png = dir() + (dark ? QStringLiteral("/dark/") : QStringLiteral("/light/")) + name + QStringLiteral(".png");
    return QFileInfo::exists(png) ? QUrl::fromLocalFile(png).toString() : QString();
}
}

namespace
{
// samsung-galaxybook's profiles and SamsungSystemSupportOSD's entries (OSD_PERF_MODE0-3: the
// LanguageResource.ini keys and its PNG resources 141/142, 143/144, 139/140, 135/136).
struct SamsungMode { const char *profile, *key, *en, *es, *picture; };
const SamsungMode kSamsungModes[] = {
    {"low-power", "DREAM_ST_OPT_SILENT_M_NOISE", "Silent", "Silencioso", "perf-silent"},
    {"quiet", "DREAM_ST_OPT_QUIET", "Quiet", "Discreto", "perf-quiet"},
    {"balanced", "DREAM_ST_OPT_OPTIMIZED", "Optimised", "Optimizado", "perf-optimised"},
    {"performance", "DREAM_ST_OPT_HIGH_PERFORMANCE", "High performance", "Alto rendimiento", "perf-high"},
};
}

QString PerformanceMode::label(const QString &profile) const
{
    if (m_vendor == QLatin1String("samsung-galaxybook")) {
        // OSDHandler: "<WDS_TPLATFORM_HEADER_PERFORMANCE_MODE_ABB>: <DREAM_ST_OPT_…>" on one line.
        QString name = profile;
        for (const SamsungMode &m : kSamsungModes)
            if (profile == QLatin1String(m.profile))
                name = SamsungOsd::text(QLatin1String(m.key), m.en, m.es);
        return SamsungOsd::text(QStringLiteral("WDS_TPLATFORM_HEADER_PERFORMANCE_MODE_ABB"), "Performance mode", "Modo Rendimiento")
             + QStringLiteral(": ") + name;
    }
    // Windows 11's power-mode names (Settings › System › Power & battery).
    const bool es = QLocale().name().startsWith(QLatin1String("es"));
    const QString name = profile == QLatin1String("performance") ? (es ? QStringLiteral("Máximo rendimiento") : QStringLiteral("Best performance"))
                       : profile == QLatin1String("low-power") || profile == QLatin1String("quiet")
                             ? (es ? QStringLiteral("Máxima eficiencia energética") : QStringLiteral("Best power efficiency"))
                             : (es ? QStringLiteral("Equilibrado") : QStringLiteral("Balanced"));
    return (es ? QStringLiteral("Modo de energía: ") : QStringLiteral("Power mode: ")) + name;
}

QString PerformanceMode::icon(const QString &profile, bool dark) const
{
    if (m_vendor != QLatin1String("samsung-galaxybook"))
        return QString();
    for (const SamsungMode &m : kSamsungModes)
        if (profile == QLatin1String(m.profile))
            return SamsungOsd::picture(QLatin1String(m.picture), dark);
    return QString();
}
