// SPDX-License-Identifier: GPL-3.0-or-later
#include "kbdbacklight.h"

#include "performancemode.h"

#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusReply>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QLocale>
#include <QSocketNotifier>

#include <fcntl.h>
#include <unistd.h>

namespace
{
const QString kService = QStringLiteral("org.freedesktop.UPower");
const QString kPath = QStringLiteral("/org/freedesktop/UPower/KbdBacklight");
const QString kIface = QStringLiteral("org.freedesktop.UPower.KbdBacklight");
}

KbdBacklight *KbdBacklight::instance()
{
    static KbdBacklight kbd;
    return &kbd;
}

KbdBacklight *KbdBacklight::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

int KbdBacklight::readSysfs(const char *file) const
{
    QFile f(m_led + QLatin1Char('/') + QLatin1String(file));
    return f.open(QIODevice::ReadOnly) ? f.readAll().trimmed().toInt() : -1;
}

KbdBacklight::KbdBacklight(QObject *parent)
    : QObject(parent)
{
    // Benches without the hardware (tests/shell-kwin): FENESTRA_FAKE_KBD_BACKLIGHT=<driver>:<max>.
    const QByteArray fake = qgetenv("FENESTRA_FAKE_KBD_BACKLIGHT");
    if (!fake.isEmpty()) {
        m_vendor = QString::fromLatin1(fake.split(':').value(0));
        m_max = fake.split(':').value(1).toInt();
        return;
    }
    const QDir leds(QStringLiteral("/sys/class/leds"));
    for (const QString &name : leds.entryList(QDir::Dirs | QDir::NoDotAndDotDot | QDir::System, QDir::Name)) {
        if (name.endsWith(QLatin1String("::kbd_backlight"))) {
            m_name = name;
            m_led = leds.filePath(name);
            m_vendor = name.section(QStringLiteral("::"), 0, 0);
            break;
        }
    }
    // UPower picks the same device (the first *kbd_backlight LED).
    QDBusMessage max = QDBusMessage::createMethodCall(kService, kPath, kIface, QStringLiteral("GetMaxBrightness"));
    const QDBusReply<int> maxReply = QDBusConnection::systemBus().call(max, QDBus::Block, 1000);
    if (maxReply.isValid() && maxReply.value() > 0) {
        m_upower = true;
        m_max = maxReply.value();
        QDBusMessage get = QDBusMessage::createMethodCall(kService, kPath, kIface, QStringLiteral("GetBrightness"));
        const QDBusReply<int> value = QDBusConnection::systemBus().call(get, QDBus::Block, 1000);
        m_level = value.isValid() ? value.value() : 0;
    } else if (!m_led.isEmpty()) {
        m_max = std::max(0, readSysfs("max_brightness"));
        m_level = std::max(0, readSysfs("brightness"));
    }
    if (m_max <= 0)
        return;
    // The firmware's own key: brightness_hw_changed (kernel ≥ 4.11, LED_BRIGHT_HW_CHANGED).
    const QString hw = m_led + QStringLiteral("/brightness_hw_changed");
    if (!m_led.isEmpty() && QFileInfo::exists(hw)) {
        m_hwFd = ::open(QFile::encodeName(hw).constData(), O_RDONLY | O_CLOEXEC);
        if (m_hwFd >= 0) {
            char buf[16];
            (void)::read(m_hwFd, buf, sizeof buf); // arm (reading before the first change fails with ENODATA: fine)
            m_hwNotifier = new QSocketNotifier(m_hwFd, QSocketNotifier::Exception, this);
            connect(m_hwNotifier, &QSocketNotifier::activated, this, &KbdBacklight::readHwChanged);
        }
    }
    if (m_upower) {
        auto bus = QDBusConnection::systemBus();
        // UPower ≥ 0.99.4 tells who changed it; older ones only send BrightnessChanged.
        if (!bus.connect(kService, kPath, kIface, QStringLiteral("BrightnessChangedWithSource"), this,
                         SLOT(onUPowerChanged(int, QString))))
            bus.connect(kService, kPath, kIface, QStringLiteral("BrightnessChanged"), this, SLOT(onUPowerChangedLegacy(int)));
    }
}

void KbdBacklight::readHwChanged()
{
    ::lseek(m_hwFd, 0, SEEK_SET);
    char buf[16] = {};
    const ssize_t n = ::read(m_hwFd, buf, sizeof buf - 1);
    if (n <= 0)
        return;
    const int v = std::clamp(QByteArray(buf, int(n)).trimmed().toInt(), 0, m_max);
    m_level = v;
    Q_EMIT changed();
    Q_EMIT keyChanged(v);
}

void KbdBacklight::onUPowerChanged(int value, const QString &source)
{
    const bool changedValue = value != m_level;
    m_level = std::clamp(value, 0, m_max);
    if (changedValue)
        Q_EMIT changed();
    // "internal": the firmware changed it (the hotkey). With brightness_hw_changed the sysfs
    // watch already reported it.
    if (source == QLatin1String("internal") && !m_hwNotifier)
        Q_EMIT keyChanged(m_level);
}

void KbdBacklight::onUPowerChangedLegacy(int value)
{
    if (value == m_level)
        return;
    m_level = std::clamp(value, 0, m_max);
    Q_EMIT changed();
}

void KbdBacklight::setLevel(int level)
{
    level = std::clamp(level, 0, m_max);
    if (!available() || level == m_level)
        return;
    m_level = level;
    if (m_led.isEmpty() && !m_upower) { // fake device
        Q_EMIT changed();
        return;
    }
    QDBusMessage msg;
    if (m_upower) {
        msg = QDBusMessage::createMethodCall(kService, kPath, kIface, QStringLiteral("SetBrightness"));
        msg << level;
    } else {
        msg = QDBusMessage::createMethodCall(QStringLiteral("org.freedesktop.login1"), QStringLiteral("/org/freedesktop/login1/session/auto"),
                                             QStringLiteral("org.freedesktop.login1.Session"), QStringLiteral("SetBrightness"));
        msg << QStringLiteral("leds") << m_name << uint(level);
    }
    QDBusConnection::systemBus().asyncCall(msg);
    Q_EMIT changed();
}

void KbdBacklight::step(int delta)
{
    if (!available())
        return;
    setLevel(m_level + delta);
    Q_EMIT keyChanged(m_level);
}

void KbdBacklight::toggle()
{
    if (!available())
        return;
    // As the firmware toggles: the next level, back to off after the brightest.
    setLevel(m_level >= m_max ? 0 : m_level + 1);
    Q_EMIT keyChanged(m_level);
}

void KbdBacklight::testKey(int level)
{
    m_level = std::clamp(level, 0, m_max);
    Q_EMIT changed();
    Q_EMIT keyChanged(m_level);
}

QString KbdBacklight::samsungLabel(int level) const
{
    static const char *const keys[] = {"PC_SAMSUNGSETTINGS_OSD_KBDBACKLIGHT_LEVEL0", "PC_SAMSUNGSETTINGS_OSD_KBDBACKLIGHT_LEVEL30",
                                       "PC_SAMSUNGSETTINGS_OSD_KBDBACKLIGHT_LEVEL60", "PC_SAMSUNGSETTINGS_OSD_KBDBACKLIGHT_LEVEL100"};
    static const int values[] = {0, 30, 60, 100};
    // The firmware's four levels (max_brightness 3); another range is shown in percent.
    const int i = m_max == 3 ? std::clamp(level, 0, 3) : -1;
    const QString value = QString::number(i >= 0 ? values[i] : (m_max > 0 ? qRound(100.0 * level / m_max) : 0));
    const QString en = QStringLiteral("Keyboard backlight brightness: ") + value;
    const QString es = QStringLiteral("Brillo de retroiluminación de teclado: ") + value;
    if (i < 0) {
        const QString full = SamsungOsd::text(QStringLiteral("PC_SAMSUNGSETTINGS_OSD_KBDBACKLIGHT_LEVEL100"),
                                              "Keyboard backlight brightness: 100", "Brillo de retroiluminación de teclado: 100");
        return full.left(full.lastIndexOf(QLatin1Char(':'))) + QStringLiteral(": ") + value;
    }
    return SamsungOsd::text(QLatin1String(keys[i]), en.toUtf8().constData(), es.toUtf8().constData());
}

QString KbdBacklight::samsungIcon(bool dark) const
{
    return SamsungOsd::picture(QStringLiteral("kbd-backlight"), dark);
}
