// SPDX-License-Identifier: GPL-3.0-or-later
// What the shell asks KWin for: the Fenestra decoration and Alt+Tab switcher following the colour
// scheme (kwinrc + reconfigure), and placing the active window in a Snap Layouts zone (W03)
// through KWin's scripting D-Bus API.
#pragma once

#include <QObject>
#include <QQmlEngine>
#include <QRectF>

class KWinIntegration : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
public:
    static KWinIntegration *instance();
    static KWinIntegration *create(QQmlEngine *, QJSEngine *);
    // zone: fractions of the work area (x, y, width, height in 0–1).
    Q_INVOKABLE void placeActiveWindow(const QRectF &zone);
    Q_INVOKABLE void toggleOverview();
private:
    explicit KWinIntegration(QObject *parent = nullptr);
    void applyTheme();
    void applyLockScreen();
    void runScript(const QString &name, const QString &code);
};
