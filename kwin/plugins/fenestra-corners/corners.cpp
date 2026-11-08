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
        straight edge next to that corner (its border, so the curve keeps the border), over what
        the window shows just outside the corner (its shadow there, or nothing).

    Snapped (KWin's quick tiles and custom tiles): drawn the same way, but square: corners a frame
    left round (Aurorae rounds its title bar unless the window is maximized; a toolkit that does
    not get the tiled state) are filled with the window's own row next to them.

    Unredirected (no offscreen copy, direct scan-out possible): maximized and full-screen windows
    (Aurorae and the toolkits square those themselves) and everything that is not an app window
    (shell surfaces, menus, tooltips, OSDs, lock screen).
*/
#include "corners.h"

#include <core/pixelgrid.h>
#include <core/rendertarget.h>
#include <core/renderviewport.h>
#include <effect/effecthandler.h>
#include <effect/effectwindow.h>
#include <opengl/glshader.h>
#include <opengl/glshadermanager.h>
#include <window.h>

#include <QVector4D>

namespace KWin
{

namespace
{
// Windows 11 DWMWCP_ROUND radius and frame border at 100 % (logical px).
constexpr qreal Radius = 8.0;
constexpr qreal Border = 1.0;

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

    vec2 p = position0 - box.xy;
    vec2 s = vec2(p.x < 0.0 ? -1.0 : 1.0, p.y < 0.0 ? -1.0 : 1.0);
    float r = p.x > 0.0 ? (p.y < 0.0 ? cornerRadius.y : cornerRadius.z)
                        : (p.y < 0.0 ? cornerRadius.x : cornerRadius.w);
    vec2 c = abs(p) - (box.zw - vec2(r)); // from the arc's centre towards the corner
    bool inCorner = r > 0.0 && c.x > 0.0 && c.y > 0.0 && abs(p).x <= box.z && abs(p).y <= box.w;
    if (squareCorners > 0.5) {
        // Snapped: a corner the frame left round (its very corner pixel is see-through: Aurorae's
        // title bar, a toolkit that does not get the tiled state) is rebuilt square from the
        // window's own edges next to it: the column below the arc for pixels nearer the side edge
        // (keeps the side border), the row beside it for the others (keeps the top/bottom border).
        if (inCorner && sampleAt(box.xy + s * (box.zw - vec2(0.5)), toTex).a < 0.5) {
            vec2 from = c.x > c.y ? vec2(abs(p).x, box.w - r - 0.5) : vec2(box.z - r - 0.5, abs(p).y);
            result = sampleAt(box.xy + s * from, toTex);
        }
    } else if (inCorner && result.a > 0.9) {
        float d = length(c) - r;                          // > 0 outside the arc
        float outer = clamp(0.5 - d, 0.0, 1.0);
        float inner = clamp(0.5 - (d + borderWidth), 0.0, 1.0);
        // The window's own straight edge next to this corner (left / right border, just past the arc).
        vec4 edge = sampleAt(box.xy + s * vec2(box.z - 0.5, box.w - r - 0.5), toTex);
        // What lies just outside the corner (the window's shadow, or nothing).
        vec4 behind = sampleAt(box.xy + s * (box.zw + vec2(0.5)), toTex);
        vec4 win = result * inner + edge * (outer - inner);
        result = win + behind * (1.0 - win.a);
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
    if (!window || window->maximizeMode() == MaximizeFull) {
        return Corners::None;
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
        ShaderManager::instance()->popShader();
    }
    return OffscreenEffect::drawWindow(renderTarget, viewport, w, mask, deviceRegion, data);
}

} // namespace KWin
