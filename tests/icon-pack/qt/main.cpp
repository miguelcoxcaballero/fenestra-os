// SPDX-License-Identifier: GPL-3.0-or-later
// iconpack-test PACKDIR: checks that Fenestra Shell's icon lookup (shell/src/core/iconoverrides.cpp)
// finds the icons fenestra-import-windows-assets installed from a pack, and keeps Fenestra's own
// icons where the pack maps nothing. PACKDIR = ~/.local/share/fenestra/packs/<id> of that import.
// With --no-pack it checks the fallback only (no icon-overrides.json).
#include <QGuiApplication>
#include <QIcon>
#include <QQmlEngine>
#include <QQuickItem>
#include <QQuickView>
#include <QQuickWindow>
#include <QSGRendererInterface>
#include <QTimer>
#include <QUrl>
#include <cstdio>

#include "iconoverrides.h"

static int failures = 0;
static void check(bool ok, const QString &what)
{
    std::printf("%s %s\n", ok ? "ok  " : "FAIL", qPrintable(what));
    if (!ok)
        ++failures;
}

// Alpha masks equal (same shape) within a few levels of antialiasing.
static bool sameShape(const QImage &a, const QImage &b)
{
    if (a.size() != b.size() || a.isNull())
        return false;
    const QImage x = a.convertToFormat(QImage::Format_ARGB32), y = b.convertToFormat(QImage::Format_ARGB32);
    int diff = 0, ink = 0;
    for (int j = 0; j < x.height(); ++j)
        for (int i = 0; i < x.width(); ++i) {
            const int p = qAlpha(x.pixel(i, j)), q = qAlpha(y.pixel(i, j));
            ink += p > 128;
            diff += std::abs(p - q) > 64;
        }
    return ink > 0 && diff * 50 <= ink; // under 2 % of the ink differs
}

static QRgb dominant(const QImage &img)
{
    const QImage x = img.convertToFormat(QImage::Format_ARGB32);
    QHash<QRgb, int> n;
    for (int j = 0; j < x.height(); ++j)
        for (int i = 0; i < x.width(); ++i)
            if (qAlpha(x.pixel(i, j)) == 255)
                ++n[x.pixel(i, j) | 0xff000000];
    QRgb best = 0;
    int most = 0;
    for (auto it = n.begin(); it != n.end(); ++it)
        if (it.value() > most) { most = it.value(); best = it.key(); }
    return best;
}

// The colour of the most opaque glyph pixels of a grab on black.
static QRgb strongest(const QImage &img)
{
    QRgb best = 0;
    int level = -1;
    for (int j = 0; j < img.height(); ++j)
        for (int i = 0; i < img.width(); ++i) {
            const QRgb p = img.pixel(i, j);
            if (const int l = qMax(qRed(p), qMax(qGreen(p), qBlue(p))); l > level) { level = l; best = p | 0xff000000; }
        }
    return best;
}

int main(int argc, char **argv)
{
    QQuickWindow::setGraphicsApi(QSGRendererInterface::Software);
    QGuiApplication app(argc, argv);
    const bool noPack = app.arguments().contains(QStringLiteral("--no-pack"));
    const QString pack = noPack ? QString() : app.arguments().value(1);
    bool dark = true;
    IconOverrides::setDarkMode([&] { return dark; });
    auto *ov = IconOverrides::instance();
    IconProvider icons;
    TintProvider tint;
    const QSize s16(16, 16), s48(48, 48);
    auto file = [&](const QString &rel) { return QIcon(pack + QLatin1Char('/') + rel).pixmap(s16).toImage(); };

    if (noPack) {
        check(ov->isEmpty(), QStringLiteral("no icon-overrides.json: nothing overridden"));
        check(ov->icon(QStringLiteral("go-previous-symbolic")).isNull(), QStringLiteral("go-previous-symbolic -> Fenestra theme"));
    } else {
        check(!ov->isEmpty(), QStringLiteral("icon-overrides.json loaded from ") + IconOverrides::path());
        // image://icon/<name>: dark = white glyph, light = currentColor glyph
        QImage got = icons.requestPixmap(QStringLiteral("go-previous-symbolic"), nullptr, s16).toImage();
        check(sameShape(got, file(QStringLiteral("glyphs/white/go-previous.svg"))) && qRed(dominant(got)) == 255,
              QStringLiteral("image://icon/go-previous-symbolic (Quick Settings back) = pack glyph go-previous, white in dark mode"));
        dark = false;
        got = icons.requestPixmap(QStringLiteral("go-previous-symbolic"), nullptr, s16).toImage();
        check(sameShape(got, file(QStringLiteral("glyphs/go-previous.svg"))) && qRed(dominant(got)) == 0,
              QStringLiteral("image://icon/go-previous-symbolic in light mode = currentColor glyph"));
        dark = true;
        got = icons.requestPixmap(QStringLiteral("pan-up-symbolic"), nullptr, s16).toImage();
        check(sameShape(got, file(QStringLiteral("glyphs/white/pan-up.svg"))), QStringLiteral("image://icon/pan-up-symbolic (tray ^) = pack glyph pan-up"));
        got = icons.requestPixmap(QStringLiteral("emblem-system-symbolic"), nullptr, s16).toImage();
        check(sameShape(got, file(QStringLiteral("glyphs/white/preferences-system.svg"))),
              QStringLiteral("image://icon/emblem-system-symbolic (Quick Settings gear) = pack glyph preferences-system"));
        // app logos, through the Fenestra app's own icon name (alias)
        QSize size;
        got = icons.requestPixmap(QStringLiteral("org.gnome.Calculator"), &size, s48).toImage();
        check(size == s48 && dominant(got) == qRgb(0, 120, 212), QStringLiteral("image://icon/org.gnome.Calculator = pack logo calculator (48 px)"));
        dark = false;
        got = icons.requestPixmap(QStringLiteral("org.gnome.Calculator"), &size, s48).toImage();
        check(dominant(got) == qRgb(250, 200, 0), QStringLiteral("light mode: apps/light variant of calculator"));
        dark = true;
        got = icons.requestPixmap(QStringLiteral("microsoft-edge"), &size, QSize(24, 24)).toImage();
        check(size == QSize(24, 24) && dominant(got) == qRgb(0, 150, 100), QStringLiteral("image://icon/microsoft-edge = pack logo (24 px taskbar size)"));
        check(ov->icon(QStringLiteral("org.mozilla.firefox")).isNull(), QStringLiteral("Firefox keeps its own icon (no Edge logo on it)"));
        check(ov->icon(QStringLiteral("megaphone")).isNull() && ov->icon(QStringLiteral("folder")).isNull(),
              QStringLiteral("unmapped names (megaphone, folder) -> Fenestra theme"));
        // image://tint: names, Fenestra asset files and the snipping toolbar's qrc glyphs
        auto tinted = [&](const QString &what) {
            return tint.requestImage(QStringLiteral("ff0000/") + QString::fromUtf8(QUrl::toPercentEncoding(what)), nullptr, s16);
        };
        got = tinted(QStringLiteral("qrc:/qt/qml/Fenestra/Shell/snip/icons/snip-rectangle.svg"));
        check(sameShape(got, file(QStringLiteral("glyphs/white/selection-rectangle.svg"))) && dominant(got) == qRgb(255, 0, 0),
              QStringLiteral("snipping toolbar Rectangle (qrc snip-rectangle.svg) = pack glyph selection-rectangle, tinted"));
        got = tinted(QStringLiteral("file:///usr/share/fenestra/assets/power/3.svg"));
        check(sameShape(got, file(QStringLiteral("glyphs/white/system-shutdown.svg"))), QStringLiteral("Start power Shut down (assets/power/3.svg) = pack glyph system-shutdown"));
        got = tinted(QStringLiteral("night-light-symbolic"));
        check(sameShape(got, file(QStringLiteral("glyphs/white/night-light.svg"))), QStringLiteral("image://tint/.../night-light-symbolic = pack glyph night-light"));
        check(ov->redirect(QStringLiteral("file:///usr/share/fenestra/assets/power/0.svg")).isEmpty(),
              QStringLiteral("assets/power/0.svg (no glyph in icons.json) -> Fenestra's own file"));
    }

    // QML: Image.source = file:///usr/share/fenestra/assets/... goes through the URL interceptor
    // (dark surfaces show assets untinted), also when bound from another url property (SymbolicIcon).
    QQuickView view;
    view.engine()->addUrlInterceptor(new IconOverrideInterceptor);
    view.engine()->addImageProvider(QStringLiteral("icon"), new IconProvider);
    view.setColor(Qt::black);
    view.setResizeMode(QQuickView::SizeViewToRootObject);
    view.setSource(QUrl(QStringLiteral("data:text/plain,") + QString::fromUtf8(QUrl::toPercentEncoding(QStringLiteral(R"(
import QtQuick
Item {
    width: 64; height: 32
    Image { x: 0; width: 16; height: 16; sourceSize: Qt.size(16, 16); source: "file:///usr/share/fenestra/assets/menu-icons/win11-menu-cancel.svg" }
    Image { x: 24; width: 16; height: 16; sourceSize: Qt.size(16, 16); property url src_: "file:///usr/share/fenestra/assets/power/1.svg"; source: src_ }
    Image { x: 48; width: 16; height: 16; sourceSize: Qt.size(16, 16); source: "image://icon/airplane-mode-symbolic" }
}
)")))));
    if (view.status() != QQuickView::Ready) {
        // data: URLs need Qt 6.x QML; fall back to a temporary file
        std::printf("FAIL QML did not load\n");
        return 1;
    }
    view.show();
    QImage shot;
    QTimer::singleShot(800, [&] { shot = view.grabWindow(); app.quit(); });
    app.exec();
    const QImage cancel = shot.copy(0, 0, 16, 16), lock = shot.copy(24, 0, 16, 16), plane = shot.copy(48, 0, 16, 16);
    auto inkOf = [](const QImage &img) { // grabbed on black: the glyph's coverage as alpha
        QImage a(img.size(), QImage::Format_ARGB32);
        for (int j = 0; j < img.height(); ++j)
            for (int i = 0; i < img.width(); ++i)
                a.setPixel(i, j, qRgba(255, 255, 255, qMax(qRed(img.pixel(i, j)), qMax(qGreen(img.pixel(i, j)), qBlue(img.pixel(i, j))))));
        return a;
    };
    if (noPack) {
        const QImage own = QIcon(QStringLiteral("/usr/share/fenestra/assets/menu-icons/win11-menu-cancel.svg")).pixmap(s16).toImage();
        check(sameShape(inkOf(cancel), own) && strongest(cancel) != qRgb(255, 255, 255),
              QStringLiteral("QML Image menu-icons/win11-menu-cancel.svg = Fenestra's own file (its own colour)"));
    } else {
        check(sameShape(inkOf(cancel), file(QStringLiteral("glyphs/white/window-close-symbolic.svg"))) && strongest(cancel) == qRgb(255, 255, 255),
              QStringLiteral("QML Image menu-icons/win11-menu-cancel.svg (jump list Close window) -> pack glyph, white"));
        check(sameShape(inkOf(lock), file(QStringLiteral("glyphs/white/system-lock-screen.svg"))),
              QStringLiteral("QML Image bound through a url property (power/1.svg, Lock) -> pack glyph"));
        check(sameShape(inkOf(plane), file(QStringLiteral("glyphs/white/airplane-mode.svg"))),
              QStringLiteral("QML image://icon/airplane-mode-symbolic -> pack glyph"));
    }
    shot.save(QStringLiteral("/out/iconpack-qml%1.png").arg(noPack ? QStringLiteral("-nopack") : QString()));
    std::printf("%s\n", failures ? "SOME FAILED" : "ALL PASS");
    return failures ? 1 : 0;
}
