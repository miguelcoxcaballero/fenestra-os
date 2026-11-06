// SPDX-License-Identifier: GPL-3.0-or-later
// Fenestra Shell options: ~/.config/fenestra/shell.conf ([Taskbar], [Appearance]).
// Fenestra Settings writes the same file; changes apply live (file watcher, no polling).
#pragma once

#include <QFileSystemWatcher>
#include <QObject>
#include <QQmlEngine>
#include <QSettings>
#include <QColor>
#include <QStringList>

class ShellSettings : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    // "center" | "left" (B01)
    Q_PROPERTY(QString taskbarAlignment READ taskbarAlignment WRITE setTaskbarAlignment NOTIFY changed)
    // "hidden" | "icon" | "iconLabel" | "box" (B06)
    Q_PROPERTY(QString searchMode READ searchMode WRITE setSearchMode NOTIFY changed)
    Q_PROPERTY(bool showWeather READ showWeather WRITE setShowWeather NOTIFY changed)
    Q_PROPERTY(QStringList pinnedApps READ pinnedApps WRITE setPinnedApps NOTIFY changed)
    // "dark" | "light"
    Q_PROPERTY(QString colorScheme READ colorScheme WRITE setColorScheme NOTIFY changed)
    Q_PROPERTY(QString accentColor READ accentColor WRITE setAccentColor NOTIFY changed)
    Q_PROPERTY(QString wallpaper READ wallpaper WRITE setWallpaper NOTIFY changed)

public:
    static ShellSettings *instance();
    static ShellSettings *create(QQmlEngine *, QJSEngine *);

    QString taskbarAlignment() const { return m_alignment; }
    QString searchMode() const { return m_searchMode; }
    bool showWeather() const { return m_showWeather; }
    QStringList pinnedApps() const { return m_pinned; }
    QString colorScheme() const { return m_scheme; }
    QString accentColor() const { return m_accent; }
    QString wallpaper() const { return m_wallpaper; }

    void setTaskbarAlignment(const QString &v) { write(QStringLiteral("Taskbar/Alignment"), v); }
    void setSearchMode(const QString &v) { write(QStringLiteral("Taskbar/SearchMode"), v); }
    void setShowWeather(bool v) { write(QStringLiteral("Taskbar/Weather"), v); }
    void setPinnedApps(const QStringList &v) { write(QStringLiteral("Taskbar/Pinned"), v); }
    void setColorScheme(const QString &v) { write(QStringLiteral("Appearance/ColorScheme"), v); }
    void setAccentColor(const QString &v) { write(QStringLiteral("Appearance/Accent"), v); }
    void setWallpaper(const QString &v) { write(QStringLiteral("Appearance/Wallpaper"), v); }

    Q_INVOKABLE void pin(const QString &storageId);
    Q_INVOKABLE void unpin(const QString &storageId);
    Q_INVOKABLE bool isPinned(const QString &storageId) const { return m_pinned.contains(storageId); }

    static QString path();

Q_SIGNALS:
    void changed();

private:
    explicit ShellSettings(QObject *parent = nullptr);
    void load();
    void watch();
    void write(const QString &key, const QVariant &value);

    QFileSystemWatcher m_watcher;
    QString m_alignment, m_searchMode, m_scheme, m_accent, m_wallpaper;
    bool m_showWeather = true;
    QStringList m_pinned;
};
