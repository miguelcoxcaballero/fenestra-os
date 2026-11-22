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
#include <QDateTime>
#include <QDir>
#include <QGuiApplication>
#include <QSaveFile>
#include <QScreen>

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

// org.fenestra.Shell.Cast on the shell's connection (/org/fenestra/Shell/Cast): the Cast page's
// actions for scripts and tests, which can drive a cast without clicking in Quick settings.
class CastAdaptor : public QDBusAbstractAdaptor
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.fenestra.Shell.Cast")
public:
    explicit CastAdaptor(Cast *c)
        : QDBusAbstractAdaptor(c), m_c(c) {}
public Q_SLOTS:
    void Search(bool on) { on ? m_c->start() : m_c->stop(); }
    void Connect(const QString &id) { m_c->connectTo(id); }
    void Disconnect() { m_c->disconnect(); }
    // {"searching", "active", "state", "devices": [{id, name, kind, state}]}
    QString Status()
    {
        return QString::fromUtf8(QJsonDocument(QJsonObject{{QStringLiteral("searching"), m_c->searching()},
                                                           {QStringLiteral("active"), m_c->active()},
                                                           {QStringLiteral("state"), m_c->activeState()},
                                                           {QStringLiteral("devices"), QJsonArray::fromVariantList(m_c->devices())}})
                                     .toJson(QJsonDocument::Compact));
    }
private:
    Cast *m_c;
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
    m_avahi = sys.interface()->isServiceRegistered(QStringLiteral("org.freedesktop.Avahi")).value();
    m_poll.setInterval(1000);
    connect(&m_poll, &QTimer::timeout, this, &Cast::poll);
    new CastAdaptor(this);
    QDBusConnection::sessionBus().registerObject(QStringLiteral("/org/fenestra/Shell/Cast"), this);
}

bool Cast::streamer() const
{
    return !QStandardPaths::findExecutable(QStringLiteral("gnome-network-displays-daemon")).isEmpty();
}

namespace {
const QString kGnd = QStringLiteral("org.gnome.NetworkDisplays.Manager");
const QString kGndPath = QStringLiteral("/org/gnome/NetworkDisplays/Manager");
const QString kGndUnit = QStringLiteral("fenestra-network-displays.service");
// NdSinkState (gnome-network-displays src/nd-sink.h)
enum { SinkDisconnected = 0, SinkEnsureFirewall, SinkWaitP2P, SinkWaitSocket, SinkWaitStreaming, SinkStreaming, SinkError };
// NdSinkProtocol: META 0, DUMMY_WFD_P2P 1, DUMMY_CC 2, WFD_P2P 3, WFD_MICE 4, CC 5
QString kindOf(uint protocol)
{
    return (protocol == 2 || protocol == 5) ? QStringLiteral("chromecast") : QStringLiteral("miracast");
}
QString stateName(int s)
{
    if (s == SinkStreaming)
        return QStringLiteral("connected");
    if (s == SinkError)
        return QStringLiteral("error");
    if (s > SinkDisconnected)
        return QStringLiteral("connecting");
    return {};
}
}

QString Cast::activeState() const
{
    if (m_active.isEmpty())
        return {};
    // StartStream returns before the stream unit has told the daemon anything
    return m_activeState == SinkDisconnected ? QStringLiteral("connecting") : stateName(m_activeState);
}

QVariantList Cast::devices() const
{
    QVariantList out;
    for (QVariantMap d : m_displays) {
        if (d.value(QStringLiteral("id")).toString() == m_active)
            d.insert(QStringLiteral("state"), activeState());
        out.append(d);
    }
    return out;
}

// GNOME Network Displays' daemon finds Miracast receivers (Wi-Fi P2P, and Miracast over the
// network) and Chromecasts, and runs each stream as a systemd user unit. It is not D-Bus
// activatable, so Fenestra starts it as a unit of its own while the Cast page is open or a stream
// is running, and stops it after (its search keeps Wi-Fi P2P busy).
void Cast::ensureDaemon()
{
    auto bus = QDBusConnection::sessionBus();
    if (bus.interface()->isServiceRegistered(kGnd).value())
        return;
    // it takes a moment to appear on the bus: one start at a time
    const qint64 now = QDateTime::currentMSecsSinceEpoch();
    if (now - m_daemonLaunched < 5000)
        return;
    m_daemonLaunched = now;
    QProcess::startDetached(QStringLiteral("systemd-run"),
                            {QStringLiteral("--user"), QStringLiteral("--collect"), QStringLiteral("--quiet"),
                             QStringLiteral("--unit=") + kGndUnit, QStringLiteral("--description=Wireless displays (Cast)"),
                             QStringLiteral("gnome-network-displays-daemon")});
}

void Cast::updateRunning()
{
    const bool want = m_searching || !m_active.isEmpty();
    if (want && !m_poll.isActive()) {
        m_poll.start();
    } else if (!want) {
        m_poll.stop();
        QProcess::startDetached(QStringLiteral("systemctl"), {QStringLiteral("--user"), QStringLiteral("stop"), kGndUnit});
    }
}

void Cast::start()
{
    if (m_searching || !supported() || !streamer())
        return;
    m_searching = true;
    ensureDaemon();
    updateRunning();
    poll();
    Q_EMIT changed();
}

void Cast::stop()
{
    if (!m_searching)
        return;
    m_searching = false;
    updateRunning();
    if (m_active.isEmpty())
        m_displays.clear();
    Q_EMIT changed();
}

void Cast::poll()
{
    QDBusMessage get = QDBusMessage::createMethodCall(kGnd, kGndPath, kProps, QStringLiteral("Get"));
    get << kGnd << QStringLiteral("Displays");
    auto *w = new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(get, 2000), this);
    connect(w, &QDBusPendingCallWatcher::finished, this, [this, w] {
        w->deleteLater();
        QDBusPendingReply<QDBusVariant> r = *w;
        if (r.isError()) {
            ensureDaemon();   // still starting, or it went away
            return;
        }
        QList<QVariantMap> list;
        const QDBusArgument arg = r.value().variant().value<QDBusArgument>();
        arg.beginArray();
        while (!arg.atEnd()) {
            QVariantMap m;
            arg >> m;
            const QString uuid = m.value(QStringLiteral("uuid")).toString();
            const uint protocol = m.value(QStringLiteral("protocol")).toUInt();
            const int state = int(m.value(QStringLiteral("state")).toUInt());
            if (protocol == 0)   // META: the same display reached two ways; its parts are listed too
                continue;
            list.append({{QStringLiteral("id"), uuid},
                         {QStringLiteral("name"), m.value(QStringLiteral("display-name")).toString()},
                         {QStringLiteral("kind"), kindOf(protocol)},
                         {QStringLiteral("state"), stateName(state)}});
        }
        arg.endArray();
        std::sort(list.begin(), list.end(), [](const QVariantMap &a, const QVariantMap &b) {
            return a.value(QStringLiteral("name")).toString().localeAwareCompare(b.value(QStringLiteral("name")).toString()) < 0;
        });
        bool dirty = list != m_displays;
        m_displays = list;
        if (dirty)
            Q_EMIT changed();
    });
}

void Cast::connectTo(const QString &id)
{
    if (!streamer()) {
        QProcess::startDetached(QStringLiteral("fenestra-store"), {QStringLiteral("--app"), QStringLiteral("org.gnome.NetworkDisplays")});
        return;
    }
    if (id == m_active)
        return;
    if (!m_active.isEmpty())
        disconnect();
    // Choosing the display is the consent, as on Windows: the Fenestra portal lets the stream
    // record the main screen without KDE's "what to share" chooser (fenestra_portal/screencast.py).
    if (QScreen *screen = QGuiApplication::primaryScreen()) {
        const QPoint pos = screen->geometry().topLeft();
        const QString dir = QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation) + QStringLiteral("/fenestra");
        QDir().mkpath(dir);
        QSaveFile f(dir + QStringLiteral("/cast-grant"));
        if (f.open(QIODevice::WriteOnly)) {
            f.write(QJsonDocument(QJsonObject{{QStringLiteral("time"), double(QDateTime::currentSecsSinceEpoch())},
                                              {QStringLiteral("output"), QStringLiteral("%1x%2").arg(pos.x()).arg(pos.y())}})
                        .toJson(QJsonDocument::Compact));
            f.commit();
        }
    }
    m_active = id;
    m_unit.clear();
    m_activeState = SinkDisconnected;
    m_startedAt = QDateTime::currentMSecsSinceEpoch() - 1000;
    // gnome-network-displays-stream crashes on its way out (a double free in its PulseAudio
    // teardown, after the stream is over); the failed unit it leaves would make the next
    // StartStream to this display fail with UnitExists
    QProcess::execute(QStringLiteral("systemctl"), {QStringLiteral("--user"), QStringLiteral("reset-failed"),
                                                    QStringLiteral("gnome-network-displays-stream-%1.service").arg(id)});
    // a receiver that never answers: Windows gives up after about half a minute too
    QTimer::singleShot(45000, this, [this, id, at = m_startedAt] {
        if (m_active == id && m_startedAt == at && m_activeState < SinkStreaming) {
            qInfo() << "cast:" << id << "did not answer";
            failed();
        }
    });
    updateRunning();
    Q_EMIT changed();
    QDBusMessage start = QDBusMessage::createMethodCall(kGnd, kGndPath, kGnd, QStringLiteral("StartStream"));
    start << id;
    auto *w = new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(start, 10000), this);
    connect(w, &QDBusPendingCallWatcher::finished, this, [this, w, id] {
        w->deleteLater();
        QDBusPendingReply<QString> r = *w;
        if (m_active != id)
            return;
        if (r.isError()) {
            qWarning() << "cast: StartStream failed:" << r.error().message();
            failed();
            return;
        }
        m_unit = r.value();
        follow();
    });
}

// The stream runs in its own unit (gnome-network-displays-stream-<uuid>.service) and the daemon's
// Displays never show its progress, so the unit's journal does: NdStream's "State changed to
// ND_SINK_STATE_…" lines (Miracast, Chromecast), the receiver's first RTSP request for receivers
// that skip them, and systemd's own lines when the unit stops or fails.
void Cast::follow()
{
    stopFollowing();
    m_journal = new QProcess(this);
    m_journal->setProcessChannelMode(QProcess::SeparateChannels);
    const QString id = m_active;
    connect(m_journal, &QProcess::readyReadStandardOutput, this, [this, id] {
        if (!m_journal || m_active != id)
            return;
        m_journalBuffer += m_journal->readAllStandardOutput();
        int nl;
        while ((nl = m_journalBuffer.indexOf('\n')) >= 0) {
            const QString line = QString::fromUtf8(m_journalBuffer.left(nl));
            m_journalBuffer.remove(0, nl + 1);
            journalLine(line);
            if (m_active != id)
                return;
        }
    });
    QProcess *j = m_journal;
    connect(j, &QProcess::finished, this, [this, id, j] {
        if (m_active == id && m_journal == j)
            ended();
    });
    m_journal->start(QStringLiteral("journalctl"), {QStringLiteral("--user"), QStringLiteral("--unit=") + m_unit, QStringLiteral("--follow"),
                                                   QStringLiteral("--output=cat"), QStringLiteral("--no-pager"),
                                                   // this run only: a display keeps its uuid, and so its unit name
                                                   QStringLiteral("--since=@%1").arg(m_startedAt / 1000)});
}

void Cast::journalLine(const QString &line)
{
    static const QRegularExpression stateRe(QStringLiteral("State changed to ND_SINK_STATE_([A-Z_]+)"));
    const QRegularExpressionMatch m = stateRe.match(line);
    int state = -1;
    if (m.hasMatch()) {
        static const QHash<QString, int> names{{QStringLiteral("DISCONNECTED"), SinkDisconnected}, {QStringLiteral("ENSURE_FIREWALL"), SinkEnsureFirewall},
                                               {QStringLiteral("WAIT_P2P"), SinkWaitP2P}, {QStringLiteral("WAIT_SOCKET"), SinkWaitSocket},
                                               {QStringLiteral("WAIT_STREAMING"), SinkWaitStreaming}, {QStringLiteral("STREAMING"), SinkStreaming},
                                               {QStringLiteral("ERROR"), SinkError}};
        state = names.value(m.captured(1), -1);
        if (state == SinkDisconnected && m_activeState == SinkStreaming) {
            ended();   // the receiver hung up
            return;
        }
    } else if (line.startsWith(QLatin1String("WfdClient: Got ")) && m_activeState < SinkStreaming) {
        state = SinkStreaming;   // the receiver talks RTSP to us: the picture is on its way
    } else if (line.contains(QLatin1String(".service: Failed with result")) || line.contains(QLatin1String(".service: Deactivated"))
               || line.contains(QLatin1String(".service: Main process exited"))) {
        if (m_activeState == SinkStreaming)
            ended();
        else
            failed();
        return;
    }
    if (state >= 0 && state != m_activeState) {
        m_activeState = state;
        if (state == SinkError) {
            failed();
            return;
        }
        Q_EMIT changed();
    }
}

void Cast::stopFollowing()
{
    if (!m_journal)
        return;
    QProcess *j = m_journal;
    m_journal = nullptr;
    j->disconnect(this);
    j->kill();
    j->deleteLater();
    m_journalBuffer.clear();
}

// The display could not be reached: "Couldn't connect" for a moment, then the row is plain again.
void Cast::failed()
{
    const QString id = m_active;
    stopFollowing();
    m_activeState = SinkError;
    Q_EMIT changed();
    QTimer::singleShot(4000, this, [this, id] {
        if (m_active == id)
            disconnect();
    });
}

void Cast::ended()
{
    qInfo() << "cast: the stream to" << m_active << "ended";
    disconnect();
}

void Cast::disconnect()
{
    if (m_active.isEmpty())
        return;
    stopFollowing();
    if (!m_unit.isEmpty()) {
        QDBusMessage stop = QDBusMessage::createMethodCall(kGnd, kGndPath, kGnd, QStringLiteral("StopStream"));
        stop << m_unit;
        QDBusConnection::sessionBus().asyncCall(stop);
        // the daemon may already be gone; the unit is what streams
        QProcess::startDetached(QStringLiteral("systemctl"), {QStringLiteral("--user"), QStringLiteral("stop"), m_unit});
        // it crashes on its way out (see connectTo): don't leave a failed unit behind
        QTimer::singleShot(4000, this, [unit = m_unit] {
            QProcess::startDetached(QStringLiteral("systemctl"), {QStringLiteral("--user"), QStringLiteral("reset-failed"), unit});
        });
    }
    m_active.clear();
    m_unit.clear();
    m_activeState = SinkDisconnected;
    // let StopStream reach the daemon before it may be stopped
    QTimer::singleShot(1500, this, &Cast::updateRunning);
    Q_EMIT changed();
}

#include "projection.moc"
