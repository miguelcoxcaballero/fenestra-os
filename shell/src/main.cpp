// SPDX-License-Identifier: GPL-3.0-or-later
// Fenestra Shell: taskbar, Start, quick settings and desktop of the Fenestra session.
// KWin composites and manages windows; every surface here is a layer-shell surface.
#include <QCommandLineParser>
#include <QFont>
#include <QGuiApplication>
#include <QIcon>
#include <QQmlApplicationEngine>
#include <QQuickWindow>

#include "acrylic.h"
#include "backdrop.h"
#include "batteryalerts.h"
#include "iconoverrides.h"
#include "kwinintegration.h"
#include "notifications.h"
#include "polkitagent.h"
#include "shellcontrol.h"
#include "shortcuts.h"
#include "snip.h"
#include "testprobe.h"
#include "theme.h"
#include "trayitems.h"

int main(int argc, char *argv[])
{
    // Windows draws the shell's text with greyscale antialiasing (user-win11 captures); Qt Quick's
    // distance-field text otherwise follows fontconfig's rgba and draws colour fringes, which are
    // also wrong on translucent surfaces.
    if (!qEnvironmentVariableIsSet("QSG_DISTANCEFIELD_ANTIALIASING"))
        qputenv("QSG_DISTANCEFIELD_ANTIALIASING", "gray");
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

    // Native-rendered text (and QPainter text): no subpixel antialiasing either.
    {
        QFont f = QGuiApplication::font();
        f.setStyleStrategy(QFont::StyleStrategy(f.styleStrategy() | QFont::NoSubpixelAntialias));
        QGuiApplication::setFont(f);
    }
    QQmlApplicationEngine engine;
    // Glyphs and app logos of an imported icon pack replace Fenestra's own (core/iconoverrides.h).
    IconOverrides::setDarkMode([] { return Theme::instance()->dark(); });
    engine.addUrlInterceptor(new IconOverrideInterceptor);
    engine.addImageProvider(QStringLiteral("icon"), new IconProvider);
    engine.addImageProvider(QStringLiteral("sni"), new TrayImageProvider);
    engine.addImageProvider(QStringLiteral("tint"), new TintProvider);
    engine.addImageProvider(QStringLiteral("notification"), new NotificationImageProvider);
    engine.addImageProvider(QStringLiteral("snip"), new SnipImageProvider);
    engine.addImageProvider(QStringLiteral("acrylic"), new AcrylicProvider);
    engine.addImageProvider(QStringLiteral("popupshadow"), new PopupShadowProvider);
    engine.addImageProvider(QStringLiteral("backdrop"), new BackdropProvider);
    TrayItems::instance(); // own org.kde.StatusNotifierWatcher before apps start
    QObject::connect(&engine, &QQmlApplicationEngine::objectCreationFailed, &app,
                     [] { QCoreApplication::exit(1); }, Qt::QueuedConnection);
    engine.loadFromModule("Fenestra.Shell", "Main");
    ShellControl::instance()->registerOnBus();
    Notifications::instance()->registerOnBus();
    PolkitAgent::instance()->registerAgent();
    Shortcuts::instance()->install();
    KWinIntegration::instance(); // Fenestra decoration and switcher in kwinrc
    BatteryAlerts::instance(); // low-battery notices and Energy saver, as Windows
    TestProbe::installIfRequested(&engine);
    return app.exec();
}
