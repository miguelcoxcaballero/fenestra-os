// SPDX-License-Identifier: GPL-3.0-or-later
// Installed applications (KService: the XDG .desktop database) and launching (KIO, which
// passes an xdg-activation token so KWin gives the new window focus).
#pragma once

#include <KService>
#include <QObject>
#include <QQmlEngine>
#include <QVariantMap>

class Apps : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
public:
    static Apps *instance();
    static Apps *create(QQmlEngine *, QJSEngine *);

    // The .desktop entry of a window: Wayland app_id / X11 WM_CLASS, then StartupWMClass.
    KService::Ptr serviceForWindow(const QString &appId) const;
    KService::Ptr service(const QString &storageId) const;

    // {storageId, name, icon} or an empty map.
    Q_INVOKABLE QVariantMap info(const QString &storageId) const;
    Q_INVOKABLE bool launch(const QString &storageId);
    Q_INVOKABLE void runCommand(const QString &command);

Q_SIGNALS:
    void launched(const QString &storageId);
    void databaseChanged();

private:
    explicit Apps(QObject *parent = nullptr);
};
