// SPDX-License-Identifier: GPL-3.0-or-later
#include "kwinintegration.h"

#include "desktop.h"
#include "shellsettings.h"
#include "status.h"
#include "theme.h"

#include <QUrl>

#include <KConfigGroup>
#include <KSharedConfig>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCall>
#include <QDBusReply>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
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
    connect(Theme::instance(), &Theme::changed, this, &KWinIntegration::applyLockScreen);
    connect(&m_spotlightWatcher, &QFileSystemWatcher::directoryChanged, this, &KWinIntegration::applyLockScreen);
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

// Today's Windows Spotlight picture, as the GNOME layer showed it: the original photos copied from
// the user's Windows by windows-spotlight-sync (/var/lib/windows-spotlight), else Fenestra's own
// Spotlight state. Only the services' own image directories are accepted.
static QString spotlightPicture()
{
    static const QRegularExpression ok(QStringLiteral(
        "^/(var/lib/windows-spotlight/images/[a-f0-9]{64}|var/lib/fenestra-spotlight/images/[a-f0-9]{64}|usr/share/backgrounds/fenestra/[A-Za-z0-9._-]+)\\.jpg$"));
    for (const QString &state : {QStringLiteral("/var/lib/windows-spotlight/current.json"), QStringLiteral("/var/lib/fenestra-spotlight/current.json")}) {
        QFile f(state);
        if (!f.open(QIODevice::ReadOnly))
            continue;
        const QString path = QJsonDocument::fromJson(f.readAll()).object().value(QStringLiteral("image")).toString();
        if (ok.match(path).hasMatch() && QFileInfo::exists(path))
            return path;
    }
    return {};
}

void KWinIntegration::applyLockScreen()
{
    // KWin's screen locker (kscreenlocker) draws shells/org.fenestra.desktop's lockscreen (Plasma 6
    // takes the lock screen from the shell package named in plasmashellrc [Shell] ShellPackage).
    // Its [Greeter][LnF][General] values: the picture (Spotlight as on Windows, else the desktop's)
    // and the accent. Network and battery the lock screen reads itself.
    auto shellrc = KSharedConfig::openConfig(QStringLiteral("plasmashellrc"));
    KConfigGroup shell = shellrc->group(QStringLiteral("Shell"));
    if (shell.readEntry("ShellPackage") != QLatin1String("org.fenestra.desktop")) {
        shell.writeEntry("ShellPackage", QStringLiteral("org.fenestra.desktop"));
        shellrc->sync();
    }
    for (const QString &dir : {QStringLiteral("/var/lib/windows-spotlight"), QStringLiteral("/var/lib/fenestra-spotlight")}) {
        if (QFileInfo(dir).isDir() && !m_spotlightWatcher.directories().contains(dir))
            m_spotlightWatcher.addPath(dir);
    }
    auto locker = KSharedConfig::openConfig(QStringLiteral("kscreenlockerrc"));
    KConfigGroup general = locker->group(QStringLiteral("Greeter")).group(QStringLiteral("LnF")).group(QStringLiteral("General"));
    QString picture = spotlightPicture();
    if (picture.isEmpty())
        picture = QUrl(WallpaperSource::instance()->image()).toLocalFile();
    const QString accent = Theme::instance()->accent().name(QColor::HexRgb);
    if (general.readEntry("Picture") == picture && general.readEntry("Background") == picture && general.readEntry("Accent") == accent)
        return;
    general.writeEntry("Picture", picture);
    general.writeEntry("Background", picture);
    general.writeEntry("Accent", accent);
    general.deleteEntry("Network");
    general.deleteEntry("Battery");
    locker->sync();
}
