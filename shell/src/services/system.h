// SPDX-License-Identifier: GPL-3.0-or-later
// Quick settings and OSD back ends (Q01–Q03, B08 privacy): media players (MPRIS), screen
// brightness (backlight via logind), power profiles (power-profiles-daemon), Wi-Fi networks and
// airplane mode (NetworkManager), microphone and location in use.
#pragma once

#include <QAbstractListModel>
#include <QDBusContext>
#include <QDBusVariant>
#include <QHash>
#include <QObject>
#include <QQmlEngine>
#include <QSet>
#include <QStringList>
#include <QTimer>
#include <QVariantMap>

// The player shown in the media card: the first one playing, else the last one that played.
class Media : public QObject, protected QDBusContext
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(bool available READ available NOTIFY changed)
    Q_PROPERTY(bool playing READ playing NOTIFY changed)
    Q_PROPERTY(QString appName READ appName NOTIFY changed)
    Q_PROPERTY(QString appIcon READ appIcon NOTIFY changed)
    Q_PROPERTY(QString title READ title NOTIFY changed)
    Q_PROPERTY(QString artist READ artist NOTIFY changed)
    Q_PROPERTY(QString artUrl READ artUrl NOTIFY changed)
    Q_PROPERTY(bool canGoPrevious READ canGoPrevious NOTIFY changed)
    Q_PROPERTY(bool canGoNext READ canGoNext NOTIFY changed)
public:
    static Media *instance();
    static Media *create(QQmlEngine *, QJSEngine *);
    bool available() const { return !m_current.isEmpty(); }
    bool playing() const;
    QString appName() const;
    QString appIcon() const;
    QString title() const;
    QString artist() const;
    QString artUrl() const;
    bool canGoPrevious() const;
    bool canGoNext() const;
    Q_INVOKABLE void playPause();
    Q_INVOKABLE void previous();
    Q_INVOKABLE void next();
Q_SIGNALS:
    void changed();
private Q_SLOTS:
    void onNameOwnerChanged(const QString &name, const QString &oldOwner, const QString &newOwner);
    void onPropertiesChanged(const QString &interface, const QVariantMap &changed, const QStringList &invalidated);
private:
    explicit Media(QObject *parent = nullptr);
    void addPlayer(const QString &service);
    void pick();
    void call(const QString &method);
    struct Player { QString service, owner; QVariantMap root, player; };
    QHash<QString, Player> m_players; // by unique owner
    QString m_current;                // owner
    QStringList m_order;              // owners, last that played last
};

class Brightness : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(bool available READ available CONSTANT)
    Q_PROPERTY(int percent READ percent WRITE setPercent NOTIFY changed)
public:
    static Brightness *instance();
    static Brightness *create(QQmlEngine *, QJSEngine *);
    bool available() const { return !m_device.isEmpty() && m_max > 0; }
    int percent() const;
    void setPercent(int percent);
    Q_INVOKABLE void step(int delta); // ±percent, for the keys
Q_SIGNALS:
    void changed();
private:
    explicit Brightness(QObject *parent = nullptr);
    QString m_device;
    int m_max = 0, m_value = 0;
};

class PowerProfiles : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(bool available READ available NOTIFY changed)
    Q_PROPERTY(QString active READ active WRITE setActive NOTIFY changed) // power-saver | balanced | performance
    Q_PROPERTY(QStringList profiles READ profiles NOTIFY changed)
public:
    static PowerProfiles *instance();
    static PowerProfiles *create(QQmlEngine *, QJSEngine *);
    bool available() const { return !m_profiles.isEmpty(); }
    QString active() const { return m_active; }
    QStringList profiles() const { return m_profiles; }
    void setActive(const QString &profile);
Q_SIGNALS:
    void changed();
private Q_SLOTS:
    void onPropertiesChanged(const QString &interface, const QVariantMap &changed, const QStringList &invalidated);
private:
    explicit PowerProfiles(QObject *parent = nullptr);
    void load();
    QString m_service, m_path, m_iface;
    QString m_active;
    QStringList m_profiles;
};

// Wi-Fi networks for the quick settings subpage, connected first then strongest, one row per SSID.
// Rows are updated in place (never a model reset), so a delegate that shows the inline password
// field keeps it while scans add, remove or re-sort access points. The connect attempt is
// tracked here: rows report "Connecting" / "Verifying and connecting", and a rejected key brings
// the password field back (keyRejected) with Windows' message in the row's status.
class WifiNetworks : public QAbstractListModel
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(bool enabled READ enabled WRITE setEnabled NOTIFY enabledChanged)
    Q_PROPERTY(bool airplaneMode READ airplaneMode WRITE setAirplaneMode NOTIFY enabledChanged)
    Q_PROPERTY(bool hasWifi READ hasWifi NOTIFY enabledChanged)
    Q_PROPERTY(int count READ rowCount NOTIFY countChanged)
public:
    enum Roles { SsidRole = Qt::UserRole + 1, SignalRole, SecuredRole, ActiveRole, KnownRole, ConnectingRole,
                 StatusRole, ErrorRole, EnterpriseRole };
    static WifiNetworks *instance();
    static WifiNetworks *create(QQmlEngine *, QJSEngine *);
    int rowCount(const QModelIndex &parent = {}) const override;
    QVariant data(const QModelIndex &index, int role) const override;
    QHash<int, QByteArray> roleNames() const override;
    bool enabled() const;
    void setEnabled(bool on);
    bool airplaneMode() const;
    void setAirplaneMode(bool on);
    bool hasWifi() const;
    Q_INVOKABLE void scan();
    // Known network or open one: activates it. Secured unknown one (or a saved one whose key was
    // just rejected): needs the password. Enterprise networks open Settings › Wi-Fi instead.
    Q_INVOKABLE bool needsPassword(int row) const;
    Q_INVOKABLE void connectTo(int row, const QString &password = QString());
    Q_INVOKABLE void disconnectFrom(int row);
    Q_INVOKABLE void cancel(int row);
Q_SIGNALS:
    void enabledChanged();
    void countChanged();
    void keyRejected(const QString &ssid);
private:
    explicit WifiNetworks(QObject *parent = nullptr);
    void watchDevice(const QString &uni);
    void scheduleRebuild();
    void rebuild();
    void onDeviceState(const QString &devicePath, int newState, int reason);
    void finishAttempt(bool ok, int reason);
    struct Net { QString ssid, apPath, devicePath, connectionPath; int signal = 0; bool secured = false, active = false,
                 connecting = false, enterprise = false; QString keyMgmt; };
    struct Attempt { QString ssid, uuid, devicePath; bool created = false, withKey = false, started = false; };
    QString statusOf(const Net &n) const;
    QList<Net> m_nets;
    Attempt m_attempt;
    QHash<QString, QString> m_errors;   // ssid -> message shown in the row until the next attempt
    QSet<QString> m_rejected;           // ssid whose saved key was rejected: ask again
    QTimer *m_rebuildTimer = nullptr;
};

// Microphone and location in use (B08 privacy glyphs).
class Privacy : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(QStringList microphoneApps READ microphoneApps NOTIFY changed)
    Q_PROPERTY(bool locationInUse READ locationInUse NOTIFY changed)
public:
    static Privacy *instance();
    static Privacy *create(QQmlEngine *, QJSEngine *);
    QStringList microphoneApps() const { return m_mic; }
    bool locationInUse() const { return m_location; }
Q_SIGNALS:
    void changed();
private Q_SLOTS:
    void onGeoClue(const QString &interface, const QVariantMap &changed, const QStringList &invalidated);
private:
    explicit Privacy(QObject *parent = nullptr);
    void updateMic();
    QStringList m_mic;
    bool m_location = false;
};

// Night light (KWin night colour): kwinrc [NightColor] Active, applied with KWin's reconfigure.
class NightLight : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(bool active READ active WRITE setActive NOTIFY changed)
public:
    static NightLight *instance();
    static NightLight *create(QQmlEngine *, QJSEngine *);
    bool active() const;
    void setActive(bool on);
Q_SIGNALS:
    void changed();
private:
    explicit NightLight(QObject *parent = nullptr);
};
