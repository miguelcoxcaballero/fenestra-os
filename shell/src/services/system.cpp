// SPDX-License-Identifier: GPL-3.0-or-later
#include "system.h"

#include "apps.h"

#include <KConfigGroup>
#include <KConfigWatcher>
#include <KDesktopFile>
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
#include <QStandardPaths>
#include <algorithm>
#include <QDebug>
#include <QTimer>
#include <QUuid>
#include <QProcess>
#include <QLocale>

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
namespace {
// Same rule as Strings.qml (Spanish by system locale); the row status is composed here.
QString wtr(const char *en, const char *es)
{
    return QLocale().name().startsWith(QLatin1String("es")) ? QString::fromUtf8(es) : QString::fromUtf8(en);
}
constexpr int kStatePrepare = 40, kStateActivated = 100, kStateDisconnected = 30, kStateFailed = 120;
constexpr int kReasonNoSecrets = 7, kReasonSupplicantFirst = 8, kReasonSupplicantLast = 11;
constexpr int kReasonUserRequested = 39, kReasonNewActivation = 60;

QString keyMgmtFor(const NetworkManager::AccessPoint::Ptr &ap, bool *enterprise)
{
    const int sec = int(ap->wpaFlags()) | int(ap->rsnFlags());
    *enterprise = sec & NetworkManager::AccessPoint::KeyMgmt8021x;
    if (*enterprise)
        return QStringLiteral("wpa-eap");
    if (sec & NetworkManager::AccessPoint::KeyMgmtPsk)
        return QStringLiteral("wpa-psk");      // WPA2 and WPA2/WPA3 transition
    if (sec & NetworkManager::AccessPoint::KeyMgmtSAE)
        return QStringLiteral("sae");          // WPA3-only: wpa-psk would be refused
    if (sec & (NetworkManager::AccessPoint::KeyMgmtOWE | NetworkManager::AccessPoint::KeyMgmtOWETM))
        return QStringLiteral("owe");
    if (ap->capabilities() & NetworkManager::AccessPoint::Privacy)
        return QStringLiteral("none");         // WEP
    return {};
}
} // namespace

SINGLETON(WifiNetworks)

WifiNetworks::WifiNetworks(QObject *parent)
    : QAbstractListModel(parent)
{
    m_rebuildTimer = new QTimer(this);
    m_rebuildTimer->setSingleShot(true);
    m_rebuildTimer->setInterval(80);   // a scan adds dozens of access points at once
    connect(m_rebuildTimer, &QTimer::timeout, this, &WifiNetworks::rebuild);
    auto *n = NetworkManager::notifier();
    connect(n, &NetworkManager::Notifier::wirelessEnabledChanged, this, [this] { Q_EMIT enabledChanged(); scheduleRebuild(); });
    connect(n, &NetworkManager::Notifier::wwanEnabledChanged, this, &WifiNetworks::enabledChanged);
    connect(n, &NetworkManager::Notifier::deviceAdded, this, [this](const QString &uni) { watchDevice(uni); Q_EMIT enabledChanged(); scheduleRebuild(); });
    connect(n, &NetworkManager::Notifier::deviceRemoved, this, [this] { Q_EMIT enabledChanged(); scheduleRebuild(); });
    connect(n, &NetworkManager::Notifier::activeConnectionsChanged, this, [this] { scheduleRebuild(); });
    auto *sn = NetworkManager::settingsNotifier();
    connect(sn, &NetworkManager::SettingsNotifier::connectionAdded, this, [this] { scheduleRebuild(); });
    connect(sn, &NetworkManager::SettingsNotifier::connectionRemoved, this, [this] { scheduleRebuild(); });
    for (const NetworkManager::Device::Ptr &d : NetworkManager::networkInterfaces())
        watchDevice(d->uni());
    rebuild();
}

void WifiNetworks::watchDevice(const QString &uni)
{
    auto w = NetworkManager::findNetworkInterface(uni).objectCast<NetworkManager::WirelessDevice>();
    if (!w)
        return;
    connect(w.data(), &NetworkManager::WirelessDevice::accessPointAppeared, this, [this, w](const QString &ap) {
        if (auto p = w->findAccessPoint(ap))
            connect(p.data(), &NetworkManager::AccessPoint::signalStrengthChanged, this, &WifiNetworks::scheduleRebuild,
                    Qt::UniqueConnection);
        scheduleRebuild();
    });
    connect(w.data(), &NetworkManager::WirelessDevice::accessPointDisappeared, this, &WifiNetworks::scheduleRebuild);
    connect(w.data(), &NetworkManager::WirelessDevice::activeAccessPointChanged, this, &WifiNetworks::scheduleRebuild);
    connect(w.data(), &NetworkManager::Device::stateChanged, this,
            [this, uni](NetworkManager::Device::State ns, NetworkManager::Device::State, NetworkManager::Device::StateChangeReason r) {
                onDeviceState(uni, int(ns), int(r));
            });
    for (const QString &apUni : w->accessPoints())
        if (auto p = w->findAccessPoint(apUni))
            connect(p.data(), &NetworkManager::AccessPoint::signalStrengthChanged, this, &WifiNetworks::scheduleRebuild,
                    Qt::UniqueConnection);
}

void WifiNetworks::scheduleRebuild()
{
    if (!m_rebuildTimer->isActive())
        m_rebuildTimer->start();
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
        if (!w || !NetworkManager::isWirelessEnabled())
            continue;
        const int state = int(d->state());
        const auto ac = d->activeConnection();
        const QString acUuid = ac ? ac->uuid() : QString();
        const QString activeAp = w->activeAccessPoint() ? w->activeAccessPoint()->uni() : QString();
        for (const QString &apUni : w->accessPoints()) {
            const NetworkManager::AccessPoint::Ptr ap = w->findAccessPoint(apUni);
            if (!ap || ap->ssid().isEmpty())
                continue;
            Net net;
            net.ssid = ap->ssid();
            net.apPath = ap->uni();
            net.devicePath = d->uni();
            net.signal = ap->signalStrength();
            net.keyMgmt = keyMgmtFor(ap, &net.enterprise);
            net.secured = !net.keyMgmt.isEmpty() && net.keyMgmt != QLatin1String("owe");
            QString uuid;
            qlonglong newest = -1;
            for (const NetworkManager::Connection::Ptr &c : connections) {
                const auto cs = c->settings();
                auto wifi = cs->setting(NetworkManager::Setting::Wireless).dynamicCast<NetworkManager::WirelessSetting>();
                if (!wifi || QString::fromUtf8(wifi->ssid()) != net.ssid)
                    continue;
                if (wifi->mode() != NetworkManager::WirelessSetting::Infrastructure)
                    continue;   // a hotspot profile with the same name is not this network
                const qlonglong ts = cs->timestamp().isValid() ? cs->timestamp().toSecsSinceEpoch() : 0;
                if (ts > newest) {   // several profiles for one SSID: the most recently used one
                    newest = ts;
                    net.connectionPath = c->path();
                    uuid = cs->uuid();
                }
            }
            const bool mine = (!acUuid.isEmpty() && acUuid == uuid) || ap->uni() == activeAp
                || (!m_attempt.ssid.isEmpty() && m_attempt.ssid == net.ssid && m_attempt.devicePath == d->uni());
            net.active = mine && state == kStateActivated && ac;
            net.connecting = mine && ((state >= kStatePrepare && state < kStateActivated)
                                      || (m_attempt.ssid == net.ssid && !m_attempt.uuid.isEmpty()));
            if (net.active)
                net.connecting = false;
            auto it = bySsid.find(net.ssid);
            if (it == bySsid.end() || net.active || net.connecting
                || (!it->active && !it->connecting && net.signal > it->signal))
                bySsid.insert(net.ssid, net);
        }
    }
    QList<Net> nets = bySsid.values();
    std::sort(nets.begin(), nets.end(), [](const Net &a, const Net &b) {
        const bool pa = a.active || a.connecting, pb = b.active || b.connecting;
        return pa != pb ? pa : a.signal != b.signal ? a.signal > b.signal : a.ssid < b.ssid;
    });

    // Update in place: delegates (and a password being typed) survive the update.
    const int oldCount = m_nets.size();
    for (int i = m_nets.size() - 1; i >= 0; --i) {
        const QString &ssid = m_nets.at(i).ssid;
        if (std::none_of(nets.cbegin(), nets.cend(), [&](const Net &n) { return n.ssid == ssid; })) {
            beginRemoveRows({}, i, i);
            m_nets.removeAt(i);
            endRemoveRows();
        }
    }
    for (int i = 0; i < nets.size(); ++i) {
        int j = -1;
        for (int k = i; k < m_nets.size(); ++k)
            if (m_nets.at(k).ssid == nets.at(i).ssid) {
                j = k;
                break;
            }
        if (j < 0) {
            beginInsertRows({}, i, i);
            m_nets.insert(i, nets.at(i));
            endInsertRows();
            continue;
        }
        if (j != i) {
            beginMoveRows({}, j, j, {}, i);
            m_nets.move(j, i);
            endMoveRows();
        }
        m_nets[i] = nets.at(i);
        Q_EMIT dataChanged(index(i), index(i));
    }
    if (oldCount != m_nets.size())
        Q_EMIT countChanged();
}

int WifiNetworks::rowCount(const QModelIndex &parent) const { return parent.isValid() ? 0 : m_nets.size(); }

QString WifiNetworks::statusOf(const Net &n) const
{
    if (n.active)
        return n.secured ? wtr("Connected, secured", "Conectado, protegida") : wtr("Connected", "Conectado");
    if (n.connecting)
        return m_attempt.ssid == n.ssid && m_attempt.withKey ? wtr("Verifying and connecting", "Comprobando y conectando")
                                                             : wtr("Connecting", "Conectando");
    if (m_errors.contains(n.ssid))
        return m_errors.value(n.ssid);
    return n.secured ? wtr("Secured", "Segura") : wtr("Open", "Abierta");
}

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
    case ConnectingRole: return n.connecting;
    case StatusRole: return statusOf(n);
    case ErrorRole: return m_errors.value(n.ssid);
    case EnterpriseRole: return n.enterprise;
    }
    return {};
}

QHash<int, QByteArray> WifiNetworks::roleNames() const
{
    return {{SsidRole, "ssid"}, {SignalRole, "signal"}, {SecuredRole, "secured"}, {ActiveRole, "active"}, {KnownRole, "known"},
            {ConnectingRole, "connecting"}, {StatusRole, "status"}, {ErrorRole, "error"}, {EnterpriseRole, "enterprise"}};
}

bool WifiNetworks::needsPassword(int row) const
{
    if (row < 0 || row >= m_nets.size())
        return false;
    const Net &n = m_nets.at(row);
    return n.secured && (n.connectionPath.isEmpty() || m_rejected.contains(n.ssid));
}

void WifiNetworks::connectTo(int row, const QString &password, const QString &identity)
{
    if (row < 0 || row >= m_nets.size())
        return;
    const Net n = m_nets.at(row);
    m_errors.remove(n.ssid);
    m_attempt = Attempt{n.ssid, {}, n.devicePath, false, !password.isEmpty(), false};

    auto watch = [this, ssid = n.ssid](const QDBusPendingCall &call) {
        auto *w = new QDBusPendingCallWatcher(call, this);
        connect(w, &QDBusPendingCallWatcher::finished, this, [this, ssid](QDBusPendingCallWatcher *w) {
            w->deleteLater();
            if (w->isError() && m_attempt.ssid == ssid) {
                qWarning() << "Wi-Fi: activation refused:" << w->error().message();
                finishAttempt(false, 0);
            }
        });
    };
    auto securitySettings = [&n, &password]() {
        QVariantMap sec{{QStringLiteral("key-mgmt"), n.keyMgmt}};
        if (n.keyMgmt == QLatin1String("none")) {
            sec.insert(QStringLiteral("wep-key0"), password);
            sec.insert(QStringLiteral("wep-key-flags"), 0u);
            const bool hex = (password.size() == 10 || password.size() == 26);
            sec.insert(QStringLiteral("wep-key-type"), (hex || password.size() == 5 || password.size() == 13) ? 1u : 2u);
        } else if (n.keyMgmt != QLatin1String("owe")) {
            sec.insert(QStringLiteral("psk"), password);
            sec.insert(QStringLiteral("psk-flags"), 0u);   // stored by NetworkManager (no secret agent needed)
        }
        return sec;
    };

    if (!n.connectionPath.isEmpty()) {
        auto c = NetworkManager::findConnection(n.connectionPath);
        m_attempt.uuid = c ? c->uuid() : QString();
        if (c && !password.isEmpty()) {
            // a saved network whose key was rejected: update that profile, never add a duplicate
            NMVariantMapMap map = c->settings()->toMap();
            if (n.enterprise) {
                // keep the saved EAP method, CA, domain...: only the user name and password change
                QVariantMap x = map.value(QStringLiteral("802-1x"));
                if (!identity.isEmpty())
                    x.insert(QStringLiteral("identity"), identity);
                x.insert(QStringLiteral("password"), password);
                x.insert(QStringLiteral("password-flags"), 0u);
                map.insert(QStringLiteral("802-1x"), x);
            } else {
                map.insert(QStringLiteral("802-11-wireless-security"), securitySettings());
            }
            auto *w = new QDBusPendingCallWatcher(c->update(map), this);
            connect(w, &QDBusPendingCallWatcher::finished, this, [this, n, watch](QDBusPendingCallWatcher *w) {
                w->deleteLater();
                if (w->isError()) {
                    finishAttempt(false, 0);
                    return;
                }
                m_rejected.remove(n.ssid);
                watch(NetworkManager::activateConnection(n.connectionPath, n.devicePath, n.apPath));
            });
        } else {
            watch(NetworkManager::activateConnection(n.connectionPath, n.devicePath, n.apPath));
        }
        scheduleRebuild();
        return;
    }
    // New network: our own uuid, so the attempt can be followed (and the profile removed if
    // it never connects: Windows keeps no profile for a network it could not join).
    const QString uuid = QUuid::createUuid().toString(QUuid::WithoutBraces);
    m_attempt.uuid = uuid;
    m_attempt.created = true;
    NMVariantMapMap settings;
    settings.insert(QStringLiteral("connection"), QVariantMap{{QStringLiteral("id"), n.ssid}, {QStringLiteral("uuid"), uuid},
                                                              {QStringLiteral("type"), QStringLiteral("802-11-wireless")},
                                                              {QStringLiteral("autoconnect"), true}});
    settings.insert(QStringLiteral("802-11-wireless"), QVariantMap{{QStringLiteral("ssid"), n.ssid.toUtf8()},
                                                                   {QStringLiteral("mode"), QStringLiteral("infrastructure")}});
    if (n.enterprise) {
        // Windows' first try: PEAP with MSCHAPv2 (what most universities and companies use, eduroam
        // included); every other setting is in Settings › Wi-Fi.
        settings.insert(QStringLiteral("802-11-wireless-security"), QVariantMap{{QStringLiteral("key-mgmt"), QStringLiteral("wpa-eap")}});
        settings.insert(QStringLiteral("802-1x"), QVariantMap{{QStringLiteral("eap"), QStringList{QStringLiteral("peap")}},
                                                              {QStringLiteral("phase2-auth"), QStringLiteral("mschapv2")},
                                                              {QStringLiteral("identity"), identity},
                                                              {QStringLiteral("password"), password},
                                                              {QStringLiteral("password-flags"), 0u}});
    } else if (!n.keyMgmt.isEmpty())
        settings.insert(QStringLiteral("802-11-wireless-security"), securitySettings());
    watch(NetworkManager::addAndActivateConnection(settings, n.devicePath, n.apPath));
    scheduleRebuild();
}

void WifiNetworks::onDeviceState(const QString &devicePath, int newState, int reason)
{
    if (!m_attempt.ssid.isEmpty() && m_attempt.devicePath == devicePath) {
        auto d = NetworkManager::findNetworkInterface(devicePath);
        const auto ac = d ? d->activeConnection() : NetworkManager::ActiveConnection::Ptr();
        const bool mine = ac && ac->uuid() == m_attempt.uuid;
        if (mine && newState >= kStatePrepare && newState <= kStateActivated)
            m_attempt.started = true;
        if (newState == kStateActivated && mine)
            finishAttempt(true, 0);
        else if (newState == kStateFailed && (mine || m_attempt.started))
            finishAttempt(false, reason);
        else if (m_attempt.started && !mine && newState == kStateDisconnected
                 && (reason == kReasonNewActivation || reason == kReasonUserRequested))
            m_attempt = Attempt{};   // replaced by another connection or cancelled
    }
    scheduleRebuild();
}

void WifiNetworks::finishAttempt(bool ok, int reason)
{
    const Attempt a = m_attempt;
    m_attempt = Attempt{};
    if (!ok) {
        if (a.created && !a.uuid.isEmpty())
            QTimer::singleShot(300, this, [uuid = a.uuid] {
                if (auto c = NetworkManager::findConnectionByUuid(uuid))
                    c->remove();
            });
        const bool keyProblem = reason == kReasonNoSecrets || (reason >= kReasonSupplicantFirst && reason <= kReasonSupplicantLast);
        bool secured = false;
        for (const Net &n : std::as_const(m_nets))
            if (n.ssid == a.ssid)
                secured = n.secured;
        if (keyProblem && secured) {
            bool enterprise = false;
            for (const Net &n : std::as_const(m_nets))
                if (n.ssid == a.ssid)
                    enterprise = n.enterprise;
            m_errors.insert(a.ssid, enterprise ? wtr("Can't connect. Check your user name and password, or the network's settings in Settings.",
                                                     "No se puede conectar. Revisa el usuario y la contraseña, o la configuración de la red en Configuración.")
                                               : wtr("The network security key isn't correct. Please try again.",
                                                     "La clave de seguridad de red no es correcta. Inténtalo de nuevo."));
            if (!a.created)
                m_rejected.insert(a.ssid);
            Q_EMIT keyRejected(a.ssid);
        } else {
            m_errors.insert(a.ssid, wtr("Can't connect to this network", "No se puede conectar a esta red"));
        }
    }
    scheduleRebuild();
}

void WifiNetworks::cancel(int row)
{
    if (row < 0 || row >= m_nets.size() || m_attempt.ssid != m_nets.at(row).ssid)
        return;
    const Attempt a = m_attempt;
    m_attempt = Attempt{};
    for (const NetworkManager::ActiveConnection::Ptr &ac : NetworkManager::activeConnections())
        if (ac->uuid() == a.uuid)
            NetworkManager::deactivateConnection(ac->path());
    if (a.created)
        QTimer::singleShot(300, this, [uuid = a.uuid] {
            if (auto c = NetworkManager::findConnectionByUuid(uuid))
                c->remove();
        });
    scheduleRebuild();
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
    // Started after the app that uses it: no change will come. Only if it is running (asking would start it).
    if (QDBusConnection::systemBus().interface()->isServiceRegistered(QStringLiteral("org.freedesktop.GeoClue2"))) {
        QDBusMessage get = QDBusMessage::createMethodCall(QStringLiteral("org.freedesktop.GeoClue2"), QStringLiteral("/org/freedesktop/GeoClue2/Manager"),
                                                          QStringLiteral("org.freedesktop.DBus.Properties"), QStringLiteral("Get"));
        get << QStringLiteral("org.freedesktop.GeoClue2.Manager") << QStringLiteral("InUse");
        auto *w = new QDBusPendingCallWatcher(QDBusConnection::systemBus().asyncCall(get), this);
        connect(w, &QDBusPendingCallWatcher::finished, this, [this](QDBusPendingCallWatcher *w) {
            QDBusPendingReply<QDBusVariant> reply = *w;
            w->deleteLater();
            if (reply.isValid())
                onGeoClue({}, {{QStringLiteral("InUse"), reply.value().variant()}}, {});
        });
    }
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
        refreshLocationApps();
        Q_EMIT changed();
    }
}

void Privacy::refreshLocationApps()
{
    QStringList apps;
    const QDir proc(QStringLiteral("/proc"));
    for (const QString &pid : proc.entryList(QDir::Dirs | QDir::NoDotAndDotDot)) {
        if (!pid.at(0).isDigit())
            continue;
        QFile maps(proc.filePath(pid + QStringLiteral("/maps")));
        if (!maps.open(QIODevice::ReadOnly))
            continue;
        const QByteArray all = maps.readAll();
        if (!all.contains("libgeoclue") && !all.contains("qtposition_geoclue"))
            continue;
        QFile commFile(proc.filePath(pid + QStringLiteral("/comm")));
        if (!commFile.open(QIODevice::ReadOnly))
            continue;
        const QString comm = QString::fromUtf8(commFile.readAll().trimmed());
        if (comm.startsWith(QLatin1String("xdg-desktop-por"))) // on behalf of an app that isn't named
            continue;
        QString name = comm;
        for (const QString &dir : QStandardPaths::standardLocations(QStandardPaths::ApplicationsLocation)) {
            const QStringList files = QDir(dir).entryList({QLatin1Char('*') + comm + QStringLiteral("*.desktop")}, QDir::Files);
            if (!files.isEmpty()) {
                name = KDesktopFile(dir + QLatin1Char('/') + files.first()).readName();
                break;
            }
        }
        if (!apps.contains(name))
            apps << name;
    }
    if (apps != m_locationApps) {
        m_locationApps = apps;
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
