// SPDX-License-Identifier: GPL-3.0-or-later
// Game controllers count as using the PC, as on Windows. KWin's idle timer only sees what goes
// through libinput (keyboard, mouse, touchpad, touch, tablets); libinput leaves joysticks alone,
// so a game played with a controller looked idle and the screen locked and went off on battery.
// This watches every joystick node (udev ID_INPUT_JOYSTICK, readable by the seat's user) and
// reports presses and real stick/trigger movement; resting sticks' jitter is not activity.
#pragma once

#include <QHash>
#include <QObject>

class QSocketNotifier;

class GamepadActivity : public QObject
{
    Q_OBJECT
public:
    static GamepadActivity *instance();

Q_SIGNALS:
    void activity();

private:
    explicit GamepadActivity(QObject *parent = nullptr);
    void scan();
    void readEvents(int fd);
    void close(int fd);

    struct Pad {
        QSocketNotifier *notifier = nullptr;
        QString node;
        QHash<int, int> reference;   // axis -> value when it last counted as activity
        QHash<int, int> range;       // axis -> max - min
    };
    QHash<int, Pad> m_pads;          // fd -> pad
};
