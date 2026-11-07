// SPDX-License-Identifier: GPL-3.0-or-later
#include "notifications.h"

#include "apps.h"
#include "shellsettings.h"

#include <algorithm>
#include <QDBusArgument>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QFileInfo>
#include <QUrl>
#include <QTextDocumentFragment>

namespace
{
enum CloseReason : uint { Expired = 1, Dismissed = 2, Closed = 3 };
constexpr int kDefaultTimeout = 5000;   // banners without an explicit timeout
constexpr int kMaxHistory = 100;

QImage readImageData(const QDBusArgument &arg)
{
    int w = 0, h = 0, stride = 0, bits = 0, channels = 0;
    bool alpha = false;
    QByteArray data;
    arg.beginStructure();
    arg >> w >> h >> stride >> alpha >> bits >> channels >> data;
    arg.endStructure();
    if (w <= 0 || h <= 0 || bits != 8 || (channels != 3 && channels != 4) || data.size() < stride * (h - 1) + w * channels)
        return {};
    QImage img(reinterpret_cast<const uchar *>(data.constData()), w, h, stride,
               alpha ? QImage::Format_RGBA8888 : QImage::Format_RGB888);
    return img.copy();
}
QString plain(const QString &markup)
{
    // Body markup (<b>, <i>, <a>, &amp;): shown as text, as the GNOME layer did.
    return QTextDocumentFragment::fromHtml(QString(markup).replace(QLatin1Char('\n'), QLatin1String("<br>"))).toPlainText();
}
}

Notifications *Notifications::instance()
{
    static auto *n = new Notifications;
    return n;
}

Notifications *Notifications::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

Notifications::Notifications(QObject *parent)
    : QAbstractListModel(parent)
{
    m_dnd = ShellSettings::instance()->value(QStringLiteral("Notifications/DoNotDisturb"), false).toBool();
    // Fenestra Settings changes it in shell.conf: apply it live (not during a Focus session).
    connect(ShellSettings::instance(), &ShellSettings::fileChanged, this, [this] {
        const bool dnd = ShellSettings::instance()->value(QStringLiteral("Notifications/DoNotDisturb"), false).toBool();
        if (dnd != m_dnd && !m_focusEnd.isValid()) {
            m_dnd = dnd;
            Q_EMIT doNotDisturbChanged();
        }
    });
    m_focusTimer.setInterval(1000);
    connect(&m_focusTimer, &QTimer::timeout, this, [this] {
        if (focusRemaining() <= 0)
            endFocus();
        else
            Q_EMIT focusChanged();
    });
}

void Notifications::registerOnBus()
{
    auto bus = QDBusConnection::sessionBus();
    bus.registerObject(QStringLiteral("/org/freedesktop/Notifications"), this,
                       QDBusConnection::ExportScriptableSlots | QDBusConnection::ExportScriptableSignals);
    if (!bus.registerService(QStringLiteral("org.freedesktop.Notifications")))
        qWarning("fenestra-shell: another notification server owns org.freedesktop.Notifications");
}

QStringList Notifications::GetCapabilities()
{
    return {QStringLiteral("body"), QStringLiteral("body-markup"), QStringLiteral("actions"), QStringLiteral("icon-static"),
            QStringLiteral("persistence"), QStringLiteral("x-kde-urls")};
}

QString Notifications::GetServerInformation()
{
    if (calledFromDBus()) {
        setDelayedReply(true);
        connection().send(message().createReply({QStringLiteral("Fenestra Shell"), QStringLiteral("Fenestra"),
                                                 QCoreApplication::applicationVersion(), QStringLiteral("1.2")}));
    }
    return QStringLiteral("Fenestra Shell");
}

uint Notifications::Notify(const QString &appName, uint replacesId, const QString &appIcon, const QString &summary,
                           const QString &body, const QStringList &actions, const QVariantMap &hints, int expireTimeout)
{
    Item item;
    item.id = replacesId && rowOf(replacesId) >= 0 ? replacesId : m_nextId++;
    item.desktopEntry = hints.value(QStringLiteral("desktop-entry")).toString();
    item.appName = appName;
    item.appIcon = appIcon;
    if (const KService::Ptr s = Apps::instance()->service(item.desktopEntry)) {
        if (item.appName.isEmpty())
            item.appName = s->name();
        if (item.appIcon.isEmpty())
            item.appIcon = s->icon();
    }
    item.summary = summary;
    item.body = plain(body);
    for (int i = 0; i + 1 < actions.size(); i += 2)
        item.actions.append(QVariantMap{{QStringLiteral("key"), actions.at(i)}, {QStringLiteral("label"), actions.at(i + 1)}});
    item.time = QDateTime::currentDateTime();
    item.urgency = hints.value(QStringLiteral("urgency"), 1).toInt();
    item.resident = hints.value(QStringLiteral("resident")).toBool();
    item.transient = hints.value(QStringLiteral("transient")).toBool();
    item.timeout = expireTimeout;
    if (hints.contains(QStringLiteral("value")))
        item.value = std::clamp(hints.value(QStringLiteral("value")).toInt(), 0, 100);
    for (const char *key : {"image-data", "image_data", "icon_data"}) {
        if (hints.contains(QLatin1String(key))) {
            const QImage img = readImageData(hints.value(QLatin1String(key)).value<QDBusArgument>());
            if (!img.isNull()) {
                m_images.insert(item.id, img);
                item.image = QStringLiteral("image://notification/%1/%2").arg(item.id).arg(QDateTime::currentMSecsSinceEpoch());
            }
            break;
        }
    }
    const QString path = hints.value(QStringLiteral("image-path"), hints.value(QStringLiteral("image_path"))).toString();
    if (item.image.isEmpty() && !path.isEmpty())
        item.image = path.startsWith(QLatin1Char('/')) ? QUrl::fromLocalFile(path).toString() : path;

    const int row = rowOf(item.id);
    if (row >= 0) {
        m_items[row] = item;
        Q_EMIT dataChanged(index(row), index(row));
    } else {
        beginInsertRows({}, 0, 0);
        m_items.prepend(item);
        endInsertRows();
        while (m_items.size() > kMaxHistory) {
            beginRemoveRows({}, m_items.size() - 1, m_items.size() - 1);
            m_images.remove(m_items.takeLast().id);
            endRemoveRows();
        }
        Q_EMIT countChanged();
    }
    // Banners: not with Do not disturb, except critical ones.
    if (!m_dnd || item.urgency == 2) {
        m_popups.removeAll(item.id);
        m_popups.append(item.id);
        Q_EMIT popupsChanged();
        schedulePopupEnd(item);
    }
    return item.id;
}

void Notifications::schedulePopupEnd(const Item &item)
{
    delete m_popupTimers.take(item.id);
    if (item.urgency == 2 && item.timeout <= 0)
        return; // critical: stays until dismissed
    auto *t = new QTimer(this);
    t->setSingleShot(true);
    t->setInterval(item.timeout > 0 ? item.timeout : kDefaultTimeout);
    const uint id = item.id;
    const bool transient = item.transient;
    connect(t, &QTimer::timeout, this, [this, id, transient] {
        if (transient)
            close(id, Expired);
        else
            hidePopup(id);
    });
    m_popupTimers.insert(item.id, t);
    t->start();
}

void Notifications::CloseNotification(uint id)
{
    close(id, Closed);
}

void Notifications::close(uint id, uint reason)
{
    delete m_popupTimers.take(id);
    if (m_popups.removeAll(id))
        Q_EMIT popupsChanged();
    const int row = rowOf(id);
    if (row < 0)
        return;
    beginRemoveRows({}, row, row);
    m_items.removeAt(row);
    endRemoveRows();
    m_images.remove(id);
    Q_EMIT countChanged();
    if (!m_shellOwned.remove(id))
        Q_EMIT NotificationClosed(id, reason);
}

void Notifications::hidePopup(uint id)
{
    delete m_popupTimers.take(id);
    if (m_popups.removeAll(id))
        Q_EMIT popupsChanged();
}

void Notifications::dismiss(uint id)
{
    close(id, Dismissed);
}

void Notifications::invoke(uint id, const QString &actionKey)
{
    const int row = rowOf(id);
    if (row < 0)
        return;
    const Item item = m_items.at(row);
    if (m_shellOwned.contains(id)) {
        Q_EMIT shellAction(id, actionKey);
    } else {
        Q_EMIT ActionInvoked(id, actionKey);
        // No action list but a desktop entry: clicking opens the app.
        if (actionKey == QLatin1String("default") && item.actions.isEmpty() && !item.desktopEntry.isEmpty())
            Apps::instance()->launch(item.desktopEntry);
    }
    if (!item.resident)
        close(id, Dismissed);
    else
        hidePopup(id);
}

void Notifications::clearAll()
{
    const auto items = m_items;
    for (const Item &i : items)
        close(i.id, Dismissed);
}

void Notifications::setDoNotDisturb(bool on)
{
    if (on == m_dnd)
        return;
    m_dnd = on;
    ShellSettings::instance()->setValue(QStringLiteral("Notifications/DoNotDisturb"), on);
    Q_EMIT doNotDisturbChanged();
}

int Notifications::focusRemaining() const
{
    return m_focusEnd.isValid() ? int(std::max<qint64>(0, QDateTime::currentDateTime().secsTo(m_focusEnd))) : 0;
}

void Notifications::startFocus(int minutes)
{
    // Focus (calendar card): banners off for the session, the previous state comes back after.
    if (!m_focusEnd.isValid())
        m_dndBeforeFocus = m_dnd;
    m_focusEnd = QDateTime::currentDateTime().addSecs(std::clamp(minutes, 5, 240) * 60);
    setDoNotDisturb(true);
    m_focusTimer.start();
    Q_EMIT focusChanged();
}

void Notifications::endFocus()
{
    if (!m_focusEnd.isValid())
        return;
    m_focusEnd = {};
    m_focusTimer.stop();
    setDoNotDisturb(m_dndBeforeFocus);
    Q_EMIT focusChanged();
}

uint Notifications::notify(const QString &appName, const QString &icon, const QString &summary, const QString &body,
                           const QString &imagePath, const QVariantList &actions)
{
    QStringList flat;
    for (const QVariant &a : actions)
        flat << a.toMap().value(QStringLiteral("key")).toString() << a.toMap().value(QStringLiteral("label")).toString();
    QVariantMap hints;
    if (!imagePath.isEmpty())
        hints.insert(QStringLiteral("image-path"), imagePath);
    const uint id = Notify(appName, 0, icon, summary, body, flat, hints, -1);
    m_shellOwned.insert(id);
    return id;
}

int Notifications::rowOf(uint id) const
{
    for (int i = 0; i < m_items.size(); ++i)
        if (m_items.at(i).id == id)
            return i;
    return -1;
}

int Notifications::rowCount(const QModelIndex &parent) const
{
    return parent.isValid() ? 0 : m_items.size();
}

QVariant Notifications::data(const QModelIndex &index, int role) const
{
    if (!index.isValid() || index.row() >= m_items.size())
        return {};
    const Item &i = m_items.at(index.row());
    switch (role) {
    case IdRole: return i.id;
    case AppNameRole: return i.appName;
    case AppIconRole: return i.appIcon;
    case Qt::DisplayRole:
    case SummaryRole: return i.summary;
    case BodyRole: return i.body;
    case ActionsRole: return i.actions;
    case ImageRole: return i.image;
    case TimeRole: return i.time;
    case UrgencyRole: return i.urgency;
    case DesktopEntryRole: return i.desktopEntry;
    case ValueRole: return i.value;
    }
    return {};
}

QHash<int, QByteArray> Notifications::roleNames() const
{
    return {{IdRole, "notificationId"}, {AppNameRole, "appName"}, {AppIconRole, "appIcon"}, {SummaryRole, "summary"},
            {BodyRole, "body"}, {ActionsRole, "actions"}, {ImageRole, "image"}, {TimeRole, "time"},
            {UrgencyRole, "urgency"}, {DesktopEntryRole, "desktopEntry"}, {ValueRole, "value"}};
}

QVariantList Notifications::popups() const
{
    QVariantList out;
    for (uint id : m_popups) {
        const int row = rowOf(id);
        if (row < 0)
            continue;
        const Item &i = m_items.at(row);
        out.append(QVariantMap{{QStringLiteral("notificationId"), i.id}, {QStringLiteral("appName"), i.appName},
                               {QStringLiteral("appIcon"), i.appIcon}, {QStringLiteral("summary"), i.summary},
                               {QStringLiteral("body"), i.body}, {QStringLiteral("actions"), i.actions},
                               {QStringLiteral("image"), i.image}, {QStringLiteral("urgency"), i.urgency},
                               {QStringLiteral("value"), i.value}});
    }
    return out;
}

QImage NotificationImageProvider::requestImage(const QString &id, QSize *size, const QSize &requested)
{
    QImage img = Notifications::instance()->image(id.section(QLatin1Char('/'), 0, 0).toUInt());
    if (!img.isNull() && requested.isValid())
        img = img.scaled(requested, Qt::KeepAspectRatio, Qt::SmoothTransformation);
    if (size)
        *size = img.size();
    return img;
}
