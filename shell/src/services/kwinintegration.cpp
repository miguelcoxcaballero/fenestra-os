// SPDX-License-Identifier: GPL-3.0-or-later
#include "kwinintegration.h"

#include "desktop.h"
#include "shellsettings.h"
#include "status.h"

#include <QUrl>

#include <KConfigGroup>
#include <KSharedConfig>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCall>
#include <QDBusReply>
#include <QDir>
#include <QFile>
#include <QStandardPaths>

KWinIntegration *KWinIntegration::instance()
{
    static auto *k = new KWinIntegration;
    return k;
}

KWinIntegration *KWinIntegration::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

KWinIntegration::KWinIntegration(QObject *parent)
    : QObject(parent)
{
    connect(ShellSettings::instance(), &ShellSettings::changed, this, &KWinIntegration::applyTheme);
    connect(WallpaperSource::instance(), &WallpaperSource::changed, this, &KWinIntegration::applyLockScreen);
    connect(NetworkStatus::instance(), &NetworkStatus::changed, this, &KWinIntegration::applyLockScreen);
    connect(PowerStatus::instance(), &PowerStatus::changed, this, &KWinIntegration::applyLockScreen);
    applyTheme();
    applyLockScreen();
}

void KWinIntegration::applyTheme()
{
    // Decoration (kwin/aurorae, built by tools/build-aurorae-theme.py) and switcher (kwin/tabbox).
    const QString scheme = ShellSettings::instance()->colorScheme() == QLatin1String("light") ? QStringLiteral("Light") : QStringLiteral("Dark");
    auto cfg = KSharedConfig::openConfig(QStringLiteral("kwinrc"));
    KConfigGroup deco = cfg->group(QStringLiteral("org.kde.kdecoration2"));
    const QString theme = QStringLiteral("__aurorae__svg__Fenestra-") + scheme;
    bool changed = false;
    // KWin 6.8 migrates "org.kde.kwin.aurorae" to the C++ renderer "org.kde.kwin.aurorae.v2".
    const QString library = deco.readEntry("library");
    if (deco.readEntry("theme") != theme || !library.startsWith(QLatin1String("org.kde.kwin.aurorae"))) {
        deco.writeEntry("library", QStringLiteral("org.kde.kwin.aurorae"));
        deco.writeEntry("theme", theme);
        deco.writeEntry("ButtonsOnLeft", QString());
        deco.writeEntry("ButtonsOnRight", QStringLiteral("IAX")); // minimize, maximize, close
        changed = true;
    }
    // Windows' 1 px frame: with the default (automatic / "Normal") border size Aurorae widens the
    // theme's 1 px sides and bottom to ~4 px of title-bar colour around the client; "Tiny" keeps
    // the theme's own borders (tests/window-frames).
    if (deco.readEntry("BorderSize") != QLatin1String("Tiny") || deco.readEntry("BorderSizeAuto", true)) {
        deco.writeEntry("BorderSize", QStringLiteral("Tiny"));
        deco.writeEntry("BorderSizeAuto", false);
        changed = true;
    }
    // Title text: Windows' caption font (NONCLIENTMETRICS lfCaptionFont), Segoe UI 9 pt.
    KConfigGroup wm = KSharedConfig::openConfig(QStringLiteral("kdeglobals"))->group(QStringLiteral("WM"));
    const QString captionFont = QStringLiteral("Segoe UI,9,-1,5,400,0,0,0,0,0,0,0,0,0,0,1");
    if (wm.readEntry("activeFont") != captionFont) {
        wm.writeEntry("activeFont", captionFont);
        wm.sync();
        changed = true;
    }
    KConfigGroup tabbox = cfg->group(QStringLiteral("TabBox"));
    if (tabbox.readEntry("LayoutName") != QLatin1String("fenestra")) {
        tabbox.writeEntry("LayoutName", QStringLiteral("fenestra"));
        changed = true;
    }
    if (!changed)
        return;
    cfg->sync();
    QDBusConnection::sessionBus().asyncCall(QDBusMessage::createMethodCall(QStringLiteral("org.kde.KWin"), QStringLiteral("/KWin"),
                                                                           QStringLiteral("org.kde.KWin"), QStringLiteral("reconfigure")));
}

void KWinIntegration::runScript(const QString &name, const QString &code)
{
    // org.kde.kwin.Scripting: load a script file, run it, unload it.
    const QString dir = QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation) + QStringLiteral("/fenestra");
    QDir().mkpath(dir);
    const QString path = dir + QLatin1Char('/') + name + QStringLiteral(".js");
    QFile f(path);
    if (!f.open(QIODevice::WriteOnly))
        return;
    f.write(code.toUtf8());
    f.close();
    auto bus = QDBusConnection::sessionBus();
    QDBusMessage unload = QDBusMessage::createMethodCall(QStringLiteral("org.kde.KWin"), QStringLiteral("/Scripting"),
                                                         QStringLiteral("org.kde.kwin.Scripting"), QStringLiteral("unloadScript"));
    unload << name;
    bus.call(unload, QDBus::Block, 1000);
    QDBusMessage load = QDBusMessage::createMethodCall(QStringLiteral("org.kde.KWin"), QStringLiteral("/Scripting"),
                                                       QStringLiteral("org.kde.kwin.Scripting"), QStringLiteral("loadScript"));
    load << path << name;
    QDBusReply<int> id = bus.call(load, QDBus::Block, 2000);
    if (!id.isValid() || id.value() < 0)
        return;
    bus.asyncCall(QDBusMessage::createMethodCall(QStringLiteral("org.kde.KWin"), QStringLiteral("/Scripting/Script%1").arg(id.value()),
                                                 QStringLiteral("org.kde.kwin.Script"), QStringLiteral("run")));
}

void KWinIntegration::placeActiveWindow(const QRectF &zone)
{
    runScript(QStringLiteral("fenestra-snap"), QStringLiteral(R"(
const w = workspace.activeWindow;
if (w && w.normalWindow && w.resizeable) {
    const a = workspace.clientArea(KWin.MaximizeArea, w);
    w.setMaximize(false, false);
    w.frameGeometry = {x: Math.round(a.x + a.width * %1), y: Math.round(a.y + a.height * %2),
                       width: Math.round(a.width * %3), height: Math.round(a.height * %4)};
}
)").arg(zone.x()).arg(zone.y()).arg(zone.width()).arg(zone.height()));
}

void KWinIntegration::toggleOverview()
{
    // Task View (W04): KWin's Overview effect, with virtual desktops.
    QDBusConnection::sessionBus().asyncCall(QDBusMessage::createMethodCall(QStringLiteral("org.kde.kglobalaccel"), QStringLiteral("/component/kwin"),
                                                                           QStringLiteral("org.kde.kglobalaccel.Component"), QStringLiteral("invokeShortcut"))
                                            << QStringLiteral("Overview"));
}

void KWinIntegration::applyLockScreen()
{
    // KWin's screen locker (kscreenlocker) draws lnf/org.fenestra.desktop's LockScreen.qml; its
    // [Greeter][LnF][General] values are the picture and the status shown on it (L01).
    auto globals = KSharedConfig::openConfig(QStringLiteral("kdeglobals"));
    KConfigGroup kde = globals->group(QStringLiteral("KDE"));
    if (kde.readEntry("LookAndFeelPackage") != QLatin1String("org.fenestra.desktop")) {
        kde.writeEntry("LookAndFeelPackage", QStringLiteral("org.fenestra.desktop"));
        globals->sync();
    }
    auto locker = KSharedConfig::openConfig(QStringLiteral("kscreenlockerrc"));
    KConfigGroup general = locker->group(QStringLiteral("Greeter")).group(QStringLiteral("LnF")).group(QStringLiteral("General"));
    const QString image = QUrl(WallpaperSource::instance()->image()).toLocalFile();
    auto *net = NetworkStatus::instance();
    auto *power = PowerStatus::instance();
    // Battery in steps of 5 %: the file is not rewritten on every percent.
    const int battery = power->hasBattery() ? (power->percentage() / 5) * 5 : -1;
    const QString network = net->connected() ? net->name() : QString();
    if (general.readEntry("Background") == image && general.readEntry("Network") == network && general.readEntry("Battery", -2) == battery)
        return;
    general.writeEntry("Background", image);
    general.writeEntry("Network", network);
    general.writeEntry("Battery", battery);
    locker->sync();
}
