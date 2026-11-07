// SPDX-License-Identifier: GPL-3.0-or-later
// org.fenestra.Shell on the session bus: what global shortcuts and scripts call to open Start and
// Search (Super alone is the "start" global shortcut, services/shortcuts.cpp).
#pragma once

#include <QDBusConnection>
#include <QObject>
#include <QQmlEngine>

class ShellControl : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_CLASSINFO("D-Bus Interface", "org.fenestra.Shell")
public:
    static ShellControl *instance()
    {
        static auto *c = new ShellControl;
        return c;
    }
    static ShellControl *create(QQmlEngine *, QJSEngine *)
    {
        QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
        return instance();
    }
    void registerOnBus()
    {
        auto bus = QDBusConnection::sessionBus();
        bus.registerObject(QStringLiteral("/org/fenestra/Shell"), this, QDBusConnection::ExportScriptableSlots);
        bus.registerService(QStringLiteral("org.fenestra.Shell"));
    }

public Q_SLOTS:
    Q_SCRIPTABLE void ToggleStart() { Q_EMIT toggleStartRequested(); }
    Q_SCRIPTABLE void ToggleSearch() { Q_EMIT toggleSearchRequested(); }

Q_SIGNALS:
    void toggleStartRequested();
    void toggleSearchRequested();

private:
    // Not `using QObject::QObject`: inherited constructors stay public, and QML would then build
    // its own instance instead of calling create() (two objects, D-Bus calls reaching neither QML).
    explicit ShellControl(QObject *parent = nullptr) : QObject(parent) {}
};
