// SPDX-License-Identifier: GPL-3.0-or-later
// Turns the screen off when the PC is idle, which nothing else does in a Fenestra session (Plasma's
// PowerDevil is not running here, GNOME's settings daemon neither):
//   - plugged in: never, unlocked or locked;
//   - on battery, unlocked: after Settings > Power's "Turn off my screen after"
//     (org.gnome.desktop.session idle-delay; 0 = never), unless an app asked to keep it on (video);
//   - on battery, locked: after a minute, as Windows' lock screen (and apps can't hold it on).
// Any input wakes it: KWin does that itself. KWin's org.freedesktop.ScreenSaver forwards apps'
// Inhibit calls to PowerDevil's PolicyAgent, so this service takes that name; Wayland clients'
// idle inhibitors are already honoured by the idle timer.
#pragma once

#include <QDBusContext>
#include <QObject>
#include <QSet>

typedef struct _GSettings GSettings;

class PowerIdle : public QObject, protected QDBusContext
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.kde.Solid.PowerManagement.PolicyAgent")
public:
    static PowerIdle *instance();

public Q_SLOTS:
    Q_SCRIPTABLE uint AddInhibition(uint types, const QString &appName, const QString &reason);
    Q_SCRIPTABLE void ReleaseInhibition(uint cookie);

private Q_SLOTS:
    void batteryChanged();

private:
    explicit PowerIdle(QObject *parent = nullptr);
    static void onDelayChanged(GSettings *, const char *, void *self);
    void rearm();
    void timedOut(int id);

    GSettings *m_settings = nullptr;
    bool m_onBattery = false;
    bool m_testBattery = false;
    int m_timeout = -1;
    uint m_nextCookie = 1;
    QSet<uint> m_screenInhibitions;
};
