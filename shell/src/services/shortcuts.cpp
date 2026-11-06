// SPDX-License-Identifier: GPL-3.0-or-later
#include "shortcuts.h"

#include "apps.h"
#include "kwinintegration.h"
#include "notifications.h"
#include "status.h"
#include "system.h"

#include <KGlobalAccel>
#include <PulseAudioQt/Context>
#include <PulseAudioQt/Server>
#include <PulseAudioQt/Source>
#include <QAction>
#include <QClipboard>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusUnixFileDescriptor>
#include <QDateTime>
#include <QDir>
#include <QGuiApplication>
#include <QImage>
#include <QStandardPaths>
#include <QThread>
#include <QUrl>
#include <fcntl.h>
#include <unistd.h>

Shortcuts *Shortcuts::instance()
{
    static auto *s = new Shortcuts;
    return s;
}

Shortcuts *Shortcuts::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

Shortcuts::Shortcuts(QObject *parent)
    : QObject(parent)
{
}

QAction *Shortcuts::add(const QString &id, const QString &text, const QList<QKeySequence> &keys)
{
    auto *a = new QAction(text, this);
    a->setObjectName(id);
    a->setProperty("componentName", QStringLiteral("fenestra-shell"));
    a->setProperty("componentDisplayName", QStringLiteral("Fenestra Shell"));
    KGlobalAccel::self()->setDefaultShortcut(a, keys);
    KGlobalAccel::self()->setShortcut(a, keys, KGlobalAccel::Autoloading);
    return a;
}

void Shortcuts::volume(int delta)
{
    auto *audio = AudioStatus::instance();
    if (!audio->available())
        return;
    if (delta == 0)
        audio->setMuted(!audio->muted());
    else {
        if (audio->muted())
            audio->setMuted(false);
        audio->setVolume(std::clamp(audio->volume() + delta, 0, 100));
    }
    // The sink reports the new volume asynchronously; show the value we asked for.
    Q_EMIT osd(QStringLiteral("volume"), audio->muted() && delta == 0 ? -1 : std::clamp(audio->volume() + delta, 0, 100));
}

void Shortcuts::install()
{
    connect(add(QStringLiteral("volume-up"), QStringLiteral("Volume up"), {QKeySequence(Qt::Key_VolumeUp)}), &QAction::triggered, this, [this] { volume(+2); });
    connect(add(QStringLiteral("volume-down"), QStringLiteral("Volume down"), {QKeySequence(Qt::Key_VolumeDown)}), &QAction::triggered, this, [this] { volume(-2); });
    connect(add(QStringLiteral("volume-mute"), QStringLiteral("Mute"), {QKeySequence(Qt::Key_VolumeMute)}), &QAction::triggered, this, [this] { volume(0); });
    connect(add(QStringLiteral("mic-mute"), QStringLiteral("Mute microphone"), {QKeySequence(Qt::Key_MicMute)}), &QAction::triggered, this, [this] {
        if (auto *src = PulseAudioQt::Context::instance()->server()->defaultSource()) {
            src->setMuted(!src->isMuted());
            Q_EMIT osd(QStringLiteral("microphone"), src->isMuted() ? 100 : -1); // value: the new state before the async update
        }
    });
    connect(add(QStringLiteral("brightness-up"), QStringLiteral("Brightness up"), {QKeySequence(Qt::Key_MonBrightnessUp)}), &QAction::triggered, this, [this] {
        Brightness::instance()->step(+5);
        Q_EMIT osd(QStringLiteral("brightness"), Brightness::instance()->percent());
    });
    connect(add(QStringLiteral("brightness-down"), QStringLiteral("Brightness down"), {QKeySequence(Qt::Key_MonBrightnessDown)}), &QAction::triggered, this, [this] {
        Brightness::instance()->step(-5);
        Q_EMIT osd(QStringLiteral("brightness"), Brightness::instance()->percent());
    });
    connect(add(QStringLiteral("security-screen"), QStringLiteral("Security options (Ctrl+Alt+Del)"),
                {QKeySequence(Qt::CTRL | Qt::ALT | Qt::Key_Delete)}),
            &QAction::triggered, this, &Shortcuts::securityScreenRequested);
    connect(add(QStringLiteral("task-manager"), QStringLiteral("Task Manager"), {QKeySequence(Qt::CTRL | Qt::SHIFT | Qt::Key_Escape)}),
            &QAction::triggered, this, [] { Apps::instance()->runCommand(QStringLiteral("fenestra-taskmgr")); });
    connect(add(QStringLiteral("notification-center"), QStringLiteral("Notifications and calendar"), {QKeySequence(Qt::META | Qt::Key_N)}),
            &QAction::triggered, this, &Shortcuts::notificationCenterRequested);
    connect(add(QStringLiteral("quick-settings"), QStringLiteral("Quick settings"), {QKeySequence(Qt::META | Qt::Key_A)}),
            &QAction::triggered, this, &Shortcuts::quickSettingsRequested);
    connect(add(QStringLiteral("search"), QStringLiteral("Search"), {QKeySequence(Qt::META | Qt::Key_S)}),
            &QAction::triggered, this, &Shortcuts::searchRequested);
    connect(add(QStringLiteral("snap-layouts"), QStringLiteral("Snap layouts"), {QKeySequence(Qt::META | Qt::Key_Z)}),
            &QAction::triggered, this, &Shortcuts::snapLayoutsRequested);
    connect(add(QStringLiteral("task-view"), QStringLiteral("Task View"), {QKeySequence(Qt::META | Qt::Key_Tab)}),
            &QAction::triggered, this, [] { KWinIntegration::instance()->toggleOverview(); });
    connect(add(QStringLiteral("screenshot"), QStringLiteral("Take a screenshot"), {QKeySequence(Qt::Key_Print)}),
            &QAction::triggered, this, &Shortcuts::takeScreenshot);
}

void Shortcuts::takeScreenshot()
{
    // KWin ScreenShot2 (allowed by X-KDE-DBUS-Restricted-Interfaces in org.fenestra.Shell.desktop):
    // the image comes through a pipe, the reply describes it.
    int fds[2];
    if (pipe2(fds, O_CLOEXEC) != 0)
        return;
    QDBusMessage msg = QDBusMessage::createMethodCall(QStringLiteral("org.kde.KWin.ScreenShot2"), QStringLiteral("/org/kde/KWin/ScreenShot2"),
                                                      QStringLiteral("org.kde.KWin.ScreenShot2"), QStringLiteral("CaptureWorkspace"));
    msg << QVariantMap{{QStringLiteral("include-cursor"), false}, {QStringLiteral("native-resolution"), true}}
        << QVariant::fromValue(QDBusUnixFileDescriptor(fds[1]));
    ::close(fds[1]);
    const int readFd = fds[0];
    auto *data = new QByteArray;
    QThread *reader = QThread::create([readFd, data] {
        char buf[65536];
        ssize_t n;
        while ((n = ::read(readFd, buf, sizeof buf)) > 0)
            data->append(buf, n);
        ::close(readFd);
    });
    auto *w = new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(msg), this);
    connect(w, &QDBusPendingCallWatcher::finished, this, [this, reader, data](QDBusPendingCallWatcher *w) {
        w->deleteLater();
        QDBusPendingReply<QVariantMap> r = *w;
        reader->wait();
        reader->deleteLater();
        const QVariantMap meta = r.isValid() ? r.value() : QVariantMap();
        const int width = meta.value(QStringLiteral("width")).toInt(), height = meta.value(QStringLiteral("height")).toInt();
        const int stride = meta.value(QStringLiteral("stride")).toInt();
        const auto format = QImage::Format(meta.value(QStringLiteral("format")).toInt());
        if (width <= 0 || height <= 0 || data->size() < stride * height) {
            delete data;
            return;
        }
        const QImage img = QImage(reinterpret_cast<const uchar *>(data->constData()), width, height, stride, format).copy();
        delete data;
        const QString dir = QStandardPaths::writableLocation(QStandardPaths::PicturesLocation) + QStringLiteral("/Screenshots");
        QDir().mkpath(dir);
        const QString path = dir + QStringLiteral("/Screenshot_%1.png").arg(QDateTime::currentDateTime().toString(QStringLiteral("yyyyMMdd_HHmmss")));
        if (!img.save(path))
            return;
        QGuiApplication::clipboard()->setImage(img);
        Q_EMIT screenshotSaved(path);
        const bool es = QLocale().name().startsWith(QLatin1String("es"));
        // The wording of the GNOME layer's toast (screenshotToast.js).
        const uint id = Notifications::instance()->notify(
            es ? QStringLiteral("Recortes") : QStringLiteral("Snipping Tool"), QStringLiteral("applets-screenshooter"),
            es ? QStringLiteral("Captura de pantalla copiada en el portapapeles") : QStringLiteral("Screenshot copied to clipboard"),
            es ? QStringLiteral("Se guardó automáticamente en la carpeta de capturas de pantalla.") : QStringLiteral("Automatically saved to screenshots folder."),
            path, {QVariantMap{{QStringLiteral("key"), QStringLiteral("open")}, {QStringLiteral("label"), es ? QStringLiteral("Marcar y compartir") : QStringLiteral("Mark-up and share")}}});
        connect(Notifications::instance(), &Notifications::shellAction, this, [id, path](uint which, const QString &) {
            if (which == id)
                Apps::instance()->runCommand(QStringLiteral("xdg-open \"%1\"").arg(path));
        });
    });
    reader->start();
}
