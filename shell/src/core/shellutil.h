// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <KWindowEffects>
#include <LayerShellQt/Window>
#include <QGuiApplication>
#include <QObject>
#include <QQmlEngine>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QScreen>
#include <QStandardPaths>
#include <QWindow>
#include <QHash>
#include <QPointer>
#include <QQuickItem>
#include <QQuickWindow>
#include <QRegion>
#include <QVariantList>
#include <cmath>

class ShellUtil : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
public:
    using QObject::QObject;
    // Puts a (not yet shown) shell surface on the output called `name` (B10). QML's
    // `Window.screen: Qt.application.screens[i]` leaves layer surfaces on the first output.
    Q_INVOKABLE bool placeOnScreen(QWindow *window, const QString &name) const
    {
        if (!window)
            return false;
        for (QScreen *screen : QGuiApplication::screens()) {
            if (screen->name() == name) {
                window->setScreen(screen);
                // The output of the layer surface (get_layer_surface) comes from LayerShellQt's own
                // screen; without it KWin puts the surface on the active output.
                if (auto *layer = LayerShellQt::Window::get(window))
                    layer->setScreen(screen);
                return true;
            }
        }
        return false;
    }
    // ~/.local/state/fenestra/session-ok: the Fenestra session worked for this user (the
    // migrator offers it as the default only after that).
    Q_INVOKABLE void markSessionOk() const
    {
        const QString dir = QStandardPaths::writableLocation(QStandardPaths::GenericStateLocation) + QStringLiteral("/fenestra");
        QDir().mkpath(dir);
        QFile f(dir + QStringLiteral("/session-ok"));
        if (f.open(QIODevice::WriteOnly))
            f.write(QDateTime::currentDateTime().toString(Qt::ISODate).toUtf8() + '\n');
    }
    Q_INVOKABLE bool configFileExists(const QString &name) const
    {
        return QFileInfo::exists(QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation) + QLatin1Char('/') + name);
    }
    // Keep a popup's scene graph while it is hidden (QQuickWindow::persistentSceneGraph is not
    // exposed to QML): its acrylic layers are ready in the first frame of the next opening.
    Q_INVOKABLE void keepScene(QWindow *window) const
    {
        if (auto *qw = qobject_cast<QQuickWindow *>(window)) {
            qw->setPersistentSceneGraph(true);
            qw->setPersistentGraphics(true);
        }
    }
    // The window's real (fractional) scale; QML's Screen.devicePixelRatio is the screen's integer one.
    Q_INVOKABLE qreal scaleOf(QWindow *window) const { return window ? window->devicePixelRatio() : 1.0; }
    // KWin's blur behind the whole surface (drawn only with OpenGL compositing).
    Q_INVOKABLE void enableBlur(QWindow *window, int radius) const
    {
        Q_UNUSED(radius)
        if (window)
            KWindowEffects::enableBlurBehind(window, true);
    }
    // KWin's blur behind exactly these items: each one's rounded rectangle (radius px) where it is
    // drawn now (scene geometry, so the motion's Translate and the item's clipping ancestors count),
    // cut to the surface. Called on every frame of an open/close motion, so that the blur moves and
    // is clipped with the panel instead of waiting at its final place. Invisible items are skipped;
    // no item: no blur. Unchanged regions are not sent again.
    Q_INVOKABLE void setBlurItems(QWindow *window, const QVariantList &items, int radius)
    {
        if (!window)
            return;
        const QRegion region = itemsRegion(window, items, radius);
        auto it = m_blur.find(window);
        if (it != m_blur.end() && it.value() == region)
            return;
        m_blur.insert(window, region);
        KWindowEffects::enableBlurBehind(window, !region.isEmpty(), region);
    }
    Q_INVOKABLE void clearBlur(QWindow *window)
    {
        if (!window)
            return;
        m_blur.remove(window);
        KWindowEffects::enableBlurBehind(window, false);
    }
    // Input region of the surface = these items' rectangles (the shadow and the gap above the
    // taskbar stay click-through). No item: the whole surface.
    Q_INVOKABLE void setInputItems(QWindow *window, const QVariantList &items) const
    {
        if (window)
            window->setMask(itemsRegion(window, items, 0));
    }
    // Rounded rectangle as a region of whole logical px: rows inset at the corners.
    static QRegion roundedRegion(const QRect &r, int radius)
    {
        radius = std::min({radius, r.width() / 2, r.height() / 2});
        if (radius <= 0)
            return QRegion(r);
        QRegion out(r.adjusted(0, radius, 0, -radius));
        for (int i = 0; i < radius; ++i) {
            const double dy = radius - i - 0.5;
            const int inset = int(std::lround(radius - std::sqrt(std::max(0.0, double(radius) * radius - dy * dy))));
            out += QRect(r.left() + inset, r.top() + i, r.width() - 2 * inset, 1);
            out += QRect(r.left() + inset, r.bottom() - i, r.width() - 2 * inset, 1);
        }
        return out;
    }

private:
    static QRegion itemsRegion(QWindow *window, const QVariantList &items, int radius)
    {
        QRegion region;
        for (const QVariant &v : items) {
            auto *item = qobject_cast<QQuickItem *>(v.value<QObject *>());
            if (!item || !item->isVisible() || item->width() <= 0 || item->height() <= 0)
                continue;
            QRectF r = item->mapRectToScene(QRectF(0, 0, item->width(), item->height()));
            for (QQuickItem *p = item->parentItem(); p; p = p->parentItem())
                if (p->clip())
                    r &= p->mapRectToScene(QRectF(0, 0, p->width(), p->height()));
            if (r.isEmpty())
                continue;
            const QRect ri(QPoint(int(std::lround(r.left())), int(std::lround(r.top()))),
                           QPoint(int(std::lround(r.right())) - 1, int(std::lround(r.bottom())) - 1));
            region += roundedRegion(ri, radius);
        }
        return region & QRect(0, 0, window->width(), window->height());
    }
    QHash<QWindow *, QRegion> m_blur;
};
