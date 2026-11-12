// SPDX-License-Identifier: GPL-3.0-or-later
#include "trayitems.h"
#include "guard.h"

#include <QCoreApplication>
#include <QDBusArgument>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusMessage>
#include <QDBusMetaType>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusServiceWatcher>
#include <QDBusVariant>
#include <QRegularExpression>
#include <QtEndian>

namespace
{
const QString kItemIface = QStringLiteral("org.kde.StatusNotifierItem");
const QString kMenuIface = QStringLiteral("com.canonical.dbusmenu");
QDBusServiceWatcher *gWatcher = nullptr;

// IconPixmap a(iiay): ARGB32 in network byte order; take the largest.
QImage readPixmaps(const QDBusArgument &arg)
{
    QImage best;
    arg.beginArray();
    while (!arg.atEnd()) {
        int w = 0, h = 0;
        QByteArray bytes;
        arg.beginStructure();
        arg >> w >> h >> bytes;
        arg.endStructure();
        if (w <= 0 || h <= 0 || bytes.size() < w * h * 4 || w * h <= best.width() * best.height())
            continue;
        QImage img(w, h, QImage::Format_ARGB32);
        const quint32 *src = reinterpret_cast<const quint32 *>(bytes.constData());
        for (int y = 0; y < h; ++y) {
            auto *line = reinterpret_cast<quint32 *>(img.scanLine(y));
            for (int x = 0; x < w; ++x)
                line[x] = qFromBigEndian(src[y * w + x]);
        }
        best = img;
    }
    arg.endArray();
    return best;
}

// dbusmenu layout (ia{sv}av) -> flat list; submenu children follow their parent, indented.
void readLayout(const QDBusArgument &arg, QVariantList &out, int depth)
{
    int id = 0;
    QVariantMap props;
    arg.beginStructure();
    arg >> id >> props;
    if (depth > 0 && props.value(QStringLiteral("visible"), true).toBool()) {
        const bool separator = props.value(QStringLiteral("type")).toString() == QLatin1String("separator");
        QString text = props.value(QStringLiteral("label")).toString();
        text.remove(QRegularExpression(QStringLiteral("_(?=[^_])"))); // mnemonic underscores
        out.append(QVariantMap{{QStringLiteral("id"), id}, {QStringLiteral("text"), text},
                               {QStringLiteral("icon"), props.value(QStringLiteral("icon-name")).toString()},
                               {QStringLiteral("enabled"), props.value(QStringLiteral("enabled"), true).toBool()},
                               {QStringLiteral("separator"), separator},
                               {QStringLiteral("checked"), props.value(QStringLiteral("toggle-state"), -1).toInt() == 1},
                               {QStringLiteral("depth"), depth - 1}});
    }
    arg.beginArray();
    while (!arg.atEnd()) {
        QDBusVariant child;
        arg >> child;
        readLayout(child.variant().value<QDBusArgument>(), out, depth + 1);
    }
    arg.endArray();
    arg.endStructure();
}
}

TrayItems *TrayItems::instance()
{
    static auto *t = new TrayItems;
    return t;
}

TrayItems *TrayItems::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

TrayItems::TrayItems(QObject *parent)
    : QAbstractListModel(parent)
{
    auto bus = QDBusConnection::sessionBus();
    gWatcher = new QDBusServiceWatcher(this);
    gWatcher->setConnection(bus);
    gWatcher->setWatchMode(QDBusServiceWatcher::WatchForUnregistration);
    connect(gWatcher, &QDBusServiceWatcher::serviceUnregistered, this, &TrayItems::removeService);

    bus.registerObject(QStringLiteral("/StatusNotifierWatcher"), this,
                       QDBusConnection::ExportScriptableSlots | QDBusConnection::ExportScriptableSignals
                           | QDBusConnection::ExportAllProperties);
    if (!bus.registerService(QStringLiteral("org.kde.StatusNotifierWatcher")))
        qWarning("fenestra-shell: another StatusNotifierWatcher is running; tray icons may be missing");
    bus.registerService(QStringLiteral("org.kde.StatusNotifierHost-%1").arg(QCoreApplication::applicationPid()));
}

QStringList TrayItems::registeredItems() const
{
    QStringList list;
    for (const Item &i : m_items)
        list << i.service + i.path;
    return list;
}

void TrayItems::RegisterStatusNotifierItem(const QString &serviceOrPath)
{
    QString service = serviceOrPath, path = QStringLiteral("/StatusNotifierItem");
    if (serviceOrPath.startsWith(QLatin1Char('/'))) {
        service = message().service();
        path = serviceOrPath;
    }
    addItem(service, path);
}

void TrayItems::RegisterStatusNotifierHost(const QString &)
{
    Q_EMIT StatusNotifierHostRegistered();
}

void TrayItems::addItem(const QString &service, const QString &path)
{
    // Key by the unique connection name, so signals (sent from it) find the item.
    auto *iface = QDBusConnection::sessionBus().interface();
    const QString owner = service.startsWith(QLatin1Char(':')) ? service : iface->serviceOwner(service).value();
    if (owner.isEmpty())
        return;
    const QString key = owner + path;
    if (rowOf(key) >= 0)
        return;
    beginInsertRows({}, m_items.size(), m_items.size());
    m_items.append({key, owner, path});
    endInsertRows();
    Q_EMIT countChanged();
    gWatcher->addWatchedService(owner);
    auto bus = QDBusConnection::sessionBus();
    for (const char *signal : {"NewIcon", "NewTitle", "NewStatus", "NewToolTip", "NewAttentionIcon", "NewMenu"})
        bus.connect(owner, path, kItemIface, QLatin1String(signal), this, SLOT(onItemChanged()));
    refresh(key);
    Q_EMIT StatusNotifierItemRegistered(service + path);
}

void TrayItems::removeService(const QString &service)
{
    for (int row = m_items.size() - 1; row >= 0; --row) {
        if (m_items.at(row).service != service)
            continue;
        const QString name = m_items.at(row).service + m_items.at(row).path;
        beginRemoveRows({}, row, row);
        m_pixmaps.remove(m_items.at(row).key);
        m_items.removeAt(row);
        endRemoveRows();
        Q_EMIT countChanged();
        Q_EMIT StatusNotifierItemUnregistered(name);
    }
    gWatcher->removeWatchedService(service);
}

void TrayItems::onItemChanged()
{
    const QString key = message().service() + message().path();
    if (rowOf(key) >= 0)
        refresh(key);
}

void TrayItems::refresh(const QString &key)
{
    const int row = rowOf(key);
    if (row < 0)
        return;
    QDBusMessage msg = QDBusMessage::createMethodCall(m_items[row].service, m_items[row].path,
                                                      QStringLiteral("org.freedesktop.DBus.Properties"), QStringLiteral("GetAll"));
    msg << kItemIface;
    auto *w = new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(msg), this);
    connect(w, &QDBusPendingCallWatcher::finished, this, [this, key](QDBusPendingCallWatcher *w) {
        w->deleteLater();
        const QDBusMessage reply = w->reply();
        const int row = rowOf(key);
        if (row < 0 || reply.type() != QDBusMessage::ReplyMessage || reply.arguments().isEmpty())
            return;
        QVariantMap props;
        reply.arguments().first().value<QDBusArgument>() >> props;
        Item &i = m_items[row];
        i.id = props.value(QStringLiteral("Id")).toString();
        i.title = props.value(QStringLiteral("Title")).toString();
        i.status = props.value(QStringLiteral("Status")).toString();
        i.iconName = props.value(QStringLiteral("IconName")).toString();
        if (i.status == QLatin1String("NeedsAttention") && !props.value(QStringLiteral("AttentionIconName")).toString().isEmpty())
            i.iconName = props.value(QStringLiteral("AttentionIconName")).toString();
        i.iconThemePath = props.value(QStringLiteral("IconThemePath")).toString();
        i.itemIsMenu = props.value(QStringLiteral("ItemIsMenu")).toBool();
        i.menuPath = props.value(QStringLiteral("Menu")).value<QDBusObjectPath>().path();
        if (props.contains(QStringLiteral("ToolTip"))) {
            const QDBusArgument tip = props.value(QStringLiteral("ToolTip")).value<QDBusArgument>();
            QString iconName, title, text;
            tip.beginStructure();
            tip >> iconName;
            readPixmaps(tip);
            tip >> title >> text;
            tip.endStructure();
            i.toolTip = title.isEmpty() ? text : title;
        }
        if (props.contains(QStringLiteral("IconPixmap"))) {
            const QImage img = readPixmaps(props.value(QStringLiteral("IconPixmap")).value<QDBusArgument>());
            if (!img.isNull()) {
                m_pixmaps.insert(key, img);
                ++i.pixmapSerial;
            }
        }
        Q_EMIT dataChanged(index(row), index(row));
    });
}

int TrayItems::rowOf(const QString &key) const
{
    for (int i = 0; i < m_items.size(); ++i)
        if (m_items.at(i).key == key)
            return i;
    return -1;
}

int TrayItems::rowCount(const QModelIndex &parent) const
{
    return parent.isValid() ? 0 : m_items.size();
}

QVariant TrayItems::data(const QModelIndex &index, int role) const
{
    if (!index.isValid() || index.row() >= m_items.size())
        return {};
    const Item &i = m_items.at(index.row());
    switch (role) {
    case KeyRole: return i.key;
    case Qt::DisplayRole:
    case TitleRole: return i.title.isEmpty() ? i.id : i.title;
    case IconNameRole: return i.iconName;
    case IconUrlRole:
        // Prefer the themed icon; fall back to the pixmap the item sent.
        return !i.iconName.isEmpty() ? QStringLiteral("image://icon/") + i.iconName
               : m_pixmaps.contains(i.key) ? QStringLiteral("image://sni/%1/%2").arg(QString::fromLatin1(i.key.toUtf8().toHex())).arg(i.pixmapSerial)
                                           : QString();
    case StatusRole: return i.status;
    case ToolTipRole: return i.toolTip.isEmpty() ? (i.title.isEmpty() ? i.id : i.title) : i.toolTip;
    case HasMenuRole: return !i.menuPath.isEmpty() && i.menuPath != QLatin1String("/");
    }
    return {};
}

QHash<int, QByteArray> TrayItems::roleNames() const
{
    return {{KeyRole, "key"}, {TitleRole, "title"}, {IconNameRole, "iconName"}, {IconUrlRole, "iconUrl"},
            {StatusRole, "status"}, {ToolTipRole, "toolTip"}, {HasMenuRole, "hasMenu"}};
}

static void callItem(const QString &service, const QString &path, const QString &method, const QVariantList &args)
{
    QDBusMessage msg = QDBusMessage::createMethodCall(service, path, kItemIface, method);
    msg.setArguments(args);
    QDBusConnection::sessionBus().asyncCall(msg);
}

void TrayItems::activate(int row, int x, int y)
{
    if (row < 0 || row >= m_items.size())
        return;
    const Item &i = m_items.at(row);
    if (i.itemIsMenu && !i.menuPath.isEmpty()) {
        requestMenu(row);
        return;
    }
    callItem(i.service, i.path, QStringLiteral("Activate"), {x, y});
}

void TrayItems::secondaryActivate(int row, int x, int y)
{
    if (row >= 0 && row < m_items.size())
        callItem(m_items[row].service, m_items[row].path, QStringLiteral("SecondaryActivate"), {x, y});
}

void TrayItems::scroll(int row, int delta)
{
    if (row >= 0 && row < m_items.size())
        callItem(m_items[row].service, m_items[row].path, QStringLiteral("Scroll"), {delta, QStringLiteral("vertical")});
}

void TrayItems::contextMenu(int row, int x, int y)
{
    if (row >= 0 && row < m_items.size())
        callItem(m_items[row].service, m_items[row].path, QStringLiteral("ContextMenu"), {x, y});
}

void TrayItems::requestMenu(int row)
{
    if (row < 0 || row >= m_items.size() || m_items[row].menuPath.isEmpty())
        return;
    const Item i = m_items.at(row);
    QDBusMessage about = QDBusMessage::createMethodCall(i.service, i.menuPath, kMenuIface, QStringLiteral("AboutToShow"));
    about << 0;
    QDBusConnection::sessionBus().call(about, QDBus::Block, 500);
    QDBusMessage msg = QDBusMessage::createMethodCall(i.service, i.menuPath, kMenuIface, QStringLiteral("GetLayout"));
    msg << 0 << -1 << QStringList();
    auto *w = new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(msg), this);
    const QString key = i.key;
    connect(w, &QDBusPendingCallWatcher::finished, this, [this, key](QDBusPendingCallWatcher *w) {
        w->deleteLater();
        const QDBusMessage reply = w->reply();
        const int row = rowOf(key);
        if (row < 0 || reply.type() != QDBusMessage::ReplyMessage || reply.arguments().size() < 2)
            return;
        QVariantList items;
        readLayout(reply.arguments().at(1).value<QDBusArgument>(), items, 0);
        Q_EMIT menuReady(row, items);
    });
}

void TrayItems::triggerMenuItem(int row, int id)
{
    if (row < 0 || row >= m_items.size())
        return;
    const Item &i = m_items.at(row);
    QDBusMessage msg = QDBusMessage::createMethodCall(i.service, i.menuPath, kMenuIface, QStringLiteral("Event"));
    msg << id << QStringLiteral("clicked") << QVariant::fromValue(QDBusVariant(0)) << uint(0);
    QDBusConnection::sessionBus().asyncCall(msg);
}

QImage TrayImageProvider::requestImage(const QString &id, QSize *size, const QSize &requested)
try {
    const QString key = QString::fromUtf8(QByteArray::fromHex(id.section(QLatin1Char('/'), 0, 0).toLatin1()));
    QImage img = TrayItems::instance()->pixmap(key);
    if (!img.isNull() && requested.isValid())
        img = img.scaled(requested, Qt::KeepAspectRatio, Qt::SmoothTransformation);
    if (size)
        *size = img.size();
    return img;
} catch (...) {
    return providerFailed("TrayImageProvider", id, size);
}
