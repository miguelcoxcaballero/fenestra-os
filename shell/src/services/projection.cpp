// SPDX-License-Identifier: GPL-3.0-or-later
#include "projection.h"

#include <QDBusAbstractAdaptor>
#include <QDBusArgument>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusMessage>
#include <QDBusObjectPath>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusReply>
#include <QDBusVariant>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QSet>
#include <QDebug>
#include <QStandardPaths>

namespace {
const QString kOsdService = QStringLiteral("org.kde.kscreen.osdService");
const QString kOsdPath = QStringLiteral("/org/kde/kscreen/osdService");
const QString kNM = QStringLiteral("org.freedesktop.NetworkManager");
const QString kP2P = QStringLiteral("org.freedesktop.NetworkManager.Device.WifiP2P");
const QString kProps = QStringLiteral("org.freedesktop.DBus.Properties");
constexpr int kPanel = 7;   // libkscreen Output::Type::Panel: the built-in screen

// One output of kscreen-doctor -j.
struct Out {
    int id = 0;
    QString name;
    bool panel = false, enabled = false, primary = false;
    int width = 0, height = 0;      // logical size of the current (or preferred) mode
    int replicationSource = 0;
};

QList<Out> outputs(const QByteArray &json)
{
    QList<Out> list;
    const auto arr = QJsonDocument::fromJson(json).object().value(QStringLiteral("outputs")).toArray();
    for (const QJsonValue &v : arr) {
        const QJsonObject o = v.toObject();
        if (!o.value(QStringLiteral("connected")).toBool())
            continue;
        Out out;
        out.id = o.value(QStringLiteral("id")).toInt();
        out.name = o.value(QStringLiteral("name")).toString();
        out.panel = o.value(QStringLiteral("type")).toInt() == kPanel;
        out.enabled = o.value(QStringLiteral("enabled")).toBool();
        out.primary = o.value(QStringLiteral("priority")).toInt() == 1;
        out.replicationSource = o.value(QStringLiteral("replicationSource")).toInt();
        QString mode = o.value(QStringLiteral("currentModeId")).toString();
        if (mode.isEmpty() || !out.enabled) {
            const auto pref = o.value(QStringLiteral("preferredModes")).toArray();
            if (!pref.isEmpty())
                mode = pref.first().toString();
        }
        double scale = o.value(QStringLiteral("scale")).toDouble(1);
        if (scale <= 0)
            scale = 1;
        for (const QJsonValue &m : o.value(QStringLiteral("modes")).toArray()) {
            const QJsonObject mo = m.toObject();
            if (mo.value(QStringLiteral("id")).toString() == mode) {
                const QJsonObject size = mo.value(QStringLiteral("size")).toObject();
                out.width = qRound(size.value(QStringLiteral("width")).toInt() / scale);
                out.height = qRound(size.value(QStringLiteral("height")).toInt() / scale);
            }
        }
        list.append(out);
    }
    return list;
}

// "PC screen": the built-in panel, or on a desktop the primary display.
int mainIndex(const QList<Out> &list)
{
    for (int i = 0; i < list.size(); ++i)
        if (list[i].panel)
            return i;
    for (int i = 0; i < list.size(); ++i)
        if (list[i].primary)
            return i;
    return list.isEmpty() ? -1 : 0;
}

// org.kde.kscreen.osdService for KWin: the same two calls KDE's service answers.
class OsdAdaptor : public QDBusAbstractAdaptor
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.kde.kscreen.osdService")
public:
    explicit OsdAdaptor(Projection *p)
        : QDBusAbstractAdaptor(p), m_p(p) {}
public Q_SLOTS:
    void showActionSelector() { m_p->showActionSelector(); }
    void hideOsd() { m_p->hideOsd(); }
private:
    Projection *m_p;
};
}

// ---- Projection ------------------------------------------------------------------------------
Projection *Projection::instance()
{
    static Projection p;
    return &p;
}

Projection *Projection::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

Projection::Projection(QObject *parent)
    : QObject(parent)
{
    new OsdAdaptor(this);
    takeOsdService();
    refresh();
}

void Projection::takeOsdService()
{
    auto bus = QDBusConnection::sessionBus();
    bus.registerObject(kOsdPath, this, QDBusConnection::ExportAdaptors);
    if (bus.registerService(kOsdService))
        return;
    // KDE's own chooser is running (started by D-Bus activation): stop it and take the name.
    QProcess::startDetached(QStringLiteral("systemctl"), {QStringLiteral("--user"), QStringLiteral("stop"), QStringLiteral("plasma-kscreen-osd.service")});
    QTimer::singleShot(1000, this, [] {
        if (!QDBusConnection::sessionBus().registerService(kOsdService))
            qWarning() << "projection: org.kde.kscreen.osdService is taken; KDE's display chooser stays";
    });
}

void Projection::showActionSelector()
{
    refresh();
    Q_EMIT selectorRequested();
}

void Projection::hideOsd()
{
    Q_EMIT hideRequested();
}

void Projection::refresh()
{
    auto *p = new QProcess(this);
    connect(p, &QProcess::finished, this, [this, p] {
        parse(p->readAllStandardOutput());
        p->deleteLater();
    });
    p->start(QStringLiteral("kscreen-doctor"), {QStringLiteral("-j")});
}

void Projection::parse(const QByteArray &json)
{
    m_last = json;
    const QList<Out> list = outputs(json);
    const int main = mainIndex(list);
    QString mode;
    int externals = 0;
    if (main >= 0) {
        const Out &m = list[main];
        bool extOn = false, mirrored = true;
        for (int i = 0; i < list.size(); ++i) {
            if (i == main)
                continue;
            ++externals;
            if (list[i].enabled) {
                extOn = true;
                mirrored &= list[i].replicationSource == m.id;
            }
        }
        if (externals == 0 || !extOn)
            mode = QStringLiteral("pc");
        else if (!m.enabled)
            mode = QStringLiteral("second");
        else if (mirrored)
            mode = QStringLiteral("duplicate");
        else
            mode = QStringLiteral("extend");
    }
    if (mode != m_mode || externals != m_externals) {
        m_mode = mode;
        m_externals = externals;
        Q_EMIT changed();
    }
}

void Projection::setMode(const QString &mode)
{
    const QList<Out> list = outputs(m_last);
    const int main = mainIndex(list);
    if (main < 0 || m_busy)
        return;
    const Out &m = list[main];
    QStringList args;
    auto set = [&args](const QString &name, const QString &what) { args << QStringLiteral("output.%1.%2").arg(name, what); };
    int x = m.width;   // Extend: the other displays to the right of the PC screen, as Windows
    for (int i = 0; i < list.size(); ++i) {
        if (i == main)
            continue;
        const Out &o = list[i];
        if (mode == QLatin1String("pc")) {
            set(o.name, QStringLiteral("disable"));
        } else {
            set(o.name, QStringLiteral("enable"));
            if (mode == QLatin1String("duplicate")) {
                set(o.name, QStringLiteral("mirror.%1").arg(m.name));
            } else {
                set(o.name, QStringLiteral("mirror.none"));
                if (mode == QLatin1String("extend")) {
                    set(o.name, QStringLiteral("position.%1,0").arg(x));
                    x += o.width;
                } else {
                    set(o.name, QStringLiteral("position.%1,0").arg(x - m.width));
                    x += o.width;
                }
            }
        }
    }
    // the PC screen: on, except for "Second screen only" (and never with nothing else on)
    if (mode == QLatin1String("second") && list.size() > 1)
        set(m.name, QStringLiteral("disable"));
    else {
        set(m.name, QStringLiteral("enable"));
        set(m.name, QStringLiteral("position.0,0"));
    }
    m_busy = true;
    m_mode = mode;   // shown at once, confirmed by the refresh below
    Q_EMIT changed();
    auto *p = new QProcess(this);
    connect(p, &QProcess::finished, this, [this, p] {
        if (p->exitCode() != 0)
            qWarning() << "projection: kscreen-doctor failed:" << p->readAllStandardError();
        p->deleteLater();
        m_busy = false;
        refresh();
    });
    p->start(QStringLiteral("kscreen-doctor"), args);
}

// ---- Cast ------------------------------------------------------------------------------------
Cast *Cast::instance()
{
    static Cast c;
    return &c;
}

Cast *Cast::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

Cast::Cast(QObject *parent)
    : QObject(parent)
{
    // NetworkManager's Wi-Fi P2P device (Wi-Fi Direct: Miracast)
    auto sys = QDBusConnection::systemBus();
    const QDBusReply<QList<QDBusObjectPath>> devs = sys.call(QDBusMessage::createMethodCall(kNM, QStringLiteral("/org/freedesktop/NetworkManager"), kNM,
                                                                                             QStringLiteral("GetDevices")), QDBus::Block, 2000);
    if (devs.isValid()) {
        for (const QDBusObjectPath &d : devs.value()) {
            QDBusMessage get = QDBusMessage::createMethodCall(kNM, d.path(), kProps, QStringLiteral("Get"));
            get << QStringLiteral("org.freedesktop.NetworkManager.Device") << QStringLiteral("DeviceType");
            const QDBusReply<QDBusVariant> type = sys.call(get, QDBus::Block, 1000);
            if (type.isValid() && type.value().variant().toUInt() == 30) {   // NM_DEVICE_TYPE_WIFI_P2P
                m_p2p = d.path();
                break;
            }
        }
    }
    // Avahi (mDNS): Chromecasts announce _googlecast._tcp
    m_avahi = !QStandardPaths::findExecutable(QStringLiteral("avahi-browse")).isEmpty()
        && sys.interface()->isServiceRegistered(QStringLiteral("org.freedesktop.Avahi")).value();
    m_poll.setInterval(2000);
    connect(&m_poll, &QTimer::timeout, this, &Cast::pollPeers);
}

bool Cast::streamer() const
{
    return !QStandardPaths::findExecutable(QStringLiteral("gnome-network-displays")).isEmpty();
}

QVariantList Cast::devices() const
{
    QVariantList out;
    for (const QVariantMap &d : m_found)
        out.append(d);
    std::sort(out.begin(), out.end(), [](const QVariant &a, const QVariant &b) {
        return a.toMap().value(QStringLiteral("name")).toString().localeAwareCompare(b.toMap().value(QStringLiteral("name")).toString()) < 0;
    });
    return out;
}

void Cast::start()
{
    if (m_searching || !supported())
        return;
    m_searching = true;
    m_found.clear();
    if (m_avahi) {
        m_browse = new QProcess(this);
        m_browse->setProcessChannelMode(QProcess::SeparateChannels);
        connect(m_browse, &QProcess::readyReadStandardOutput, this, &Cast::readAvahi);
        // -r resolve, -p parsable, -k keep names unescaped; runs until stop()
        m_browse->start(QStringLiteral("avahi-browse"), {QStringLiteral("-rpk"), QStringLiteral("_googlecast._tcp")});
    }
    if (!m_p2p.isEmpty())
        pollPeers();
    m_poll.start();
    Q_EMIT changed();
}

void Cast::stop()
{
    if (!m_searching)
        return;
    m_searching = false;
    m_poll.stop();
    if (m_browse) {
        m_browse->kill();
        m_browse->deleteLater();
        m_browse = nullptr;
    }
    if (!m_p2p.isEmpty())
        QDBusConnection::systemBus().asyncCall(QDBusMessage::createMethodCall(kNM, m_p2p, kP2P, QStringLiteral("StopFind")));
    m_found.clear();
    Q_EMIT changed();
}

void Cast::pollPeers()
{
    if (m_p2p.isEmpty())
        return;
    auto sys = QDBusConnection::systemBus();
    // a find lasts 30 s; asking again keeps it going while the page is open
    static int ticks = 0;
    if (ticks++ % 12 == 0) {
        QDBusMessage find = QDBusMessage::createMethodCall(kNM, m_p2p, kP2P, QStringLiteral("StartFind"));
        find << QVariantMap{{QStringLiteral("timeout"), 30}};
        sys.asyncCall(find);
    }
    QDBusMessage get = QDBusMessage::createMethodCall(kNM, m_p2p, kProps, QStringLiteral("Get"));
    get << kP2P << QStringLiteral("Peers");
    auto *w = new QDBusPendingCallWatcher(sys.asyncCall(get), this);
    connect(w, &QDBusPendingCallWatcher::finished, this, [this, w] {
        w->deleteLater();
        QDBusPendingReply<QDBusVariant> r = *w;
        if (r.isError() || !m_searching)
            return;
        QList<QDBusObjectPath> peers;
        r.value().variant().value<QDBusArgument>() >> peers;
        auto sys = QDBusConnection::systemBus();
        QSet<QString> seen;
        bool changedAny = false;
        for (const QDBusObjectPath &peer : peers) {
            QDBusMessage all = QDBusMessage::createMethodCall(kNM, peer.path(), kProps, QStringLiteral("GetAll"));
            all << QStringLiteral("org.freedesktop.NetworkManager.WifiP2PPeer");
            const QDBusReply<QVariantMap> props = sys.call(all, QDBus::Block, 1000);
            if (!props.isValid())
                continue;
            // a Miracast receiver announces Wi-Fi Display information elements
            if (props.value().value(QStringLiteral("WfdIEs")).toByteArray().isEmpty())
                continue;
            const QString id = QStringLiteral("miracast:") + props.value().value(QStringLiteral("HwAddress")).toString();
            seen.insert(id);
            if (!m_found.contains(id)) {
                QString name = props.value().value(QStringLiteral("Name")).toString();
                m_found.insert(id, {{QStringLiteral("id"), id}, {QStringLiteral("name"), name.isEmpty() ? id.mid(9) : name},
                                    {QStringLiteral("kind"), QStringLiteral("miracast")}});
                changedAny = true;
            }
        }
        for (auto it = m_found.begin(); it != m_found.end();) {
            if (it.key().startsWith(QLatin1String("miracast:")) && !seen.contains(it.key())) {
                it = m_found.erase(it);
                changedAny = true;
            } else {
                ++it;
            }
        }
        if (changedAny)
            Q_EMIT changed();
    });
}

void Cast::readAvahi()
{
    m_avahiBuffer += m_browse->readAllStandardOutput();
    bool changedAny = false;
    int nl;
    while ((nl = m_avahiBuffer.indexOf('\n')) >= 0) {
        const QString line = QString::fromUtf8(m_avahiBuffer.left(nl));
        m_avahiBuffer.remove(0, nl + 1);
        // =;iface;proto;name;type;domain;host;address;port;"txt" "txt"... (resolved)
        // -;iface;proto;name;type;domain (gone)
        const QStringList f = line.split(QLatin1Char(';'));
        if (f.size() < 4)
            continue;
        const QString id = QStringLiteral("chromecast:") + f[3];
        if (f[0] == QLatin1String("-")) {
            changedAny |= m_found.remove(id) > 0;
        } else if (f[0] == QLatin1String("=") && f.size() >= 10 && !m_found.contains(id)) {
            QString name = f[3];
            const QRegularExpressionMatch fn = QRegularExpression(QStringLiteral("\"fn=([^\"]*)\"")).match(f.mid(9).join(QLatin1Char(';')));
            if (fn.hasMatch())
                name = fn.captured(1);
            m_found.insert(id, {{QStringLiteral("id"), id}, {QStringLiteral("name"), name}, {QStringLiteral("kind"), QStringLiteral("chromecast")}});
            changedAny = true;
        }
    }
    if (changedAny)
        Q_EMIT changed();
}

void Cast::connectTo(const QString &id)
{
    Q_UNUSED(id)
    // GNOME Network Displays streams the screen to Miracast and Chromecast receivers; it lists the
    // same displays and connects to the one chosen there. Without it, the Store offers it.
    if (streamer())
        QProcess::startDetached(QStringLiteral("gnome-network-displays"), {});
    else
        QProcess::startDetached(QStringLiteral("fenestra-store"), {QStringLiteral("--app"), QStringLiteral("org.gnome.NetworkDisplays")});
}

#include "projection.moc"
