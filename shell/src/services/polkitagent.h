// SPDX-License-Identifier: GPL-3.0-or-later
// Authentication agent (Q06): polkit asks the user for a password with the shell's own dialog
// (GNOME Shell was the agent before; without one every pkexec and admin action fails).
#pragma once

#include <PolkitQt1/Agent/Listener>
#include <PolkitQt1/Details>
#include <PolkitQt1/Agent/Session>
#include <PolkitQt1/Identity>
#include <QObject>
#include <QPointer>
#include <QQmlEngine>

class PolkitAgent : public PolkitQt1::Agent::Listener
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(bool active READ active NOTIFY changed)
    Q_PROPERTY(QString message READ message NOTIFY changed)
    Q_PROPERTY(QString iconName READ iconName NOTIFY changed)
    Q_PROPERTY(QString prompt READ prompt NOTIFY changed)
    Q_PROPERTY(bool echo READ echo NOTIFY changed)
    Q_PROPERTY(QString userName READ userName NOTIFY changed)
    Q_PROPERTY(QString error READ error NOTIFY changed)
    Q_PROPERTY(QString actionId READ actionId NOTIFY changed)
public:
    static PolkitAgent *instance();
    static PolkitAgent *create(QQmlEngine *, QJSEngine *);
    void registerAgent();

    bool active() const { return m_result; }
    QString message() const { return m_message; }
    QString iconName() const { return m_icon; }
    QString prompt() const { return m_prompt; }
    bool echo() const { return m_echo; }
    QString userName() const { return m_identity.toString().section(QLatin1Char(':'), 1); }
    QString error() const { return m_error; }
    QString actionId() const { return m_actionId; }

    Q_INVOKABLE void respond(const QString &password);
    Q_INVOKABLE void cancel();

public Q_SLOTS:
    void initiateAuthentication(const QString &actionId, const QString &message, const QString &iconName,
                                const PolkitQt1::Details &details, const QString &cookie,
                                const PolkitQt1::Identity::List &identities, PolkitQt1::Agent::AsyncResult *result) override;
    bool initiateAuthenticationFinish() override;
    void cancelAuthentication() override;

Q_SIGNALS:
    void changed();

private:
    explicit PolkitAgent(QObject *parent = nullptr);
    void startSession();
    void finish();
    QPointer<PolkitQt1::Agent::Session> m_session;
    PolkitQt1::Agent::AsyncResult *m_result = nullptr;
    PolkitQt1::Identity m_identity;
    QString m_cookie, m_message, m_icon, m_prompt, m_error, m_actionId;
    bool m_echo = false, m_gained = false;
};
