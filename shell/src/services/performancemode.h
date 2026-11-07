// SPDX-License-Identifier: GPL-3.0-or-later
// Performance-mode banner. A laptop's Fn key for performance modes (Samsung Galaxy Book Fn+F11,
// ThinkPad Fn+L/M/H, ASUS Fn+F5…) changes the kernel's platform profile in the firmware driver;
// Windows then shows the OEM's on-screen banner (not a notification). Here: the platform profile is
// watched (sysfs poll) and a change the shell did not cause (not a plug/unplug or a power-mode change
// from Quick settings, which tuned applies itself) raises keyChanged(), and the shell shows the banner
// (qml/osd): label() and icon() give its text and picture.
//   samsung-galaxybook: SamsungSystemSupportOSD's banner (Samsung System Support Service, the
//     sfourswcomp15 driver package): "Modo Rendimiento: Optimizado" with its own icons, strings
//     from its LanguageResource.ini (both imported from the user's Windows by
//     fenestra-import-windows-assets into ~/.local/share/fenestra/oem/samsung/osd; built-in
//     English/Spanish otherwise);
//   other drivers: Windows' power-mode names in a Windows-style banner.
#pragma once

#include <QObject>
#include <QQmlEngine>
#include <QString>

class QSocketNotifier;

class PerformanceMode : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(QString profile READ profile NOTIFY changed)
    Q_PROPERTY(QString vendor READ vendor CONSTANT)
public:
    static PerformanceMode *instance();
    static PerformanceMode *create(QQmlEngine *, QJSEngine *);
    QString profile() const { return m_profile; }
    QString vendor() const { return m_vendor; }
    // The banner's text and picture (file URL, or "" for the shell's own glyph) for a profile.
    Q_INVOKABLE QString label(const QString &profile) const;
    Q_INVOKABLE QString icon(const QString &profile, bool dark) const;
    // Test probe: show the banner for a profile as if the key had changed it.
    Q_INVOKABLE void testNotify(const QString &profile) { Q_EMIT keyChanged(profile); }
Q_SIGNALS:
    void changed();
    void keyChanged(const QString &profile);

private:
    explicit PerformanceMode(QObject *parent = nullptr);
    void readProfile();
    QString m_path;      // the platform profile attribute
    QString m_vendor;    // driver name (samsung-galaxybook, thinkpad-acpi…)
    QString m_profile;
    int m_fd = -1;
    QSocketNotifier *m_notifier = nullptr;
    qint64 m_quietUntil = 0;   // ms since epoch: changes before this are the system's own
};

// Samsung System Support OSD's strings and pictures, as imported from the user's Windows
// (~/.local/share/fenestra/oem/samsung/osd/strings.json: {locale: {key: text}}, and
// {dark,light}/<name>.png), with built-in English / Spanish fallbacks.
namespace SamsungOsd
{
QString text(const QString &key, const char *en, const char *es);
QString picture(const QString &name, bool dark);
}
