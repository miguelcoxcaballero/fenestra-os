// SPDX-License-Identifier: GPL-3.0-or-later
// Battery levels as Windows 11 (defaults of its power plan and Energy saver):
//   20 %  Energy saver turns on by itself and lowers the screen brightness by 30 %
//   10 %  "Your battery is running low" (low battery level)
//    7 %  "Your battery is very low" (reserve battery level)
//    5 %  critical level: the critical notice again, and the brightness drops further
// Plugging in turns off what was turned on automatically and gives the brightness back.
// Refresh rate (Windows' dynamic refresh rate saves the same way): on battery the built-in panel
// (eDP / LVDS / DSI) runs at the 60 Hz mode of its current resolution, on AC at its highest rate.
// Opt-in (Display/DynamicRefresh=true in shell.conf): smoothness first, the panel keeps its highest
// rate by default. Uses kscreen-doctor (any KWin system).
// Sources: learn.microsoft.com battery-saver and battery-settings pages.
#pragma once

#include <QObject>
#include <QQmlEngine>

class BatteryAlerts : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
public:
    static BatteryAlerts *instance();
    static BatteryAlerts *create(QQmlEngine *, QJSEngine *);
    // Test probe: feed a level as if UPower reported it (real updates are ignored meanwhile);
    // percent < 0 ends the test and goes back to the real battery.
    Q_INVOKABLE void testLevel(int percent, bool pluggedIn);
    Q_INVOKABLE QString testState() const;

private:
    explicit BatteryAlerts(QObject *parent = nullptr);
    void update(int percent, bool hasBattery, bool pluggedIn);
    void dimBy(double factor);
    void restore();
    void applyRefresh(bool onBattery);
    int m_refreshState = -1;      // last applied: 1 battery, 0 AC, -1 none
    bool m_testing = false;
    int m_last = -1;              // last level seen on battery, -1 = plugged in / unknown
    bool m_saverAuto = false;     // Energy saver turned on by us
    QString m_saverBefore;        // the power profile it replaced
    int m_brightnessBefore = -1;  // brightness before we dimmed, -1 = not dimmed
    int m_brightnessSet = -1;     // what we set (the user changing it cancels the restore)
    bool m_notifiedLow = false, m_notifiedReserve = false, m_notifiedCritical = false;
};
