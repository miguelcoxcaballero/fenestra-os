// SPDX-License-Identifier: GPL-3.0-or-later
// Performance-mode popup. A laptop's Fn key for performance modes (Samsung Galaxy Book Fn+F11,
// ThinkPad Fn+L/M/H, ASUS Fn+F5…) changes the kernel's platform profile in the firmware driver;
// Windows then shows the OEM app's notification. Here: the platform profile is watched (sysfs
// poll) and a change the shell did not cause (not a plug/unplug or a power-mode change from
// Quick settings, which tuned applies itself) shows the same notification:
//   samsung-galaxybook: Samsung Settings' toast, "Performance mode: Silent / Quiet / Optimised /
//     High performance" with its icons (imported from the user's Windows when present,
//     ~/.local/share/fenestra/oem/samsung, fenestra-import-windows-assets);
//   other drivers: Windows' own power-mode names.
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
    // Test probe: show the notification for a profile as if the key had changed it.
    Q_INVOKABLE void testNotify(const QString &profile) { notifyChange(profile); }
Q_SIGNALS:
    void changed();

private:
    explicit PerformanceMode(QObject *parent = nullptr);
    void readProfile();
    void notifyChange(const QString &profile);
    QString m_path;      // the platform profile attribute
    QString m_vendor;    // driver name (samsung-galaxybook, thinkpad-acpi…)
    QString m_profile;
    int m_fd = -1;
    QSocketNotifier *m_notifier = nullptr;
    qint64 m_quietUntil = 0;   // ms since epoch: changes before this are the system's own
    uint m_lastId = 0;
};
