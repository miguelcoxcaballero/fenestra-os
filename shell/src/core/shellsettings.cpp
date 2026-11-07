// SPDX-License-Identifier: GPL-3.0-or-later
#include "shellsettings.h"

#include <QDir>
#include <QFileInfo>
#include <QStandardPaths>
#include <QUrl>

namespace
{
// Defaults of the GNOME layer (desktop/dconf/local.d/00-fenestra, 10-fenestra-theme).
const QStringList kDefaultPinned{QStringLiteral("org.mozilla.firefox.desktop"), QStringLiteral("org.gnome.Nautilus.desktop")};
const QString kDefaultAccent = QStringLiteral("#0078D4");
const QString kDefaultWallpaper = QStringLiteral("/usr/share/backgrounds/fenestra/fenestra-bloom-dark.jpg");
}

ShellSettings *ShellSettings::instance()
{
    static auto *s = new ShellSettings;
    return s;
}

ShellSettings *ShellSettings::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

QString ShellSettings::path()
{
    return QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation) + QStringLiteral("/fenestra/shell.conf");
}

ShellSettings::ShellSettings(QObject *parent)
    : QObject(parent)
{
    load();
    // Editors and Settings replace the file atomically: watch the directory too.
    connect(&m_watcher, &QFileSystemWatcher::fileChanged, this, [this] { load(); watch(); });
    connect(&m_watcher, &QFileSystemWatcher::directoryChanged, this, [this] { load(); watch(); });
    watch();
}

void ShellSettings::watch()
{
    const QFileInfo fi(path());
    QDir().mkpath(fi.absolutePath());
    if (!m_watcher.directories().contains(fi.absolutePath()))
        m_watcher.addPath(fi.absolutePath());
    if (fi.exists() && !m_watcher.files().contains(fi.absoluteFilePath()))
        m_watcher.addPath(fi.absoluteFilePath());
}

void ShellSettings::load()
{
    QSettings s(path(), QSettings::IniFormat);
    auto pick = [](const QString &v, const QStringList &allowed) { return allowed.contains(v) ? v : allowed.first(); };
    const QString alignment = pick(s.value(QStringLiteral("Taskbar/Alignment")).toString(), {QStringLiteral("center"), QStringLiteral("left")});
    const QString search = pick(s.value(QStringLiteral("Taskbar/SearchMode")).toString(),
                                {QStringLiteral("box"), QStringLiteral("hidden"), QStringLiteral("icon"), QStringLiteral("iconLabel")});
    const bool weather = s.value(QStringLiteral("Taskbar/Weather"), true).toBool();
    // Present but empty (QSettings writes @Invalid() for an empty list): no pins, not the defaults.
    const QStringList pinned = s.contains(QStringLiteral("Taskbar/Pinned")) ? s.value(QStringLiteral("Taskbar/Pinned")).toStringList() : kDefaultPinned;
    const QString scheme = pick(s.value(QStringLiteral("Appearance/ColorScheme")).toString(), {QStringLiteral("dark"), QStringLiteral("light")});
    QString accent = s.value(QStringLiteral("Appearance/Accent"), kDefaultAccent).toString();
    if (!QColor::isValidColorName(accent))
        accent = kDefaultAccent;
    const QString wallpaper = s.value(QStringLiteral("Appearance/Wallpaper"), kDefaultWallpaper).toString();
    const bool reduceMotion = s.value(QStringLiteral("Appearance/ReduceMotion"), false).toBool();
    const bool transparency = s.value(QStringLiteral("Appearance/Transparency"), true).toBool();
    auto iconUrl = [&s](const QString &key) {
        const QString path = s.value(key).toString();
        return !path.isEmpty() && QFileInfo::exists(path) ? QUrl::fromLocalFile(path).toString() : QString();
    };
    const QString startIcon = iconUrl(QStringLiteral("Appearance/StartIcon"));
    const QString searchIcon = iconUrl(QStringLiteral("Appearance/SearchIcon"));

    Q_EMIT fileChanged();
    if (alignment == m_alignment && search == m_searchMode && weather == m_showWeather && pinned == m_pinned
        && scheme == m_scheme && accent == m_accent && wallpaper == m_wallpaper && reduceMotion == m_reduceMotion && transparency == m_transparency
        && startIcon == m_startIcon && searchIcon == m_searchIcon)
        return;
    m_alignment = alignment;
    m_searchMode = search;
    m_showWeather = weather;
    m_pinned = pinned;
    m_scheme = scheme;
    m_accent = accent;
    m_wallpaper = wallpaper;
    m_reduceMotion = reduceMotion;
    m_transparency = transparency;
    m_startIcon = startIcon;
    m_searchIcon = searchIcon;
    Q_EMIT changed();
}

void ShellSettings::write(const QString &key, const QVariant &value)
{
    {
        QSettings s(path(), QSettings::IniFormat);
        s.setValue(key, value);
    }
    load();
    watch();
}

void ShellSettings::pin(const QString &storageId)
{
    if (storageId.isEmpty() || m_pinned.contains(storageId))
        return;
    setPinnedApps(m_pinned + QStringList{storageId});
}

void ShellSettings::unpin(const QString &storageId)
{
    QStringList p = m_pinned;
    if (p.removeAll(storageId))
        setPinnedApps(p);
}

QVariant ShellSettings::value(const QString &key, const QVariant &fallback) const
{
    return QSettings(path(), QSettings::IniFormat).value(key, fallback);
}
