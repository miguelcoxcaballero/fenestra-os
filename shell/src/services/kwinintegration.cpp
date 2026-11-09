// SPDX-License-Identifier: GPL-3.0-or-later
#include "kwinintegration.h"

#include "desktop.h"
#include "shellsettings.h"
#include "status.h"
#include "theme.h"
#include "weather.h"
#include "iconoverrides.h"

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
#include <QJsonArray>
#include <QJsonObject>
#include <QPixmap>
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
    connect(Weather::instance(), &Weather::changed, this, &KWinIntegration::applyLockScreen);
    connect(&m_spotlightWatcher, &QFileSystemWatcher::directoryChanged, this, &KWinIntegration::applyLockScreen);
    applyTheme();
    applyLockScreen();
    applyKeyboard();
}

void KWinIntegration::applyKeyboard()
{
    // Windows' Spanish layout has the euro on AltGr+E and on AltGr+5; XKB's only on E. The option
    // acts on the first layout only, and on other layouts AltGr+5 is taken (French: "[").
    auto cfg = KSharedConfig::openConfig(QStringLiteral("kxkbrc"));
    KConfigGroup layout = cfg->group(QStringLiteral("Layout"));
    const QString euro = QStringLiteral("eurosign:5");
    QStringList options = layout.readEntry("Options", QString()).split(QLatin1Char(','), Qt::SkipEmptyParts);
    const bool wanted = layout.readEntry("LayoutList", QString()).split(QLatin1Char(',')).value(0) == QLatin1String("es");
    if (options.contains(euro) == wanted)
        return;
    options.removeAll(euro);
    if (wanted)
        options.append(euro);
    // KConfig::Notify: KWin watches kxkbrc and reloads the keymap.
    layout.writeEntry("ResetOldOptions", true, KConfig::Notify);
    layout.writeEntry("Options", options.join(QLatin1Char(',')), KConfig::Notify);
    cfg->sync();
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
    // App window motion as Windows 11 (kwin/effects/fenestra-window-motion): open, close,
    // minimize to the taskbar button, restore and maximize. KWin's own effects for the same
    // transitions are switched off, or both would animate. Fenestra's popups are layer-shell
    // "dock" surfaces, which neither animates.
    KConfigGroup plugins = cfg->group(QStringLiteral("Plugins"));
    const QList<QPair<QString, bool>> effects = {
        {QStringLiteral("fenestra-window-motionEnabled"), true},
        {QStringLiteral("scaleEnabled"), false}, {QStringLiteral("glideEnabled"), false},
        {QStringLiteral("fadeEnabled"), false}, {QStringLiteral("squashEnabled"), false},
        {QStringLiteral("magiclampEnabled"), false}, {QStringLiteral("maximizeEnabled"), false},
    };
    for (const auto &[key, enabled] : effects) {
        if (!plugins.hasKey(key) || plugins.readEntry(key, !enabled) != enabled) {
            plugins.writeEntry(key, enabled);
            changed = true;
        }
    }
    KConfigGroup tabbox = cfg->group(QStringLiteral("TabBox"));
    if (tabbox.readEntry("LayoutName") != QLatin1String("fenestra")) {
        tabbox.writeEntry("LayoutName", QStringLiteral("fenestra"));
        changed = true;
    }
    // The preview shown while a window is dragged to a screen edge (kwin/outline/fenestra). KWin
    // loads it the first time it shows one: a change of scheme applies from the next session.
    // QmlPath is relative to the data directories (KWin passes it to QStandardPaths::locate).
    const QString preview = QStringLiteral("kwin/outline/fenestra/") + scheme.toLower() + QStringLiteral(".qml");
    const bool previewInstalled = !QStandardPaths::locate(QStandardPaths::GenericDataLocation, preview).isEmpty();
    KConfigGroup outline = cfg->group(QStringLiteral("Outline"));
    if (previewInstalled && outline.readEntry("QmlPath") != preview) {
        outline.writeEntry("QmlPath", preview);
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

// What Windows shows about today's Spotlight photo on the lock screen ("info" hotspot: the place
// and the copyright; "basic" hotspots: a sentence and a link, at a corner or a point of the
// photo). Windows keeps it next to the photos it downloaded (ContentDeliveryManager's
// TargetedContentCache, JSON); the photo is matched by its SHA-256, the name of Fenestra's copy.
static QJsonObject spotlightMetadata(const QString &picture)
{
    const QString hex = QFileInfo(picture).completeBaseName().toLower();
    if (hex.size() != 64)
        return {};
    const QString rel = QStringLiteral("AppData/Local/Packages/Microsoft.Windows.ContentDeliveryManager_cw5n1h2txyewy/LocalState/TargetedContentCache/v3");
    for (const QFileInfo &mnt : QDir(QStringLiteral("/mnt")).entryInfoList(QDir::Dirs | QDir::NoDotAndDotDot)) {
        for (const QFileInfo &user : QDir(mnt.filePath() + QStringLiteral("/Users")).entryInfoList(QDir::Dirs | QDir::NoDotAndDotDot)) {
            QDir cache(user.filePath() + QLatin1Char('/') + rel);
            if (!cache.exists())
                continue;
            for (const QFileInfo &sub : cache.entryInfoList(QDir::Dirs | QDir::NoDotAndDotDot)) {
                for (const QFileInfo &item : QDir(sub.filePath()).entryInfoList(QDir::Files)) {
                    if (item.size() > 2 * 1024 * 1024)
                        continue;
                    QFile f(item.filePath());
                    if (!f.open(QIODevice::ReadOnly))
                        continue;
                    const QJsonObject o = QJsonDocument::fromJson(f.readAll()).object();
                    if (o.value(QStringLiteral("name")).toString() != QLatin1String("LockScreen"))
                        continue;
                    const QJsonObject img = o.value(QStringLiteral("properties")).toObject().value(QStringLiteral("landscapeImage")).toObject();
                    if (QByteArray::fromBase64(img.value(QStringLiteral("sha256")).toString().toLatin1()).toHex() != hex.toLatin1())
                        continue;
                    QJsonObject out;
                    QJsonArray spots;
                    const double w = img.value(QStringLiteral("width")).toDouble(1920), h = img.value(QStringLiteral("height")).toDouble(1080);
                    for (const QJsonValue &v : o.value(QStringLiteral("items")).toArray()) {
                        const QJsonObject p = v.toObject().value(QStringLiteral("properties")).toObject();
                        const auto text = [&p](const char *k) { return p.value(QLatin1String(k)).toObject().value(QStringLiteral("text")).toString(); };
                        const QJsonObject click = p.value(QStringLiteral("onClick")).toObject().value(QStringLiteral("parameters")).toObject();
                        const QString uri = click.value(QStringLiteral("uri")).toString();
                        const bool web = uri.startsWith(QLatin1String("https://"));
                        if (text("template") == QLatin1String("infoHotspot")) {
                            out[QStringLiteral("title")] = text("description");
                            out[QStringLiteral("copyright")] = text("copyright");
                            out[QStringLiteral("url")] = web ? uri : QString();
                        } else {
                            QJsonObject spot{{QStringLiteral("title"), text("title")}, {QStringLiteral("action"), text("actionText")},
                                             {QStringLiteral("location"), text("location")}, {QStringLiteral("url"), web ? uri : QString()}};
                            if (click.contains(QStringLiteral("landscapeX"))) {
                                spot[QStringLiteral("x")] = click.value(QStringLiteral("landscapeX")).toString().toDouble() / w;
                                spot[QStringLiteral("y")] = click.value(QStringLiteral("landscapeY")).toString().toDouble() / h;
                            }
                            spots.append(spot);
                        }
                    }
                    out[QStringLiteral("hotspots")] = spots;
                    return out;
                }
            }
        }
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
    QMap<QString, QString> values{{QStringLiteral("Picture"), picture}, {QStringLiteral("Background"), picture}, {QStringLiteral("Accent"), accent}};
    // Spotlight: the photo's place, copyright and hotspots (JSON), as Windows' lock screen shows them.
    if (picture != m_spotlightFor) {
        m_spotlightFor = picture;
        m_spotlightMeta = QString::fromUtf8(QJsonDocument(spotlightMetadata(picture)).toJson(QJsonDocument::Compact));
    }
    values[QStringLiteral("Spotlight")] = m_spotlightMeta == QLatin1String("{}") ? QString() : m_spotlightMeta;
    // Weather card of the clock view (Windows 11 24H2's lock screen widgets): the taskbar's weather,
    // its icon rendered from the icon pack into the cache (the lock screen has no icon theme).
    auto *w = Weather::instance();
    QString icon;
    if (w->available() && !w->iconName().isEmpty()) {
        const QString dir = QStandardPaths::writableLocation(QStandardPaths::GenericCacheLocation) + QStringLiteral("/fenestra/lockscreen");
        QDir().mkpath(dir);
        icon = dir + QStringLiteral("/weather-") + w->iconName() + QStringLiteral(".png");
        if (!QFileInfo::exists(icon)) {
            QSize size;
            const QPixmap px = IconProvider().requestPixmap(w->iconName(), &size, QSize(168, 168));
            if (px.isNull() || !px.save(icon))
                icon.clear();
        }
    }
    static const QRegularExpression number(QStringLiteral("^(-?[0-9]+)(.*)$"));
    const auto m = number.match(w->temperature());
    values[QStringLiteral("WeatherLocation")] = w->available() ? w->location() : QString();
    values[QStringLiteral("WeatherTemperature")] = w->available() && m.hasMatch() ? m.captured(1) : QString();
    values[QStringLiteral("WeatherUnit")] = m.hasMatch() ? m.captured(2) : QString();
    values[QStringLiteral("WeatherCondition")] = w->available() ? w->condition() : QString();
    values[QStringLiteral("WeatherFeelsLike")] = w->available() ? w->feelsLike() : QString();
    values[QStringLiteral("WeatherIcon")] = icon;
    bool same = true;
    for (auto it = values.cbegin(); it != values.cend(); ++it)
        same = same && general.readEntry(it.key()) == it.value();
    if (same)
        return;
    for (auto it = values.cbegin(); it != values.cend(); ++it)
        general.writeEntry(it.key(), it.value());
    general.deleteEntry("Network");
    general.deleteEntry("Battery");
    locker->sync();
}
