// SPDX-License-Identifier: GPL-3.0-or-later
#include "snip.h"

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
    connect(w, &QDBusPendingCallWatcher::finished, this, [reader, data, done](QDBusPendingCallWatcher *w) {
        w->deleteLater();
        QDBusPendingReply<QVariantMap> r = *w;
        if (!r.isValid())
            qWarning("fenestra-shell: ScreenShot2.CaptureWorkspace failed: %s", qPrintable(r.error().message()));
        reader->wait();
        reader->deleteLater();
        const QVariantMap meta = r.isValid() ? r.value() : QVariantMap();
        const int width = meta.value(QStringLiteral("width")).toInt(), height = meta.value(QStringLiteral("height")).toInt();
        const int stride = meta.value(QStringLiteral("stride")).toInt();
        const auto format = QImage::Format(meta.value(QStringLiteral("format")).toInt());
        QImage img;
        if (width > 0 && height > 0 && data->size() >= stride * height)
            img = QImage(reinterpret_cast<const uchar *>(data->constData()), width, height, stride, format).copy();
        delete data;
        done(img);
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
{
    const QString screen = QUrl::fromPercentEncoding(id.section(QLatin1Char('/'), 0, 0).toUtf8());
    const QImage img = Snip::instance()->frozenFor(screen);
    if (size)
        *size = img.size();
    return img;
}
