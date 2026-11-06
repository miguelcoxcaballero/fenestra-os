// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <KWindowEffects>
#include <LayerShellQt/Window>
#include <QGuiApplication>
#include <QObject>
#include <QQmlEngine>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QScreen>
#include <QStandardPaths>
#include <QWindow>

class ShellUtil : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
public:
    using QObject::QObject;
    // Puts a (not yet shown) shell surface on the output called `name` (B10). QML's
    // `Window.screen: Qt.application.screens[i]` leaves layer surfaces on the first output.
    Q_INVOKABLE bool placeOnScreen(QWindow *window, const QString &name) const
    {
        if (!window)
            return false;
        for (QScreen *screen : QGuiApplication::screens()) {
            if (screen->name() == name) {
                window->setScreen(screen);
                // The output of the layer surface (get_layer_surface) comes from LayerShellQt's own
                // screen; without it KWin puts the surface on the active output.
                if (auto *layer = LayerShellQt::Window::get(window))
                    layer->setScreen(screen);
                return true;
            }
        }
        return false;
    }
    // ~/.local/state/fenestra/session-ok: the Fenestra session worked for this user (the
    // migrator offers it as the default only after that).
    Q_INVOKABLE void markSessionOk() const
    {
        const QString dir = QStandardPaths::writableLocation(QStandardPaths::GenericStateLocation) + QStringLiteral("/fenestra");
        QDir().mkpath(dir);
        QFile f(dir + QStringLiteral("/session-ok"));
        if (f.open(QIODevice::WriteOnly))
            f.write(QDateTime::currentDateTime().toString(Qt::ISODate).toUtf8() + '\n');
    }
    Q_INVOKABLE bool configFileExists(const QString &name) const
    {
        return QFileInfo::exists(QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation) + QLatin1Char('/') + name);
    }
    // KWin's blur behind the whole surface (org_kde_kwin_blur; drawn only with OpenGL compositing).
    Q_INVOKABLE void enableBlur(QWindow *window, int radius) const
    {
        Q_UNUSED(radius)
        if (window)
            KWindowEffects::enableBlurBehind(window, true);
    }
};
