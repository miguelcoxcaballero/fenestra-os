// SPDX-License-Identifier: GPL-3.0-or-later
// System state shown in the tray (B08): network, volume, battery, keyboard layout. Each one is
// driven by its service's signals; a missing service (no NetworkManager, no battery) only hides
// its icon.
#pragma once

#include <QDBusVariant>
#include <QObject>
#include <QPointer>
#include <QQmlEngine>
#include <QStringList>
#include <QVariantList>

#include <PulseAudioQt/Sink>

class NetworkStatus : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    // "wifi" | "ethernet" | "vpn" | "none" | "disabled" | "unavailable"
    Q_PROPERTY(QString kind READ kind NOTIFY changed)
    Q_PROPERTY(int signal READ signalStrength NOTIFY changed)  // 0–100 for Wi-Fi
    Q_PROPERTY(bool connected READ connected NOTIFY changed)
    Q_PROPERTY(bool limited READ limited NOTIFY changed)       // connected, no internet
    Q_PROPERTY(QString name READ name NOTIFY changed)          // SSID or connection name
    Q_PROPERTY(QString iconName READ iconName NOTIFY changed)
public:
    static NetworkStatus *instance();
    static NetworkStatus *create(QQmlEngine *, QJSEngine *);
    QString kind() const { return m_kind; }
    int signalStrength() const { return m_signal; }
    bool connected() const { return m_connected; }
    bool limited() const { return m_limited; }
    QString name() const { return m_name; }
    QString iconName() const;
Q_SIGNALS:
    void changed();
private:
    explicit NetworkStatus(QObject *parent = nullptr);
    void update();
    void watchAccessPoint();
    QString m_kind = QStringLiteral("unavailable"), m_name;
    int m_signal = 0;
    bool m_connected = false, m_limited = false;
    QMetaObject::Connection m_apConnection;
};

class AudioStatus : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(bool available READ available NOTIFY changed)
    Q_PROPERTY(int volume READ volume WRITE setVolume NOTIFY changed)   // 0–100 (up to 150 boosted)
    Q_PROPERTY(bool muted READ muted WRITE setMuted NOTIFY changed)
    Q_PROPERTY(QString outputName READ outputName NOTIFY changed)
    Q_PROPERTY(QString iconName READ iconName NOTIFY changed)
    Q_PROPERTY(QVariantList outputs READ outputs NOTIFY outputsChanged) // [{id, name, isDefault}]
public:
    static AudioStatus *instance();
    QVariantList outputs() const;
    Q_INVOKABLE void setDefaultOutput(const QString &id);
    static AudioStatus *create(QQmlEngine *, QJSEngine *);
    bool available() const { return m_sink; }
    int volume() const;
    bool muted() const;
    QString outputName() const;
    QString iconName() const;
    void setVolume(int percent);
    void setMuted(bool muted);
Q_SIGNALS:
    void changed();
    void outputsChanged();
private:
    explicit AudioStatus(QObject *parent = nullptr);
    void setSink(PulseAudioQt::Sink *sink);
    QPointer<PulseAudioQt::Sink> m_sink;
};

class PowerStatus : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(bool hasBattery READ hasBattery NOTIFY changed)
    Q_PROPERTY(int percentage READ percentage NOTIFY changed)
    Q_PROPERTY(bool charging READ charging NOTIFY changed)
    Q_PROPERTY(bool pluggedIn READ pluggedIn NOTIFY changed)
    Q_PROPERTY(qint64 timeToEmpty READ timeToEmpty NOTIFY changed)  // seconds, 0 = unknown
    Q_PROPERTY(qint64 timeToFull READ timeToFull NOTIFY changed)
    Q_PROPERTY(QString iconSource READ iconSource NOTIFY changed)   // assets/generated/battery
    Q_PROPERTY(double energyRate READ energyRate NOTIFY changed)    // W into or out of the battery
    Q_PROPERTY(double chargerMaxWatts READ chargerMaxWatts NOTIFY changed) // 0 = the system doesn't say
    Q_PROPERTY(int healthPercent READ healthPercent NOTIFY changed) // full / design capacity, 0 = unknown
public:
    static PowerStatus *instance();
    static PowerStatus *create(QQmlEngine *, QJSEngine *);
    bool hasBattery() const { return m_present; }
    int percentage() const { return m_percentage; }
    bool charging() const { return m_state == 1 || m_state == 5; } // charging, pending charge
    bool pluggedIn() const { return m_state == 1 || m_state == 4 || m_state == 5; }
    qint64 timeToEmpty() const { return m_toEmpty; }
    qint64 timeToFull() const { return m_toFull; }
    QString iconSource() const;
    double energyRate() const { return m_energyRate; }
    double chargerMaxWatts() const;
    int healthPercent() const;
Q_SIGNALS:
    void changed();
private Q_SLOTS:
    void onPropertiesChanged(const QString &interface, const QVariantMap &changed, const QStringList &invalidated);
private:
    explicit PowerStatus(QObject *parent = nullptr);
    void load();
    bool m_present = false;
    int m_percentage = 0;
    uint m_state = 0;
    qint64 m_toEmpty = 0, m_toFull = 0;
    double m_energyRate = 0;
};

class KeyboardStatus : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(QString shortName READ shortName NOTIFY changed)  // "ESP", "ENG"…
    Q_PROPERTY(QString longName READ longName NOTIFY changed)
    Q_PROPERTY(int count READ count NOTIFY changed)
    // Windows' input indicator, two lines: the language (3 letters, "ENG") over the keyboard's
    // region (2 letters, "ES"), e.g. English (United Kingdom) with a Spanish keyboard.
    Q_PROPERTY(QString language READ language NOTIFY changed)
    Q_PROPERTY(QString region READ region NOTIFY changed)
public:
    static KeyboardStatus *instance();
    static KeyboardStatus *create(QQmlEngine *, QJSEngine *);
    QString shortName() const;
    QString longName() const { return m_current >= 0 && m_current < m_long.size() ? m_long.at(m_current) : QString(); }
    int count() const { return m_short.size(); }
    QString language() const;
    QString region() const;
    Q_INVOKABLE void next();
Q_SIGNALS:
    void changed();
private Q_SLOTS:
    void onLayoutChanged(uint index);
    void reload();
private:
    explicit KeyboardStatus(QObject *parent = nullptr);
    QStringList m_short, m_long, m_layouts;
    int m_current = -1;
};
