/*
    SPDX-License-Identifier: GPL-3.0-or-later

    A drag that starts when the pointer has already stopped. KWin makes the surface the drag began
    on its first target and only looks for the real one on the next pointer motion
    (SeatInterfacePrivate::startDrag, DragAndDropInputFilter::motion; KWin 6.8). An app that needs
    a moment before it asks for the drag (Chromium loads the file's icon first: the downloads
    bubble) gets there after a quick flick has ended; with no further motion the button's release
    is a drop on the bubble itself, which the app cancels. Windows drops where the pointer is.
    Here the pointer's motion is processed once more, at its current place, right after any pointer
    drag starts: the target is then whatever is under the pointer.
*/
#pragma once

#include <QObject>

namespace KWin
{

class DragStartFix : public QObject
{
    Q_OBJECT

public:
    explicit DragStartFix(QObject *parent = nullptr);
};

} // namespace KWin
