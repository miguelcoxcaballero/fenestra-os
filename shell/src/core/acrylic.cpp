// SPDX-License-Identifier: GPL-3.0-or-later
#include "acrylic.h"

#include <QPainter>
#include <QtMath>
#include <QQuickWindow>
#include <QTextLayout>
#include <QUrl>
#include <cmath>
#include <vector>

#include "tokens.h"

namespace
{
// Separable Gaussian taps, centre displaced by `off` px (a positive off moves the result right/down).
std::vector<float> kernel(qreal sigma, qreal off, int &radius)
{
    radius = std::max(1, int(std::ceil(3 * sigma + std::abs(off))));
    std::vector<float> k(2 * radius + 1);
    double sum = 0;
    for (int i = -radius; i <= radius; ++i) {
        const double x = i - off;
        sum += k[i + radius] = float(std::exp(-x * x / (2 * sigma * sigma)));
    }
    for (float &v : k)
        v = float(v / sum);
    return k;
}

// out[y][x] = Σ k[j] · in[clamp(y)][clamp(x - j)]   (edges clamped; `clamp` false = zero outside)
void blurRows(const std::vector<float> &in, std::vector<float> &out, int w, int h, int ch,
              const std::vector<float> &k, int r, bool clamp)
{
    out.assign(size_t(w) * h * ch, 0.f);
    for (int y = 0; y < h; ++y)
        for (int x = 0; x < w; ++x)
            for (int c = 0; c < ch; ++c) {
                float acc = 0;
                for (int j = -r; j <= r; ++j) {
                    int sx = x - j;
                    if (sx < 0 || sx >= w) {
                        if (!clamp)
                            continue;
                        sx = std::clamp(sx, 0, w - 1);
                    }
                    acc += k[j + r] * in[(size_t(y) * w + sx) * ch + c];
                }
                out[(size_t(y) * w + x) * ch + c] = acc;
            }
}

void blurCols(const std::vector<float> &in, std::vector<float> &out, int w, int h, int ch,
              const std::vector<float> &k, int r, bool clamp, int y0 = 0, int rows = -1)
{
    if (rows < 0)
        rows = h;
    out.assign(size_t(w) * rows * ch, 0.f);
    for (int y = 0; y < rows; ++y)
        for (int j = -r; j <= r; ++j) {
            int sy = y0 + y - j;
            if (sy < 0 || sy >= h) {
                if (!clamp)
                    continue;
                sy = std::clamp(sy, 0, h - 1);
            }
            const float kw = k[j + r];
            const float *src = &in[size_t(sy) * w * ch];
            float *dst = &out[size_t(y) * w * ch];
            for (int i = 0; i < w * ch; ++i)
                dst[i] += kw * src[i];
        }
}

// W3C compositing: non-separable blend helpers (the ones Direct2D's blend effect implements).
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

// Fenestra's own noise texture (not Microsoft's asset): grey, uniform, 256×256, tiled.
inline float noiseAt(int x, int y)
{
    quint32 h = quint32(x & 255) * 374761393u + quint32(y & 255) * 668265263u;
    h = (h ^ (h >> 13)) * 1274126177u;
    return float((h ^ (h >> 16)) & 255) / 255.f;
}
}

namespace Acrylic
{
Recipe taskbarRecipe(bool dark)
{
    auto *t = Tokens::instance();
    const QString s = dark ? QStringLiteral(".dark") : QStringLiteral(".light");
    Recipe r;
    r.tint = QColor(t->v(QStringLiteral("taskbar.acrylic.tint") + s, dark ? "#202020" : "#f3f3f3").toString());
    r.tintOpacity = t->v(QStringLiteral("taskbar.acrylic.tint.opacity") + s, dark ? 0.5 : 0.0).toDouble();
    r.luminosityOpacity = t->v(QStringLiteral("taskbar.acrylic.luminosity.opacity") + s, dark ? 0.96 : 0.90).toDouble();
    r.blur = t->v(QStringLiteral("taskbar.acrylic.blur"), 30).toDouble();
    r.noise = t->v(QStringLiteral("taskbar.acrylic.noise.opacity"), 0.02).toDouble();
    return r;
}

QImage renderStrip(const QString &source, QSize screen, int strip, qreal dpr, const Recipe &rc)
{
    if (screen.isEmpty() || strip <= 0)
        return {};
    strip = std::min(strip, screen.height());
    const int w = screen.width();
    const qreal sigma = rc.blur * dpr;
    const int r = int(std::ceil(3 * sigma));
    // Rows of the backdrop that reach the strip through the blur: [top, screen.height()).
    const int top = std::max(0, screen.height() - strip - r);
    const int h = screen.height() - top;
    std::vector<float> img(size_t(w) * h * 3);
    if (source.startsWith(QLatin1Char('#'))) {
        const QColor c(source);
        for (size_t i = 0; i < img.size(); i += 3) {
            img[i] = float(c.redF()); img[i + 1] = float(c.greenF()); img[i + 2] = float(c.blueF());
        }
    } else {
        QImage wp(source);
        if (wp.isNull())
            return {};
        // Desktop.qml: Image.PreserveAspectCrop, centred, same size as the screen.
        const QImage cover = wp.scaled(screen, Qt::KeepAspectRatioByExpanding, Qt::SmoothTransformation);
        const int ox = (cover.width() - w) / 2, oy = (cover.height() - screen.height()) / 2;
        const QImage band = cover.copy(ox, oy + top, w, h).convertToFormat(QImage::Format_RGB32);
        for (int y = 0; y < h; ++y) {
            const QRgb *line = reinterpret_cast<const QRgb *>(band.constScanLine(y));
            for (int x = 0; x < w; ++x) {
                float *p = &img[(size_t(y) * w + x) * 3];
                p[0] = qRed(line[x]) / 255.f; p[1] = qGreen(line[x]) / 255.f; p[2] = qBlue(line[x]) / 255.f;
            }
        }
    }
    // Blur: the screen edges extend their last pixels (nothing is drawn beyond the output).
    // σ = 30 px is wide: blurring a 4× box-downsampled copy with σ/4 and sampling it bilinearly
    // differs from the full-resolution blur by < 0.5 level and is ~50× faster (a theme or
    // wallpaper change must not leave the fallback colour on screen for seconds).
    const int f = sigma >= 8 ? 4 : 1;
    const int ws = (w + f - 1) / f, hs = (h + f - 1) / f;
    std::vector<float> small(size_t(ws) * hs * 3, 0.f);
    for (int sy = 0; sy < hs; ++sy)
        for (int sx = 0; sx < ws; ++sx)
            for (int c = 0; c < 3; ++c) {
                float acc = 0; int n = 0;
                for (int y = sy * f; y < std::min(h, sy * f + f); ++y)
                    for (int x = sx * f; x < std::min(w, sx * f + f); ++x, ++n)
                        acc += img[(size_t(y) * w + x) * 3 + c];
                small[(size_t(sy) * ws + sx) * 3 + c] = acc / n;
            }
    int rs = 0;
    const std::vector<float> ks = kernel(sigma / f, 0, rs);
    std::vector<float> tmp, sb;
    blurRows(small, tmp, ws, hs, 3, ks, rs, true);
    blurCols(tmp, sb, ws, hs, 3, ks, rs, true);
    std::vector<float> blurred(size_t(w) * strip * 3);
    for (int y = 0; y < strip; ++y) {
        const float fy = std::clamp((h - strip + y + 0.5f) / f - 0.5f, 0.f, float(hs - 1));
        const int y0 = int(fy), y1 = std::min(y0 + 1, hs - 1);
        const float ty = fy - y0;
        for (int x = 0; x < w; ++x) {
            const float fx = std::clamp((x + 0.5f) / f - 0.5f, 0.f, float(ws - 1));
            const int x0 = int(fx), x1 = std::min(x0 + 1, ws - 1);
            const float tx = fx - x0;
            for (int c = 0; c < 3; ++c) {
                auto at = [&](int yy, int xx) { return sb[(size_t(yy) * ws + xx) * 3 + c]; };
                blurred[(size_t(y) * w + x) * 3 + c] = (at(y0, x0) * (1 - tx) + at(y0, x1) * tx) * (1 - ty)
                                                     + (at(y1, x0) * (1 - tx) + at(y1, x1) * tx) * ty;
            }
        }
    }

    const Rgb tint{float(rc.tint.redF()), float(rc.tint.greenF()), float(rc.tint.blueF())};
    const float tintLum = lum(tint), aL = float(rc.luminosityOpacity), aT = float(rc.tintOpacity), aN = float(rc.noise);
    QImage out(w, strip, QImage::Format_RGB32);
    for (int y = 0; y < strip; ++y) {
        QRgb *line = reinterpret_cast<QRgb *>(out.scanLine(y));
        for (int x = 0; x < w; ++x) {
            const float *p = &blurred[(size_t(y) * w + x) * 3];
            const Rgb b{p[0], p[1], p[2]};
            const Rgb s1 = mix(b, setLum(b, tintLum), aL);         // luminosity of the tint
            const Rgb s2 = mix(s1, setLum(tint, lum(s1)), aT);     // hue and saturation of the tint
            const float n = noiseAt(x, y);
            const Rgb o = mix(s2, Rgb{n, n, n}, aN);
            auto q = [](float v) { return std::clamp(int(std::lround(v * 255.f)), 0, 255); };
            line[x] = qRgb(q(o.r), q(o.g), q(o.b));
        }
    }
    out.setDevicePixelRatio(dpr);
    return out;
}

QImage shadowMask(const QImage &alpha8, qreal sigma, qreal dx, qreal dy, qreal strength)
{
    const int w = alpha8.width(), h = alpha8.height();
    std::vector<float> m(size_t(w) * h);
    for (int y = 0; y < h; ++y) {
        const uchar *line = alpha8.constScanLine(y);
        for (int x = 0; x < w; ++x)
            m[size_t(y) * w + x] = line[x] / 255.f;
    }
    int rx = 0, ry = 0;
    const auto kx = kernel(sigma, dx, rx), ky = kernel(sigma, dy, ry);
    std::vector<float> t, b;
    blurRows(m, t, w, h, 1, kx, rx, false);
    blurCols(t, b, w, h, 1, ky, ry, false);
    QImage out(w, h, QImage::Format_Alpha8);
    for (int y = 0; y < h; ++y) {
        uchar *line = out.scanLine(y);
        for (int x = 0; x < w; ++x)
            line[x] = uchar(std::clamp(int(std::lround(b[size_t(y) * w + x] * strength * 255.f)), 0, 255));
    }
    return out;
}
}

QImage AcrylicProvider::requestImage(const QString &id, QSize *size, const QSize &)
{
    // dark/1920/1080/48/1/<source>
    const QStringList p = id.split(QLatin1Char('/'));
    QImage img;
    if (p.size() >= 6) {
        const QString source = QUrl::fromPercentEncoding(p.mid(5).join(QLatin1Char('/')).toUtf8());
        const qreal dpr = std::max(0.5, p[4].toDouble());
        const QSize screen(qRound(p[1].toInt() * dpr), qRound(p[2].toInt() * dpr));
        img = Acrylic::renderStrip(source, screen, qRound(p[3].toInt() * dpr), dpr,
                                   Acrylic::taskbarRecipe(p[0] != QLatin1String("light")));
    }
    if (size)
        *size = img.size();
    return img;
}

ShadowLabel::ShadowLabel(QQuickItem *parent)
    : QQuickPaintedItem(parent)
{
    setAntialiasing(true);
}

void ShadowLabel::geometryChange(const QRectF &n, const QRectF &o)
{
    QQuickPaintedItem::geometryChange(n, o);
    if (n.width() != o.width())
        relayout();
}

void ShadowLabel::relayout()
{
    QStringList lines;
    const qreal avail = width() - 2 * m_pad;
    int widest = 0;
    if (avail > 0 && !m_text.isEmpty()) {
        const QFontMetricsF fm(m_font);
        QTextLayout layout(m_text, m_font);
        QTextOption opt;
        opt.setWrapMode(QTextOption::WrapAtWordBoundaryOrAnywhere);
        layout.setTextOption(opt);
        layout.beginLayout();
        for (QTextLine l = layout.createLine(); l.isValid(); l = layout.createLine()) {
            l.setLineWidth(avail);
            if (m_maxLines > 0 && lines.size() == m_maxLines - 1) {
                // Last allowed line: the rest of the text, with "…" if it does not fit.
                const QString rest = m_text.mid(l.textStart());
                lines << fm.elidedText(rest, Qt::ElideRight, avail);
                break;
            }
            lines << m_text.mid(l.textStart(), l.textLength()).trimmed();
        }
        layout.endLayout();
        for (const QString &s : std::as_const(lines))
            widest = std::max(widest, int(std::ceil(fm.horizontalAdvance(s))));
    }
    m_lines = lines;
    m_textWidth = widest;
    setImplicitHeight(m_lines.size() * m_lineHeight + 2 * m_pad);
    m_cache = QImage();
    Q_EMIT layoutChanged();
    update();
}

void ShadowLabel::paint(QPainter *painter)
{
    const qreal dpr = window() ? window()->effectiveDevicePixelRatio() : 1.0;
    const QSize dev(qCeil(width() * dpr), qCeil(height() * dpr));
    if (dev.isEmpty() || m_lines.isEmpty())
        return;
    if (m_cache.size() != dev) {
        // Text alone, then its shadow under it.
        QImage text(dev, QImage::Format_ARGB32_Premultiplied);
        text.fill(Qt::transparent);
        text.setDevicePixelRatio(dpr);
        {
            QPainter p(&text);
            p.setRenderHint(QPainter::TextAntialiasing);
            p.setFont(m_font);
            p.setPen(m_color);
            const QFontMetricsF fm(m_font);
            // Each line box is lineHeight tall; the font's ascent+descent is centred in it.
            const qreal base = (m_lineHeight - (fm.ascent() + fm.descent())) / 2 + fm.ascent();
            for (int i = 0; i < m_lines.size(); ++i) {
                const qreal lw = fm.horizontalAdvance(m_lines[i]);
                p.drawText(QPointF(m_pad + (width() - 2 * m_pad - lw) / 2, m_pad + i * m_lineHeight + base), m_lines[i]);
            }
        }
        const QImage mask = Acrylic::shadowMask(text.convertToFormat(QImage::Format_Alpha8), m_shadowBlur * dpr,
                                                m_shadowX * dpr, m_shadowY * dpr, m_shadowStrength * m_shadowColor.alphaF());
        m_cache = QImage(dev, QImage::Format_ARGB32_Premultiplied);
        m_cache.fill(Qt::transparent);
        {
            QPainter p(&m_cache);
            QImage shadow(dev, QImage::Format_ARGB32_Premultiplied);
            shadow.fill(QColor(m_shadowColor.red(), m_shadowColor.green(), m_shadowColor.blue()));
            QPainter sp(&shadow);
            sp.setCompositionMode(QPainter::CompositionMode_DestinationIn);
            sp.drawImage(0, 0, mask);
            sp.end();
            p.drawImage(0, 0, shadow);
            text.setDevicePixelRatio(1);
            p.drawImage(0, 0, text);
        }
        m_cache.setDevicePixelRatio(dpr);
    }
    painter->drawImage(QRectF(0, 0, width(), height()), m_cache);
}
