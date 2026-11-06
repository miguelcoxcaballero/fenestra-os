// SPDX-License-Identifier: GPL-3.0-or-later
// Notification server (N01, N02): org.freedesktop.Notifications 1.2 in the shell, with history,
// banners (popups), Do not disturb and the Focus session of the calendar card.
#pragma once

#include <QAbstractListModel>
#include <QDBusContext>
#include <QDateTime>
#include <QImage>
#include <QQmlEngine>
#include <QQuickImageProvider>
#include <QTimer>

class Notifications : public QAbstractListModel, protected QDBusContext
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_CLASSINFO("D-Bus Interface", "org.freedesktop.Notifications")
    Q_PROPERTY(int count READ rowCount NOTIFY countChanged)
    Q_PROPERTY(QVariantList popups READ popups NOTIFY popupsChanged)        // banners on screen, newest last
    Q_PROPERTY(bool doNotDisturb READ doNotDisturb WRITE setDoNotDisturb NOTIFY doNotDisturbChanged)
    Q_PROPERTY(int focusRemaining READ focusRemaining NOTIFY focusChanged)  // seconds, 0 = no Focus session
public:
    enum Roles { IdRole = Qt::UserRole + 1, AppNameRole, AppIconRole, SummaryRole, BodyRole, ActionsRole,
                 ImageRole, TimeRole, UrgencyRole, DesktopEntryRole };
    struct Item {
        uint id = 0;
        QString appName, appIcon, summary, body, desktopEntry, image;
        QVariantList actions; // [{key, label}]
        QDateTime time;
        int urgency = 1;
        bool resident = false, transient = false;
        int timeout = -1;
    };

    static Notifications *instance();
    static Notifications *create(QQmlEngine *, QJSEngine *);
    void registerOnBus();

    int rowCount(const QModelIndex &parent = {}) const override;
    QVariant data(const QModelIndex &index, int role) const override;
    QHash<int, QByteArray> roleNames() const override;

    QVariantList popups() const;
    bool doNotDisturb() const { return m_dnd; }
    void setDoNotDisturb(bool on);
    int focusRemaining() const;

    Q_INVOKABLE void invoke(uint id, const QString &actionKey);  // "default" = clicked
    Q_INVOKABLE void dismiss(uint id);                           // closed by the user
    Q_INVOKABLE void hidePopup(uint id);                         // banner timed out: stays in history
    Q_INVOKABLE void clearAll();
    Q_INVOKABLE void startFocus(int minutes);
    Q_INVOKABLE void endFocus();
    // For the shell's own notices (screenshots…).
    uint notify(const QString &appName, const QString &icon, const QString &summary, const QString &body,
                const QString &imagePath = {}, const QVariantList &actions = {});
    QImage image(uint id) const { return m_images.value(id); }

public Q_SLOTS:
    // org.freedesktop.Notifications
    Q_SCRIPTABLE QStringList GetCapabilities();
    Q_SCRIPTABLE uint Notify(const QString &appName, uint replacesId, const QString &appIcon, const QString &summary,
                             const QString &body, const QStringList &actions, const QVariantMap &hints, int expireTimeout);
    Q_SCRIPTABLE void CloseNotification(uint id);
    // Replies (name, vendor, version, spec version): four out arguments, sent from the D-Bus context.
    Q_SCRIPTABLE QString GetServerInformation();

Q_SIGNALS:
    Q_SCRIPTABLE void NotificationClosed(uint id, uint reason);
    Q_SCRIPTABLE void ActionInvoked(uint id, const QString &actionKey);
    Q_SCRIPTABLE void ActivationToken(uint id, const QString &token);
    void countChanged();
    void popupsChanged();
    void doNotDisturbChanged();
    void focusChanged();
    // Shell-internal actions of its own notices.
    void shellAction(uint id, const QString &actionKey);

private:
    explicit Notifications(QObject *parent = nullptr);
    int rowOf(uint id) const;
    void close(uint id, uint reason);
    void schedulePopupEnd(const Item &item);
    QList<Item> m_items;                 // newest first
    QList<uint> m_popups;
    QHash<uint, QImage> m_images;
    QHash<uint, QTimer *> m_popupTimers;
    uint m_nextId = 1;
    bool m_dnd = false;
    bool m_dndBeforeFocus = false;
    QDateTime m_focusEnd;
    QTimer m_focusTimer;
    QSet<uint> m_shellOwned;
};

// image://notification/<id>: image-data hints and the shell's own thumbnails.
class NotificationImageProvider : public QQuickImageProvider
{
public:
    NotificationImageProvider() : QQuickImageProvider(QQuickImageProvider::Image) {}
    QImage requestImage(const QString &id, QSize *size, const QSize &requested) override;
};
