// SPDX-License-Identifier: GPL-3.0-or-later
// Search (S04, S05): apps, Fenestra Settings pages (its own index, --export-search-index),
// documents, folders and photos (an index of the user's folders built off the UI thread),
// and the web. Results come in the GNOME layer's sections and limits (windowsSearchResults.js).
#pragma once

#include <QDateTime>
#include <QObject>
#include <QQmlEngine>
#include <QVariantList>

class Search : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(QString text READ text WRITE setText NOTIFY resultsChanged)
    // "all" | "web" | "apps" | "files" | "settings" | "folders" | "photos"
    Q_PROPERTY(QString filter READ filter WRITE setFilter NOTIFY resultsChanged)
    // [{title, items: [{kind, title, subtitle, icon, iconSource, id, path, modified}]}]; first section is "Best match"
    Q_PROPERTY(QVariantList sections READ sections NOTIFY resultsChanged)
    Q_PROPERTY(QVariantMap best READ best NOTIFY resultsChanged)
    Q_PROPERTY(bool indexing READ indexing NOTIFY indexingChanged)
    Q_PROPERTY(int indexedFiles READ indexedFiles NOTIFY indexingChanged)
    Q_PROPERTY(int settingsEntries READ settingsEntries NOTIFY resultsChanged)
public:
    static Search *instance();
    static Search *create(QQmlEngine *, QJSEngine *);

    QString text() const { return m_text; }
    QString filter() const { return m_filter; }
    QVariantList sections() const { return m_sections; }
    QVariantMap best() const { return m_best; }
    bool indexing() const { return m_indexing; }
    int indexedFiles() const { return m_files.size(); }
    int settingsEntries() const { return m_settingsIndex.size(); }
    void setText(const QString &text);
    void setFilter(const QString &filter);

    // Opens a result (and records it in the history); "location" opens its folder.
    Q_INVOKABLE void activate(const QVariantMap &item, const QString &action = QString());
    Q_INVOKABLE void searchWeb(const QString &text);
    Q_INVOKABLE void copyPath(const QVariantMap &item);
    // Called when Search opens: refresh the file index when it is old, load the Settings index.
    Q_INVOKABLE void prepare();

    struct FileEntry { QString path, name, lower; bool dir; bool image; QDateTime modified; };

Q_SIGNALS:
    void resultsChanged();
    void indexingChanged();
    void activated();

private:
    explicit Search(QObject *parent = nullptr);
    void run();
    void loadSettingsIndex();
    void indexFiles();
    QString m_text, m_filter = QStringLiteral("all");
    QVariantList m_sections;
    QVariantMap m_best;
    QList<FileEntry> m_files;
    QDateTime m_filesAt;
    bool m_indexing = false;
    QVariantList m_settingsIndex; // [{page, key, title, where, icon, hay}]
    bool m_settingsLoading = false;
};
