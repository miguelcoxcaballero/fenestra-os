/*
    SPDX-License-Identifier: GPL-3.0-or-later

    Fenestra rounded corners (see corners.h).

    Every free-floating app window and dialog is drawn through an offscreen texture
    (OffscreenEffect) with a shader that works only inside the four corner squares of the window's
    frame (the frame geometry: Aurorae's frame for server-side decorations, the xdg window
    geometry for client-side ones, the client-drawn shadow stays outside it):

      - a pixel the window left translucent there (a toolkit that already rounds, its own shadow,
        Aurorae's round title-bar corners) is kept: the toolkit's own corner is not redrawn;
      - an opaque pixel (a square corner: Chromium/Electron, Qt, X11 apps, the client area under
        Aurorae's frame, an app snapped by the toolkit but not by KWin) is clipped to an 8 px
        (x scale) arc, antialiased, with a 1 px (x scale) ring in the colour of the window's own
        straight edge next to that corner (its border, so the curve keeps the border); what the
        window draws around a clipped corner (a toolkit's 1 px outline, its shadow) follows the
        curve too: at a distance d outside the arc it shows what lies d outside the straight side
        edge, so no square ring of outline is left at the corner.

    Snapped (KWin's quick tiles and custom tiles): drawn the same way, but square: corners a frame
    left round (Aurorae rounds its title bar unless the window is maximized; a toolkit that does
    not get the tiled state) are filled with the window's own row next to them.

    Unredirected (no offscreen copy, direct scan-out possible): maximized and full-screen windows
    (Aurorae and the toolkits square those themselves) and everything that is not an app window
    (shell surfaces, menus, tooltips, OSDs, lock screen).

    Caption buttons (hasCaption): Electron apps with titleBarStyle "hidden" + titleBarOverlay paint
    their own minimize / maximize / close (GNOME's circles, or Chromium's glyphs without GTK 3), in
    code no theme reaches. The same shader draws Windows' buttons over them, in the window's frame
    (so they follow its animations and its rounded corner): 46 x 32 px per button at 100 %, the
    same glyphs as window-*-symbolic, on the colour of the app's own header just left of them;
    hover / pressed / inactive as desktop/gtk/caption-buttons-gtk4.css. An input filter gives the
    pointer's hover and takes the clicks there, so the app's own buttons never see them.
*/
#include "corners.h"
#include "caret.h"

#include <core/pixelgrid.h>
#include <core/rendertarget.h>
#include <core/renderviewport.h>
#include <effect/effecthandler.h>
#include <effect/effectwindow.h>
#include <input.h>
#include <input_event.h>
#include <opengl/glshader.h>
#include <opengl/glshadermanager.h>
#include <opengl/gltexture.h>
#include <window.h>

#include <QImage>
#include <QPainter>
#include <QPainterPath>
#include <QVector2D>
#include <QVector3D>
#include <QVector4D>

#include <cmath>

namespace KWin
{

namespace
{
// Windows 11 DWMWCP_ROUND radius and frame border at 100 % (logical px).
constexpr qreal Radius = 8.0;
constexpr qreal Border = 1.0;

// Caption buttons (logical px), as Aurorae's Fenestra theme lays them out: 46 wide, the frame's
// 1 px border + 32 high, glyph 16 x 16 centred 17.33 below the top.
constexpr qreal CaptionPitch = 46.0;
constexpr qreal CaptionWidth = 138.7; // three buttons and the window's right border
constexpr qreal CaptionHeight = 33.0;
constexpr qreal CaptionGlyphY = 17.33;
// Electron's own strip behind its buttons: from this far left of the right edge, this high. It is
// narrower than Windows' three buttons, and the app's toolbar may reach into the difference, so
// the buttons only cover the app there while hovered or pressed.
constexpr qreal CaptionStripWidth = 113.0;
constexpr qreal CaptionStripHeight = 36.0;

// Electron apps whose title bar has no window-manager frame and whose buttons are Electron's.
// fenestra-window-motion, while an X11 window that draws its own frame waits for its new picture:
// "WxH" (logical px), only that much of the window's top-left is its old picture.
constexpr int HoldCropRole = 0x46454e;

const char *const CaptionApps[] = {"com.anthropic.claude"};

QRectF captionRect(const RectF &frame)
{
    return QRectF(frame.right() - CaptionWidth, frame.top(), CaptionWidth, CaptionHeight);
}

// base.frag of KWin 6.8 (src/opengl/base.frag) with the corner pass in place of its own
// TRAIT_ROUNDED_CORNERS (which clips everything outside the frame, client shadows included).
const char FragmentSource[] = R"GLSL(#version 140

#if TRAIT_MAP_TEXTURE
uniform sampler2D sampler;
in vec2 texcoord0;
#endif

uniform vec4 box;          // frame: centre (xy) and half extents (zw), device px of position0
uniform vec4 cornerRadius; // top-left, top-right, bottom-right, bottom-left (device px)
uniform float borderWidth; // device px
uniform float squareCorners; // 1: tiled window, its corners are filled square
uniform vec4 capRect;      // caption buttons x0, y0, x1, y1 (device px of position0); x1 = 0: none
uniform float capPitch;
uniform float capStrip;    // Electron's strip starts here (device px)
uniform float capButtons;  // bottom of the buttons (capRect.w: of Electron's strip)
uniform vec3 capGlyphX;    // left of each glyph cell
uniform float capGlyphY;
uniform int capCell;       // glyph cell size
uniform int capHover;      // 0 minimize, 1 maximize, 2 close, -1 none
uniform int capPress;
uniform float capInactive;
uniform float capRestore;  // 1: maximized, the restore glyph
uniform sampler2D capGlyphs; // minimize, maximize, restore, close in a row
uniform vec2 holdCrop;     // device px; 0: none (see HoldCropRole)
in vec2 position0;

#if TRAIT_MODULATE
uniform vec4 modulation;
#endif

#if TRAIT_ADJUST_SATURATION
#include "saturation.glsl"
#endif

#if TRAIT_TRANSFORM_COLORSPACE
#include "colormanagement.glsl"
#endif

out vec4 fragColor;

vec4 sampleAt(vec2 p, mat2 toTex)
{
    vec2 tc = texcoord0 + toTex * (p - position0);
    if (tc.x < 0.0 || tc.y < 0.0 || tc.x > 1.0 || tc.y > 1.0) {
        return vec4(0.0);
    }
    return texture(sampler, tc);
}

void main(void)
{
    vec4 result = texture(sampler, texcoord0);

    // Texture coordinates are an affine function of position0 on the window quad: its Jacobian
    // (evaluated here, in uniform control flow) maps a position offset to a texture offset.
    mat2 dp = mat2(dFdx(position0), dFdy(position0));
    mat2 dt = mat2(dFdx(texcoord0), dFdy(texcoord0));
    float det = determinant(dp);
    mat2 toTex = abs(det) > 1e-6 ? dt * inverse(dp) : mat2(0.0);

    if (capRect.z > 0.0 && position0.x >= capRect.x && position0.x < capRect.z
        && position0.y >= capRect.y && position0.y < capRect.w) {
        int i = int(min(2.0, floor((position0.x - capRect.x) / capPitch)));
        vec3 back = sampleAt(vec2(capRect.x - 2.5, capRect.y + 3.5), toTex).rgb; // the app's header
        vec3 fg = dot(back, vec3(0.2126, 0.7152, 0.0722)) < 0.5 ? vec3(1.0) : vec3(0.0);
        bool hover = i == capHover && position0.y < capButtons;
        bool press = i == capPress && position0.y < capButtons;
        vec3 col = !hover && !press && position0.x < capStrip ? result.rgb : back;
        float glyph = capInactive > 0.5 && !hover ? 0.3628 : 1.0;
        if (i == 2 && (hover || press)) {
            col = press ? mix(back, vec3(0.7686, 0.1686, 0.1098), 0.9) : vec3(0.7686, 0.1686, 0.1098);
            fg = vec3(1.0);
            glyph = press ? 0.7 : 1.0;
        } else if (press) {
            col = mix(back, fg, 0.0419);
            glyph = 0.786;
        } else if (hover) {
            col = mix(back, fg, 0.0605);
        }
        int cell = i == 0 ? 0 : i == 2 ? 3 : capRestore > 0.5 ? 2 : 1;
        ivec2 t = ivec2(floor(position0.x - capGlyphX[i]), floor(position0.y - capGlyphY));
        float a = 0.0;
        if (t.x >= 0 && t.y >= 0 && t.x < capCell && t.y < capCell) {
            a = texelFetch(capGlyphs, ivec2(cell * capCell + t.x, t.y), 0).a;
        }
        result = vec4(mix(col, fg, a * glyph), 1.0);
    }

    vec2 p = position0 - box.xy;
    vec2 s = vec2(p.x < 0.0 ? -1.0 : 1.0, p.y < 0.0 ? -1.0 : 1.0);
    float r = p.x > 0.0 ? (p.y < 0.0 ? cornerRadius.y : cornerRadius.z)
                        : (p.y < 0.0 ? cornerRadius.x : cornerRadius.w);
    vec2 c = abs(p) - (box.zw - vec2(r)); // from the arc's centre towards the corner
    bool inCorner = r > 0.0 && c.x > 0.0 && c.y > 0.0 && abs(p).x <= box.z && abs(p).y <= box.w;
    // The whole quadrant past the arc's centre, outside the frame too (a toolkit's 1 px outline,
    // its shadow).
    bool inQuadrant = r > 0.0 && c.x > 0.0 && c.y > 0.0;
    if (squareCorners > 0.5) {
        // Snapped: a corner the frame left round (its very corner pixel is see-through: Aurorae's
        // title bar, a toolkit that does not get the tiled state) is rebuilt square from the
        // window's own edges next to it: the column below the arc for pixels nearer the side edge
        // (keeps the side border), the row beside it for the others (keeps the top/bottom border).
        if (inCorner && sampleAt(box.xy + s * (box.zw - vec2(0.5)), toTex).a < 0.5) {
            vec2 from = c.x > c.y ? vec2(abs(p).x, box.w - r - 0.5) : vec2(box.z - r - 0.5, abs(p).y);
            result = sampleAt(box.xy + s * from, toTex);
        }
    } else if (inQuadrant && sampleAt(box.xy + s * (box.zw - vec2(0.5)), toTex).a > 0.9) {
        // A square corner (its very corner pixel is opaque): rounded, and so is everything the
        // window draws around it. What lies at a distance d outside the arc is what the window
        // shows at the same distance outside its straight side edge (its outline, its shadow, or
        // nothing): the ring around the frame follows the curve instead of staying a square.
        float d = length(c) - r;                          // > 0 outside the arc
        float outer = clamp(0.5 - d, 0.0, 1.0);
        float inner = clamp(0.5 - (d + borderWidth), 0.0, 1.0);
        // The window's own straight edge next to this corner (left / right border, just past the arc).
        vec4 edge = sampleAt(box.xy + s * vec2(box.z - 0.5, box.w - r - 0.5), toTex);
        vec4 behind = sampleAt(box.xy + s * vec2(box.z + max(d, 0.5), box.w - r - 0.5), toTex);
        vec4 win = result * inner + edge * (outer - inner);
        result = win + behind * (1.0 - win.a);
    }

    if (holdCrop.x > 0.0 && (position0.x >= holdCrop.x || position0.y >= holdCrop.y)) {
        result = vec4(0.0);
    }

#if TRAIT_TRANSFORM_COLORSPACE
    result = encodingToNits(result, sourceNamedTransferFunction, sourceTransferFunctionParams.x, sourceTransferFunctionParams.y);
    result.rgb = (colorimetryTransform * vec4(result.rgb, 1.0)).rgb;
#endif

#if TRAIT_ADJUST_SATURATION
    result = adjustSaturation(result);
#endif

#if TRAIT_MODULATE
    result *= modulation;
#endif

#if TRAIT_TRANSFORM_COLORSPACE
    result.rgb = doTonemapping(result.rgb);
    result = nitsToDestinationEncoding(result);
#endif

    fragColor = result;
}
)GLSL";

bool isShellSurface(const EffectWindow *w)
{
    const QString cls = w->windowClass();
    return cls.startsWith(QLatin1String("fenestra-shell"));
}
}

class CaptionFilter : public InputEventFilter
{
public:
    explicit CaptionFilter(CornersEffect *effect)
        : InputEventFilter(InputFilterOrder::Decoration)
        , m_effect(effect)
    {
    }
    bool pointerMotion(PointerMotionEvent *event) override
    {
        m_effect->captionMotion(event->position);
        return false;
    }
    bool pointerButton(PointerButtonEvent *event) override
    {
        return m_effect->captionButton(event);
    }

private:
    CornersEffect *m_effect;
};

CornersEffect::CornersEffect()
{
    // RoundedCorners: the generated vertex shader passes position0 (the quad's device position).
    m_shader = ShaderManager::instance()->generateCustomShader(ShaderTrait::MapTexture | ShaderTrait::Modulate | ShaderTrait::AdjustSaturation
                                                                   | ShaderTrait::TransformColorspace | ShaderTrait::RoundedCorners,
                                                               QByteArray(), QByteArray(FragmentSource));
    if (!m_shader) {
        qWarning("fenestra-corners: the corner shader did not compile");
        return;
    }
    connect(effects, &EffectsHandler::windowAdded, this, &CornersEffect::update);
    connect(effects, &EffectsHandler::windowDeleted, this, &CornersEffect::forget);
    connect(effects, &EffectsHandler::windowActivated, this, [this](EffectWindow *) {
        for (const auto &[w, corners] : m_windows) {
            if (hasCaption(w)) {
                w->addRepaintFull();
            }
        }
    });
    m_filter = std::make_unique<CaptionFilter>(this);
    input()->installInputEventFilter(m_filter.get());
    m_caret = std::make_unique<TextCaret>();
    for (EffectWindow *w : effects->stackingOrder()) {
        update(w);
    }
}

CornersEffect::~CornersEffect() = default;

bool CornersEffect::supported()
{
    return effects->isOpenGLCompositing() && OffscreenEffect::supported();
}

int CornersEffect::requestedEffectChainPosition() const
{
    // After blur (20, draws behind the window) and Fenestra's window motion (60, transforms it):
    // the offscreen copy is drawn with their transform.
    return 90;
}

bool CornersEffect::isActive() const
{
    return m_shader != nullptr;
}

bool CornersEffect::hasCaption(const EffectWindow *w)
{
    if (w->hasDecoration() || w->isFullScreen() || w->isDeleted() || !w->isNormalWindow()) {
        return false;
    }
    const Window *window = w->window();
    if (!window || !window->isResizable()) { // small helper windows (quick entry) have no buttons
        return false;
    }
    const QString cls = w->windowClass().toLower();
    for (const char *app : CaptionApps) {
        if (cls.contains(QLatin1String(app))) {
            return true;
        }
    }
    return false;
}

EffectWindow *CornersEffect::captionAt(const QPointF &pos, int *button) const
{
    Window *window = input()->findToplevel(pos);
    EffectWindow *w = window ? window->effectWindow() : nullptr;
    if (!w || !m_windows.contains(w) || !hasCaption(w)) {
        return nullptr;
    }
    const QRectF rect = captionRect(w->frameGeometry());
    if (!rect.contains(pos)) {
        return nullptr;
    }
    *button = std::min(2, int((pos.x() - rect.left()) / CaptionPitch));
    return w;
}

void CornersEffect::setCaptionState(EffectWindow *w, int hover, int press)
{
    if (w == m_captionWindow && hover == m_hover && press == m_press) {
        return;
    }
    if (m_captionWindow) {
        m_captionWindow->addRepaintFull();
    }
    m_captionWindow = w;
    m_hover = hover;
    m_press = press;
    if (w) {
        w->addRepaintFull();
    }
}

void CornersEffect::captionMotion(const QPointF &pos)
{
    int button = -1;
    EffectWindow *w = captionAt(pos, &button);
    if (m_pressButton >= 0) { // the press keeps its window; pressed only while the pointer is on it
        const bool on = w == m_captionWindow && button == m_pressButton;
        setCaptionState(m_captionWindow, on ? button : -1, on ? m_pressButton : -2);
        return;
    }
    setCaptionState(w, w ? button : -1, -1);
}

bool CornersEffect::captionButton(PointerButtonEvent *event)
{
    if (event->button != Qt::LeftButton) {
        return false;
    }
    int button = -1;
    EffectWindow *w = captionAt(event->position, &button);
    if (event->state == PointerButtonState::Pressed) {
        if (!w) {
            return false;
        }
        m_pressButton = button;
        setCaptionState(w, button, button);
        return true;
    }
    if (m_pressButton < 0) { // the press was not ours
        return false;
    }
    const bool on = w && w == m_captionWindow && button == m_pressButton;
    const int pressed = m_pressButton;
    Window *window = on ? w->window() : nullptr;
    m_pressButton = -1;
    setCaptionState(w, w ? button : -1, -1);
    if (window) {
        if (pressed == 0) {
            window->setMinimized(true);
        } else if (pressed == 1) {
            window->maximize(window->maximizeMode() == MaximizeFull ? MaximizeRestore : MaximizeFull);
        } else {
            window->closeWindow();
        }
    }
    return true;
}

void CornersEffect::updateGlyphs(int cell)
{
    if (m_glyphs && m_glyphCell == cell) {
        return;
    }
    // desktop's window-*-symbolic icons (16 x 16), as geometry.
    QPainterPath minimize;
    minimize.addRect(3, 8, 10, 1);
    const auto rounded = [](qreal x, qreal y, qreal w, qreal h, qreal r) {
        QPainterPath path;
        path.addRoundedRect(QRectF(x, y, w, h), r, r);
        return path;
    };
    const QPainterPath maximize = rounded(3, 3, 10, 10, 1.5).subtracted(rounded(4, 4, 8, 8, 0.5));
    const QPainterPath restore = rounded(3, 5, 8, 8, 1.5).subtracted(rounded(4, 6, 6, 6, 0.5))
                                     .united(rounded(5, 3, 8, 8, 1.5).subtracted(rounded(-4, 4, 16, 12, 0.5)));
    QPainterPath close;
    const QPointF points[] = {{3.35, 2.65}, {8, 7.29}, {12.65, 2.65}, {13.35, 3.35}, {8.71, 8}, {13.35, 12.65},
                              {12.65, 13.35}, {8, 8.71}, {3.35, 13.35}, {2.65, 12.65}, {7.29, 8}, {2.65, 3.35}};
    close.addPolygon(QPolygonF(QList<QPointF>(std::begin(points), std::end(points))));
    close.closeSubpath();

    QImage atlas(cell * 4, cell, QImage::Format_ARGB32_Premultiplied);
    atlas.fill(Qt::transparent);
    QPainter painter(&atlas);
    painter.setRenderHint(QPainter::Antialiasing);
    painter.setPen(Qt::NoPen);
    painter.setBrush(Qt::white);
    painter.scale(cell / 16.0, cell / 16.0);
    for (const QPainterPath &glyph : {minimize, maximize, restore, close}) {
        painter.drawPath(glyph);
        painter.translate(16, 0);
    }
    painter.end();
    m_glyphs = GLTexture::upload(atlas);
    m_glyphCell = cell;
}

CornersEffect::Corners CornersEffect::cornersFor(const EffectWindow *w)
{
    if (!w->isManaged() || w->isPopupWindow() || w->isLockScreen() || w->isOutline() || w->isFullScreen()) {
        return Corners::None;
    }
    if (!w->isNormalWindow() && !w->isDialog()) {
        return Corners::None;
    }
    if (isShellSurface(w) && !w->hasDecoration()) { // the shell's own surfaces; its dialogs are app windows
        return Corners::None;
    }
    const Window *window = w->window();
    if (!window) {
        return Corners::None;
    }
    if (window->maximizeMode() == MaximizeFull) {
        // The shader draws its buttons, or crops its old picture.
        return hasCaption(w) || w->data(HoldCropRole).isValid() ? Corners::Square : Corners::None;
    }
    const RectF frame = w->frameGeometry();
    if (frame.width() <= 2 * Radius || frame.height() <= 2 * Radius) {
        return Corners::None;
    }
    if (window->tile() || window->requestedTile() || window->quickTileMode() != QuickTileMode(QuickTileFlag::None)) {
        return Corners::Square;
    }
    return Corners::Round;
}

void CornersEffect::update(EffectWindow *w)
{
    if (!m_shader) {
        return;
    }
    const auto it = m_windows.find(w);
    const Corners had = it == m_windows.end() ? Corners::None : it->second;
    // A closing window keeps the corners it had (its close animation).
    const Corners want = w->isDeleted() ? had : cornersFor(w);
    if (want == had) {
        return;
    }
    if (had == Corners::None) {
        redirect(w);
        setShader(w, m_shader.get());
    }
    if (want == Corners::None) {
        unredirect(w);
        m_windows.erase(w);
    } else {
        m_windows[w] = want;
    }
    w->addRepaintFull();
}

void CornersEffect::forget(EffectWindow *w)
{
    m_windows.erase(w); // OffscreenEffect drops the redirection of a deleted window itself
    if (w == m_captionWindow) {
        m_captionWindow = nullptr;
        m_hover = m_press = m_pressButton = -1;
    }
}

void CornersEffect::prePaintWindow(RenderView *view, EffectWindow *w, WindowPrePaintData &data)
{
    // States change in many ways (maximize, tiles, full screen, rules): checked on each paint.
    update(w);
    if (const auto it = m_windows.find(w); it != m_windows.end() && it->second == Corners::Round) {
        // The window's opaque region (client and frame) no longer holds at the clipped corners:
        // without this KWin skips drawing what lies under them (black corners).
        data.setTranslucent();
    }
    effects->prePaintWindow(view, w, data);
}

bool CornersEffect::drawWindow(const RenderTarget &renderTarget, const RenderViewport &viewport, EffectWindow *w, int mask,
                               const Region &deviceRegion, WindowPaintData &data)
{
    if (const auto it = m_windows.find(w); it != m_windows.end()) {
        // position0 is the window quad in device px with the frame's top-left at 0, 0
        // (OffscreenEffect::drawWindow).
        const qreal scale = viewport.scale();
        const RectF frame = snapToPixels(w->frameGeometry(), scale);
        const qreal hw = frame.width() * scale / 2, hh = frame.height() * scale / 2;
        const qreal r = std::round(Radius * scale);
        ShaderManager::instance()->pushShader(m_shader.get());
        m_shader->setUniform("box", QVector4D(hw, hh, hw, hh));
        m_shader->setUniform("cornerRadius", QVector4D(r, r, r, r));
        m_shader->setUniform("borderWidth", float(Border * scale));
        m_shader->setUniform("squareCorners", it->second == Corners::Square ? 1.0f : 0.0f);
        QVector2D crop;
        const QStringList size = w->data(HoldCropRole).toString().split(QLatin1Char('x'));
        if (size.size() == 2) {
            crop = QVector2D(std::round(size[0].toDouble() * scale), std::round(size[1].toDouble() * scale));
        }
        m_shader->setUniform("holdCrop", crop);
        const bool caption = hasCaption(w);
        if (caption) {
            const int cell = int(std::round(16 * scale));
            updateGlyphs(cell);
            const qreal x0 = (frame.width() - CaptionWidth) * scale;
            const qreal pitch = CaptionPitch * scale;
            const auto glyphX = [&](int i) {
                return float(std::floor(x0 + pitch * (i + 0.5) - cell / 2.0 + 0.5));
            };
            const bool ours = w == m_captionWindow;
            m_shader->setUniform("capRect", QVector4D(x0, 0, frame.width() * scale, std::round(CaptionStripHeight * scale)));
            m_shader->setUniform("capStrip", float((frame.width() - CaptionStripWidth) * scale));
            m_shader->setUniform("capButtons", float(std::round(CaptionHeight * scale)));
            m_shader->setUniform("capPitch", float(pitch));
            m_shader->setUniform("capGlyphX", QVector3D(glyphX(0), glyphX(1), glyphX(2)));
            m_shader->setUniform("capGlyphY", float(std::floor(CaptionGlyphY * scale - cell / 2.0 + 0.5)));
            m_shader->setUniform("capCell", cell);
            m_shader->setUniform("capHover", ours ? m_hover : -1);
            m_shader->setUniform("capPress", ours ? m_press : -1);
            m_shader->setUniform("capInactive", effects->activeWindow() == w ? 0.0f : 1.0f);
            m_shader->setUniform("capRestore", w->window()->maximizeMode() == MaximizeFull ? 1.0f : 0.0f);
            m_shader->setUniform("capGlyphs", 1);
            glActiveTexture(GL_TEXTURE1);
            m_glyphs->bind();
            glActiveTexture(GL_TEXTURE0);
        } else {
            m_shader->setUniform("capRect", QVector4D(0, 0, 0, 0));
        }
        ShaderManager::instance()->popShader();
        const bool drawn = OffscreenEffect::drawWindow(renderTarget, viewport, w, mask, deviceRegion, data);
        if (caption) {
            glActiveTexture(GL_TEXTURE1);
            m_glyphs->unbind();
            glActiveTexture(GL_TEXTURE0);
        }
        return drawn;
    }
    return OffscreenEffect::drawWindow(renderTarget, viewport, w, mask, deviceRegion, data);
}

} // namespace KWin
