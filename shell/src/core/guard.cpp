// SPDX-License-Identifier: GPL-3.0-or-later
#include "guard.h"

#include <QEvent>
#include <QMetaObject>

static QByteArray currentException()
{
    try {
        throw;
    } catch (const std::exception &e) {
        return QByteArray(typeid(e).name()) + ": " + e.what();
    } catch (...) {
        return "unknown exception";
    }
}

bool ShellApplication::notify(QObject *receiver, QEvent *event)
{
    try {
        return QGuiApplication::notify(receiver, event);
    } catch (...) {
        qCritical("fenestra-shell: survived %s in event %d for %s", currentException().constData(), int(event->type()),
                  receiver ? receiver->metaObject()->className() : "?");
        return false;
    }
}

QImage providerFailed(const char *provider, const QString &id, QSize *size)
{
    qCritical("fenestra-shell: survived %s in %s for %s", currentException().constData(), provider, qPrintable(id.left(120)));
    QImage empty(1, 1, QImage::Format_ARGB32_Premultiplied);
    empty.fill(Qt::transparent);
    if (size)
        *size = empty.size();
    return empty;
}
