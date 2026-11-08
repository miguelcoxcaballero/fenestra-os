// SPDX-License-Identifier: GPL-3.0-or-later
#include "desktop.h"

#include "apps.h"
#include "shellsettings.h"

#include <QRegularExpression>

#include <KDesktopFile>
#include <KIO/CopyJob>
#include <KIO/OpenUrlJob>
#include <KIO/RestoreJob>
#include <KIO/SimpleJob>
#include <QClipboard>
#include <QColor>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCall>
#include <QDir>
#include <QFile>
#include <QGuiApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMimeData>
#include <QMimeDatabase>
#include <QProcess>
#include <QStandardPaths>

namespace
{
QString positionsPath()
{
    return QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation) + QStringLiteral("/fenestra/desktop-positions.json");
}
QString folderIcon(const QString &path)
{
    // Windows' folder icons (the icon pack: "folder", "folder-full"). Explorer's "full" icon is a
    // preview of the FILES inside: a folder holding only other folders (or nothing) is the closed one.
    const bool hasFiles = !QDir(path).entryList(QDir::Files | QDir::NoDotAndDotDot).isEmpty();
    return hasFiles ? QStringLiteral("folder-full") : QStringLiteral("folder");
}
}

DesktopModel *DesktopModel::instance()
{
    static auto *m = new DesktopModel;
    return m;
}

DesktopModel *DesktopModel::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

DesktopModel::DesktopModel(QObject *parent)
    : QAbstractListModel(parent)
{
    m_dir = QStandardPaths::writableLocation(QStandardPaths::DesktopLocation);
    if (m_dir.isEmpty() || QDir(m_dir) == QDir::home())
        m_dir = QDir::homePath() + QStringLiteral("/Desktop");
    QDir().mkpath(m_dir);
    m_watcher.addPath(m_dir);
    connect(&m_watcher, &QFileSystemWatcher::directoryChanged, this, &DesktopModel::reload);
    QFile f(positionsPath());
    if (f.open(QIODevice::ReadOnly)) {
        const QJsonObject o = QJsonDocument::fromJson(f.readAll()).object();
        for (auto it = o.begin(); it != o.end(); ++it) {
            const QJsonArray a = it.value().toArray();
            m_positions.insert(it.key(), QPoint(a.at(0).toInt(), a.at(1).toInt()));
        }
    }
    reload();
}

QStringList DesktopModel::templates() const
{
    const QString dir = QStandardPaths::writableLocation(QStandardPaths::TemplatesLocation);
    if (dir.isEmpty() || QDir(dir) == QDir::home())
        return QDir(QDir::homePath() + QStringLiteral("/Templates")).entryList(QDir::Files);
    return QDir(dir).entryList(QDir::Files);
}

void DesktopModel::reload()
{
    QList<Item> items;
    items.append({QStringLiteral("Recycle Bin"), QString(), QStringLiteral("user-trash"), QString(), false, true, {}});
    QMimeDatabase mimes;
    const QFileInfoList entries = QDir(m_dir).entryInfoList(QDir::AllEntries | QDir::NoDotAndDotDot, QDir::DirsFirst | QDir::Name | QDir::IgnoreCase);
    for (const QFileInfo &fi : entries) {
        Item it{fi.fileName(), fi.absoluteFilePath(), {}, {}, fi.isDir(), false, {}};
        if (fi.isDir()) {
            it.icon = folderIcon(fi.absoluteFilePath());
        } else if (fi.suffix() == QLatin1String("desktop")) {
            KDesktopFile df(fi.absoluteFilePath());
            it.name = df.readName().isEmpty() ? fi.completeBaseName() : df.readName();
            it.icon = df.readIcon();
        } else {
            it.icon = mimes.mimeTypeForFile(fi).iconName();
        }
        items.append(it);
    }
    beginResetModel();
    m_items = items;
    layout();
    endResetModel();
    if (!m_pendingRename.isEmpty()) {
        for (int i = 0; i < m_items.size(); ++i)
            if (m_items.at(i).path == m_pendingRename) {
                m_pendingRename.clear();
                Q_EMIT renameRequested(i);
                break;
            }
    }
}

void DesktopModel::layout()
{
    // Remembered cells first; new items fill the first free cells, column by column.
    QSet<QPair<int, int>> used;
    for (Item &it : m_items) {
        const QString key = it.trash ? QStringLiteral(":trash") : it.name;
        it.cell = QPoint(-1, -1);
        if (m_positions.contains(key)) {
            const QPoint p = m_positions.value(key);
            if (p.y() < m_rows && !used.contains({p.x(), p.y()})) {
                it.cell = p;
                used.insert({p.x(), p.y()});
            }
        }
    }
    int col = 0, row = 0;
    for (Item &it : m_items) {
        if (it.cell.x() >= 0)
            continue;
        while (used.contains({col, row})) {
            if (++row >= m_rows) { row = 0; ++col; }
        }
        it.cell = QPoint(col, row);
        used.insert({col, row});
    }
}

void DesktopModel::setRowsPerColumn(int rows)
{
    if (rows < 1 || rows == m_rows)
        return;
    m_rows = rows;
    layout();
    if (!m_items.isEmpty())
        Q_EMIT dataChanged(index(0), index(m_items.size() - 1), {CellRole});
}

void DesktopModel::moveTo(int row, int column, int gridRow)
{
    if (row < 0 || row >= m_items.size() || column < 0 || gridRow < 0 || gridRow >= m_rows)
        return;
    // Swap with whatever is in the target cell.
    for (Item &other : m_items)
        if (other.cell == QPoint(column, gridRow))
            other.cell = m_items[row].cell;
    m_items[row].cell = QPoint(column, gridRow);
    savePositions();
    Q_EMIT dataChanged(index(0), index(m_items.size() - 1), {CellRole});
}

void DesktopModel::savePositions() const
{
    QJsonObject o;
    for (const Item &it : m_items)
        o.insert(it.trash ? QStringLiteral(":trash") : it.name, QJsonArray{it.cell.x(), it.cell.y()});
    QDir().mkpath(QFileInfo(positionsPath()).absolutePath());
    QFile f(positionsPath());
    if (f.open(QIODevice::WriteOnly))
        f.write(QJsonDocument(o).toJson(QJsonDocument::Compact));
}

int DesktopModel::rowCount(const QModelIndex &parent) const { return parent.isValid() ? 0 : m_items.size(); }

QVariant DesktopModel::data(const QModelIndex &index, int role) const
{
    if (!index.isValid() || index.row() >= m_items.size())
        return {};
    const Item &it = m_items.at(index.row());
    switch (role) {
    case Qt::DisplayRole:
    case NameRole: return it.trash && QLocale().name().startsWith(QLatin1String("es")) ? QStringLiteral("Papelera de reciclaje") : it.name;
    case PathRole: return it.path;
    case UrlRole: return it.trash ? QUrl(QStringLiteral("trash:/")) : QUrl::fromLocalFile(it.path);
    case IconRole: return it.icon;
    case IconSourceRole: return it.iconSource;
    case IsDirRole: return it.dir;
    case IsTrashRole: return it.trash;
    case CellRole: return it.cell;
    }
    return {};
}

QHash<int, QByteArray> DesktopModel::roleNames() const
{
    return {{NameRole, "name"}, {PathRole, "path"}, {UrlRole, "url"}, {IconRole, "icon"}, {IconSourceRole, "iconSource"},
            {IsDirRole, "isDir"}, {IsTrashRole, "isTrash"}, {CellRole, "cell"}};
}

QList<QUrl> DesktopModel::urls(const QList<int> &rows) const
{
    QList<QUrl> out;
    for (int r : rows)
        if (r >= 0 && r < m_items.size() && !m_items.at(r).trash)
            out << QUrl::fromLocalFile(m_items.at(r).path);
    return out;
}

void DesktopModel::open(int row)
{
    if (row < 0 || row >= m_items.size())
        return;
    const Item &it = m_items.at(row);
    if (it.path.endsWith(QLatin1String(".desktop"))) {
        Apps::instance()->runCommand(QStringLiteral("gio launch \"%1\"").arg(it.path));
        return;
    }
    auto *job = new KIO::OpenUrlJob(it.trash ? QUrl(QStringLiteral("trash:/")) : QUrl::fromLocalFile(it.path));
    job->setRunExecutables(false);
    job->start();
}

void DesktopModel::trash(const QList<int> &rows)
{
    const QList<QUrl> list = urls(rows);
    if (!list.isEmpty())
        KIO::trash(list); // to the Recycle Bin, restorable (no confirmation, as on the desktop of the GNOME layer)
}

void DesktopModel::rename(int row, const QString &newName)
{
    if (row < 0 || row >= m_items.size() || m_items.at(row).trash || newName.trimmed().isEmpty() || newName.contains(QLatin1Char('/')))
        return;
    const QString oldName = m_items.at(row).name;
    const QUrl from = QUrl::fromLocalFile(m_items.at(row).path);
    const QUrl to = QUrl::fromLocalFile(m_dir + QLatin1Char('/') + newName.trimmed());
    if (m_positions.contains(oldName))
        m_positions.insert(newName.trimmed(), m_positions.take(oldName));
    KIO::rename(from, to, KIO::HideProgressInfo);
}

void DesktopModel::newFolder()
{
    const bool es = QLocale().name().startsWith(QLatin1String("es"));
    const QString base = es ? QStringLiteral("Nueva carpeta") : QStringLiteral("New folder");
    QString name = base;
    for (int n = 2; QFileInfo::exists(m_dir + QLatin1Char('/') + name); ++n)
        name = QStringLiteral("%1 (%2)").arg(base).arg(n);
    m_pendingRename = m_dir + QLatin1Char('/') + name;
    QDir(m_dir).mkdir(name);
}

void DesktopModel::newFromTemplate(const QString &templateName)
{
    QString dir = QStandardPaths::writableLocation(QStandardPaths::TemplatesLocation);
    if (dir.isEmpty() || QDir(dir) == QDir::home())
        dir = QDir::homePath() + QStringLiteral("/Templates");
    const QFileInfo src(dir + QLatin1Char('/') + templateName);
    QString name = src.fileName();
    for (int n = 2; QFileInfo::exists(m_dir + QLatin1Char('/') + name); ++n)
        name = QStringLiteral("%1 (%2).%3").arg(src.completeBaseName()).arg(n).arg(src.suffix());
    m_pendingRename = m_dir + QLatin1Char('/') + name;
    QFile::copy(src.absoluteFilePath(), m_pendingRename);
}

void DesktopModel::copyAsPath(const QList<int> &rows)
{
    QStringList paths;
    for (const QUrl &u : urls(rows))
        paths << QLatin1Char('"') + u.toLocalFile() + QLatin1Char('"');
    QGuiApplication::clipboard()->setText(paths.join(QLatin1Char('\n')));
}

void DesktopModel::copy(const QList<int> &rows, bool cut)
{
    auto *data = new QMimeData;
    data->setUrls(urls(rows));
    // GNOME/Nautilus clipboard format, so Files can paste what the desktop cut or copied.
    QByteArray gnome = cut ? "cut" : "copy";
    for (const QUrl &u : urls(rows))
        gnome += '\n' + u.toEncoded();
    data->setData(QStringLiteral("x-special/gnome-copied-files"), gnome);
    data->setData(QStringLiteral("application/x-kde-cutselection"), cut ? "1" : "0");
    QGuiApplication::clipboard()->setMimeData(data);
}

void DesktopModel::paste()
{
    const QMimeData *data = QGuiApplication::clipboard()->mimeData();
    if (!data)
        return;
    QList<QUrl> list = data->urls();
    bool cut = data->data(QStringLiteral("application/x-kde-cutselection")) == "1";
    if (list.isEmpty() && data->hasFormat(QStringLiteral("x-special/gnome-copied-files"))) {
        const QList<QByteArray> lines = data->data(QStringLiteral("x-special/gnome-copied-files")).split('\n');
        cut = lines.value(0) == "cut";
        for (int i = 1; i < lines.size(); ++i)
            list << QUrl::fromEncoded(lines.at(i));
    }
    dropUrls(list, cut);
}

void DesktopModel::dropUrls(const QList<QUrl> &list, bool move)
{
    if (list.isEmpty())
        return;
    const QUrl dest = QUrl::fromLocalFile(m_dir);
    if (move)
        KIO::move(list, dest);
    else
        KIO::copy(list, dest);
}

void DesktopModel::properties(const QList<int> &rows)
{
    QStringList uris;
    for (const QUrl &u : urls(rows))
        uris << u.toString();
    QDBusMessage msg = QDBusMessage::createMethodCall(QStringLiteral("org.freedesktop.FileManager1"), QStringLiteral("/org/freedesktop/FileManager1"),
                                                      QStringLiteral("org.freedesktop.FileManager1"), QStringLiteral("ShowItemProperties"));
    msg << uris << QString();
    QDBusConnection::sessionBus().asyncCall(msg);
}

void DesktopModel::openTerminal()
{
    // xdg-terminal-exec where available, else the terminals Fedora ships.
    for (const QString &t : {QStringLiteral("xdg-terminal-exec"), QStringLiteral("ptyxis"), QStringLiteral("gnome-terminal"), QStringLiteral("konsole")}) {
        if (!QStandardPaths::findExecutable(t).isEmpty()) {
            QProcess::startDetached(t, {}, m_dir);
            return;
        }
    }
}

void DesktopModel::sortBy(const QString &key)
{
    if (key.isEmpty()) { // Refresh
        reload();
        return;
    }
    QList<Item> sorted = m_items;
    std::stable_sort(sorted.begin(), sorted.end(), [&key](const Item &a, const Item &b) {
        if (a.trash != b.trash)
            return a.trash;
        if (key == QLatin1String("type") && a.dir != b.dir)
            return a.dir;
        if (key == QLatin1String("type"))
            return QFileInfo(a.path).suffix() < QFileInfo(b.path).suffix();
        if (key == QLatin1String("date"))
            return QFileInfo(a.path).lastModified() > QFileInfo(b.path).lastModified();
        return a.name.compare(b.name, Qt::CaseInsensitive) < 0;
    });
    m_positions.clear();
    int col = 0, row = 0;
    for (const Item &it : sorted) {
        m_positions.insert(it.trash ? QStringLiteral(":trash") : it.name, QPoint(col, row));
        if (++row >= m_rows) { row = 0; ++col; }
    }
    savePositions();
    layout();
    Q_EMIT dataChanged(index(0), index(m_items.size() - 1), {CellRole});
}

WallpaperSource *WallpaperSource::instance()
{
    static auto *w = new WallpaperSource;
    return w;
}

WallpaperSource *WallpaperSource::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

WallpaperSource::WallpaperSource(QObject *parent)
    : QObject(parent)
{
    connect(ShellSettings::instance(), &ShellSettings::changed, this, &WallpaperSource::update);
    connect(&m_watcher, &QFileSystemWatcher::directoryChanged, this, &WallpaperSource::update);
    connect(&m_watcher, &QFileSystemWatcher::fileChanged, this, &WallpaperSource::update);
    update();
}

void WallpaperSource::update()
{
    const QString w = ShellSettings::instance()->wallpaper();
    QString image, color = QStringLiteral("#202020");
    if (w.startsWith(QLatin1Char('#')) && QColor::isValidColorName(w)) {
        color = w;
    } else if (w == QLatin1String("spotlight")) {
        const QString dir = QStringLiteral("/var/lib/fenestra-spotlight");
        if (QFileInfo(dir).isDir() && !m_watcher.directories().contains(dir))
            m_watcher.addPath(dir);
        QFile f(dir + QStringLiteral("/current.json"));
        if (f.open(QIODevice::ReadOnly)) {
            const QString path = QJsonDocument::fromJson(f.readAll()).object().value(QStringLiteral("image")).toString();
            // Same allow-list as the GNOME layer (fenestra-spotlight/face.js).
            static const QRegularExpression ok(QStringLiteral(
                "^/(var/lib/fenestra-spotlight/images/[a-f0-9]{64}|usr/share/backgrounds/fenestra/[A-Za-z0-9._-]+)\\.jpg$"));
            if (ok.match(path).hasMatch() && QFileInfo::exists(path))
                image = QUrl::fromLocalFile(path).toString();
        }
    } else if (QFileInfo::exists(w)) {
        image = QUrl::fromLocalFile(w).toString();
    }
    if (image == m_image && color == m_color)
        return;
    m_image = image;
    m_color = color;
    Q_EMIT changed();
}
