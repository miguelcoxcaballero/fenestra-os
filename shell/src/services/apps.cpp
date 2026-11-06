// SPDX-License-Identifier: GPL-3.0-or-later
#include "apps.h"

#include <KApplicationTrader>
#include <KIO/ApplicationLauncherJob>
#include <KIO/CommandLauncherJob>
#include <KSycoca>
#include <QProcess>

Apps *Apps::instance()
{
    static auto *a = new Apps;
    return a;
}

Apps *Apps::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

Apps::Apps(QObject *parent)
    : QObject(parent)
{
    // Installs and removals update the database; KSycoca tells us (inotify, no polling).
    connect(KSycoca::self(), &KSycoca::databaseChanged, this, &Apps::databaseChanged);
}

KService::Ptr Apps::service(const QString &storageId) const
{
    if (storageId.isEmpty())
        return {};
    KService::Ptr s = KService::serviceByStorageId(storageId);
    if (!s && !storageId.endsWith(QLatin1String(".desktop")))
        s = KService::serviceByStorageId(storageId + QLatin1String(".desktop"));
    return s;
}

KService::Ptr Apps::serviceForWindow(const QString &appId) const
{
    if (appId.isEmpty())
        return {};
    if (KService::Ptr s = service(appId))
        return s;
    if (KService::Ptr s = KService::serviceByDesktopName(appId.toLower()))
        return s;
    const auto matches = KApplicationTrader::query([&appId](const KService::Ptr &s) {
        const QString wmClass = s->property<QString>(QStringLiteral("StartupWMClass"));
        return !wmClass.isEmpty() && wmClass.compare(appId, Qt::CaseInsensitive) == 0;
    });
    return matches.isEmpty() ? KService::Ptr() : matches.first();
}

QVariantMap Apps::info(const QString &storageId) const
{
    const KService::Ptr s = service(storageId);
    if (!s)
        return {};
    return {{QStringLiteral("storageId"), s->storageId()}, {QStringLiteral("name"), s->name()},
            {QStringLiteral("icon"), s->icon()}, {QStringLiteral("comment"), s->comment()},
            {QStringLiteral("mimeTypes"), s->mimeTypes()}};
}

bool Apps::launch(const QString &storageId)
{
    const KService::Ptr s = service(storageId);
    if (!s)
        return false;
    if (qEnvironmentVariableIntValue("FENESTRA_SHELL_TEST") == 1 && qEnvironmentVariableIsSet("FENESTRA_SHELL_NO_ACTIVATION")) {
        // Headless bench only: KWin 6.8.2 without OpenGL crashes when a launcher requests an
        // xdg-activation token (EffectsHandler::startupAdded with no effects). gio sends none.
        QProcess::startDetached(QStringLiteral("gio"), {QStringLiteral("launch"), s->entryPath()});
    } else {
        auto *job = new KIO::ApplicationLauncherJob(s);
        job->start();
    }
    Q_EMIT launched(s->storageId());
    return true;
}

void Apps::runCommand(const QString &command)
{
    auto *job = new KIO::CommandLauncherJob(command);
    job->start();
}
