// SPDX-License-Identifier: GPL-3.0-or-later
// Icons of the user's imported Fenestra icon pack (docs/ICON-PACK-FORMAT.md, glyphs/ and app logos).
// The importer (tools/fenestra-import-windows-assets) maps pack glyphs onto the names and files the
// shell asks for and writes ~/.local/share/fenestra/icon-overrides.json:
//   icons / icons_light   icon name -> pack files (image://icon/<name>, image://tint/<rgb>/<name>)
//   assets / assets_light  path under /usr/share/fenestra/assets -> pack file (menus, power, Ctrl+Alt+Del)
//   snip                  snipping toolbar glyph name (qml/snip/icons/<name>.svg) -> pack file
// Without that file (no pack imported) every lookup misses and Fenestra's own icons are used.
#pragma once

#include <QHash>
#include <QIcon>
#include <QQmlAbstractUrlInterceptor>
#include <QQuickImageProvider>
#include <QString>
#include <QStringList>
#include <functional>

class IconOverrides
{
public:
    static IconOverrides *instance();
    // Where the shell's dark/light mode comes from (Theme::dark in the shell; tests set their own).
    static void setDarkMode(std::function<bool()> dark);
    static bool dark();
    static QString path(); // $XDG_DATA_HOME/fenestra/icon-overrides.json

    void reload();
    bool isEmpty() const { return m_icons.isEmpty() && m_assets.isEmpty() && m_snip.isEmpty(); }
    // Pack icon for a theme icon name (null QIcon when the pack has none).
    QIcon icon(const QString &name) const;
    // Pack file for a Fenestra asset ("menu-icons/win11-menu-cancel.svg"), or empty.
    QString asset(const QString &relative) const;
    QString snip(const QString &name) const;
    // file:///usr/share/fenestra/assets/... or qrc:/.../snip/icons/<name>.svg -> local pack file, or empty.
    QString redirect(const QString &url) const;

private:
    IconOverrides();
    QHash<QString, QStringList> m_icons, m_iconsLight;
    QHash<QString, QString> m_assets, m_assetsLight, m_snip;
};

// Image.source = file:///usr/share/fenestra/assets/... -> the pack's file (dark surfaces show assets as is).
class IconOverrideInterceptor : public QQmlAbstractUrlInterceptor
{
public:
    QUrl intercept(const QUrl &url, DataType type) override;
};

// image://icon/<name>: the pack's icon, else the Fenestra icon theme (hicolor as fallback).
class IconProvider : public QQuickImageProvider
{
public:
    IconProvider() : QQuickImageProvider(QQuickImageProvider::Pixmap) {}
    QPixmap requestPixmap(const QString &id, QSize *size, const QSize &requested) override;
};

// image://tint/<rrggbb>/<icon name, file or qrc URL>: a glyph recoloured (light mode: Fenestra's white
// line-art glyphs drawn in #1a1a1a), with QPainter so it works with every scene graph backend.
class TintProvider : public QQuickImageProvider
{
public:
    TintProvider() : QQuickImageProvider(QQuickImageProvider::Image) {}
    QImage requestImage(const QString &id, QSize *size, const QSize &requested) override;
};
