// SPDX-License-Identifier: GPL-3.0-or-later
// Fenestra Shell: taskbar, Start, quick settings and desktop of the Fenestra session.
// KWin composites and manages windows; every surface here is a layer-shell surface.
#include <QCommandLineParser>
#include <QGuiApplication>
#include <QIcon>
#include <QQmlApplicationEngine>
#include <QQuickImageProvider>
#include <QQuickWindow>

#include "testprobe.h"

namespace
{
// image://icon/<name>: icons from the Fenestra icon theme (hicolor as fallback).
class IconProvider : public QQuickImageProvider
{
public:
    IconProvider() : QQuickImageProvider(QQuickImageProvider::Pixmap) {}
    QPixmap requestPixmap(const QString &id, QSize *size, const QSize &requested) override
    {
        const QSize want = requested.isValid() ? requested : QSize(32, 32);
        QIcon icon = QIcon::fromTheme(id);
        if (icon.isNull())
            icon = QIcon::fromTheme(id.toLower());
        if (icon.isNull())
            icon = QIcon::fromTheme(QStringLiteral("application-x-executable"));
        const QPixmap pixmap = icon.pixmap(want);
        if (size)
            *size = pixmap.size();
        return pixmap;
    }
};
}

int main(int argc, char *argv[])
{
    QGuiApplication::setDesktopFileName(QStringLiteral("org.fenestra.Shell"));
    QGuiApplication app(argc, argv);
    QGuiApplication::setApplicationName(QStringLiteral("fenestra-shell"));
    QGuiApplication::setApplicationVersion(QStringLiteral(FENESTRA_SHELL_VERSION));
    // Closing the last flyout must not end the shell.
    QGuiApplication::setQuitOnLastWindowClosed(false);

    QCommandLineParser parser;
    parser.addHelpOption();
    parser.addVersionOption();
    parser.process(app);

    if (QGuiApplication::platformName() != QLatin1String("wayland")) {
        qCritical("fenestra-shell needs a Wayland session (KWin); platform is %s",
                  qPrintable(QGuiApplication::platformName()));
        return 2;
    }

    if (QIcon::themeName().isEmpty() || QIcon::themeName() == QLatin1String("hicolor"))
        QIcon::setThemeName(QStringLiteral("Fenestra"));

    QQmlApplicationEngine engine;
    engine.addImageProvider(QStringLiteral("icon"), new IconProvider);
    QObject::connect(&engine, &QQmlApplicationEngine::objectCreationFailed, &app,
                     [] { QCoreApplication::exit(1); }, Qt::QueuedConnection);
    engine.loadFromModule("Fenestra.Shell", "Main");
    TestProbe::installIfRequested(&engine);
    return app.exec();
}
