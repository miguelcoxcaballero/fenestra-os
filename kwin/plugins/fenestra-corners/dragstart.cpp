// SPDX-License-Identifier: GPL-3.0-or-later
#include "dragstart.h"

#include <input.h>
#include <pointer_input.h>
#include <wayland/seat.h>
#include <wayland_server.h>

#include <QTimer>

#include <chrono>

namespace KWin
{

DragStartFix::DragStartFix(QObject *parent)
    : QObject(parent)
{
    if (!waylandServer() || !waylandServer()->seat()) {
        return;
    }
    connect(waylandServer()->seat(), &SeatInterface::dragStarted, this, [this] {
        // The signal comes from inside startDrag: let it finish first.
        QTimer::singleShot(0, this, [] {
            SeatInterface *seat = waylandServer()->seat();
            if (!seat->isDragPointer() || seat->isDragTouch() || !input() || !input()->pointer()) {
                return;
            }
            // Input events carry CLOCK_MONOTONIC times.
            const auto now = std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now().time_since_epoch());
            input()->pointer()->processMotionAbsolute(input()->globalPointer(), now);
            input()->pointer()->processFrame();
        });
    });
}

} // namespace KWin
