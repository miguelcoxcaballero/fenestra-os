// SPDX-License-Identifier: GPL-3.0-or-later
// Live window pictures for the taskbar's hover previews (B03), as Plasma's task manager makes them:
// KWin streams a window over PipeWire (zkde_screencast_unstable_v1.stream_window, by the window's
// uuid from org_kde_plasma_window_management), KPipeWire's PipeWireSourceItem (QML module
// org.kde.pipewire) draws the stream. KWin offers the protocol only to clients whose .desktop file
// lists it in X-KDE-Wayland-Interfaces (data/org.fenestra.Shell.desktop).
//
// Where the protocol or PipeWire is missing (KWin without OpenGL, no PipeWire daemon) the preview
// falls back to WindowSnapshot: KWin's ScreenShot2.CaptureWindow, taken when the preview opens and
// refreshed while it stays open (image://windowshot/<uuid>/<serial>).
#pragma once

#include <QHash>
#include <QImage>
#include <QMutex>
#include <QObject>
#include <QPointer>
#include <QQmlEngine>
#include <QQuickImageProvider>
#include <QtWaylandClient/QWaylandClientExtension>

#include "qwayland-zkde-screencast-unstable-v1.h"

class ScreencastManager : public QWaylandClientExtensionTemplate<ScreencastManager>,
                          public QtWayland::zkde_screencast_unstable_v1
{
    Q_OBJECT
public:
    static ScreencastManager *instance();
    ~ScreencastManager() override;

private:
    ScreencastManager();
};

class ScreencastStreamObject : public QObject, public QtWayland::zkde_screencast_stream_unstable_v1
{
    Q_OBJECT
public:
    explicit ScreencastStreamObject(::zkde_screencast_stream_unstable_v1 *object);
    ~ScreencastStreamObject() override;
    quint32 node = 0;
    quint64 serial = 0;

Q_SIGNALS:
    void ready();
    void failedWith(const QString &error);
    void ended();

protected:
    void zkde_screencast_stream_unstable_v1_created(uint32_t node) override;
    void zkde_screencast_stream_unstable_v1_serial(uint32_t hi, uint32_t lo) override;
    void zkde_screencast_stream_unstable_v1_failed(const QString &error) override;
    void zkde_screencast_stream_unstable_v1_closed() override;
};

// One window's stream while `uuid` is set and `enabled`: nodeId / objectSerial for PipeWireSourceItem.
class ScreencastStream : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    Q_PROPERTY(QString uuid READ uuid WRITE setUuid NOTIFY uuidChanged)
    Q_PROPERTY(bool enabled READ enabled WRITE setEnabled NOTIFY enabledChanged)
    Q_PROPERTY(uint nodeId READ nodeId NOTIFY streamChanged)
    Q_PROPERTY(quint64 objectSerial READ objectSerial NOTIFY streamChanged)
    // False when KWin does not offer the protocol (or not to us) or refused this window.
    Q_PROPERTY(bool available READ available NOTIFY availableChanged)
public:
    explicit ScreencastStream(QObject *parent = nullptr);
    ~ScreencastStream() override;
    QString uuid() const { return m_uuid; }
    void setUuid(const QString &uuid);
    bool enabled() const { return m_enabled; }
    void setEnabled(bool enabled);
    uint nodeId() const { return m_stream ? m_stream->node : 0; }
    quint64 objectSerial() const { return m_stream ? m_stream->serial : 0; }
    bool available() const;

Q_SIGNALS:
    void uuidChanged();
    void enabledChanged();
    void streamChanged();
    void availableChanged();

private:
    void restart();
    QString m_uuid;
    bool m_enabled = true;
    bool m_failed = false;
    ScreencastStreamObject *m_stream = nullptr;
};

// Fallback: a still of the window from KWin (ScreenShot2.CaptureWindow), device pixels.
class WindowSnapshot : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
public:
    static WindowSnapshot *instance();
    static WindowSnapshot *create(QQmlEngine *, QJSEngine *) { return instance(); }
    // Asks KWin for a new picture of the window; captured(uuid, serial) when it is in.
    Q_INVOKABLE void capture(const QString &uuid);
    Q_INVOKABLE void release(const QString &uuid);
    QImage image(const QString &uuid) const;

Q_SIGNALS:
    void captured(const QString &uuid, int serial);

private:
    explicit WindowSnapshot(QObject *parent = nullptr) : QObject(parent) {}
    mutable QMutex m_lock;
    QHash<QString, QImage> m_images;
    QHash<QString, int> m_serials;
    QHash<QString, bool> m_pending;
};

class WindowSnapshotProvider : public QQuickImageProvider
{
public:
    WindowSnapshotProvider() : QQuickImageProvider(QQuickImageProvider::Image) {}
    QImage requestImage(const QString &id, QSize *size, const QSize &requested) override;
};
