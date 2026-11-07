// SPDX-License-Identifier: GPL-3.0-or-later
#include "iconoverrides.h"

#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPainter>
#include <QRegularExpression>
#include <QStandardPaths>
#include <QUrl>

namespace
{
const QString kAssets = QStringLiteral("/usr/share/fenestra/assets/");
std::function<bool()> g_dark = [] { return true; };

// Only regular files that exist are used: a stale entry falls back to Fenestra's icon.
QString existing(const QString &file)
{
    const QFileInfo fi(file);
    return fi.isAbsolute() && fi.isFile() ? fi.filePath() : QString();
}
}

IconOverrides *IconOverrides::instance()
{
    static IconOverrides overrides;
    return &overrides;
}

void IconOverrides::setDarkMode(std::function<bool()> dark)
{
    g_dark = std::move(dark);
}

bool IconOverrides::dark()
{
    return g_dark();
}

QString IconOverrides::path()
{
    return QStandardPaths::writableLocation(QStandardPaths::GenericDataLocation) + QStringLiteral("/fenestra/icon-overrides.json");
}

IconOverrides::IconOverrides()
{
    reload();
}

void IconOverrides::reload()
{
    m_icons.clear();
    m_iconsLight.clear();
    m_assets.clear();
    m_assetsLight.clear();
    m_snip.clear();
    QFile f(path());
    if (!f.open(QIODevice::ReadOnly) || f.size() > (8 << 20))
        return;
    const QJsonObject root = QJsonDocument::fromJson(f.readAll()).object();
    if (root.value(QStringLiteral("version")).toInt() != 1)
        return;
    auto lists = [&](const char *key, QHash<QString, QStringList> &into) {
        const QJsonObject o = root.value(QLatin1String(key)).toObject();
        for (auto it = o.begin(); it != o.end(); ++it) {
            QStringList files;
            const QJsonArray a = it.value().toArray();
            for (const auto &v : a)
                if (const QString file = existing(v.toString()); !file.isEmpty())
                    files << file;
            if (!files.isEmpty())
                into.insert(it.key(), files);
        }
    };
    auto strings = [&](const char *key, QHash<QString, QString> &into) {
        const QJsonObject o = root.value(QLatin1String(key)).toObject();
        for (auto it = o.begin(); it != o.end(); ++it)
            if (const QString file = existing(it.value().toString()); !file.isEmpty())
                into.insert(it.key(), file);
    };
    lists("icons", m_icons);
    lists("icons_light", m_iconsLight);
    strings("assets", m_assets);
    strings("assets_light", m_assetsLight);
    strings("snip", m_snip);
}

QIcon IconOverrides::icon(const QString &name) const
{
    const QStringList *files = nullptr;
    if (!dark())
        if (auto it = m_iconsLight.constFind(name); it != m_iconsLight.constEnd())
            files = &it.value();
    if (!files)
        if (auto it = m_icons.constFind(name); it != m_icons.constEnd())
            files = &it.value();
    if (!files)
        return {};
    QIcon icon;
    for (const QString &file : *files)
        icon.addFile(file); // every size of an app logo; one scalable SVG for a glyph
    return icon;
}

QString IconOverrides::asset(const QString &relative) const
{
    if (!dark())
        if (auto it = m_assetsLight.constFind(relative); it != m_assetsLight.constEnd())
            return it.value();
    return m_assets.value(relative);
}

QString IconOverrides::snip(const QString &name) const
{
    return m_snip.value(name);
}

// A shell installed for one user (tools/install-shell-user.sh) brings its own copy of the assets
// to ~/.local/share/fenestra/shell-assets, since it cannot write /usr/share/fenestra/assets.
static QString userShellAsset(const QString &relative)
{
    static const QString dir = QStandardPaths::writableLocation(QStandardPaths::GenericDataLocation)
        + QStringLiteral("/fenestra/shell-assets/");
    static const bool present = QFileInfo(dir).isDir();
    if (!present)
        return {};
    const QString file = dir + relative;
    return QFileInfo::exists(file) ? file : QString();
}

QString IconOverrides::redirect(const QString &url) const
{
    if (url.startsWith(QLatin1String("file://"))) {
        const QString file = QUrl(url).toLocalFile();
        if (!file.startsWith(kAssets))
            return {};
        const QString relative = file.mid(kAssets.size());
        if (!isEmpty())
            if (const QString pack = asset(relative); !pack.isEmpty())
                return pack;
        return userShellAsset(relative);
    }
    if (isEmpty())
        return {};
    if (url.startsWith(QLatin1String("qrc:"))) {
        static const QRegularExpression snipIcon(QStringLiteral("/snip/icons/([A-Za-z0-9._-]+)\\.svg$"));
        const auto m = snipIcon.match(QUrl(url).path());
        return m.hasMatch() ? snip(m.captured(1)) : QString();
    }
    return {};
}

QUrl IconOverrideInterceptor::intercept(const QUrl &url, DataType type)
{
    if (type != UrlString || !url.isLocalFile())
        return url;
    const QString file = IconOverrides::instance()->redirect(url.toString());
    return file.isEmpty() ? url : QUrl::fromLocalFile(file);
}

QPixmap IconProvider::requestPixmap(const QString &id, QSize *size, const QSize &requested)
{
    const QSize want = requested.isValid() ? requested : QSize(32, 32);
    QIcon icon = IconOverrides::instance()->icon(id);
    if (icon.isNull())
        icon = QIcon::fromTheme(id);
    if (icon.isNull())
        icon = QIcon::fromTheme(id.toLower());
    if (icon.isNull())
        icon = QIcon::fromTheme(QStringLiteral("application-x-executable"));
    const QPixmap pixmap = icon.pixmap(want);
    if (size)
        *size = pixmap.size();
    return pixmap;
}

QImage TintProvider::requestImage(const QString &id, QSize *size, const QSize &requested)
{
    const QColor color(QLatin1Char('#') + id.section(QLatin1Char('/'), 0, 0));
    const QString what = QUrl::fromPercentEncoding(id.section(QLatin1Char('/'), 1).toUtf8());
    const QSize want = requested.isValid() ? requested : QSize(16, 16);
    QImage img;
    if (const QString packFile = IconOverrides::instance()->redirect(what); !packFile.isEmpty())
        img = QIcon(packFile).pixmap(want).toImage();
    else if (what.startsWith(QLatin1String("file:")))
        img = QIcon(QUrl(what).toLocalFile()).pixmap(want).toImage();
    else if (what.startsWith(QLatin1String("qrc:"))) // glyphs built into the shell (qml/snip/icons)
        img = QIcon(QLatin1Char(':') + QUrl(what).path()).pixmap(want).toImage();
    else if (QIcon pack = IconOverrides::instance()->icon(what); !pack.isNull())
        img = pack.pixmap(want).toImage();
    else
        img = QIcon::fromTheme(what).pixmap(want).toImage();
    img = img.convertToFormat(QImage::Format_ARGB32_Premultiplied);
    QPainter p(&img);
    p.setCompositionMode(QPainter::CompositionMode_SourceIn);
    p.fillRect(img.rect(), color);
    p.end();
    if (size)
        *size = img.size();
    return img;
}
