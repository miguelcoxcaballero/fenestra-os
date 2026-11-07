// SPDX-License-Identifier: GPL-3.0-or-later
// Snipping overlay (Q04): Super+Shift+S and Print freeze the screen once (KWin ScreenShot2
// CaptureWorkspace), the overlay (qml/snip) shows that picture dimmed on every output and the
// selection — rectangle, window, output or freeform lasso — is cropped from the same picture, so
// what is seen is what is saved. The result goes to the clipboard and ~/Pictures/Screenshots with
// the screenshot toast.
//
// Tests (FENESTRA_SHELL_TEST=1): FENESTRA_SHELL_SNIP_IMAGE=<png> replaces ScreenShot2 (the bench's
// KWin has no OpenGL and its screenshot effect crashes, FEASIBILITY.md).
#pragma once

#include <QImage>
#include <QObject>
#include <QQmlEngine>
#include <QQuickImageProvider>
#include <QRect>
#include <functional>

class Snip : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    // The overlay is up (a frozen picture is held).
    Q_PROPERTY(bool active READ active NOTIFY activeChanged)
    // "rectangle" | "window" | "screen" | "freeform"; kept between openings, like the reference.
    Q_PROPERTY(QString mode READ mode WRITE setMode NOTIFY modeChanged)
    // Bumped on every capture: part of the overlay's image URL, so a new picture is loaded.
    Q_PROPERTY(int serial READ serial NOTIFY activeChanged)
    Q_PROPERTY(QString lastSaved READ lastSaved NOTIFY saved)

public:
    static Snip *instance();
    static Snip *create(QQmlEngine *, QJSEngine *);

    bool active() const { return m_active; }
    QString mode() const { return m_mode; }
    void setMode(const QString &mode);
    int serial() const { return m_serial; }
    QString lastSaved() const { return m_lastSaved; }

    // Freezes the screen and opens the overlay (no-op while it is open or a capture is running).
    Q_INVOKABLE void start();
    Q_INVOKABLE void cancel();
    // Selections in global logical coordinates (the coordinates of QScreen::geometry()).
    Q_INVOKABLE bool captureRect(const QRectF &global);
    Q_INVOKABLE bool captureScreen(const QString &name);
    // Freeform: the lasso as flat global coordinates [x0, y0, x1, y1, ...].
    Q_INVOKABLE bool captureFreeform(const QList<qreal> &globalXY);
    // The whole workspace straight away, without the overlay.
    Q_INVOKABLE void captureWorkspaceNow();
    // Test probe (FENESTRA_SHELL_TEST=1): `count` screen captures back to back into dir/fNNN.png
    // (with ms timestamps in dir/times.txt), to look at a few frames of a glitch.
    Q_INVOKABLE void testBurst(const QString &dir, int count);

    // The frozen picture of one output (for the image provider).
    QImage frozenFor(const QString &screen) const;

Q_SIGNALS:
    void activeChanged();
    void modeChanged();
    void saved(const QString &path);
    void failed(const QString &reason);

private:
    explicit Snip(QObject *parent = nullptr);
    void grabWorkspace(std::function<void(const QImage &)> done);
    QRect pixelRect(const QRectF &global) const;
    bool deliver(const QImage &image);
    void finish(const QImage &image, bool toClipboard);
    static QRect workspace();

    bool m_active = false;
    bool m_grabbing = false;
    QString m_mode = QStringLiteral("rectangle");
    int m_serial = 0;
    QImage m_frozen;
    QRect m_workspace;     // logical
    qreal m_scale = 1;     // frozen pixels per logical pixel
    QString m_lastSaved;
};

// image://snip/<output name>/<serial>: the frozen picture of that output.
class SnipImageProvider : public QQuickImageProvider
{
public:
    SnipImageProvider() : QQuickImageProvider(QQuickImageProvider::Image) {}
    QImage requestImage(const QString &id, QSize *size, const QSize &requested) override;
};
