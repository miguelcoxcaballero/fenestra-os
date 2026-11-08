/*
    SPDX-License-Identifier: GPL-3.0-or-later

    Fenestra rounded corners: Windows 11's DWM rounds the corners of every top-level window
    itself (DWMWCP_ROUND, 8 px at 100 %), whatever draws the frame, and squares them while the
    window is maximized, snapped or full screen. This effect does the same in KWin.
*/
#pragma once

#include <effect/offscreeneffect.h>

#include <memory>
#include <unordered_map>

namespace KWin
{

class GLShader;

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

private:
    void update(EffectWindow *w);
    void forget(EffectWindow *w);

    std::unique_ptr<GLShader> m_shader;
    std::unordered_map<EffectWindow *, Corners> m_windows;
};

} // namespace KWin
