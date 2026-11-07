// SPDX-License-Identifier: GPL-3.0-or-later
// Taskbar buttons (B02): pinned apps in their order, then running apps that are not pinned.
// Windows are grouped by their .desktop entry; a window with no entry is its own button.
#pragma once

#include <QAbstractListModel>
#include <QQmlEngine>
#include <QVariantList>

class PlasmaWindow;

class TaskbarModel : public QAbstractListModel
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
public:
    enum Roles { StorageIdRole = Qt::UserRole + 1, NameRole, IconRole, PinnedRole, WindowCountRole,
                 ActiveRole, AttentionRole, WindowsRole };

    static TaskbarModel *instance();
    static TaskbarModel *create(QQmlEngine *, QJSEngine *);

    int rowCount(const QModelIndex &parent = {}) const override;
    QVariant data(const QModelIndex &index, int role) const override;
    QHash<int, QByteArray> roleNames() const override;

    // Click: launch (no window), activate/minimize (one), next window of the group (several).
    Q_INVOKABLE void activate(int row);
    Q_INVOKABLE void newInstance(int row);
    Q_INVOKABLE void closeAll(int row);
    Q_INVOKABLE void togglePinned(int row);
    // Drag and drop of pinned buttons: new order of the pinned part.
    Q_INVOKABLE void movePinned(int from, int to);
    // Drag and drop of any button (Windows: pinned and running buttons can be reordered; the pinned
    // order is saved, the place of a running unpinned button lasts while it runs).
    Q_INVOKABLE void move(int from, int to);

private:
    explicit TaskbarModel(QObject *parent = nullptr);
    struct Entry {
        QString key;        // storageId, or "window:<uuid>" when there is no .desktop entry
        QString storageId;
        QString name;
        QString icon;
        bool pinned = false;
        QList<PlasmaWindow *> windows;
    };
    void rebuild();
    QList<Entry> m_entries;
    QStringList m_order;   // button keys in the order the user left them
    int m_cycle = 0;
};
