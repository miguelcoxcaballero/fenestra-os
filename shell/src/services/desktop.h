// SPDX-License-Identifier: GPL-3.0-or-later
// Desktop icons (D01, D02; DING under GNOME): the XDG Desktop folder plus the Recycle Bin, in a
// column-major grid; positions remembered; file operations through KIO (undoable, async).
#pragma once

#include <QSize>
#include <QAbstractListModel>
#include <QFileSystemWatcher>
#include <QHash>
#include <QPoint>
#include <QQmlEngine>
#include <QUrl>

class DesktopModel : public QAbstractListModel
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(QString folder READ folder CONSTANT)
    Q_PROPERTY(QStringList templates READ templates NOTIFY templatesChanged)
public:
    enum Roles { NameRole = Qt::UserRole + 1, PathRole, UrlRole, IconRole, IconSourceRole, IsDirRole, IsTrashRole, CellRole };
    static DesktopModel *instance();
    static DesktopModel *create(QQmlEngine *, QJSEngine *);

    int rowCount(const QModelIndex &parent = {}) const override;
    QVariant data(const QModelIndex &index, int role) const override;
    QHash<int, QByteArray> roleNames() const override;
    QString folder() const { return m_dir; }
    QStringList templates() const;

    // Grid layout: rows per column comes from the screen; cells are {column, row}.
    Q_INVOKABLE void setRowsPerColumn(int rows);
    Q_INVOKABLE void moveTo(int row, int column, int gridRow);
    Q_INVOKABLE void open(int row);
    Q_INVOKABLE void trash(const QList<int> &rows);
    Q_INVOKABLE void rename(int row, const QString &newName);
    Q_INVOKABLE void newFolder();
    Q_INVOKABLE void newFromTemplate(const QString &templateName);
    Q_INVOKABLE void copyAsPath(const QList<int> &rows);
    Q_INVOKABLE void copy(const QList<int> &rows, bool cut);
    Q_INVOKABLE void paste();
    Q_INVOKABLE void properties(const QList<int> &rows);
    Q_INVOKABLE void openTerminal();
    Q_INVOKABLE void dropUrls(const QList<QUrl> &urls, bool move);
    Q_INVOKABLE QList<QUrl> urls(const QList<int> &rows) const;
    Q_INVOKABLE void sortBy(const QString &key); // name | type | date

Q_SIGNALS:
    void templatesChanged();
    void renameRequested(int row); // after "New folder"

private:
    explicit DesktopModel(QObject *parent = nullptr);
    void reload();
    void layout();
    void savePositions() const;
    struct Item { QString name, path, icon, iconSource; bool dir = false, trash = false; QPoint cell; };
    QList<Item> m_items;
    QHash<QString, QPoint> m_positions; // file name -> cell
    QFileSystemWatcher m_watcher;
    QString m_dir;
    int m_rows = 10;
    QString m_pendingRename;
};

// Wallpaper (D03): shell.conf Appearance/Wallpaper is a file, a solid colour "#rrggbb" or
// "spotlight" (/var/lib/fenestra-spotlight/current.json, the GNOME layer's daily picture).
class WallpaperSource : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(QString image READ image NOTIFY changed)   // file URL, or "" for a colour
    Q_PROPERTY(QString color READ color NOTIFY changed)   // background colour behind / instead of the image
    Q_PROPERTY(QSize imageSize READ imageSize NOTIFY changed)   // the file's own pixels (empty: unknown)
public:
    static WallpaperSource *instance();
    static WallpaperSource *create(QQmlEngine *, QJSEngine *);
    QString image() const { return m_image; }
    QString color() const { return m_color; }
    QSize imageSize() const { return m_imageSize; }
Q_SIGNALS:
    void changed();
private:
    explicit WallpaperSource(QObject *parent = nullptr);
    void update();
    QFileSystemWatcher m_watcher;
    QString m_image, m_color = QStringLiteral("#202020");
    QSize m_imageSize;
};
