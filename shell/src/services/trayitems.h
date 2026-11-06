// SPDX-License-Identifier: GPL-3.0-or-later
// Tray icons of apps (B08): StatusNotifierItem host + watcher (org.kde.StatusNotifierWatcher),
// with com.canonical.dbusmenu menus read into plain lists so the shell draws them itself.
#pragma once

#include <QAbstractListModel>
#include <QDBusContext>
#include <QImage>
#include <QQmlEngine>
#include <QQuickImageProvider>
#include <QStringList>
#include <QVariantList>

class TrayItems : public QAbstractListModel, protected QDBusContext
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_CLASSINFO("D-Bus Interface", "org.kde.StatusNotifierWatcher")
    Q_PROPERTY(QStringList RegisteredStatusNotifierItems READ registeredItems)
    Q_PROPERTY(bool IsStatusNotifierHostRegistered READ hostRegistered)
    Q_PROPERTY(int ProtocolVersion READ protocolVersion)
    Q_PROPERTY(int count READ rowCount NOTIFY countChanged)
public:
    enum Roles { KeyRole = Qt::UserRole + 1, TitleRole, IconNameRole, IconUrlRole, StatusRole, ToolTipRole, HasMenuRole };

    static TrayItems *instance();
    static TrayItems *create(QQmlEngine *, QJSEngine *);

    int rowCount(const QModelIndex &parent = {}) const override;
    QVariant data(const QModelIndex &index, int role) const override;
    QHash<int, QByteArray> roleNames() const override;

    QStringList registeredItems() const;
    bool hostRegistered() const { return true; }
    int protocolVersion() const { return 0; }

    Q_INVOKABLE void activate(int row, int x, int y);
    Q_INVOKABLE void secondaryActivate(int row, int x, int y);
    Q_INVOKABLE void scroll(int row, int delta);
    // Menu of the item as [{id, text, icon, enabled, separator, checked}]; empty when it has none.
    // menuReady(row, items) is emitted when the layout arrives.
    Q_INVOKABLE void requestMenu(int row);
    Q_INVOKABLE void triggerMenuItem(int row, int id);
    // Items with no menu get ContextMenu(x, y).
    Q_INVOKABLE void contextMenu(int row, int x, int y);

    QImage pixmap(const QString &key) const { return m_pixmaps.value(key); }

public Q_SLOTS:
    // org.kde.StatusNotifierWatcher
    Q_SCRIPTABLE void RegisterStatusNotifierItem(const QString &serviceOrPath);
    Q_SCRIPTABLE void RegisterStatusNotifierHost(const QString &service);

Q_SIGNALS:
    Q_SCRIPTABLE void StatusNotifierItemRegistered(const QString &item);
    Q_SCRIPTABLE void StatusNotifierItemUnregistered(const QString &item);
    Q_SCRIPTABLE void StatusNotifierHostRegistered();
    void menuReady(int row, const QVariantList &items);
    void countChanged();

private Q_SLOTS:
    void onItemChanged();

private:
    explicit TrayItems(QObject *parent = nullptr);
    struct Item {
        QString key, service, path;
        QString id, title, iconName, iconThemePath, status, toolTip, menuPath;
        bool itemIsMenu = false;
        int pixmapSerial = 0;
    };
    void addItem(const QString &service, const QString &path);
    void removeService(const QString &service);
    void refresh(const QString &key);
    int rowOf(const QString &key) const;
    QList<Item> m_items;
    QHash<QString, QImage> m_pixmaps;
};

// image://sni/<key>/<serial>: IconPixmap of a tray item.
class TrayImageProvider : public QQuickImageProvider
{
public:
    TrayImageProvider() : QQuickImageProvider(QQuickImageProvider::Image) {}
    QImage requestImage(const QString &id, QSize *size, const QSize &requested) override;
};
