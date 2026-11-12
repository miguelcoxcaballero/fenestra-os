// SPDX-License-Identifier: GPL-3.0-or-later
#include <functional>
#include <QFile>
#include <memory>
#include <atomic>
#include <poll.h>
#include <QElapsedTimer>
#include "snip.h"
#include "guard.h"

#include "apps.h"
#include "notifications.h"

#include <QClipboard>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusUnixFileDescriptor>
#include <QDateTime>
#include <QDir>
#include <QFileInfo>
#include <QGuiApplication>
#include <QLocale>
#include <QPainter>
#include <QPainterPath>
#include <QScreen>
#include <QStandardPaths>
#include <QThread>
#include <QTimer>
#include <QUrl>
#include <fcntl.h>
#include <unistd.h>

Snip *Snip::instance()
{
    static auto *s = new Snip;
    return s;
}

Snip *Snip::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

Snip::Snip(QObject *parent)
    : QObject(parent)
{
}

void Snip::setMode(const QString &mode)
{
    static const QStringList modes{QStringLiteral("rectangle"), QStringLiteral("window"), QStringLiteral("screen"), QStringLiteral("freeform")};
    if (mode == m_mode || !modes.contains(mode))
        return;
    m_mode = mode;
    Q_EMIT modeChanged();
}

QRect Snip::workspace()
{
    QRect r;
    for (QScreen *s : QGuiApplication::screens())
        r |= s->geometry();
    return r;
}

void Snip::grabWorkspace(std::function<void(const QImage &)> done)
{
    // Bench: a picture file instead of KWin (see snip.h).
    const QString testImage = qEnvironmentVariable("FENESTRA_SHELL_SNIP_IMAGE");
    if (qEnvironmentVariableIntValue("FENESTRA_SHELL_TEST") == 1 && !testImage.isEmpty()) {
        QTimer::singleShot(0, this, [done, testImage] { done(QImage(testImage)); });
        return;
    }
    // KWin ScreenShot2 (allowed by X-KDE-DBUS-Restricted-Interfaces in org.fenestra.Shell.desktop):
    // the image comes through a pipe, the reply describes it.
    int fds[2];
    if (pipe2(fds, O_CLOEXEC) != 0) {
        done({});
        return;
    }
    // One screen: CaptureScreen, which copies what the output shows. CaptureWorkspace re-renders the
    // scene and drew the taskbar as transparent black (KWin 6.8, layer surface over no wallpaper).
    const QList<QScreen *> screens = QGuiApplication::screens();
    const bool single = screens.size() == 1;
    QDBusMessage msg = QDBusMessage::createMethodCall(QStringLiteral("org.kde.KWin.ScreenShot2"), QStringLiteral("/org/kde/KWin/ScreenShot2"),
                                                      QStringLiteral("org.kde.KWin.ScreenShot2"),
                                                      single ? QStringLiteral("CaptureScreen") : QStringLiteral("CaptureWorkspace"));
    if (single)
        msg << screens.first()->name();
    // hide-caller-windows: KWin leaves out the caller's own surfaces otherwise, and the caller is the
    // shell: the taskbar (and the desktop) came out as transparent black.
    msg << QVariantMap{{QStringLiteral("include-cursor"), false}, {QStringLiteral("native-resolution"), true},
                       {QStringLiteral("hide-caller-windows"), false}}
        << QVariant::fromValue(QDBusUnixFileDescriptor(fds[1]));
    ::close(fds[1]);
    const int readFd = fds[0];
    // The reader stops once it has the bytes the reply announces (or on EOF / error / 5 s): the pending
    // call keeps a copy of the pipe's write end, so EOF alone never comes while we wait for it.
    struct Shared { QByteArray data; std::atomic<qsizetype> expected{-1}; std::atomic<bool> stop{false}; };
    auto shared = std::make_shared<Shared>();
    QThread *reader = QThread::create([readFd, shared] {
        char buf[65536];
        QElapsedTimer t; t.start();
        while (!shared->stop && t.elapsed() < 5000) {
            const qsizetype want = shared->expected;
            if (want >= 0 && shared->data.size() >= want)
                break;
            pollfd pfd{readFd, POLLIN, 0};
            if (::poll(&pfd, 1, 50) <= 0)
                continue;
            const ssize_t n = ::read(readFd, buf, sizeof buf);
            if (n <= 0)
                break;
            shared->data.append(buf, n);
        }
        ::close(readFd);
    });
    auto *w = new QDBusPendingCallWatcher(QDBusConnection::sessionBus().asyncCall(msg), this);
    connect(w, &QDBusPendingCallWatcher::finished, this, [reader, shared, done](QDBusPendingCallWatcher *w) {
        w->deleteLater();
        QDBusPendingReply<QVariantMap> r = *w;
        if (!r.isValid())
            qWarning("fenestra-shell: ScreenShot2.CaptureWorkspace failed: %s", qPrintable(r.error().message()));
        const QVariantMap meta = r.isValid() ? r.value() : QVariantMap();
        const int width = meta.value(QStringLiteral("width")).toInt(), height = meta.value(QStringLiteral("height")).toInt();
        const int stride = meta.value(QStringLiteral("stride")).toInt();
        const auto format = QImage::Format(meta.value(QStringLiteral("format")).toInt());
        if (width > 0 && height > 0 && stride > 0)
            shared->expected = qsizetype(stride) * height;
        else
            shared->stop = true;
        // Wait off the GUI thread's event processing: the reader ends by itself (size reached, 5 s cap).
        auto handled = std::make_shared<bool>(false);
        auto finish = [reader, shared, done, width, height, stride, format, handled] {
            if (*handled)
                return;
            *handled = true;
            reader->deleteLater();
            QImage img;
            if (width > 0 && height > 0 && shared->data.size() >= qsizetype(stride) * height) {
                // The screen is opaque: the buffer's alpha is whatever the surfaces left in it (0.14 under the
                // translucent taskbar), so read the same bytes as an opaque format, as Spectacle does.
                QImage::Format opaque = format;
                switch (format) {
                case QImage::Format_ARGB32: case QImage::Format_ARGB32_Premultiplied: opaque = QImage::Format_RGB32; break;
                case QImage::Format_RGBA8888: case QImage::Format_RGBA8888_Premultiplied: opaque = QImage::Format_RGBX8888; break;
                case QImage::Format_A2RGB30_Premultiplied: opaque = QImage::Format_RGB30; break;
                case QImage::Format_A2BGR30_Premultiplied: opaque = QImage::Format_BGR30; break;
                case QImage::Format_RGBA64: case QImage::Format_RGBA64_Premultiplied: opaque = QImage::Format_RGBX64; break;
                default: break;
                }
                img = QImage(reinterpret_cast<const uchar *>(shared->data.constData()), width, height, stride, opaque).copy();
            }
            else if (width > 0)
                qWarning("fenestra-shell: ScreenShot2 sent %lld of %lld bytes", qlonglong(shared->data.size()), qlonglong(stride) * height);
            done(img);
        };
        // Wait without blocking the GUI thread: the reader ends by itself (size reached, 5 s cap).
        connect(reader, &QThread::finished, reader, finish);
        if (reader->isFinished())
            QTimer::singleShot(0, reader, finish);
    });
    reader->start();
}

void Snip::start()
{
    if (m_active || m_grabbing)
        return;
    m_grabbing = true;
    // The overlay opens only after the picture is back, so it is never in it.
    grabWorkspace([this](const QImage &img) {
        m_grabbing = false;
        if (img.isNull()) {
            Q_EMIT failed(QStringLiteral("capture"));
            return;
        }
        m_workspace = workspace();
        // Native resolution: the picture can be larger than the logical workspace (scaled outputs).
        m_frozen = img.convertToFormat(QImage::Format_ARGB32_Premultiplied);
        // A screen is opaque. Qt keeps the RGBX padding byte KWin sends (the surfaces' leftover alpha,
        // ~0 under the translucent taskbar) as alpha in this conversion, which saved the taskbar as
        // transparent black: force every pixel opaque.
        for (int y = 0; y < m_frozen.height(); ++y) {
            auto *line = reinterpret_cast<QRgb *>(m_frozen.scanLine(y));
            for (int x = 0; x < m_frozen.width(); ++x)
                line[x] |= 0xff000000u;
        }
        m_scale = m_workspace.width() > 0 ? qreal(m_frozen.width()) / m_workspace.width() : 1;
        if (m_workspace.height() > 0 && qAbs(m_frozen.height() / m_scale - m_workspace.height()) > 1) {
            // A test picture of another size: stretched over the workspace.
            m_frozen = m_frozen.scaled(m_workspace.size(), Qt::IgnoreAspectRatio, Qt::SmoothTransformation);
            m_scale = 1;
        }
        ++m_serial;
        m_active = true;
        Q_EMIT activeChanged();
    });
}

void Snip::cancel()
{
    if (!m_active)
        return;
    m_active = false;
    m_frozen = QImage();
    Q_EMIT activeChanged();
}

QImage Snip::frozenFor(const QString &screen) const
{
    for (QScreen *s : QGuiApplication::screens())
        if (s->name() == screen)
            return m_frozen.copy(pixelRect(s->geometry()));
    return {};
}

QRect Snip::pixelRect(const QRectF &global) const
{
    const QRectF r = global.translated(-m_workspace.topLeft());
    return QRectF(r.x() * m_scale, r.y() * m_scale, r.width() * m_scale, r.height() * m_scale).toAlignedRect() & m_frozen.rect();
}

bool Snip::captureRect(const QRectF &global)
{
    if (!m_active)
        return false;
    const QRect px = pixelRect(global.normalized());
    if (px.width() < 1 || px.height() < 1)
        return false;
    return deliver(m_frozen.copy(px));
}

bool Snip::captureScreen(const QString &name)
{
    for (QScreen *s : QGuiApplication::screens())
        if (s->name() == name)
            return captureRect(s->geometry());
    return false;
}

bool Snip::captureFreeform(const QList<qreal> &globalXY)
{
    if (!m_active || globalXY.size() < 6)
        return false;
    QPainterPath path;
    for (qsizetype i = 0; i + 1 < globalXY.size(); i += 2) {
        const QPointF p = (QPointF(globalXY.at(i), globalXY.at(i + 1)) - QPointF(m_workspace.topLeft())) * m_scale;
        i == 0 ? path.moveTo(p) : path.lineTo(p);
    }
    path.closeSubpath();
    const QRect bounds = path.boundingRect().toAlignedRect() & m_frozen.rect();
    if (bounds.width() < 1 || bounds.height() < 1)
        return false;
    // Transparent outside the lasso: the frozen picture as the brush of the (antialiased) path.
    QImage out(bounds.size(), QImage::Format_ARGB32_Premultiplied);
    out.fill(Qt::transparent);
    QPainter p(&out);
    p.setRenderHint(QPainter::Antialiasing);
    p.translate(-bounds.topLeft());
    p.setPen(Qt::NoPen);
    p.setBrush(QBrush(m_frozen));
    p.drawPath(path);
    p.end();
    return deliver(out);
}

void Snip::captureWorkspaceNow()
{
    if (m_active || m_grabbing)
        return;
    m_grabbing = true;
    grabWorkspace([this](const QImage &img) {
        m_grabbing = false;
        if (img.isNull())
            Q_EMIT failed(QStringLiteral("capture"));
        else
            finish(img, true);
    });
}

bool Snip::deliver(const QImage &image)
{
    // Clipboard first, while the overlay still has the keyboard focus (wl_data_device needs it).
    QGuiApplication::clipboard()->setImage(image);
    m_active = false;
    m_frozen = QImage();
    Q_EMIT activeChanged();
    finish(image, false);
    return true;
}

void Snip::finish(const QImage &image, bool toClipboard)
{
    const QString dir = QStandardPaths::writableLocation(QStandardPaths::PicturesLocation) + QStringLiteral("/Screenshots");
    QDir().mkpath(dir);
    const QString stamp = QDateTime::currentDateTime().toString(QStringLiteral("yyyyMMdd_HHmmss"));
    QString path = dir + QStringLiteral("/Screenshot_%1.png").arg(stamp);
    for (int n = 2; QFileInfo::exists(path); ++n)
        path = dir + QStringLiteral("/Screenshot_%1_%2.png").arg(stamp).arg(n);
    if (!image.save(path)) {
        Q_EMIT failed(QStringLiteral("save"));
        return;
    }
    if (toClipboard)
        QGuiApplication::clipboard()->setImage(image);
    m_lastSaved = path;
    Q_EMIT saved(path);
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
}

QImage SnipImageProvider::requestImage(const QString &id, QSize *size, const QSize &)
try {
    const QString screen = QUrl::fromPercentEncoding(id.section(QLatin1Char('/'), 0, 0).toUtf8());
    const QImage img = Snip::instance()->frozenFor(screen);
    if (size)
        *size = img.size();
    return img;
} catch (...) {
    return providerFailed("SnipImageProvider", id, size);
}

void Snip::testBurst(const QString &dir, int count)
{
    if (qEnvironmentVariableIntValue("FENESTRA_SHELL_TEST") != 1 || count <= 0)
        return;
    QDir().mkpath(dir);
    auto t0 = std::make_shared<QElapsedTimer>();
    t0->start();
    auto times = std::make_shared<QStringList>();
    auto step = std::make_shared<std::function<void(int)>>();
    *step = [this, dir, count, t0, times, step](int i) {
        const qint64 asked = t0->elapsed();
        grabWorkspace([this, dir, count, t0, times, step, i, asked](const QImage &img) {
            img.save(dir + QStringLiteral("/f%1.png").arg(i, 3, 10, QLatin1Char('0')), "PNG", 0);
            *times << QStringLiteral("%1 %2 %3").arg(i).arg(asked).arg(t0->elapsed());
            if (i + 1 < count)
                (*step)(i + 1);
            else {
                QFile f(dir + QStringLiteral("/times.txt"));
                if (f.open(QIODevice::WriteOnly))
                    f.write(times->join(QLatin1Char('\n')).toUtf8());
            }
        });
    };
    (*step)(0);
}
