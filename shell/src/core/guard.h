// SPDX-License-Identifier: GPL-3.0-or-later
// The shell's safety net: the taskbar, Start and the notifications are one process, so a C++
// exception in any small part (a size that makes std::vector throw, a bad_alloc for an absurd
// image) used to end all of them. Exceptions are caught at the two places every part runs from:
//   - event handlers, timers and D-Bus replies on the main thread: ShellApplication::notify
//   - image providers, which Qt Quick calls on its own threads: function try blocks ending in
//     providerFailed(), which answers with an empty picture
// The failed operation is dropped and logged (journal: "fenestra-shell: survived ..."). Crashes
// that are not exceptions (segfaults) still end the process; systemd restarts it.
#pragma once

#include <QGuiApplication>
#include <QImage>
#include <QPixmap>

#include <exception>

class ShellApplication : public QGuiApplication
{
public:
    using QGuiApplication::QGuiApplication;
    bool notify(QObject *receiver, QEvent *event) override;
};

// For the catch clause of a provider: logs the current exception, sets *size, returns 1x1 clear.
QImage providerFailed(const char *provider, const QString &id, QSize *size);
inline QPixmap providerFailedPixmap(const char *provider, const QString &id, QSize *size)
{
    return QPixmap::fromImage(providerFailed(provider, id, size));
}
