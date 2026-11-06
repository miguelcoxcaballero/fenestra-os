// SPDX-License-Identifier: GPL-3.0-or-later
#include "polkitagent.h"

#include <PolkitQt1/Subject>
#include <unistd.h>

PolkitAgent *PolkitAgent::instance()
{
    static auto *a = new PolkitAgent;
    return a;
}

PolkitAgent *PolkitAgent::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

PolkitAgent::PolkitAgent(QObject *parent)
    : PolkitQt1::Agent::Listener(parent)
{
}

void PolkitAgent::registerAgent()
{
    PolkitQt1::UnixSessionSubject subject(getpid());
    if (!registerListener(subject, QStringLiteral("/org/fenestra/PolicyKit1/AuthenticationAgent")))
        qWarning("fenestra-shell: could not register the polkit agent (another agent is running?)");
}

void PolkitAgent::initiateAuthentication(const QString &actionId, const QString &message, const QString &iconName,
                                         const PolkitQt1::Details &, const QString &cookie,
                                         const PolkitQt1::Identity::List &identities, PolkitQt1::Agent::AsyncResult *result)
{
    if (m_result) { // one at a time
        result->setError(QStringLiteral("Another authentication is in progress"));
        result->setCompleted();
        return;
    }
    m_result = result;
    m_actionId = actionId;
    m_message = message;
    m_icon = iconName;
    m_cookie = cookie;
    m_error.clear();
    m_gained = false;
    // The current user if they are an administrator, else the first administrator.
    m_identity = identities.isEmpty() ? PolkitQt1::Identity() : identities.first();
    const QString me = QStringLiteral("unix-user:") + QString::fromLocal8Bit(qgetenv("USER"));
    for (const PolkitQt1::Identity &id : identities)
        if (id.toString() == me)
            m_identity = id;
    startSession();
    Q_EMIT changed();
}

void PolkitAgent::startSession()
{
    if (m_session)
        m_session->deleteLater();
    m_session = new PolkitQt1::Agent::Session(m_identity, m_cookie, m_result, this);
    connect(m_session, &PolkitQt1::Agent::Session::request, this, [this](const QString &request, bool echo) {
        m_prompt = request;
        m_echo = echo;
        Q_EMIT changed();
    });
    connect(m_session, &PolkitQt1::Agent::Session::showError, this, [this](const QString &text) { m_error = text; Q_EMIT changed(); });
    connect(m_session, &PolkitQt1::Agent::Session::completed, this, [this](bool gained) {
        m_gained = gained;
        if (gained) {
            finish();
        } else {
            // Wrong password: ask again (the password is always required, Q06).
            const bool es = QLocale().name().startsWith(QLatin1String("es"));
            m_error = es ? QStringLiteral("La contraseña no es correcta. Inténtalo de nuevo.") : QStringLiteral("The password is incorrect. Try again.");
            startSession();
            Q_EMIT changed();
        }
    });
    m_session->initiate();
}

void PolkitAgent::respond(const QString &password)
{
    if (m_session)
        m_session->setResponse(password);
}

void PolkitAgent::cancel()
{
    if (m_session)
        m_session->cancel();
    if (m_result) {
        m_result->setError(QStringLiteral("Cancelled"));
        finish();
    }
}

void PolkitAgent::finish()
{
    if (m_result)
        m_result->setCompleted();
    m_result = nullptr;
    if (m_session)
        m_session->deleteLater();
    m_prompt.clear();
    Q_EMIT changed();
}

bool PolkitAgent::initiateAuthenticationFinish()
{
    return true;
}

void PolkitAgent::cancelAuthentication()
{
    cancel();
}
