// SPDX-License-Identifier: GPL-3.0-or-later
// Data behind Start and Search (S01–S05): installed apps, Start pins, recent files, most-used
// apps, the user's name and picture, session actions.
#pragma once

#include <QAbstractListModel>
#include <QDateTime>
#include <QFileSystemWatcher>
#include <QObject>
#include <QQmlEngine>
#include <QVariantList>

// Every app that should be shown, sorted by name, with its "All apps" group (windowsStartHome.js).
class AllApps : public QAbstractListModel
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(int count READ rowCount NOTIFY countChanged)
public:
    enum Roles { StorageIdRole = Qt::UserRole + 1, NameRole, IconRole, GroupRole, LetterRole, GenericNameRole, KeywordsRole, CommentRole };
    static AllApps *instance();
    static AllApps *create(QQmlEngine *, QJSEngine *);
    int rowCount(const QModelIndex &parent = {}) const override;
    QVariant data(const QModelIndex &index, int role) const override;
    QHash<int, QByteArray> roleNames() const override;
    // [{name, apps: [{storageId, name, icon}]}] for the Category view, non-empty groups only.
    Q_INVOKABLE QVariantList groups() const;
    struct App { QString storageId, name, icon, group, genericName, keywords, comment; };
    const QList<App> &apps() const { return m_apps; }
Q_SIGNALS:
    void countChanged();
private:
    explicit AllApps(QObject *parent = nullptr);
    void reload();
    QList<App> m_apps;
};

// Start pins: shell.conf [Start] Pinned (default: the GNOME layer's ArcMenu pinned-apps).
class StartPins : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(QVariantList apps READ apps NOTIFY changed) // [{storageId, name, icon}]
public:
    static StartPins *instance();
    static StartPins *create(QQmlEngine *, QJSEngine *);
    QVariantList apps() const;
    Q_INVOKABLE bool isPinned(const QString &storageId) const;
    Q_INVOKABLE void pin(const QString &storageId);
    Q_INVOKABLE void unpin(const QString &storageId);
    Q_INVOKABLE void move(int from, int to);
    QStringList ids() const;
Q_SIGNALS:
    void changed();
private:
    explicit StartPins(QObject *parent = nullptr);
    void save(const QStringList &ids);
};

// ~/.local/share/recently-used.xbel, newest first (Recommended, Search documents).
class RecentFiles : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(QVariantList items READ items NOTIFY changed) // [{uri, name, icon, mime, modified, age}]
public:
    static RecentFiles *instance();
    static RecentFiles *create(QQmlEngine *, QJSEngine *);
    QVariantList items() const { return m_items; }
    // "Today at 10:42", "Yesterday at 18:03", "3 days ago" (Recommended's wording).
    Q_INVOKABLE static QString ageText(const QDateTime &when);
    Q_INVOKABLE void open(const QString &uri) const;
    Q_INVOKABLE void openLocation(const QString &uri) const;
Q_SIGNALS:
    void changed();
private:
    explicit RecentFiles(QObject *parent = nullptr);
    void reload();
    QFileSystemWatcher m_watcher;
    QVariantList m_items;
};

// Launch counts (~/.local/state/fenestra/app-usage.json) and the Search history
// (~/.local/state/windows-search/history.json, the GNOME layer's file and format).
class Usage : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(QVariantList recentSearches READ recentSearches NOTIFY changed) // [{kind, value, name, icon, age}]
public:
    static Usage *instance();
    static Usage *create(QQmlEngine *, QJSEngine *);
    Q_INVOKABLE QVariantList topApps(int count) const; // most used, then Start pins
    QVariantList recentSearches() const;
    Q_INVOKABLE void rememberQuery(const QString &query);
    Q_INVOKABLE void rememberApp(const QString &storageId);
    Q_INVOKABLE static QString ageText(qint64 msecsSinceEpoch);
    int launches(const QString &storageId) const { return m_counts.value(storageId); }
Q_SIGNALS:
    void changed();
private:
    explicit Usage(QObject *parent = nullptr);
    void saveCounts() const;
    void saveHistory() const;
    QHash<QString, int> m_counts;
    QStringList m_queries, m_apps;
    QList<QVariantMap> m_entries; // {kind: app|query, value, at}
};

// The signed-in user (AccountsService): name for the Start footer, picture.
class UserInfo : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(QString name READ name NOTIFY changed)       // first two words of the real name
    Q_PROPERTY(QString fullName READ fullName NOTIFY changed)
    Q_PROPERTY(QString picture READ picture NOTIFY changed) // file URL or ""
public:
    static UserInfo *instance();
    static UserInfo *create(QQmlEngine *, QJSEngine *);
    QString name() const;
    QString fullName() const { return m_fullName; }
    QString picture() const { return m_picture; }
Q_SIGNALS:
    void changed();
private Q_SLOTS:
    void reload();
private:
    explicit UserInfo(QObject *parent = nullptr);
    QString m_fullName, m_picture, m_path;
};

// Power and account actions (logind; signing out ends fenestra-session.target).
class Session : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(bool canSuspend READ canSuspend CONSTANT)
public:
    static Session *instance();
    static Session *create(QQmlEngine *, QJSEngine *);
    bool canSuspend() const;
    Q_INVOKABLE void lock();
    Q_INVOKABLE void suspend();
    Q_INVOKABLE void powerOff();
    Q_INVOKABLE void reboot();
    Q_INVOKABLE void logout();
    Q_INVOKABLE void switchUser();
private:
    explicit Session(QObject *parent = nullptr);
    void login1(const QString &method, const QVariantList &args = {});
};
