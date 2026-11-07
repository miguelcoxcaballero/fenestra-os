// SPDX-License-Identifier: GPL-3.0-or-later
// Taskbar acrylic (B01) and desktop label shadow (D01), drawn on the CPU so that they look the
// same with the GPU session and in the software-rendered KWin bench (tests/shell-kwin).
//
// Acrylic: Microsoft's documented recipe (WinUI AcrylicBrush, "AcrylicBackgroundFillColorBase",
// the brush whose FallbackColor #1C1C1C / #EEEEEE is exactly the taskbar colour of the
// reference shots, taken with transparency effects unavailable — the VM had no GPU):
//   backdrop → Gaussian blur (BlurAmount 30 = σ in DIPs)
//            → luminosity blend with TintColor at TintLuminosityOpacity
//            → color blend with TintColor at TintOpacity
//            → noise texture at 2 % opacity.
// Dark: TintColor #202020, TintOpacity 0.5, TintLuminosityOpacity 0.96.
// Light: TintColor #F3F3F3, TintOpacity 0, TintLuminosityOpacity 0.90.
// (WinUI's effect graph names the two blend modes the other way round — a known Composition
// bug noted in AcrylicBrush.cpp; the maths below is what it renders.)
// The backdrop is the wallpaper as Desktop.qml draws it (cover-scaled): maximized windows stop
// above the taskbar (exclusion zone), so behind it there is only the wallpaper.
#pragma once

#include <QColor>
#include <QFont>
#include <QImage>
#include <QQuickImageProvider>
#include <QQuickItem>

namespace Acrylic
{
struct Recipe {
    QColor tint;
    qreal tintOpacity = 0;
    qreal luminosityOpacity = 0;
    qreal blur = 30;      // Gaussian σ in logical px
    qreal noise = 0.02;   // opacity of the noise layer
};
Recipe taskbarRecipe(bool dark);
// Bottom strip (stripHeight device px) of a screen (screenSize device px) whose backdrop is the
// wallpaper `source` (file path) or a flat colour ("#rrggbb").
QImage renderStrip(const QString &source, QSize screenSize, int stripHeight, qreal dpr, const Recipe &r);
// Gaussian blur of an alpha mask, centre displaced by (dx, dy) px, multiplied by `strength`.
QImage shadowMask(const QImage &alpha8, qreal sigma, qreal dx, qreal dy, qreal strength);
}

// image://acrylic/<dark|light>/<width>/<height>/<strip>/<dpr>/<percent-encoded source>
class AcrylicProvider : public QQuickImageProvider
{
public:
    AcrylicProvider() : QQuickImageProvider(QQuickImageProvider::Image) {}
    QImage requestImage(const QString &id, QSize *size, const QSize &requested) override;
};

// Desktop icon label: centred, word-wrapped, at most maxLines (ellipsis on the last one), with
// the blurred drop shadow of Windows' desktop labels. The shadow needs room around the text, so
// the item is `pad` px larger than the text box on each side.
// The text is laid out and drawn in device pixels (the font at its device size, fully hinted
// there, every line on whole device pixels) and the result is placed on whole device pixels
// of the window: laying it out at the logical size and scaling it, as Qt Quick text does at
// fractional scales, spreads the letters apart and blurs every stem. `gamma` > 1 thickens the
// greyscale coverage towards the weight of Windows' ClearType labels. The shadow's blur and
// offset are device pixels, as Windows draws it at every scale.
class ShadowLabel : public QQuickItem
{
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(QString text READ text WRITE setText NOTIFY layoutChanged)
    Q_PROPERTY(QFont font READ font WRITE setFont NOTIFY layoutChanged)
    Q_PROPERTY(QColor color MEMBER m_color WRITE setColor NOTIFY styleChanged)
    Q_PROPERTY(int maxLines MEMBER m_maxLines WRITE setMaxLines NOTIFY layoutChanged)
    // Line pitch in logical px; lineHeightDevice (> 0) overrides it in device px.
    Q_PROPERTY(qreal lineHeight MEMBER m_lineHeight WRITE setLineHeight NOTIFY layoutChanged)
    Q_PROPERTY(int lineHeightDevice MEMBER m_lineHeightDevice WRITE setLineHeightDevice NOTIFY layoutChanged)
    Q_PROPERTY(int pad MEMBER m_pad WRITE setPad NOTIFY padChanged)
    Q_PROPERTY(QColor shadowColor MEMBER m_shadowColor WRITE setShadowColor NOTIFY styleChanged)
    Q_PROPERTY(qreal shadowBlur MEMBER m_shadowBlur WRITE setShadowBlur NOTIFY styleChanged)
    Q_PROPERTY(qreal shadowX MEMBER m_shadowX WRITE setShadowX NOTIFY styleChanged)
    Q_PROPERTY(qreal shadowY MEMBER m_shadowY WRITE setShadowY NOTIFY styleChanged)
    Q_PROPERTY(qreal shadowStrength MEMBER m_shadowStrength WRITE setShadowStrength NOTIFY styleChanged)
    Q_PROPERTY(qreal gamma MEMBER m_gamma WRITE setGamma NOTIFY styleChanged)
    Q_PROPERTY(int lineCount READ lineCount NOTIFY layoutChanged)
    Q_PROPERTY(int textWidth READ textWidth NOTIFY layoutChanged)   // widest line, logical px
    Q_PROPERTY(qreal textHeight READ textHeight NOTIFY layoutChanged) // lines x pitch, logical px
    // The window's real (fractional) scale; Screen.devicePixelRatio is the screen's integer one.
    Q_PROPERTY(qreal devicePixelRatio READ devicePixelRatio NOTIFY layoutChanged)
public:
    explicit ShadowLabel(QQuickItem *parent = nullptr);

    QString text() const { return m_text; }
    void setText(const QString &t) { if (t != m_text) { m_text = t; relayout(); } }
    QFont font() const { return m_font; }
    void setFont(const QFont &f) { if (f != m_font) { m_font = f; relayout(); } }
    void setColor(const QColor &c) { if (c != m_color) { m_color = c; restyle(); } }
    void setMaxLines(int n) { if (n != m_maxLines) { m_maxLines = n; relayout(); } }
    void setLineHeight(qreal n) { if (n != m_lineHeight) { m_lineHeight = n; relayout(); } }
    void setLineHeightDevice(int n) { if (n != m_lineHeightDevice) { m_lineHeightDevice = n; relayout(); } }
    void setPad(int n) { if (n != m_pad) { m_pad = n; Q_EMIT padChanged(); relayout(); } }
    void setShadowColor(const QColor &c) { if (c != m_shadowColor) { m_shadowColor = c; restyle(); } }
    void setShadowBlur(qreal v) { if (v != m_shadowBlur) { m_shadowBlur = v; restyle(); } }
    void setShadowX(qreal v) { if (v != m_shadowX) { m_shadowX = v; restyle(); } }
    void setShadowY(qreal v) { if (v != m_shadowY) { m_shadowY = v; restyle(); } }
    void setShadowStrength(qreal v) { if (v != m_shadowStrength) { m_shadowStrength = v; restyle(); } }
    void setGamma(qreal v) { if (v != m_gamma) { m_gamma = v; restyle(); } }
    int lineCount() const { return m_lines.size(); }
    int textWidth() const { return m_textWidth; }
    qreal devicePixelRatio() const { return m_dpr; }
    qreal textHeight() const { return m_dpr > 0 ? m_lines.size() * m_lineDev / m_dpr : 0; }

Q_SIGNALS:
    void layoutChanged();
    void padChanged();
    void styleChanged();

protected:
    void geometryChange(const QRectF &newGeometry, const QRectF &oldGeometry) override;
    void itemChange(ItemChange change, const ItemChangeData &value) override;
    QSGNode *updatePaintNode(QSGNode *old, UpdatePaintNodeData *) override;

private:
    void relayout();
    void restyle() { m_cache = QImage(); m_dirty = true; Q_EMIT styleChanged(); update(); }
    QImage render() const;
    qreal dpr() const;
    QString m_text;
    QFont m_font, m_devFont;
    QColor m_color = Qt::white, m_shadowColor = Qt::black;
    int m_maxLines = 2, m_pad = 6, m_textWidth = 0, m_lineHeightDevice = 0, m_lineDev = 15;
    qreal m_lineHeight = 15, m_dpr = 0;
    qreal m_shadowBlur = 1.6, m_shadowX = 0.5, m_shadowY = 1, m_shadowStrength = 1.7, m_gamma = 1;
    QStringList m_lines;
    QImage m_cache;
    bool m_dirty = true;
    QMetaObject::Connection m_px, m_py;
};
