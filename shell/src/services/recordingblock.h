// SPDX-License-Identifier: GPL-3.0-or-later
// Laptops whose firmware can block the microphone and camera (Samsung Galaxy Book "Block
// recording", samsung-galaxybook firmware attribute block_recording): Windows' Samsung Settings
// tells the user when an app tries to record while it is on. Here: when an app opens a microphone
// and the block is on, a notification says so with "Turn off" (the attribute is writable by the
// wheel group: desktop/privacy/70-fenestra-recording-block.rules). Never blocks silently.
#pragma once

#include <QObject>
#include <QQmlEngine>

class RecordingBlock : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(bool available READ available CONSTANT)
    Q_PROPERTY(bool blocked READ blocked WRITE setBlocked NOTIFY changed)
    Q_PROPERTY(bool writable READ writable CONSTANT)
public:
    static RecordingBlock *instance();
    static RecordingBlock *create(QQmlEngine *, QJSEngine *);
    bool available() const { return !m_path.isEmpty(); }
    bool blocked() const;
    bool writable() const;
    void setBlocked(bool on);
Q_SIGNALS:
    void changed();

private:
    explicit RecordingBlock(QObject *parent = nullptr);
    void check();
    QString m_path;
    QStringList m_lastApps;
    uint m_noticeId = 0;
};
