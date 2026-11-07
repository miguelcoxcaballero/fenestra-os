// SPDX-License-Identifier: GPL-3.0-or-later
#include "screencast.h"

#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusUnixFileDescriptor>
#include <QGuiApplication>
#include <QThread>

#include <fcntl.h>
#include <memory>
#include <unistd.h>

namespace
{
// KWin 6.8 offers version 6 (the stream's PipeWire object serial); 1 is enough for a node id.
constexpr int kScreencastVersion = 6;
// zkde_screencast_unstable_v1.pointer: hidden (the thumbnail never shows the pointer).
constexpr uint32_t kPointerHidden = 1;
}

ScreencastManager::ScreencastManager()
    : QWaylandClientExtensionTemplate<ScreencastManager>(kScreencastVersion)
{
    initialize();
}

ScreencastManager::~ScreencastManager()
{
    if (isActive())
        destroy();
}

ScreencastManager *ScreencastManager::instance()
{
    static auto *self = [] {
        auto *m = new ScreencastManager;
        m->setParent(QGuiApplication::instance());
        return m;
    }();
    return self;
}

ScreencastStreamObject::ScreencastStreamObject(::zkde_screencast_stream_unstable_v1 *object)
    : QtWayland::zkde_screencast_stream_unstable_v1(object)
{
}

ScreencastStreamObject::~ScreencastStreamObject()
{
    if (object())
        close();
}

void ScreencastStreamObject::zkde_screencast_stream_unstable_v1_created(uint32_t n)
{
    node = n;
    Q_EMIT ready();
}

void ScreencastStreamObject::zkde_screencast_stream_unstable_v1_serial(uint32_t hi, uint32_t lo)
{
    serial = (quint64(hi) << 32) | lo;
    Q_EMIT ready();
}

void ScreencastStreamObject::zkde_screencast_stream_unstable_v1_failed(const QString &error)
{
    Q_EMIT failedWith(error);
}

void ScreencastStreamObject::zkde_screencast_stream_unstable_v1_closed()
{
    Q_EMIT ended();
}

ScreencastStream::ScreencastStream(QObject *parent)
    : QObject(parent)
{
    connect(ScreencastManager::instance(), &ScreencastManager::activeChanged, this, [this] {
        Q_EMIT availableChanged();
        restart();
    });
}

ScreencastStream::~ScreencastStream()
{
    delete m_stream;
}

bool ScreencastStream::available() const
{
    return ScreencastManager::instance()->isActive() && !m_failed;
}

void ScreencastStream::setUuid(const QString &uuid)
{
    if (uuid == m_uuid)
        return;
    m_uuid = uuid;
    Q_EMIT uuidChanged();
    restart();
}

void ScreencastStream::setEnabled(bool enabled)
{
    if (enabled == m_enabled)
        return;
    m_enabled = enabled;
    Q_EMIT enabledChanged();
    restart();
}

void ScreencastStream::restart()
{
    const bool had = m_stream;
    delete m_stream;
    m_stream = nullptr;
    if (m_failed) {
        m_failed = false;
        Q_EMIT availableChanged();
    }
    auto *manager = ScreencastManager::instance();
    if (m_enabled && !m_uuid.isEmpty() && manager->isActive()) {
        m_stream = new ScreencastStreamObject(manager->stream_window(m_uuid, kPointerHidden));
        connect(m_stream, &ScreencastStreamObject::ready, this, &ScreencastStream::streamChanged);
        connect(m_stream, &ScreencastStreamObject::failedWith, this, [this](const QString &error) {
            qWarning("fenestra-shell: window screencast failed: %s", qPrintable(error));
            m_failed = true;
            Q_EMIT availableChanged();
        });
        connect(m_stream, &ScreencastStreamObject::ended, this, [this] {
            // KWin ended it (the window closed): no stream until the next request.
            m_stream->deleteLater();
            m_stream = nullptr;
            Q_EMIT streamChanged();
        });
    }
    if (had || m_stream)
        Q_EMIT streamChanged();
}

WindowSnapshot *WindowSnapshot::instance()
{
    static auto *self = new WindowSnapshot(QGuiApplication::instance());
    return self;
}

QImage WindowSnapshot::image(const QString &uuid) const
{
    QMutexLocker l(&m_lock);
    return m_images.value(uuid);
}

void WindowSnapshot::release(const QString &uuid)
{
    QMutexLocker l(&m_lock);
    m_images.remove(uuid);
}

void WindowSnapshot::capture(const QString &uuid)
{
    if (uuid.isEmpty() || m_pending.value(uuid))
        return;
    int fds[2];
    if (pipe2(fds, O_CLOEXEC) != 0)
        return;
    // ScreenShot2.CaptureWindow (allowed by X-KDE-DBUS-Restricted-Interfaces): the window and its
    // frame, no shadow, at logical size (more than the thumbnail's 182 x 109 needs).
    QDBusMessage msg = QDBusMessage::createMethodCall(QStringLiteral("org.kde.KWin.ScreenShot2"), QStringLiteral("/org/kde/KWin/ScreenShot2"),
                                                      QStringLiteral("org.kde.KWin.ScreenShot2"), QStringLiteral("CaptureWindow"));
    msg << uuid
        << QVariantMap{{QStringLiteral("include-cursor"), false}, {QStringLiteral("include-decoration"), true},
                       {QStringLiteral("include-shadow"), false}, {QStringLiteral("native-resolution"), false}}
        << QVariant::fromValue(QDBusUnixFileDescriptor(fds[1]));
    ::close(fds[1]);
    m_pending.insert(uuid, true);
    const int readFd = fds[0];
    auto data = std::make_shared<QByteArray>();
    QThread *reader = QThread::create([readFd, data] {
        char buf[65536];
        ssize_t n;
        while ((n = ::read(readFd, buf, sizeof buf)) > 0)
            data->append(buf, n);
        ::close(readFd);
    });
    auto *w = new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(msg), this);
    connect(w, &QDBusPendingCallWatcher::finished, this, [=, this](QDBusPendingCallWatcher *w) {
        w->deleteLater();
        QDBusPendingReply<QVariantMap> r = *w;
        if (!r.isValid()) {
            qWarning("fenestra-shell: ScreenShot2.CaptureWindow failed: %s", qPrintable(r.error().message()));
            m_pending.remove(uuid);
            connect(reader, &QThread::finished, reader, &QObject::deleteLater);
            return;
        }
        const QVariantMap meta = r.value();
        auto process = [=, this] {
            reader->deleteLater();
            m_pending.remove(uuid);
            const int width = meta.value(QStringLiteral("width")).toInt(), height = meta.value(QStringLiteral("height")).toInt();
            const int stride = meta.value(QStringLiteral("stride")).toInt();
            const auto format = QImage::Format(meta.value(QStringLiteral("format")).toInt());
            if (width <= 0 || height <= 0 || data->size() < qsizetype(stride) * height)
                return;
            const QImage shot = QImage(reinterpret_cast<const uchar *>(data->constData()), width, height, stride, format)
                                    .convertToFormat(QImage::Format_ARGB32_Premultiplied);
            int serial;
            {
                QMutexLocker l(&m_lock);
                m_images.insert(uuid, shot);
                serial = ++m_serials[uuid];
            }
            Q_EMIT captured(uuid, serial);
        };
        if (reader->isFinished())
            process();
        else
            connect(reader, &QThread::finished, this, process);
    });
    reader->start();
}

QImage WindowSnapshotProvider::requestImage(const QString &id, QSize *size, const QSize &requested)
{
    // <uuid>/<serial>
    QImage img = WindowSnapshot::instance()->image(id.section(QLatin1Char('/'), 0, 0));
    if (!img.isNull() && requested.isValid() && !requested.isEmpty())
        img = img.scaled(requested, Qt::KeepAspectRatio, Qt::SmoothTransformation);
    if (size)
        *size = img.size();
    return img;
}
