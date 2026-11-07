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
    Q_PROPERTY(bool widgetsOnHover READ widgetsOnHover NOTIFY changed)
    // Settings › Personalization › Taskbar › Task view (on by default, as in Windows 11).
    Q_PROPERTY(bool showTaskView READ showTaskView WRITE setShowTaskView NOTIFY changed)
    Q_PROPERTY(QStringList pinnedApps READ pinnedApps WRITE setPinnedApps NOTIFY changed)
    // "dark" | "light"
    Q_PROPERTY(QString colorScheme READ colorScheme WRITE setColorScheme NOTIFY changed)
    Q_PROPERTY(QString accentColor READ accentColor WRITE setAccentColor NOTIFY changed)
    Q_PROPERTY(QString wallpaper READ wallpaper WRITE setWallpaper NOTIFY changed)
    Q_PROPERTY(bool reduceMotion READ reduceMotion NOTIFY changed)
    // Windows' "Transparency effects": off = the flat fallback colours (taskbar.fill).
    Q_PROPERTY(bool transparency READ transparency NOTIFY changed)
    // Icons imported by the user (Settings / setup icon import): file URLs, or "" for Fenestra's own.
    Q_PROPERTY(QString startIcon READ startIcon NOTIFY changed)
    Q_PROPERTY(QString searchIcon READ searchIcon NOTIFY changed)

public:
    static ShellSettings *instance();
    static ShellSettings *create(QQmlEngine *, QJSEngine *);

    QString taskbarAlignment() const { return m_alignment; }
    QString searchMode() const { return m_searchMode; }
    bool showWeather() const { return m_showWeather; }
    bool widgetsOnHover() const { return m_widgetsOnHover; }
    bool showTaskView() const { return m_showTaskView; }
    QStringList pinnedApps() const { return m_pinned; }
    QString colorScheme() const { return m_scheme; }
    QString accentColor() const { return m_accent; }
    QString wallpaper() const { return m_wallpaper; }
    bool reduceMotion() const { return m_reduceMotion; }
    bool transparency() const { return m_transparency; }
    QString startIcon() const { return m_startIcon; }
    QString searchIcon() const { return m_searchIcon; }

    void setTaskbarAlignment(const QString &v) { write(QStringLiteral("Taskbar/Alignment"), v); }
    void setSearchMode(const QString &v) { write(QStringLiteral("Taskbar/SearchMode"), v); }
    void setShowWeather(bool v) { write(QStringLiteral("Taskbar/Weather"), v); }
    void setShowTaskView(bool v) { write(QStringLiteral("Taskbar/TaskView"), v); }
    void setPinnedApps(const QStringList &v) { write(QStringLiteral("Taskbar/Pinned"), v); }
    void setColorScheme(const QString &v) { write(QStringLiteral("Appearance/ColorScheme"), v); }
    void setAccentColor(const QString &v) { write(QStringLiteral("Appearance/Accent"), v); }
    void setWallpaper(const QString &v) { write(QStringLiteral("Appearance/Wallpaper"), v); }

    Q_INVOKABLE void pin(const QString &storageId);
    Q_INVOKABLE void unpin(const QString &storageId);
    Q_INVOKABLE bool isPinned(const QString &storageId) const { return m_pinned.contains(storageId); }

    static QString path();

    // Other sections of shell.conf ([Start], [Search]…) for services that own them.
    QVariant value(const QString &key, const QVariant &fallback = {}) const;
    void setValue(const QString &key, const QVariant &value) { write(key, value); }

Q_SIGNALS:
    void changed();
    void fileChanged(); // after every (re)load, whatever changed

private:
    explicit ShellSettings(QObject *parent = nullptr);
    void load();
    void watch();
    void write(const QString &key, const QVariant &value);

    QFileSystemWatcher m_watcher;
    QString m_alignment, m_searchMode, m_scheme, m_accent, m_wallpaper;
    bool m_showWeather = true;
    bool m_widgetsOnHover = true;
    bool m_showTaskView = true;
    bool m_reduceMotion = false;
    bool m_transparency = true;
    QString m_startIcon, m_searchIcon;
    QStringList m_pinned;
};
