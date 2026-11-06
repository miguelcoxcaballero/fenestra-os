// SPDX-License-Identifier: GPL-3.0-or-later
#include "search.h"

#include "apps.h"
#include "shellsettings.h"
#include "startservices.h"

#include <KIO/OpenUrlJob>
#include <QClipboard>
#include <QDir>
#include <QDirIterator>
#include <QFile>
#include <QGuiApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QMimeDatabase>
#include <QProcess>
#include <QStandardPaths>
#include <QThread>
#include <QUrl>

namespace
{
// Normalised for matching: lower case, no accents (as fenestra_settings/search.py norm()).
QString norm(const QString &s)
{
    QString d = s.toLower().normalized(QString::NormalizationForm_KD);
    QString out;
    out.reserve(d.size());
    for (QChar c : d)
        if (c.category() != QChar::Mark_NonSpacing)
            out.append(c);
    return out;
}
int score(const QString &nameNorm, const QString &hayNorm, const QString &q, const QStringList &words)
{
    for (const QString &w : words)
        if (!hayNorm.contains(w))
            return -1;
    if (nameNorm.startsWith(q))
        return 100;
    if (nameNorm.contains(QLatin1Char(' ') + q))
        return 80;
    if (nameNorm.contains(q))
        return 60;
    return 30;
}
QString cacheDir()
{
    const QString d = QStandardPaths::writableLocation(QStandardPaths::GenericCacheLocation) + QStringLiteral("/fenestra");
    QDir().mkpath(d);
    return d;
}
bool es() { return QLocale().name().startsWith(QLatin1String("es")); }
QString T(const char *en, const char *sp) { return es() ? QString::fromUtf8(sp) : QString::fromUtf8(en); }
}

Search *Search::instance()
{
    static auto *s = new Search;
    return s;
}

Search *Search::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

Search::Search(QObject *parent)
    : QObject(parent)
{
}

void Search::setText(const QString &text)
{
    if (text == m_text)
        return;
    m_text = text;
    run();
}

void Search::setFilter(const QString &filter)
{
    if (filter == m_filter)
        return;
    m_filter = filter;
    run();
}

void Search::prepare()
{
    loadSettingsIndex();
    if (!m_indexing && (!m_filesAt.isValid() || m_filesAt.secsTo(QDateTime::currentDateTime()) > 600))
        indexFiles();
}

void Search::loadSettingsIndex()
{
    if (!m_settingsIndex.isEmpty() || m_settingsLoading)
        return;
    const QString lang = es() ? QStringLiteral("es") : QStringLiteral("en");
    const QString cache = cacheDir() + QStringLiteral("/settings-index-%1.json").arg(lang);
    auto parse = [this](const QByteArray &data) {
        m_settingsIndex = QJsonDocument::fromJson(data).array().toVariantList();
        run();
    };
    QFile f(cache);
    // Reuse the cache while it is newer than the installed Settings app.
    const QFileInfo app(QStandardPaths::findExecutable(QStringLiteral("fenestra-settings")));
    if (f.open(QIODevice::ReadOnly) && (!app.exists() || QFileInfo(cache).lastModified() > app.lastModified())) {
        parse(f.readAll());
        return;
    }
    m_settingsLoading = true;
    auto *p = new QProcess(this);
    connect(p, &QProcess::finished, this, [this, p, cache, parse](int code) {
        m_settingsLoading = false;
        p->deleteLater();
        if (code != 0)
            return;
        const QByteArray data = p->readAllStandardOutput();
        QFile out(cache);
        if (out.open(QIODevice::WriteOnly))
            out.write(data);
        parse(data);
    });
    p->start(QStringLiteral("fenestra-settings"), {QStringLiteral("--export-search-index"), QStringLiteral("--lang"), lang});
}

void Search::indexFiles()
{
    m_indexing = true;
    Q_EMIT indexingChanged();
    QStringList roots;
    const QString home = QDir::homePath();
    // XDG user folders (localised names come from user-dirs.dirs); without that file Qt answers
    // $HOME, so use the XDG default names then.
    const QList<QPair<QStandardPaths::StandardLocation, const char *>> folders{
        {QStandardPaths::DesktopLocation, "Desktop"}, {QStandardPaths::DocumentsLocation, "Documents"},
        {QStandardPaths::DownloadLocation, "Downloads"}, {QStandardPaths::MusicLocation, "Music"},
        {QStandardPaths::PicturesLocation, "Pictures"}, {QStandardPaths::MoviesLocation, "Videos"}};
    for (const auto &[loc, fallback] : folders) {
        QString dir = QStandardPaths::writableLocation(loc);
        if (dir.isEmpty() || QDir(dir) == QDir(home))
            dir = home + QLatin1Char('/') + QLatin1String(fallback);
        roots << dir;
    }
    QThread *thread = QThread::create([this, roots, home] {
        QList<FileEntry> files;
        QMimeDatabase mimes;
        QSet<QString> seen;
        auto add = [&](const QFileInfo &fi) {
            if (seen.contains(fi.absoluteFilePath()))
                return;
            seen.insert(fi.absoluteFilePath());
            const bool image = !fi.isDir() && mimes.mimeTypeForFile(fi, QMimeDatabase::MatchExtension).name().startsWith(QLatin1String("image/"));
            files.append({fi.absoluteFilePath(), fi.fileName(), norm(fi.fileName()), fi.isDir(), image, fi.lastModified()});
        };
        // Top-level folders of home, then the XDG folders a few levels deep. Hidden files are skipped.
        for (const QFileInfo &fi : QDir(home).entryInfoList(QDir::Dirs | QDir::NoDotAndDotDot))
            add(fi);
        for (const QString &root : roots) {
            if (root.isEmpty() || root == home || !QFileInfo(root).isDir())
                continue;
            add(QFileInfo(root));
            QDirIterator it(root, QDir::AllEntries | QDir::NoDotAndDotDot, QDirIterator::Subdirectories);
            while (it.hasNext() && files.size() < 20000) {
                const QFileInfo fi = it.nextFileInfo();
                if (fi.absoluteFilePath().mid(root.size()).count(QLatin1Char('/')) > 4)
                    continue;
                add(fi);
            }
        }
        QMetaObject::invokeMethod(this, [this, files] {
            m_files = files;
            m_filesAt = QDateTime::currentDateTime();
            m_indexing = false;
            Q_EMIT indexingChanged();
            run();
        });
    });
    connect(thread, &QThread::finished, thread, &QObject::deleteLater);
    thread->start(QThread::LowPriority);
}

void Search::run()
{
    m_sections.clear();
    m_best.clear();
    const QString q = norm(m_text.trimmed());
    if (q.isEmpty()) {
        Q_EMIT resultsChanged();
        return;
    }
    const QStringList words = q.split(QLatin1Char(' '), Qt::SkipEmptyParts);
    const bool all = m_filter == QLatin1String("all");
    const int limit = all ? 4 : 12;
    struct Hit { int score; QVariantMap item; };
    auto take = [](QList<Hit> hits, int n) {
        std::stable_sort(hits.begin(), hits.end(), [](const Hit &a, const Hit &b) { return a.score > b.score; });
        QVariantList out;
        for (int i = 0; i < hits.size() && i < n; ++i)
            out.append(hits.at(i).item);
        return out;
    };
    QList<Hit> best;

    QList<Hit> apps;
    if (all || m_filter == QLatin1String("apps")) {
        for (const AllApps::App &a : AllApps::instance()->apps()) {
            const QString name = norm(a.name);
            int s = score(name, name + QLatin1Char(' ') + norm(a.genericName + QLatin1Char(' ') + a.keywords), q, words);
            if (s < 0)
                continue;
            s += std::min(20, Usage::instance()->launches(a.storageId));
            apps.append({s, {{QStringLiteral("kind"), QStringLiteral("app")}, {QStringLiteral("title"), a.name},
                             {QStringLiteral("subtitle"), T("App", "Aplicación")}, {QStringLiteral("icon"), a.icon},
                             {QStringLiteral("id"), a.storageId}}});
        }
    }
    QList<Hit> settings;
    if (all || m_filter == QLatin1String("settings")) {
        for (const QVariant &v : m_settingsIndex) {
            const QVariantMap e = v.toMap();
            const QString title = e.value(QStringLiteral("title")).toString();
            int s = score(norm(title), e.value(QStringLiteral("hay")).toString(), q, words);
            if (s < 0)
                continue;
            if (e.value(QStringLiteral("key")).isNull())
                s += 5; // pages before rows
            settings.append({s - int(title.size() / 10), {{QStringLiteral("kind"), QStringLiteral("setting")}, {QStringLiteral("title"), title},
                                                           {QStringLiteral("subtitle"), e.value(QStringLiteral("where"))},
                                                           {QStringLiteral("icon"), QStringLiteral("fenestra-settings")},
                                                           {QStringLiteral("id"), e.value(QStringLiteral("page"))}}});
        }
    }
    QList<Hit> docs, folders, photos;
    const bool wantFiles = all || m_filter == QLatin1String("files") || m_filter == QLatin1String("folders") || m_filter == QLatin1String("photos");
    if (wantFiles) {
        QMimeDatabase mimes;
        for (const FileEntry &f : m_files) {
            const int s = score(f.lower, f.lower, q, words);
            if (s < 0)
                continue;
            const QString kind = f.dir ? QStringLiteral("folder") : f.image ? QStringLiteral("photo") : QStringLiteral("file");
            const QString icon = f.dir ? QStringLiteral("folder") : mimes.mimeTypeForFile(f.path, QMimeDatabase::MatchExtension).iconName();
            QVariantMap item{{QStringLiteral("kind"), kind}, {QStringLiteral("title"), f.name},
                             {QStringLiteral("subtitle"), QDir::toNativeSeparators(QFileInfo(f.path).absolutePath()).replace(QDir::homePath(), QStringLiteral("~"))},
                             {QStringLiteral("icon"), icon}, {QStringLiteral("path"), f.path}, {QStringLiteral("modified"), f.modified}};
            if (f.image)
                item.insert(QStringLiteral("iconSource"), QUrl::fromLocalFile(f.path).toString());
            // Newer files first among equals.
            const int age = int(std::min<qint64>(30, f.modified.daysTo(QDateTime::currentDateTime())));
            (f.dir ? folders : f.image ? photos : docs).append({s - age / 3, item});
        }
    }

    auto section = [this](const QString &title, const QVariantList &items) {
        if (!items.isEmpty())
            m_sections.append(QVariantMap{{QStringLiteral("title"), title}, {QStringLiteral("items"), items}});
    };
    for (auto *list : {&apps, &settings, &docs, &folders, &photos})
        best += *list;
    std::stable_sort(best.begin(), best.end(), [](const Hit &a, const Hit &b) { return a.score > b.score; });
    if (!best.isEmpty() && m_filter != QLatin1String("web"))
        m_best = best.first().item;
    auto without = [this](QList<Hit> list) {
        list.erase(std::remove_if(list.begin(), list.end(), [this](const Hit &h) { return h.item == m_best; }), list.end());
        return list;
    };
    if (!m_best.isEmpty())
        section(T("Best match", "Mejor coincidencia"), {m_best});
    section(T("Apps", "Aplicaciones"), take(without(apps), limit));
    section(T("Documents", "Documentos"), take(without(docs), limit));
    section(T("Folders", "Carpetas"), take(without(folders), limit));
    section(T("Photos", "Fotos"), take(without(photos), limit));
    section(T("Settings", "Configuración"), take(without(settings), limit));
    if (all || m_filter == QLatin1String("web"))
        section(T("Search the web", "Buscar en la Web"),
                {QVariantMap{{QStringLiteral("kind"), QStringLiteral("web")}, {QStringLiteral("title"), m_text.trimmed()},
                             {QStringLiteral("subtitle"), T("See web results", "Ver resultados web")},
                             {QStringLiteral("icon"), QStringLiteral("web-browser")}}});
    if (m_best.isEmpty() && m_filter == QLatin1String("web") && !m_sections.isEmpty())
        m_best = m_sections.last().toMap().value(QStringLiteral("items")).toList().first().toMap();
    Q_EMIT resultsChanged();
}

void Search::activate(const QVariantMap &item, const QString &action)
{
    const QString kind = item.value(QStringLiteral("kind")).toString();
    Usage::instance()->rememberQuery(m_text);
    if (kind == QLatin1String("app")) {
        const QString id = item.value(QStringLiteral("id")).toString();
        Usage::instance()->rememberApp(id);
        Apps::instance()->launch(id);
    } else if (kind == QLatin1String("setting")) {
        Apps::instance()->runCommand(QStringLiteral("fenestra-settings --page ") + item.value(QStringLiteral("id")).toString());
    } else if (kind == QLatin1String("web")) {
        searchWeb(item.value(QStringLiteral("title")).toString());
    } else {
        const QString path = item.value(QStringLiteral("path")).toString();
        if (action == QLatin1String("location"))
            RecentFiles::instance()->openLocation(QUrl::fromLocalFile(path).toString());
        else
            RecentFiles::instance()->open(QUrl::fromLocalFile(path).toString());
    }
    Q_EMIT activated();
}

void Search::searchWeb(const QString &text)
{
    // [Search] WebUrl in shell.conf; the GNOME layer opened Bing (windowsSearchHome.js).
    const QString base = ShellSettings::instance()->value(QStringLiteral("Search/WebUrl"), QStringLiteral("https://www.bing.com/search?q=")).toString();
    auto *job = new KIO::OpenUrlJob(QUrl(base + QString::fromLatin1(QUrl::toPercentEncoding(text))));
    job->start();
}

void Search::copyPath(const QVariantMap &item)
{
    QGuiApplication::clipboard()->setText(QLatin1Char('"') + item.value(QStringLiteral("path")).toString() + QLatin1Char('"'));
}
