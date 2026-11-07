// SPDX-License-Identifier: GPL-3.0-or-later
// Windows' acrylic for the shell's popups (Start, Search, Quick settings, Notification Center,
// calendar, menus), computed from what is really behind them.
//
// When a popup opens, Backdrop::request() asks KWin (org.kde.KWin.ScreenShot2.CaptureArea, allowed
// by X-KDE-DBUS-Restricted-Interfaces in org.fenestra.Shell.desktop) for the screen area behind the
// popup's final place, without the shell's own surfaces (hide-caller-windows): the popup itself is
// never in it, however far it has risen. The shell's surfaces that belong in the backdrop are added
// back: the wallpaper (as Desktop.qml draws it, cover-scaled) under what KWin left transparent, and
// optionally one popup the new one opens over (a menu over Start: Start's own window, grabbed).
// Then the WinUI recipe (the same maths as the taskbar's, core/acrylic.h):
//   Gaussian blur (BlurAmount, σ in logical px) → luminosity blend with the tint's luminosity at
//   TintLuminosityOpacity → colour blend with the tint at TintOpacity → noise at 2 %,
// per recipe (acrylic.<recipe>.backdrop.* tokens, fitted to reference-shots/user-win11). Up to the
// noise everything is smooth, so it runs on a grid of σ/4 logical px and the images stay that coarse
// (image://backdrop/<id>/<recipe>, covering area(id) on the screen): the popup draws them scaled
// (bilinear) and fixed on the screen, so the panel slides over its backdrop as on Windows, with the
// noise texture (image://backdrop/noise/<dpr>, device pixels, screen-fixed) at 2 % over it.
// Everything after the capture runs on a worker thread; ready() reports the latency.
#pragma once

#include <QHash>
#include <QImage>
#include <QMutex>
#include <QObject>
#include <QQmlEngine>
#include <QQuickImageProvider>
#include <QRectF>
#include <QWindow>

class Backdrop : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
public:
    static Backdrop *instance();
    static Backdrop *create(QQmlEngine *, QJSEngine *) { return instance(); }

    // rect: logical px on `window`'s screen (the area the popup's acrylic can cover while it
    // moves). wallpaper: file path or "#rrggbb". recipes: e.g. ["panel", "base"]. under/underRect:
    // a shell window the popup opens over and its logical rectangle on the screen (or null).
    // Returns the request id (0: not possible, keep the fallback material).
    Q_INVOKABLE int request(QWindow *window, const QRectF &rect, const QString &wallpaper, const QStringList &recipes,
                            QWindow *under = nullptr, const QRectF &underRect = {});
    Q_INVOKABLE void release(int id);
    QImage image(int id, const QString &recipe) const;
    // The logical rectangle on the screen that image(id, ...) covers (its pixels are a coarse grid).
    Q_INVOKABLE QRectF area(int id) const;

Q_SIGNALS:
    void ready(int id, qreal latencyMs);
    void failed(int id);

private:
    explicit Backdrop(QObject *parent = nullptr) : QObject(parent) {}
    mutable QMutex m_lock;
    QHash<int, QHash<QString, QImage>> m_images;
    QHash<int, QRectF> m_areas;
    int m_next = 0;
};

class BackdropProvider : public QQuickImageProvider
{
public:
    BackdropProvider() : QQuickImageProvider(QQuickImageProvider::Image) {}
    QImage requestImage(const QString &id, QSize *size, const QSize &requested) override;
};
