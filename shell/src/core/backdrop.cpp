// SPDX-License-Identifier: GPL-3.0-or-later
#include "backdrop.h"
#include "guard.h"

#include <QDBusConnection>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusUnixFileDescriptor>
#include <QElapsedTimer>
#include <QGuiApplication>
#include <QQuickWindow>
#include <QScreen>
#include <QPointer>
#include <QThread>
#include <QUrl>
#include <cmath>
#include <fcntl.h>
#include <memory>
#include <unistd.h>
#include <vector>

#include "theme.h"
#include "tokens.h"

namespace
{
// Separable Gaussian taps.
std::vector<float> kernel(double sigma, int &radius)
{
    radius = std::max(1, int(std::ceil(3 * sigma)));
    std::vector<float> k(2 * radius + 1);
    double sum = 0;
    for (int i = -radius; i <= radius; ++i)
        sum += k[i + radius] = float(std::exp(-double(i) * i / (2 * sigma * sigma)));
    for (float &v : k)
        v = float(v / sum);
    return k;
}
// In-place-free separable blur of a w x h RGB float image, edges clamped (the screen's last pixels).
void blur(std::vector<float> &img, int w, int h, double sigma)
{
    int r = 0;
    const auto k = kernel(sigma, r);
    std::vector<float> tmp(img.size());
    for (int y = 0; y < h; ++y)
        for (int x = 0; x < w; ++x)
            for (int c = 0; c < 3; ++c) {
                float acc = 0;
                for (int j = -r; j <= r; ++j)
                    acc += k[j + r] * img[(size_t(y) * w + std::clamp(x - j, 0, w - 1)) * 3 + c];
                tmp[(size_t(y) * w + x) * 3 + c] = acc;
            }
    for (int y = 0; y < h; ++y)
        for (int x = 0; x < w; ++x)
            for (int c = 0; c < 3; ++c) {
                float acc = 0;
                for (int j = -r; j <= r; ++j)
                    acc += k[j + r] * tmp[(size_t(std::clamp(y - j, 0, h - 1)) * w + x) * 3 + c];
                img[(size_t(y) * w + x) * 3 + c] = acc;
            }
}

// W3C non-separable blend helpers (what Direct2D's blend effect implements), as core/acrylic.cpp.
struct Rgb { float r, g, b; };
inline float lum(Rgb c) { return 0.3f * c.r + 0.59f * c.g + 0.11f * c.b; }
inline Rgb clipColor(Rgb c)
{
    const float l = lum(c), n = std::min({c.r, c.g, c.b}), x = std::max({c.r, c.g, c.b});
    if (n < 0) {
        const float s = l / (l - n);
        c = {l + (c.r - l) * s, l + (c.g - l) * s, l + (c.b - l) * s};
    }
    if (x > 1) {
        const float s = (1 - l) / (x - l);
        c = {l + (c.r - l) * s, l + (c.g - l) * s, l + (c.b - l) * s};
    }
    return c;
}
inline Rgb setLum(Rgb c, float l)
{
    const float d = l - lum(c);
    return clipColor({c.r + d, c.g + d, c.b + d});
}
inline Rgb mix(Rgb a, Rgb b, float t) { return {a.r + (b.r - a.r) * t, a.g + (b.g - a.g) * t, a.b + (b.b - a.b) * t}; }
// The taskbar's noise texture (core/acrylic.cpp): grey, uniform, 256 x 256, tiled on the screen.
inline float noiseAt(int x, int y)
{
    quint32 h = quint32(x & 255) * 374761393u + quint32(y & 255) * 668265263u;
    h = (h ^ (h >> 13)) * 1274126177u;
    return float((h ^ (h >> 16)) & 255) / 255.f;
}
const std::vector<quint8> &noiseTile()
{
    static const std::vector<quint8> tile = [] {
        std::vector<quint8> t(256 * 256);
        for (int y = 0; y < 256; ++y)
            for (int x = 0; x < 256; ++x)
                t[y * 256 + x] = quint8(noiseAt(x, y) * 255.f);
        return t;
    }();
    return tile;
}

// over: a plain colour composited last (alpha "over"), for materials that are a translucent fill
// over a blur rather than WinUI's acrylic (Samsung's OSD: #2C2C2C at 60 % over DWM's blur-behind).
struct Recipe { Rgb tint; float tintOpacity, luminosityOpacity, noise; Rgb over; float overOpacity; };
Recipe recipe(const QString &name, bool dark)
{
    auto *t = Tokens::instance();
    const QString k = QStringLiteral("acrylic.") + name + QStringLiteral(".backdrop."), s = dark ? QStringLiteral(".dark") : QStringLiteral(".light");
    // Defaults: Start's body (user-win11 160039), see design/tokens.json.
    const QColor c(t->v(k + QStringLiteral("tint") + s, dark ? "#292929" : "#f3f3f3").toString());
    const QColor over(t->opt(k + QStringLiteral("over") + s, "#00000000").toString());
    return {{float(c.redF()), float(c.greenF()), float(c.blueF())},
            float(t->v(k + QStringLiteral("tint.opacity") + s, dark ? 0.5 : 0.0).toDouble()),
            float(t->v(k + QStringLiteral("luminosity.opacity") + s, dark ? 0.96 : 0.9).toDouble()),
            float(t->v(QStringLiteral("acrylic.backdrop.noise"), 0.02).toDouble()),
            {float(over.redF()), float(over.greenF()), float(over.blueF())}, float(over.alphaF())};
}

// The wallpaper as Desktop.qml draws it (cover-scaled, centred) at the screen's device size.
QImage wallpaperImage(const QString &source, QSize device)
{
    static QMutex lock;
    static QString cachedSource;
    static QSize cachedSize;
    static QImage cached;
    QMutexLocker l(&lock);
    if (source == cachedSource && device == cachedSize)
        return cached;
    QImage out(device, QImage::Format_RGB32);
    if (source.startsWith(QLatin1Char('#'))) {
        out.fill(QColor(source));
    } else {
        const QImage wp(source.startsWith(QLatin1String("file:")) ? QUrl(source).toLocalFile() : source);
        if (wp.isNull()) {
            out.fill(Qt::black);
        } else {
            const QImage cover = wp.scaled(device, Qt::KeepAspectRatioByExpanding, Qt::SmoothTransformation);
            out = cover.copy((cover.width() - device.width()) / 2, (cover.height() - device.height()) / 2, device.width(), device.height())
                      .convertToFormat(QImage::Format_RGB32);
        }
    }
    cachedSource = source;
    cachedSize = device;
    cached = out;
    return out;
}
}

Backdrop *Backdrop::instance()
{
    static auto *self = new Backdrop(QGuiApplication::instance());
    return self;
}

QImage Backdrop::image(int id, const QString &recipe) const
{
    QMutexLocker l(&m_lock);
    return m_images.value(id).value(recipe);
}

QRectF Backdrop::area(int id) const
{
    QMutexLocker l(&m_lock);
    return m_areas.value(id);
}

void Backdrop::release(int id)
{
    QMutexLocker l(&m_lock);
    m_images.remove(id);
    m_areas.remove(id);
}

int Backdrop::request(QWindow *window, const QRectF &rect, const QString &wallpaper, const QStringList &recipes, QWindow *under,
                      const QRectF &underRect)
{
    if (!window || rect.isEmpty() || recipes.isEmpty())
        return 0;
    QScreen *screen = window->screen();
    if (!screen)
        return 0;
    auto timer = std::make_shared<QElapsedTimer>();
    timer->start();
    const int id = ++m_next;
    const bool dark = Theme::instance()->dark();
    const double sigma = Tokens::instance()->v(QStringLiteral("acrylic.backdrop.blur"), 30).toDouble();
    const QRect screenRect(QPoint(0, 0), screen->geometry().size());
    // What reaches `rect` through the blur, inside the screen (whose edges extend their pixels).
    const int margin = int(std::ceil(3 * sigma));
    const QRect cap = rect.toAlignedRect().adjusted(-margin, -margin, margin, margin) & screenRect;
    const QRect out = rect.toAlignedRect() & screenRect;
    if (cap.isEmpty() || out.isEmpty())
        return 0;
    // A shell window this popup opens over (hidden from the capture with the rest of the shell).
    QImage underImage;
    QRectF underArea;
    if (auto *qw = qobject_cast<QQuickWindow *>(under); qw && qw->isVisible() && !underRect.isEmpty()) {
        underImage = qw->grabWindow().convertToFormat(QImage::Format_ARGB32_Premultiplied);
        underArea = underRect;
    }

    int fds[2];
    if (pipe2(fds, O_CLOEXEC) != 0)
        return 0;
    const QPoint g = screen->geometry().topLeft() + cap.topLeft();
    QDBusMessage msg = QDBusMessage::createMethodCall(QStringLiteral("org.kde.KWin.ScreenShot2"), QStringLiteral("/org/kde/KWin/ScreenShot2"),
                                                      QStringLiteral("org.kde.KWin.ScreenShot2"), QStringLiteral("CaptureArea"));
    msg << g.x() << g.y() << uint(cap.width()) << uint(cap.height())
        << QVariantMap{{QStringLiteral("include-cursor"), false}, {QStringLiteral("native-resolution"), false},
                       {QStringLiteral("hide-caller-windows"), true}}
        << QVariant::fromValue(QDBusUnixFileDescriptor(fds[1]));
    ::close(fds[1]);
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
    // The reply comes before the pipe's end: the pending call still holds our copy of the write
    // end (the sent message), so the data is complete only once the watcher is gone and the reader
    // has seen EOF; never block the GUI thread on it.
    connect(w, &QDBusPendingCallWatcher::finished, this, [=, this](QDBusPendingCallWatcher *w) {
        w->deleteLater();
        QDBusPendingReply<QVariantMap> r = *w;
        if (!r.isValid()) {
            qWarning("fenestra-shell: ScreenShot2.CaptureArea failed: %s", qPrintable(r.error().message()));
            connect(reader, &QThread::finished, reader, &QObject::deleteLater);
            Q_EMIT failed(id);
            return;
        }
        const QVariantMap meta = r.value();
        auto process = [=, this] {
        reader->deleteLater();
        const int width = meta.value(QStringLiteral("width")).toInt(), height = meta.value(QStringLiteral("height")).toInt();
        const int stride = meta.value(QStringLiteral("stride")).toInt();
        const auto format = QImage::Format(meta.value(QStringLiteral("format")).toInt());
        if (width <= 0 || height <= 0 || data->size() < qsizetype(stride) * height) {
            Q_EMIT failed(id);
            return;
        }
        const QImage shot = QImage(reinterpret_cast<const uchar *>(data->constData()), width, height, stride, format)
                                .convertToFormat(QImage::Format_ARGB32_Premultiplied);
        const qint64 captured = timer->elapsed();
        // Worker: compose, blur, recipes. The capture is logical-resolution (a quarter of the data
        // at 150 %, and what the 30 px blur leaves of it is the same); everything up to the recipe
        // runs on a 4 x smaller grid, then the result is scaled to device pixels and the noise is
        // added there.
        QThread *worker = QThread::create([=, this] {
            const double sx = double(shot.width()) / cap.width(), sy = double(shot.height()) / cap.height();
            const int W = shot.width(), H = shot.height();
            const QImage wp = wallpaperImage(wallpaper, QSize(qRound(screenRect.width() * sx), qRound(screenRect.height() * sy)));
            const int ox = qRound(cap.x() * sx), oy = qRound(cap.y() * sy);
            const int f = std::max(1, int(sigma * sx / 4));   // σ 30 -> a 7 px grid, σ 4.3 on it
            const int ws = (W + f - 1) / f, hs = (H + f - 1) / f;
            std::vector<float> small(size_t(ws) * hs * 3, 0.f);
            std::vector<float> count(size_t(ws) * hs, 0.f);
            for (int y = 0; y < H; ++y) {
                const QRgb *s = reinterpret_cast<const QRgb *>(shot.constScanLine(y));
                const QRgb *bg = oy + y < wp.height() ? reinterpret_cast<const QRgb *>(wp.constScanLine(oy + y)) : nullptr;
                float *row = &small[size_t(y / f) * ws * 3];
                float *cnt = &count[size_t(y / f) * ws];
                for (int x = 0; x < W; ++x) {
                    const QRgb b = bg && ox + x < wp.width() ? bg[ox + x] : qRgb(0, 0, 0);
                    const float t = (255 - qAlpha(s[x])) / 255.f;   // premultiplied shot over the wallpaper
                    float *p = row + (x / f) * 3;
                    p[0] += qRed(s[x]) + qRed(b) * t; p[1] += qGreen(s[x]) + qGreen(b) * t; p[2] += qBlue(s[x]) + qBlue(b) * t;
                    cnt[x / f] += 1;
                }
            }
            if (!underImage.isNull()) {
                // The popup underneath (premultiplied, its own device pixels) over the rest, on the grid.
                const QRect dst(qRound((underArea.x() - cap.x()) * sx), qRound((underArea.y() - cap.y()) * sy),
                                qRound(underArea.width() * sx), qRound(underArea.height() * sy));
                const QImage u = underImage.scaled(dst.size(), Qt::IgnoreAspectRatio, Qt::SmoothTransformation);
                std::vector<float> ua(size_t(ws) * hs, 0.f), uc(size_t(ws) * hs * 3, 0.f);
                for (int y = std::max(0, dst.top()); y < std::min(H, dst.top() + u.height()); ++y) {
                    const QRgb *s = reinterpret_cast<const QRgb *>(u.constScanLine(y - dst.top()));
                    for (int x = std::max(0, dst.left()); x < std::min(W, dst.left() + u.width()); ++x) {
                        const QRgb q = s[x - dst.left()];
                        const size_t i = size_t(y / f) * ws + x / f;
                        ua[i] += qAlpha(q) / 255.f;
                        uc[i * 3] += qRed(q); uc[i * 3 + 1] += qGreen(q); uc[i * 3 + 2] += qBlue(q);
                    }
                }
                for (size_t i = 0; i < ua.size(); ++i) {
                    if (count[i] <= 0)
                        continue;
                    const float a = ua[i] / count[i];
                    for (int c = 0; c < 3; ++c)
                        small[i * 3 + c] = uc[i * 3 + c] + small[i * 3 + c] * (1 - a);
                }
            }
            for (size_t i = 0; i < count.size(); ++i)
                for (int c = 0; c < 3; ++c)
                    small[i * 3 + c] /= 255.f * std::max(1.f, count[i]);
            const qint64 tCompose = timer->elapsed();
            blur(small, ws, hs, sigma * sx / f);
            const qint64 tBlur = timer->elapsed();
            // The images stay on the grid (one pixel per f capture px): the popup scales them
            // (bilinear, on the GPU) and adds the noise texture at device pixels (image://backdrop/noise).
            const QRectF area(cap.x(), cap.y(), ws * f / sx, hs * f / sy);
            QHash<QString, QImage> images;
            for (const QString &name : recipes) {
                const Recipe rc = recipe(name, dark);
                const float tintLum = lum(rc.tint);
                QImage grid(ws, hs, QImage::Format_RGB32);
                for (int y = 0; y < hs; ++y) {
                    QRgb *line = reinterpret_cast<QRgb *>(grid.scanLine(y));
                    for (int x = 0; x < ws; ++x) {
                        const float *v = &small[(size_t(y) * ws + x) * 3];
                        const Rgb b{v[0], v[1], v[2]};
                        const Rgb s1 = mix(b, setLum(b, tintLum), rc.luminosityOpacity);
                        const Rgb s2 = mix(mix(s1, setLum(rc.tint, lum(s1)), rc.tintOpacity), rc.over, rc.overOpacity);
                        auto q = [](float u) { return std::clamp(int(std::lround(u * 255.f)), 0, 255); };
                        line[x] = qRgb(q(s2.r), q(s2.g), q(s2.b));
                    }
                }
                images.insert(name, grid);
            }
            {
                QMutexLocker l(&m_lock);
                m_images.insert(id, images);
                m_areas.insert(id, area);
            }
            const qreal ms = timer->elapsed();
            QMetaObject::invokeMethod(this, [this, id, ms, captured, tCompose, tBlur] {
                if (qEnvironmentVariableIntValue("FENESTRA_SHELL_TEST") == 1)
                    qInfo("FENESTRA_BACKDROP id=%d capture=%lldms compose=%lld blur=%lld total=%.0fms", id, captured, tCompose, tBlur, ms);
                Q_EMIT ready(id, ms);
            }, Qt::QueuedConnection);
        });
        connect(worker, &QThread::finished, worker, &QObject::deleteLater);
        worker->start();
        };
        if (reader->isFinished())
            process();
        else
            connect(reader, &QThread::finished, this, process);
    });
    reader->start();
    return id;
}

QImage BackdropProvider::requestImage(const QString &id, QSize *size, const QSize &)
try {
    // <id>/<recipe>, or noise/<dpr>: the 256 x 256 device px noise tile (the taskbar's texture).
    const QStringList p = id.split(QLatin1Char('/'));
    QImage img;
    if (p.value(0) == QLatin1String("noise")) {
        img = QImage(256, 256, QImage::Format_RGB32);
        const quint8 *t = noiseTile().data();
        for (int y = 0; y < 256; ++y)
            for (int x = 0; x < 256; ++x)
                img.setPixel(x, y, qRgb(t[y * 256 + x], t[y * 256 + x], t[y * 256 + x]));
        img.setDevicePixelRatio(std::max(0.5, p.value(1).toDouble()));
    } else if (p.size() >= 2) {
        img = Backdrop::instance()->image(p[0].toInt(), p[1]);
    }
    if (size)
        *size = img.size();
    return img;
} catch (...) {
    return providerFailed("BackdropProvider", id, size);
}
