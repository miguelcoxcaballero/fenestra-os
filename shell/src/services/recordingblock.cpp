// SPDX-License-Identifier: GPL-3.0-or-later
#include "recordingblock.h"

#include "notifications.h"
#include "system.h"

#include <QFile>
#include <QFileInfo>
#include <QLocale>

#include <unistd.h>

namespace
{
const char *kPaths[] = {"/sys/class/firmware-attributes/samsung-galaxybook/attributes/block_recording/current_value"};
}

RecordingBlock *RecordingBlock::instance()
{
    static RecordingBlock block;
    return &block;
}

RecordingBlock *RecordingBlock::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

RecordingBlock::RecordingBlock(QObject *parent)
    : QObject(parent)
{
    for (const char *p : kPaths)
        if (QFileInfo::exists(QString::fromLatin1(p)))
            m_path = QString::fromLatin1(p);
    if (m_path.isEmpty())
        return;
    connect(Privacy::instance(), &Privacy::changed, this, &RecordingBlock::check);
    connect(Notifications::instance(), &Notifications::shellAction, this, [this](uint id, const QString &key) {
        if (id == m_noticeId && key == QLatin1String("turn-off"))
            setBlocked(false);
    });
}

bool RecordingBlock::blocked() const
{
    QFile f(m_path);
    return f.open(QIODevice::ReadOnly) && f.readAll().trimmed() == "1";
}

bool RecordingBlock::writable() const
{
    return !m_path.isEmpty() && ::access(QFile::encodeName(m_path).constData(), W_OK) == 0;
}

void RecordingBlock::setBlocked(bool on)
{
    QFile f(m_path);
    if (f.open(QIODevice::WriteOnly))
        f.write(on ? "1" : "0");
    Q_EMIT changed();
}

void RecordingBlock::check()
{
    const QStringList apps = Privacy::instance()->microphoneApps();
    QStringList fresh;
    for (const QString &a : apps)
        if (!m_lastApps.contains(a))
            fresh << a;
    m_lastApps = apps;
    if (fresh.isEmpty() || !blocked())
        return;
    const bool es = QLocale().name().startsWith(QLatin1String("es"));
    const QString who = fresh.join(QStringLiteral(", "));
    QVariantList actions;
    if (writable())
        actions << QVariantMap{{QStringLiteral("key"), QStringLiteral("turn-off")},
                               {QStringLiteral("label"), es ? QStringLiteral("Desactivar") : QStringLiteral("Turn off")}};
    if (m_noticeId)
        Notifications::instance()->CloseNotification(m_noticeId);
    m_noticeId = Notifications::instance()->notify(
        es ? QStringLiteral("Privacidad") : QStringLiteral("Privacy"), QStringLiteral("microphone-sensitivity-muted-symbolic"),
        es ? QStringLiteral("Bloqueo de grabación activado") : QStringLiteral("Block recording is on"),
        es ? QStringLiteral("%1 está intentando usar el micrófono, pero el bloqueo de grabación del equipo lo silencia.").arg(who)
           : QStringLiteral("%1 is trying to use the microphone, but the PC's Block recording setting mutes it.").arg(who),
        QString(), actions);
}
