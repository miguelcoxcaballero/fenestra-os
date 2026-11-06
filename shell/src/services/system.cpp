// SPDX-License-Identifier: GPL-3.0-or-later
#include "system.h"

#include "apps.h"

#include <KConfigGroup>
#include <KConfigWatcher>
#include <KSharedConfig>
#include <NetworkManagerQt/AccessPoint>
#include <NetworkManagerQt/ActiveConnection>
#include <NetworkManagerQt/Connection>
#include <NetworkManagerQt/Manager>
#include <NetworkManagerQt/Settings>
#include <NetworkManagerQt/WirelessDevice>
#include <NetworkManagerQt/WirelessSetting>
#include <PulseAudioQt/Client>
#include <PulseAudioQt/Context>
#include <PulseAudioQt/SourceOutput>
#include <QDBusArgument>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusMessage>
#include <QDBusMetaType>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusReply>
#include <QDir>
#include <QFile>

#define SINGLETON(Class)                                                                                               \
    Class *Class::instance()                                                                                           \
    {                                                                                                                  \
        static auto *i = new Class;                                                                                    \
        return i;                                                                                                      \
    }                                                                                                                  \
    Class *Class::create(QQmlEngine *, QJSEngine *)                                                                    \
    {                                                                                                                  \
        QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);                                          \
        return instance();                                                                                             \
    }

namespace
{
const QString kProps = QStringLiteral("org.freedesktop.DBus.Properties");
QVariantMap demarshal(const QVariant &v)
{
    if (v.canConvert<QDBusArgument>())
        return qdbus_cast<QVariantMap>(v.value<QDBusArgument>());
    return v.toMap();
}
}

// ---- Media (MPRIS) ---------------------------------------------------------------------------
SINGLETON(Media)

namespace
{
const QString kMprisPath = QStringLiteral("/org/mpris/MediaPlayer2");
const QString kMprisRoot = QStringLiteral("org.mpris.MediaPlayer2");
const QString kMprisPlayer = QStringLiteral("org.mpris.MediaPlayer2.Player");
}

Media::Media(QObject *parent)
    : QObject(parent)
{
    auto bus = QDBusConnection::sessionBus();
    bus.connect(QStringLiteral("org.freedesktop.DBus"), QStringLiteral("/org/freedesktop/DBus"), QStringLiteral("org.freedesktop.DBus"),
                QStringLiteral("NameOwnerChanged"), this, SLOT(onNameOwnerChanged(QString, QString, QString)));
    const QStringList names = bus.interface()->registeredServiceNames().value();
    for (const QString &n : names)
        if (n.startsWith(kMprisRoot + QLatin1Char('.')))
            addPlayer(n);
}

void Media::onNameOwnerChanged(const QString &name, const QString &oldOwner, const QString &newOwner)
{
    if (!name.startsWith(kMprisRoot + QLatin1Char('.')))
        return;
    if (!oldOwner.isEmpty()) {
        m_players.remove(oldOwner);
        m_order.removeAll(oldOwner);
        pick();
    }
    if (!newOwner.isEmpty())
        addPlayer(name);
}

void Media::addPlayer(const QString &service)
{
    auto bus = QDBusConnection::sessionBus();
    const QString owner = bus.interface()->serviceOwner(service).value();
    if (owner.isEmpty())
        return;
    m_players.insert(owner, {service, owner, {}, {}});
    bus.connect(owner, kMprisPath, kProps, QStringLiteral("PropertiesChanged"), this,
                SLOT(onPropertiesChanged(QString, QVariantMap, QStringList)));
    for (const QString &iface : {kMprisRoot, kMprisPlayer}) {
        QDBusMessage msg = QDBusMessage::createMethodCall(owner, kMprisPath, kProps, QStringLiteral("GetAll"));
        msg << iface;
        auto *w = new QDBusPendingCallWatcher(bus.asyncCall(msg), this);
        connect(w, &QDBusPendingCallWatcher::finished, this, [this, owner, iface](QDBusPendingCallWatcher *w) {
            w->deleteLater();
            QDBusPendingReply<QVariantMap> r = *w;
            if (!r.isValid() || !m_players.contains(owner))
                return;
            (iface == kMprisRoot ? m_players[owner].root : m_players[owner].player) = r.value();
            pick();
        });
    }
}

void Media::onPropertiesChanged(const QString &interface, const QVariantMap &props, const QStringList &)
{
    const QString owner = message().service();
    if (!m_players.contains(owner))
        return;
    QVariantMap &target = interface == kMprisRoot ? m_players[owner].root : m_players[owner].player;
    for (auto it = props.begin(); it != props.end(); ++it)
        target.insert(it.key(), it.value());
    pick();
}

void Media::pick()
{
    QString chosen;
    for (const Player &p : std::as_const(m_players)) {
        if (p.player.value(QStringLiteral("PlaybackStatus")).toString() == QLatin1String("Playing")) {
            chosen = p.owner;
            m_order.removeAll(p.owner);
            m_order.append(p.owner);
            break;
        }
    }
    // Nothing playing: keep the card for the player that played last (paused), like the reference.
    if (chosen.isEmpty())
        for (int i = m_order.size() - 1; i >= 0 && chosen.isEmpty(); --i)
            if (m_players.contains(m_order.at(i)))
                chosen = m_order.at(i);
    m_current = chosen;
    Q_EMIT changed();
}

bool Media::playing() const
{
    return m_players.value(m_current).player.value(QStringLiteral("PlaybackStatus")).toString() == QLatin1String("Playing");
}

QString Media::appName() const
{
    return m_players.value(m_current).root.value(QStringLiteral("Identity")).toString();
}

QString Media::appIcon() const
{
    const QString entry = m_players.value(m_current).root.value(QStringLiteral("DesktopEntry")).toString();
    if (const KService::Ptr s = Apps::instance()->service(entry))
        return s->icon();
    return entry.isEmpty() ? QStringLiteral("audio-x-generic") : entry;
}

QString Media::title() const
{
    return demarshal(m_players.value(m_current).player.value(QStringLiteral("Metadata"))).value(QStringLiteral("xesam:title")).toString();
}

QString Media::artist() const
{
    return demarshal(m_players.value(m_current).player.value(QStringLiteral("Metadata"))).value(QStringLiteral("xesam:artist")).toStringList().join(QStringLiteral(", "));
}

QString Media::artUrl() const
{
    return demarshal(m_players.value(m_current).player.value(QStringLiteral("Metadata"))).value(QStringLiteral("mpris:artUrl")).toString();
}

bool Media::canGoPrevious() const { return m_players.value(m_current).player.value(QStringLiteral("CanGoPrevious")).toBool(); }
bool Media::canGoNext() const { return m_players.value(m_current).player.value(QStringLiteral("CanGoNext")).toBool(); }

void Media::call(const QString &method)
{
    if (m_current.isEmpty())
        return;
    QDBusConnection::sessionBus().asyncCall(QDBusMessage::createMethodCall(m_current, kMprisPath, kMprisPlayer, method));
}

void Media::playPause() { call(QStringLiteral("PlayPause")); }
void Media::previous() { call(QStringLiteral("Previous")); }
void Media::next() { call(QStringLiteral("Next")); }

// ---- Brightness (sysfs read, logind write) ---------------------------------------------------
SINGLETON(Brightness)

Brightness::Brightness(QObject *parent)
    : QObject(parent)
{
    // Like GNOME: firmware (ACPI) before platform before raw devices.
    QDir dir(QStringLiteral("/sys/class/backlight"));
    QString best;
    int bestRank = 99;
    for (const QString &name : dir.entryList(QDir::Dirs | QDir::NoDotAndDotDot | QDir::System)) {
        QFile type(dir.filePath(name + QStringLiteral("/type")));
        if (!type.open(QIODevice::ReadOnly))
            continue;
        const QByteArray t = type.readAll().trimmed();
        const int rank = t == "firmware" ? 0 : t == "platform" ? 1 : 2;
        if (rank < bestRank) {
            bestRank = rank;
            best = name;
        }
    }
    m_device = best;
    auto read = [&](const char *file) {
        QFile f(dir.filePath(best + QLatin1Char('/') + QLatin1String(file)));
        return f.open(QIODevice::ReadOnly) ? f.readAll().trimmed().toInt() : 0;
    };
    if (!best.isEmpty()) {
        m_max = read("max_brightness");
        m_value = read("brightness");
    }
}

int Brightness::percent() const
{
    return m_max > 0 ? qRound(100.0 * m_value / m_max) : 0;
}

void Brightness::setPercent(int percent)
{
    if (!available())
        return;
    // Never fully dark from the slider (1 % minimum), as GNOME.
    const int value = std::clamp(qRound(m_max * std::clamp(percent, 1, 100) / 100.0), 1, m_max);
    if (value == m_value)
        return;
    m_value = value;
    QDBusMessage msg = QDBusMessage::createMethodCall(QStringLiteral("org.freedesktop.login1"), QStringLiteral("/org/freedesktop/login1/session/auto"),
                                                      QStringLiteral("org.freedesktop.login1.Session"), QStringLiteral("SetBrightness"));
    msg << QStringLiteral("backlight") << m_device << uint(value);
    QDBusConnection::systemBus().asyncCall(msg);
    Q_EMIT changed();
}

void Brightness::step(int delta)
{
    setPercent(percent() + delta);
}

// ---- Power profiles --------------------------------------------------------------------------
SINGLETON(PowerProfiles)

PowerProfiles::PowerProfiles(QObject *parent)
    : QObject(parent)
{
    // Newer name first (power-profiles-daemon ≥ 0.20, tuned-ppd), then the original one.
    auto *iface = QDBusConnection::systemBus().interface();
    if (iface && iface->isServiceRegistered(QStringLiteral("org.freedesktop.UPower.PowerProfiles"))) {
        m_service = QStringLiteral("org.freedesktop.UPower.PowerProfiles");
        m_path = QStringLiteral("/org/freedesktop/UPower/PowerProfiles");
        m_iface = QStringLiteral("org.freedesktop.UPower.PowerProfiles");
    } else {
        m_service = QStringLiteral("net.hadess.PowerProfiles");
        m_path = QStringLiteral("/net/hadess/PowerProfiles");
        m_iface = QStringLiteral("net.hadess.PowerProfiles");
    }
    QDBusConnection::systemBus().connect(m_service, m_path, kProps, QStringLiteral("PropertiesChanged"), this,
                                         SLOT(onPropertiesChanged(QString, QVariantMap, QStringList)));
    load();
}

void PowerProfiles::load()
{
    QDBusMessage msg = QDBusMessage::createMethodCall(m_service, m_path, kProps, QStringLiteral("GetAll"));
    msg << m_iface;
    auto *w = new QDBusPendingCallWatcher(QDBusConnection::systemBus().asyncCall(msg), this);
    connect(w, &QDBusPendingCallWatcher::finished, this, [this](QDBusPendingCallWatcher *w) {
        w->deleteLater();
        QDBusPendingReply<QVariantMap> r = *w;
        if (r.isValid())
            onPropertiesChanged(m_iface, r.value(), {});
    });
}

void PowerProfiles::onPropertiesChanged(const QString &interface, const QVariantMap &props, const QStringList &)
{
    if (interface != m_iface)
        return;
    if (props.contains(QStringLiteral("ActiveProfile")))
        m_active = props.value(QStringLiteral("ActiveProfile")).toString();
    if (props.contains(QStringLiteral("Profiles"))) {
        m_profiles.clear();
        const QDBusArgument arg = props.value(QStringLiteral("Profiles")).value<QDBusArgument>();
        arg.beginArray();
        while (!arg.atEnd()) {
            QVariantMap p;
            arg >> p;
            m_profiles << p.value(QStringLiteral("Profile")).toString();
        }
        arg.endArray();
    }
    Q_EMIT changed();
}

void PowerProfiles::setActive(const QString &profile)
{
    if (!m_profiles.contains(profile))
        return;
    QDBusMessage msg = QDBusMessage::createMethodCall(m_service, m_path, kProps, QStringLiteral("Set"));
    msg << m_iface << QStringLiteral("ActiveProfile") << QVariant::fromValue(QDBusVariant(profile));
    QDBusConnection::systemBus().asyncCall(msg);
}

// ---- Wi-Fi (NetworkManagerQt) ----------------------------------------------------------------
SINGLETON(WifiNetworks)

WifiNetworks::WifiNetworks(QObject *parent)
    : QAbstractListModel(parent)
{
    auto *n = NetworkManager::notifier();
    connect(n, &NetworkManager::Notifier::wirelessEnabledChanged, this, [this] { Q_EMIT enabledChanged(); rebuild(); });
    connect(n, &NetworkManager::Notifier::wwanEnabledChanged, this, &WifiNetworks::enabledChanged);
    connect(n, &NetworkManager::Notifier::deviceAdded, this, [this] { rebuild(); });
    connect(n, &NetworkManager::Notifier::deviceRemoved, this, [this] { rebuild(); });
    connect(n, &NetworkManager::Notifier::activeConnectionsChanged, this, [this] { rebuild(); });
    for (const NetworkManager::Device::Ptr &d : NetworkManager::networkInterfaces()) {
        if (auto w = d.objectCast<NetworkManager::WirelessDevice>()) {
            connect(w.data(), &NetworkManager::WirelessDevice::accessPointAppeared, this, [this] { rebuild(); });
            connect(w.data(), &NetworkManager::WirelessDevice::accessPointDisappeared, this, [this] { rebuild(); });
        }
    }
    rebuild();
}

bool WifiNetworks::hasWifi() const
{
    for (const NetworkManager::Device::Ptr &d : NetworkManager::networkInterfaces())
        if (d->type() == NetworkManager::Device::Wifi)
            return true;
    return false;
}

bool WifiNetworks::enabled() const { return NetworkManager::isWirelessEnabled(); }
void WifiNetworks::setEnabled(bool on) { NetworkManager::setWirelessEnabled(on); }
bool WifiNetworks::airplaneMode() const
{
    // Without NetworkManager both read "off": that is not airplane mode.
    const auto *bus = QDBusConnection::systemBus().interface();
    if (!bus || !bus->isServiceRegistered(QStringLiteral("org.freedesktop.NetworkManager")))
        return false;
    return !NetworkManager::isWirelessEnabled() && !NetworkManager::isWwanEnabled();
}

void WifiNetworks::setAirplaneMode(bool on)
{
    // Wi-Fi and mobile broadband; Bluetooth is switched by the quick settings tile (BlueZ).
    NetworkManager::setWirelessEnabled(!on);
    NetworkManager::setWwanEnabled(!on);
}

void WifiNetworks::scan()
{
    for (const NetworkManager::Device::Ptr &d : NetworkManager::networkInterfaces())
        if (auto w = d.objectCast<NetworkManager::WirelessDevice>())
            w->requestScan();
}

void WifiNetworks::rebuild()
{
    QHash<QString, Net> bySsid;
    const auto connections = NetworkManager::listConnections();
    for (const NetworkManager::Device::Ptr &d : NetworkManager::networkInterfaces()) {
        auto w = d.objectCast<NetworkManager::WirelessDevice>();
        if (!w)
            continue;
        const QString activeAp = w->activeAccessPoint() ? w->activeAccessPoint()->uni() : QString();
        for (const QString &apUni : w->accessPoints()) {
            const NetworkManager::AccessPoint::Ptr ap = w->findAccessPoint(apUni);
            if (!ap || ap->ssid().isEmpty())
                continue;
            Net net{ap->ssid(), ap->uni(), d->uni(), {}, ap->signalStrength(),
                    ap->capabilities() != NetworkManager::AccessPoint::None || ap->wpaFlags() || ap->rsnFlags(), ap->uni() == activeAp};
            for (const NetworkManager::Connection::Ptr &c : connections) {
                auto wifi = c->settings()->setting(NetworkManager::Setting::Wireless).dynamicCast<NetworkManager::WirelessSetting>();
                if (wifi && QString::fromUtf8(wifi->ssid()) == net.ssid)
                    net.connectionPath = c->path();
            }
            auto it = bySsid.find(net.ssid);
            if (it == bySsid.end() || net.active || (!it->active && net.signal > it->signal))
                bySsid.insert(net.ssid, net);
        }
    }
    QList<Net> nets = bySsid.values();
    std::sort(nets.begin(), nets.end(), [](const Net &a, const Net &b) { return a.active != b.active ? a.active : a.signal > b.signal; });
    beginResetModel();
    m_nets = nets;
    endResetModel();
}

int WifiNetworks::rowCount(const QModelIndex &parent) const { return parent.isValid() ? 0 : m_nets.size(); }

QVariant WifiNetworks::data(const QModelIndex &index, int role) const
{
    if (!index.isValid() || index.row() >= m_nets.size())
        return {};
    const Net &n = m_nets.at(index.row());
    switch (role) {
    case Qt::DisplayRole:
    case SsidRole: return n.ssid;
    case SignalRole: return n.signal;
    case SecuredRole: return n.secured;
    case ActiveRole: return n.active;
    case KnownRole: return !n.connectionPath.isEmpty();
    }
    return {};
}

QHash<int, QByteArray> WifiNetworks::roleNames() const
{
    return {{SsidRole, "ssid"}, {SignalRole, "signal"}, {SecuredRole, "secured"}, {ActiveRole, "active"}, {KnownRole, "known"}};
}

bool WifiNetworks::needsPassword(int row) const
{
    return row >= 0 && row < m_nets.size() && m_nets.at(row).secured && m_nets.at(row).connectionPath.isEmpty();
}

void WifiNetworks::connectTo(int row, const QString &password)
{
    if (row < 0 || row >= m_nets.size())
        return;
    const Net &n = m_nets.at(row);
    if (!n.connectionPath.isEmpty()) {
        NetworkManager::activateConnection(n.connectionPath, n.devicePath, n.apPath);
        return;
    }
    // New network: NetworkManager fills in the rest from the access point; the key is stored
    // for this user (agent-owned secrets would need a secret agent; system-owned is NM's default).
    NMVariantMapMap settings;
    if (n.secured)
        settings.insert(QStringLiteral("802-11-wireless-security"),
                        QVariantMap{{QStringLiteral("key-mgmt"), QStringLiteral("wpa-psk")}, {QStringLiteral("psk"), password}});
    NetworkManager::addAndActivateConnection(settings, n.devicePath, n.apPath);
}

void WifiNetworks::disconnectFrom(int row)
{
    if (row < 0 || row >= m_nets.size())
        return;
    for (const NetworkManager::ActiveConnection::Ptr &a : NetworkManager::activeConnections())
        if (a->devices().contains(m_nets.at(row).devicePath))
            NetworkManager::deactivateConnection(a->path());
}

// ---- Privacy ---------------------------------------------------------------------------------
SINGLETON(Privacy)

Privacy::Privacy(QObject *parent)
    : QObject(parent)
{
    auto *ctx = PulseAudioQt::Context::instance();
    connect(ctx, &PulseAudioQt::Context::sourceOutputAdded, this, &Privacy::updateMic);
    connect(ctx, &PulseAudioQt::Context::sourceOutputRemoved, this, &Privacy::updateMic);
    updateMic();
    QDBusConnection::systemBus().connect(QStringLiteral("org.freedesktop.GeoClue2"), QStringLiteral("/org/freedesktop/GeoClue2/Manager"), kProps,
                                         QStringLiteral("PropertiesChanged"), this, SLOT(onGeoClue(QString, QVariantMap, QStringList)));
}

void Privacy::updateMic()
{
    // Volume controls only monitor levels: not "using the microphone" (privacyIcons.js).
    static const QStringList ignored{QStringLiteral("org.gnome.VolumeControl"), QStringLiteral("org.PulseAudio.pavucontrol"),
                                     QStringLiteral("org.gnome.Settings"), QStringLiteral("fenestra-settings")};
    QStringList apps;
    for (PulseAudioQt::SourceOutput *o : PulseAudioQt::Context::instance()->sourceOutputs()) {
        const QString id = o->properties().value(QStringLiteral("application.id")).toString();
        if (ignored.contains(id))
            continue;
        const QString name = o->client() ? o->client()->name() : o->name();
        if (!apps.contains(name))
            apps << name;
    }
    if (apps != m_mic) {
        m_mic = apps;
        Q_EMIT changed();
    }
}

void Privacy::onGeoClue(const QString &, const QVariantMap &props, const QStringList &)
{
    if (props.contains(QStringLiteral("InUse"))) {
        m_location = props.value(QStringLiteral("InUse")).toBool();
        Q_EMIT changed();
    }
}

// ---- Night light -----------------------------------------------------------------------------
SINGLETON(NightLight)

NightLight::NightLight(QObject *parent)
    : QObject(parent)
{
    auto watcher = KConfigWatcher::create(KSharedConfig::openConfig(QStringLiteral("kwinrc")));
    connect(watcher.data(), &KConfigWatcher::configChanged, this, [this](const KConfigGroup &group) {
        if (group.name() == QLatin1String("NightColor"))
            Q_EMIT changed();
    });
    // The watcher lives as long as the shell (this singleton is never destroyed).
    static KConfigWatcher::Ptr keep;
    keep = watcher;
}

bool NightLight::active() const
{
    auto cfg = KSharedConfig::openConfig(QStringLiteral("kwinrc"));
    cfg->reparseConfiguration();
    return cfg->group(QStringLiteral("NightColor")).readEntry("Active", false);
}

void NightLight::setActive(bool on)
{
    auto cfg = KSharedConfig::openConfig(QStringLiteral("kwinrc"));
    cfg->group(QStringLiteral("NightColor")).writeEntry("Active", on, KConfig::Notify);
    cfg->sync();
    QDBusConnection::sessionBus().asyncCall(QDBusMessage::createMethodCall(QStringLiteral("org.kde.KWin"), QStringLiteral("/KWin"),
                                                                           QStringLiteral("org.kde.KWin"), QStringLiteral("reconfigure")));
    Q_EMIT changed();
}
