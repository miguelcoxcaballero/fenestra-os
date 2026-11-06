// SPDX-License-Identifier: GPL-3.0-or-later
// Global shortcuts of the session (KGlobalAccel, served by KWin): media keys with the OSD (Q03),
// Ctrl+Alt+Del (Q05), Ctrl+Shift+Esc (T02), Super+N / Super+A / Super+S,
// Print and Super+Shift+S (snipping overlay, Q04).
#pragma once

#include <QObject>
#include <QQmlEngine>

class QAction;

class Shortcuts : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
public:
    static Shortcuts *instance();
    static Shortcuts *create(QQmlEngine *, QJSEngine *);
    void install();
    // The whole workspace without the overlay (the Print behaviour before the snipping overlay).
    Q_INVOKABLE void takeScreenshot();

Q_SIGNALS:
    // kind: "volume" | "brightness" | "microphone"; value 0–100, -1 = muted
    void osd(const QString &kind, int value);
    void securityScreenRequested();
    void notificationCenterRequested();
    void quickSettingsRequested();
    void searchRequested();
    void screenshotSaved(const QString &path);
    void snapLayoutsRequested();

private:
    explicit Shortcuts(QObject *parent = nullptr);
    QAction *add(const QString &id, const QString &text, const QList<QKeySequence> &keys);
    void volume(int delta);
};
