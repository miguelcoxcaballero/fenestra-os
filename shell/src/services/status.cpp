// SPDX-License-Identifier: GPL-3.0-or-later
#include "status.h"

#include <NetworkManagerQt/AccessPoint>
#include <NetworkManagerQt/ActiveConnection>
#include <NetworkManagerQt/Manager>
#include <NetworkManagerQt/WirelessDevice>
#include <PulseAudioQt/Context>
#include <PulseAudioQt/Server>
#include <PulseAudioQt/Sink>
#include <QDBusArgument>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusInterface>
#include <QDBusMetaType>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusReply>
#include <QDBusServiceWatcher>

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

// ---- Network (NetworkManagerQt) ------------------------------------------------------------
SINGLETON(NetworkStatus)

NetworkStatus::NetworkStatus(QObject *parent)
    : QObject(parent)
{
    auto *n = NetworkManager::notifier();
    connect(n, &NetworkManager::Notifier::primaryConnectionChanged, this, [this] { update(); });
    connect(n, &NetworkManager::Notifier::connectivityChanged, this, [this] { update(); });
    connect(n, &NetworkManager::Notifier::statusChanged, this, [this] { update(); });
    connect(n, &NetworkManager::Notifier::wirelessEnabledChanged, this, [this] { update(); });
    connect(n, &NetworkManager::Notifier::serviceAppeared, this, [this] { update(); });
    connect(n, &NetworkManager::Notifier::serviceDisappeared, this, [this] { update(); });
    update();
}

void NetworkStatus::update()
{
    const bool running = QDBusConnection::systemBus().interface()
        && QDBusConnection::systemBus().interface()->isServiceRegistered(QStringLiteral("org.freedesktop.NetworkManager"));
    QString kind = QStringLiteral("unavailable"), name;
    bool connected = false, limited = false;
    if (running) {
        const NetworkManager::ActiveConnection::Ptr primary = NetworkManager::primaryConnection();
        if (primary && primary->state() == NetworkManager::ActiveConnection::Activated) {
            connected = true;
            name = primary->id();
            switch (primary->type()) {
            case NetworkManager::ConnectionSettings::Wireless: kind = QStringLiteral("wifi"); break;
            case NetworkManager::ConnectionSettings::Vpn:
            case NetworkManager::ConnectionSettings::WireGuard: kind = QStringLiteral("vpn"); break;
            default: kind = QStringLiteral("ethernet"); break;
            }
            limited = NetworkManager::connectivity() != NetworkManager::Full && NetworkManager::connectivity() != NetworkManager::UnknownConnectivity;
        } else {
            kind = NetworkManager::isWirelessEnabled() ? QStringLiteral("none") : QStringLiteral("disabled");
        }
    }
    const bool same = kind == m_kind && name == m_name && connected == m_connected && limited == m_limited;
    m_kind = kind;
    m_name = name;
    m_connected = connected;
    m_limited = limited;
    watchAccessPoint();
    if (!same)
        Q_EMIT changed();
}

void NetworkStatus::watchAccessPoint()
{
    disconnect(m_apConnection);
    if (m_kind != QLatin1String("wifi"))
        return;
    const NetworkManager::ActiveConnection::Ptr primary = NetworkManager::primaryConnection();
    for (const QString &uni : primary ? primary->devices() : QStringList()) {
        auto wifi = NetworkManager::findNetworkInterface(uni).objectCast<NetworkManager::WirelessDevice>();
        if (!wifi || !wifi->activeAccessPoint())
            continue;
        NetworkManager::AccessPoint::Ptr ap = wifi->activeAccessPoint();
        m_signal = ap->signalStrength();
        m_name = ap->ssid();
        m_apConnection = connect(ap.data(), &NetworkManager::AccessPoint::signalStrengthChanged, this, [this](int s) {
            // Signal strength moves by a few points all the time: only a change of bars matters.
            const int before = m_signal / 25;
            m_signal = s;
            if (s / 25 != before)
                Q_EMIT changed();
        });
        return;
    }
}

QString NetworkStatus::iconName() const
{
    // Fenestra's own glyphs (assets/generated/status, installed in the Fenestra icon theme).
    if (m_kind == QLatin1String("wifi")) {
        if (m_limited)
            return QStringLiteral("network-wireless-no-route-symbolic");
        const char *levels[] = {"none", "weak", "ok", "good", "excellent"};
        return QStringLiteral("network-wireless-signal-%1-symbolic").arg(QLatin1String(levels[std::clamp(m_signal / 20, 0, 4)]));
    }
    if (m_kind == QLatin1String("ethernet"))
        return m_limited ? QStringLiteral("network-wired-no-route-symbolic") : QStringLiteral("network-wired-symbolic");
    if (m_kind == QLatin1String("vpn"))
        return QStringLiteral("network-vpn-symbolic");
    if (m_kind == QLatin1String("disabled"))
        return QStringLiteral("network-wireless-disabled-symbolic");
    if (m_kind == QLatin1String("none"))
        return QStringLiteral("network-wireless-offline-symbolic");
    return {};
}

// ---- Audio (PulseAudioQt, also with PipeWire's pulse server) ---------------------------------
SINGLETON(AudioStatus)

AudioStatus::AudioStatus(QObject *parent)
    : QObject(parent)
{
    auto *server = PulseAudioQt::Context::instance()->server();
    connect(server, &PulseAudioQt::Server::defaultSinkChanged, this, &AudioStatus::setSink);
    setSink(server->defaultSink());
}

void AudioStatus::setSink(PulseAudioQt::Sink *sink)
{
    if (m_sink)
        disconnect(m_sink, nullptr, this, nullptr);
    m_sink = sink;
    if (sink) {
        connect(sink, &PulseAudioQt::Sink::volumeChanged, this, &AudioStatus::changed);
        connect(sink, &PulseAudioQt::Sink::mutedChanged, this, &AudioStatus::changed);
        connect(sink, &PulseAudioQt::Sink::descriptionChanged, this, &AudioStatus::changed);
    }
    Q_EMIT changed();
}

int AudioStatus::volume() const
{
    return m_sink ? qRound(100.0 * m_sink->volume() / PulseAudioQt::normalVolume()) : 0;
}

bool AudioStatus::muted() const
{
    return m_sink && m_sink->isMuted();
}

QString AudioStatus::outputName() const
{
    return m_sink ? m_sink->description() : QString();
}

void AudioStatus::setVolume(int percent)
{
    if (m_sink)
        m_sink->setVolume(qint64(std::clamp(percent, 0, 150)) * PulseAudioQt::normalVolume() / 100);
}

void AudioStatus::setMuted(bool muted)
{
    if (m_sink)
        m_sink->setMuted(muted);
}

QString AudioStatus::iconName() const
{
    if (!m_sink)
        return {};
    const int v = volume();
    if (muted() || v == 0)
        return QStringLiteral("audio-volume-muted-symbolic");
    return v < 34 ? QStringLiteral("audio-volume-low-symbolic") : v < 67 ? QStringLiteral("audio-volume-medium-symbolic")
                                                                         : QStringLiteral("audio-volume-high-symbolic");
}

// ---- Battery (UPower display device) ---------------------------------------------------------
SINGLETON(PowerStatus)

namespace
{
const QString kUPower = QStringLiteral("org.freedesktop.UPower");
const QString kDisplayDevice = QStringLiteral("/org/freedesktop/UPower/devices/DisplayDevice");
const QString kDeviceIface = QStringLiteral("org.freedesktop.UPower.Device");
}

PowerStatus::PowerStatus(QObject *parent)
    : QObject(parent)
{
    QDBusConnection::systemBus().connect(kUPower, kDisplayDevice, QStringLiteral("org.freedesktop.DBus.Properties"),
                                         QStringLiteral("PropertiesChanged"), this,
                                         SLOT(onPropertiesChanged(QString, QVariantMap, QStringList)));
    auto *watcher = new QDBusServiceWatcher(kUPower, QDBusConnection::systemBus(), QDBusServiceWatcher::WatchForRegistration, this);
    connect(watcher, &QDBusServiceWatcher::serviceRegistered, this, &PowerStatus::load);
    load();
}

void PowerStatus::load()
{
    QDBusMessage msg = QDBusMessage::createMethodCall(kUPower, kDisplayDevice, QStringLiteral("org.freedesktop.DBus.Properties"),
                                                      QStringLiteral("GetAll"));
    msg << kDeviceIface;
    auto *w = new QDBusPendingCallWatcher(QDBusConnection::systemBus().asyncCall(msg), this);
    connect(w, &QDBusPendingCallWatcher::finished, this, [this](QDBusPendingCallWatcher *w) {
        QDBusPendingReply<QVariantMap> reply = *w;
        w->deleteLater();
        if (reply.isValid())
            onPropertiesChanged(kDeviceIface, reply.value(), {});
    });
}

void PowerStatus::onPropertiesChanged(const QString &interface, const QVariantMap &props, const QStringList &)
{
    if (interface != kDeviceIface)
        return;
    // Type 2 = battery. The display device aggregates all batteries.
    if (props.contains(QStringLiteral("IsPresent")) || props.contains(QStringLiteral("Type")))
        m_present = props.value(QStringLiteral("IsPresent"), m_present).toBool()
            && props.value(QStringLiteral("Type"), 2).toUInt() == 2;
    if (props.contains(QStringLiteral("Percentage")))
        m_percentage = qRound(props.value(QStringLiteral("Percentage")).toDouble());
    if (props.contains(QStringLiteral("State")))
        m_state = props.value(QStringLiteral("State")).toUInt();
    if (props.contains(QStringLiteral("TimeToEmpty")))
        m_toEmpty = props.value(QStringLiteral("TimeToEmpty")).toLongLong();
    if (props.contains(QStringLiteral("TimeToFull")))
        m_toFull = props.value(QStringLiteral("TimeToFull")).toLongLong();
    Q_EMIT changed();
}

QString PowerStatus::iconSource() const
{
    if (!m_present)
        return {};
    // assets/generated/battery: {normal,charging}-0-<tenths>.svg
    return QStringLiteral("file:///usr/share/fenestra/assets/battery/%1-0-%2.svg")
        .arg(pluggedIn() ? QStringLiteral("charging") : QStringLiteral("normal"))
        .arg(std::clamp(qRound(m_percentage / 10.0), 0, 10));
}

// ---- Keyboard layout (KWin's org.kde.KeyboardLayouts) ----------------------------------------
SINGLETON(KeyboardStatus)

namespace
{
const QString kKeyboard = QStringLiteral("org.kde.keyboard");
const QString kLayouts = QStringLiteral("/Layouts");
const QString kLayoutsIface = QStringLiteral("org.kde.KeyboardLayouts");
}

KeyboardStatus::KeyboardStatus(QObject *parent)
    : QObject(parent)
{
    auto bus = QDBusConnection::sessionBus();
    bus.connect(kKeyboard, kLayouts, kLayoutsIface, QStringLiteral("layoutChanged"), this, SLOT(onLayoutChanged(uint)));
    bus.connect(kKeyboard, kLayouts, kLayoutsIface, QStringLiteral("layoutListChanged"), this, SLOT(reload()));
    auto *watcher = new QDBusServiceWatcher(kKeyboard, bus, QDBusServiceWatcher::WatchForRegistration, this);
    connect(watcher, &QDBusServiceWatcher::serviceRegistered, this, &KeyboardStatus::reload);
    reload();
}

void KeyboardStatus::reload()
{
    QDBusMessage list = QDBusMessage::createMethodCall(kKeyboard, kLayouts, kLayoutsIface, QStringLiteral("getLayoutsList"));
    QDBusMessage reply = QDBusConnection::sessionBus().call(list, QDBus::Block, 2000);
    m_short.clear();
    m_long.clear();
    if (reply.type() == QDBusMessage::ReplyMessage && !reply.arguments().isEmpty()) {
        const QDBusArgument arg = reply.arguments().first().value<QDBusArgument>();
        arg.beginArray();
        while (!arg.atEnd()) {
            QString shortName, displayName, longName;
            arg.beginStructure();
            arg >> shortName >> displayName >> longName;
            arg.endStructure();
            m_short << (displayName.isEmpty() ? shortName : displayName);
            m_long << longName;
        }
        arg.endArray();
    }
    QDBusMessage current = QDBusMessage::createMethodCall(kKeyboard, kLayouts, kLayoutsIface, QStringLiteral("getLayout"));
    QDBusReply<uint> index = QDBusConnection::sessionBus().call(current, QDBus::Block, 2000);
    m_current = index.isValid() ? int(index.value()) : -1;
    Q_EMIT changed();
}

void KeyboardStatus::onLayoutChanged(uint index)
{
    m_current = int(index);
    Q_EMIT changed();
}

QString KeyboardStatus::shortName() const
{
    if (m_current < 0 || m_current >= m_short.size())
        return {};
    // "es" -> "ESP" style: three upper-case letters (layout code, padded from the long name).
    QString s = m_short.at(m_current).toUpper();
    if (s.size() == 2 && m_current < m_long.size() && m_long.at(m_current).size() >= 3)
        s = m_long.at(m_current).left(3).toUpper();
    return s;
}

void KeyboardStatus::next()
{
    QDBusConnection::sessionBus().asyncCall(
        QDBusMessage::createMethodCall(kKeyboard, kLayouts, kLayoutsIface, QStringLiteral("switchToNextLayout")));
}
