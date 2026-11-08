/*
    SPDX-License-Identifier: GPL-3.0-or-later

    Fenestra rounded corners: Windows 11's DWM rounds the corners of every top-level window
    itself (DWMWCP_ROUND, 8 px at 100 %), whatever draws the frame, and squares them while the
    window is maximized, snapped or full screen. This effect does the same in KWin.

    Caption buttons of Electron apps that draw their own title bar: Electron's are hard-coded
    (GNOME circles, or Chromium's own glyphs) and no theme reaches them, so this effect draws
    Windows' over them and handles their clicks (see corners.cpp).
*/
#pragma once

#include <effect/offscreeneffect.h>

#include <memory>
#include <unordered_map>

namespace KWin
{

class GLShader;
class GLTexture;
class InputEventFilter;
struct PointerButtonEvent;

class CornersEffect : public OffscreenEffect
{
    Q_OBJECT

public:
    CornersEffect();
    ~CornersEffect() override;

    static bool supported();

    void prePaintWindow(RenderView *view, EffectWindow *w, WindowPrePaintData &data) override;
    bool drawWindow(const RenderTarget &renderTarget, const RenderViewport &viewport, EffectWindow *w, int mask,
                    const Region &deviceRegion, WindowPaintData &data) override;
    int requestedEffectChainPosition() const override;
    bool isActive() const override;

    enum class Corners {
        None, ///< not redirected: not an app window, maximized, full screen
        Round, ///< free-floating app window or dialog
        Square, ///< snapped (tiled)
    };
    static Corners cornersFor(const EffectWindow *w);
    static bool hasCaption(const EffectWindow *w);

    // From the input filter (logical px, global).
    void captionMotion(const QPointF &pos);
    bool captionButton(PointerButtonEvent *event);

private:
    void update(EffectWindow *w);
    void forget(EffectWindow *w);
    EffectWindow *captionAt(const QPointF &pos, int *button) const;
    void setCaptionState(EffectWindow *w, int hover, int press);
    void updateGlyphs(int cell);

    std::unique_ptr<GLShader> m_shader;
    std::unordered_map<EffectWindow *, Corners> m_windows;
    std::unique_ptr<InputEventFilter> m_filter;
    std::unique_ptr<GLTexture> m_glyphs;
    int m_glyphCell = 0;
    EffectWindow *m_captionWindow = nullptr; ///< under the pointer, or holding the press
    int m_hover = -1; ///< 0 minimize, 1 maximize, 2 close
    int m_press = -1; ///< the button drawn pressed (-2: held, but the pointer left it)
    int m_pressButton = -1;
};

} // namespace KWin
