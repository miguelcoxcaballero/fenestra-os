// SPDX-License-Identifier: GPL-3.0-or-later
// Fenestra Shell: taskbar, Start, quick settings and desktop of the Fenestra session.
// KWin composites and manages windows; every surface here is a layer-shell surface.
#include <QCommandLineParser>
#include <QGuiApplication>
#include <QIcon>
#include <QPainter>
#include <QUrl>
#include <QQmlApplicationEngine>
#include <QQuickImageProvider>
#include <QQuickWindow>

#include "shellcontrol.h"
#include "testprobe.h"
#include "trayitems.h"

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

// image://tint/<rrggbb>/<icon name or file URL>: a glyph recoloured (light mode: Fenestra's white
// line-art glyphs drawn in #1a1a1a), with QPainter so it works with every scene graph backend.
class TintProvider : public QQuickImageProvider
{
public:
    TintProvider() : QQuickImageProvider(QQuickImageProvider::Image) {}
    QImage requestImage(const QString &id, QSize *size, const QSize &requested) override
    {
        const QColor color(QLatin1Char('#') + id.section(QLatin1Char('/'), 0, 0));
        const QString what = QUrl::fromPercentEncoding(id.section(QLatin1Char('/'), 1).toUtf8());
        const QSize want = requested.isValid() ? requested : QSize(16, 16);
        QImage img;
        if (what.startsWith(QLatin1String("file:")))
            img = QIcon(QUrl(what).toLocalFile()).pixmap(want).toImage();
        else
            img = QIcon::fromTheme(what).pixmap(want).toImage();
        img = img.convertToFormat(QImage::Format_ARGB32_Premultiplied);
        QPainter p(&img);
        p.setCompositionMode(QPainter::CompositionMode_SourceIn);
        p.fillRect(img.rect(), color);
        p.end();
        if (size)
            *size = img.size();
        return img;
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
    engine.addImageProvider(QStringLiteral("sni"), new TrayImageProvider);
    engine.addImageProvider(QStringLiteral("tint"), new TintProvider);
    TrayItems::instance(); // own org.kde.StatusNotifierWatcher before apps start
    QObject::connect(&engine, &QQmlApplicationEngine::objectCreationFailed, &app,
                     [] { QCoreApplication::exit(1); }, Qt::QueuedConnection);
    engine.loadFromModule("Fenestra.Shell", "Main");
    ShellControl::instance()->registerOnBus();
    TestProbe::installIfRequested(&engine);
    return app.exec();
}
