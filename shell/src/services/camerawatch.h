// SPDX-License-Identifier: GPL-3.0-or-later
// Camera in use (B08 privacy glyph): PipeWire video source nodes in the "running" state, watched on
// PipeWire's own thread (pw_thread_loop); results posted to the UI thread. No polling.
#pragma once

#include <QObject>
#include <QQmlEngine>

struct pw_thread_loop;
struct pw_context;
struct pw_core;
struct pw_registry;

class CameraWatch : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(bool inUse READ inUse NOTIFY changed)
public:
    static CameraWatch *instance();
    static CameraWatch *create(QQmlEngine *, QJSEngine *);
    ~CameraWatch() override;
    bool inUse() const { return m_running > 0; }
    // Called from the PipeWire thread.
    void setRunningCount(int count);
Q_SIGNALS:
    void changed();
private:
    explicit CameraWatch(QObject *parent = nullptr);
    pw_thread_loop *m_loop = nullptr;
    pw_context *m_context = nullptr;
    pw_core *m_core = nullptr;
    pw_registry *m_registry = nullptr;
    int m_running = 0;
};
