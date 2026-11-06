// SPDX-License-Identifier: GPL-3.0-or-later
#include "kwinintegration.h"

#include "shellsettings.h"

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
    applyTheme();
}

void KWinIntegration::applyTheme()
{
    // Decoration (kwin/aurorae, built by tools/build-aurorae-theme.py) and switcher (kwin/tabbox).
    const QString scheme = ShellSettings::instance()->colorScheme() == QLatin1String("light") ? QStringLiteral("Light") : QStringLiteral("Dark");
    auto cfg = KSharedConfig::openConfig(QStringLiteral("kwinrc"));
    KConfigGroup deco = cfg->group(QStringLiteral("org.kde.kdecoration2"));
    const QString theme = QStringLiteral("__aurorae__svg__Fenestra-") + scheme;
    bool changed = false;
    if (deco.readEntry("theme") != theme || deco.readEntry("library") != QLatin1String("org.kde.kwin.aurorae")) {
        deco.writeEntry("library", QStringLiteral("org.kde.kwin.aurorae"));
        deco.writeEntry("theme", theme);
        deco.writeEntry("ButtonsOnLeft", QString());
        deco.writeEntry("ButtonsOnRight", QStringLiteral("IAX")); // minimize, maximize, close
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
