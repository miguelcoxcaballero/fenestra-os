// SPDX-License-Identifier: GPL-3.0-or-later
// Keyboard backlight, for any laptop that has one: the kernel's LED class device
// (/sys/class/leds/<driver>::kbd_backlight, brightness / max_brightness) and UPower's
// org.freedesktop.UPower.KbdBacklight, which writes it (the shell cannot: root-owned sysfs).
//   - Level changes made by the firmware hotkey (Samsung Galaxy Book Fn+F9, ThinkPad Fn+Space…)
//     raise keyChanged() so the shell shows the banner: the LED's brightness_hw_changed attribute
//     wakes poll() with POLLPRI (sysfs_notify), or, without it, UPower's
//     BrightnessChangedWithSource(value, "internal").
//   - Keyboards whose backlight keys reach userspace (KEY_KBDILLUMUP/DOWN/TOGGLE) are stepped by
//     Shortcuts (step / toggle), which shows the same banner.
//   - Quick settings' slider sets the level (setLevel): UPower, or logind's SetBrightness("leds").
#pragma once

#include <algorithm>
#include <QObject>
#include <QQmlEngine>
#include <QString>

class QSocketNotifier;

class KbdBacklight : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(bool available READ available CONSTANT)
    Q_PROPERTY(int level READ level WRITE setLevel NOTIFY changed)
    Q_PROPERTY(int maxLevel READ maxLevel CONSTANT)
    Q_PROPERTY(int percent READ percent WRITE setPercent NOTIFY changed)
    // The LED's driver (samsung-galaxybook, tpacpi, asus…): picks the OEM banner.
    Q_PROPERTY(QString vendor READ vendor CONSTANT)
public:
    static KbdBacklight *instance();
    static KbdBacklight *create(QQmlEngine *, QJSEngine *);
    bool available() const { return m_max > 0; }
    int level() const { return m_level; }
    int maxLevel() const { return m_max; }
    int percent() const { return m_max > 0 ? qRound(100.0 * m_level / m_max) : 0; }
    QString vendor() const { return m_vendor; }
    void setLevel(int level);
    void setPercent(int percent) { setLevel(qRound(m_max * std::clamp(percent, 0, 100) / 100.0)); }
    // Backlight keys handled in userspace: one level up/down (wrapping like the firmware's toggle).
    Q_INVOKABLE void step(int delta);
    Q_INVOKABLE void toggle();
    // Samsung's banner text and picture for a level (SamsungSystemSupportOSD's
    // OSD_KEYBOARDBACKLIGHT_0-3: "Keyboard backlight brightness: 0 / 30 / 60 / 100").
    Q_INVOKABLE QString samsungLabel(int level) const;
    Q_INVOKABLE QString samsungIcon(bool dark) const;
    // Test probe: as if the firmware hotkey had set this level.
    Q_INVOKABLE void testKey(int level);
Q_SIGNALS:
    void changed();
    void keyChanged(int level);

private Q_SLOTS:
    void onUPowerChanged(int value, const QString &source);
    void onUPowerChangedLegacy(int value);

private:
    explicit KbdBacklight(QObject *parent = nullptr);
    void readHwChanged();
    int readSysfs(const char *file) const;
    QString m_led;          // /sys/class/leds/<name>
    QString m_name;         // <name>
    QString m_vendor;
    int m_max = 0, m_level = 0;
    bool m_upower = false;
    int m_hwFd = -1;
    QSocketNotifier *m_hwNotifier = nullptr;
};
