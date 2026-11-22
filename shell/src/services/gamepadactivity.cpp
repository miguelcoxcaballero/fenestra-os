// SPDX-License-Identifier: GPL-3.0-or-later
#include "gamepadactivity.h"

#include <QDir>
#include <QSet>
#include <QFile>
#include <QFileSystemWatcher>
#include <QSocketNotifier>
#include <QTimer>

#include <cerrno>
#include <cstdlib>
#include <fcntl.h>
#include <linux/input.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <unistd.h>

namespace
{
const QString s_inputDir = QStringLiteral("/dev/input");

bool isJoystick(const QString &node)
{
    // udev's database entry for the node: /run/udev/data/c<major>:<minor>
    struct stat st;
    if (::stat(QFile::encodeName(node).constData(), &st) != 0 || !S_ISCHR(st.st_mode)) {
        return false;
    }
    QFile db(QStringLiteral("/run/udev/data/c%1:%2").arg(major(st.st_rdev)).arg(minor(st.st_rdev)));
    if (!db.open(QIODevice::ReadOnly)) {
        return false;
    }
    const QList<QByteArray> lines = db.readAll().split('\n');
    return lines.contains("E:ID_INPUT_JOYSTICK=1");
}
}

GamepadActivity *GamepadActivity::instance()
{
    static auto *pads = new GamepadActivity;
    return pads;
}

GamepadActivity::GamepadActivity(QObject *parent)
    : QObject(parent)
{
    auto *watcher = new QFileSystemWatcher({s_inputDir}, this);
    // udev writes its database entry (and the seat ACL) a moment after the node appears
    auto *settle = new QTimer(this);
    settle->setSingleShot(true);
    settle->setInterval(1500);
    connect(settle, &QTimer::timeout, this, &GamepadActivity::scan);
    connect(watcher, &QFileSystemWatcher::directoryChanged, settle, qOverload<>(&QTimer::start));
    scan();
}

void GamepadActivity::scan()
{
    QSet<QString> open;
    for (const Pad &pad : std::as_const(m_pads)) {
        open.insert(pad.node);
    }
    const QStringList events = QDir(s_inputDir).entryList({QStringLiteral("event*")}, QDir::System);
    for (const QString &event : events) {
        const QString node = s_inputDir + QLatin1Char('/') + event;
        if (open.contains(node) || !isJoystick(node)) {
            continue;
        }
        const int fd = ::open(QFile::encodeName(node).constData(), O_RDONLY | O_NONBLOCK | O_CLOEXEC);
        if (fd < 0) {
            continue;   // not this seat's, or already gone
        }
        Pad pad;
        pad.node = node;
        for (int axis = 0; axis < ABS_CNT; ++axis) {
            input_absinfo info{};
            if (ioctl(fd, EVIOCGABS(axis), &info) == 0 && info.maximum > info.minimum) {
                pad.range.insert(axis, info.maximum - info.minimum);
                pad.reference.insert(axis, info.value);
            }
        }
        pad.notifier = new QSocketNotifier(fd, QSocketNotifier::Read, this);
        connect(pad.notifier, &QSocketNotifier::activated, this, [this, fd] {
            readEvents(fd);
        });
        m_pads.insert(fd, pad);
        qInfo("FENESTRA_POWERIDLE gamepad %s", qPrintable(node));
    }
}

void GamepadActivity::readEvents(int fd)
{
    input_event events[64];
    const ssize_t n = ::read(fd, events, sizeof events);
    if (n < 0 && errno == EAGAIN) {
        return;
    }
    if (n <= 0) {
        close(fd);   // unplugged or out of range
        return;
    }
    Pad &pad = m_pads[fd];
    bool active = false;
    for (size_t i = 0; i < size_t(n) / sizeof *events; ++i) {
        const input_event &ev = events[i];
        if (ev.type == EV_KEY && ev.value != 0) {
            active = true;
        } else if (ev.type == EV_ABS && pad.range.contains(ev.code)) {
            // an eighth of the axis: a hand on the stick or trigger, not a resting stick's drift
            int &reference = pad.reference[ev.code];
            if (std::abs(ev.value - reference) * 8 >= pad.range.value(ev.code)) {
                reference = ev.value;
                active = true;
            }
        }
    }
    if (active) {
        Q_EMIT activity();
    }
}

void GamepadActivity::close(int fd)
{
    const Pad pad = m_pads.take(fd);
    delete pad.notifier;
    ::close(fd);
}
