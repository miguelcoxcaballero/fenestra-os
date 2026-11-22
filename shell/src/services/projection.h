// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Windows' "Project" (Win+P) and "Cast" (Win+K) pages of Quick settings.
//
// Projection: the four display modes (PC screen only, Duplicate, Extend, Second screen only),
// read from and applied with kscreen-doctor (KWin's output management). It also takes over
// org.kde.kscreen.osdService, which KWin calls when a new display is connected: instead of KDE's
// layout chooser, Fenestra shows the Project page, as Windows does with Win+P.
//
// Cast: wireless displays nearby, as Windows lists them: Miracast receivers through
// NetworkManager's Wi-Fi P2P device, Chromecasts through Avahi (_googlecast._tcp). The stream
// itself is GNOME Network Displays (both protocols); without Wi-Fi P2P and Avahi the page says
// what Windows says on a PC that cannot cast ("connect a cable").
#include <QObject>
#include <QProcess>
#include <QQmlEngine>
#include <QTimer>
#include <QVariantList>

class Projection : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    // "pc" | "duplicate" | "extend" | "second"; "" while unknown
    Q_PROPERTY(QString mode READ mode NOTIFY changed)
    // displays connected besides the built-in one
    Q_PROPERTY(int externals READ externals NOTIFY changed)
    Q_PROPERTY(bool busy READ busy NOTIFY changed)
public:
    static Projection *instance();
    static Projection *create(QQmlEngine *, QJSEngine *);
    QString mode() const { return m_mode; }
    int externals() const { return m_externals; }
    bool busy() const { return m_busy; }
    Q_INVOKABLE void refresh();
    Q_INVOKABLE void setMode(const QString &mode);
    // org.kde.kscreen.osdService (called by KWin)
    void showActionSelector();
    void hideOsd();
Q_SIGNALS:
    void changed();
    void selectorRequested();   // open Quick settings on the Project page
    void hideRequested();
private:
    explicit Projection(QObject *parent = nullptr);
    void takeOsdService();
    void parse(const QByteArray &json);
    QString m_mode;
    int m_externals = 0;
    bool m_busy = false;
    QByteArray m_last;          // the last kscreen-doctor -j
};

class Cast : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    // the PC can find wireless displays (Wi-Fi P2P for Miracast, or Avahi for Chromecast)
    Q_PROPERTY(bool supported READ supported NOTIFY changed)
    Q_PROPERTY(bool searching READ searching NOTIFY changed)
    // [{id, name, kind: "miracast"|"chromecast", state: ""|"connecting"|"connected"|"error"}]
    Q_PROPERTY(QVariantList devices READ devices NOTIFY changed)
    // the display being cast to ("" when none) and how far it got
    Q_PROPERTY(QString active READ active NOTIFY changed)
    Q_PROPERTY(QString activeState READ activeState NOTIFY changed)
    // GNOME Network Displays is installed (it finds the displays and does the streaming)
    Q_PROPERTY(bool streamer READ streamer NOTIFY changed)
public:
    static Cast *instance();
    static Cast *create(QQmlEngine *, QJSEngine *);
    bool supported() const { return !m_p2p.isEmpty() || m_avahi; }
    bool searching() const { return m_searching; }
    QVariantList devices() const;
    QString active() const { return m_active; }
    QString activeState() const;
    bool streamer() const;
    Q_INVOKABLE void start();   // the Cast page is open: look for displays
    Q_INVOKABLE void stop();
    Q_INVOKABLE void connectTo(const QString &id);
    Q_INVOKABLE void disconnect();
Q_SIGNALS:
    void changed();
private:
    explicit Cast(QObject *parent = nullptr);
    void ensureDaemon();
    void poll();
    void updateRunning();
    void follow();
    void journalLine(const QString &line);
    void stopFollowing();
    void failed();
    void ended();
    QString m_p2p;              // NetworkManager Wi-Fi P2P device path
    bool m_avahi = false;
    bool m_searching = false;
    QTimer m_poll;
    QList<QVariantMap> m_displays;   // the daemon's Displays, as shown
    QString m_active;           // uuid being cast to
    QString m_unit;             // its systemd unit (StopStream takes it)
    int m_activeState = 0;      // NdSinkState of the active display
    QProcess *m_journal = nullptr;   // journalctl -f of the stream's unit
    QByteArray m_journalBuffer;
    qint64 m_startedAt = 0;          // when the stream was asked for (ms)
    qint64 m_daemonLaunched = 0;
};
