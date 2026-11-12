// SPDX-License-Identifier: GPL-3.0-or-later
#include "caret.h"

#include <wayland/seat.h>
#include <wayland/surface.h>
#include <wayland/textinput_v2.h>
#include <wayland/textinput_v3.h>
#include <wayland_server.h>
#include <window.h>

#include <QDBusConnection>

namespace KWin
{

static const QString s_path = QStringLiteral("/org/fenestra/TextCaret");

TextCaret::TextCaret(QObject *parent)
    : QObject(parent)
{
    QDBusConnection::sessionBus().registerObject(s_path, this, QDBusConnection::ExportAllSlots);
}

TextCaret::~TextCaret()
{
    QDBusConnection::sessionBus().unregisterObject(s_path);
}

bool TextCaret::Rect(int &x, int &y, int &width, int &height)
{
    x = y = width = height = 0;
    if (!waylandServer() || !waylandServer()->seat()) {
        return false;
    }
    SeatInterface *seat = waylandServer()->seat();
    SurfaceInterface *surface = nullptr;
    QRectF rect;
    if (auto *v3 = seat->textInputV3(); v3 && v3->isEnabled() && v3->surface()) {
        surface = v3->surface();
        rect = QRectF(v3->cursorRectangle());
    } else if (auto *v2 = seat->textInputV2(); v2 && v2->isEnabled() && v2->surface()) {
        surface = v2->surface();
        rect = QRectF(v2->cursorRectangle());
    }
    // A client that enabled text input but never said where its caret is leaves 0x0 at 0,0.
    if (!surface || rect.height() <= 0) {
        return false;
    }
    SurfaceInterface *main = surface->mainSurface() ? surface->mainSurface() : surface;
    Window *window = waylandServer()->findWindow(main);
    if (!window) {
        return false;
    }
    const QPointF pos = window->mapFromLocal(surface->mapToMainSurface(rect.topLeft()));
    x = qRound(pos.x());
    y = qRound(pos.y());
    width = qMax(1, qRound(rect.width()));
    height = qRound(rect.height());
    return true;
}

} // namespace KWin
