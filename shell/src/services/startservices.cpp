// SPDX-License-Identifier: GPL-3.0-or-later
#include "startservices.h"

#include "apps.h"
#include "shellsettings.h"

#include <KApplicationTrader>
#include <KIO/OpenUrlJob>
#include <KService>
#include <KSycoca>
#include <QCollator>
#include <QDBusConnection>
#include <QDBusInterface>
#include <QDBusMessage>
#include <QDBusReply>
#include <QDesktopServices>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMimeDatabase>
#include <QProcess>
#include <QRegularExpression>
#include <QSaveFile>
#include <QSettings>
#include <QStandardPaths>
#include <QUrl>
#include <QXmlStreamReader>
#include <unistd.h>

#define SINGLETON(Class)                                                                                               \
    Class *Class::instance()                                                                                           \
    {                                                                                                                  \
        static auto *i = new Class;                                                                                    \
        return i;                                                                                                      \
    }                                                                                                                  \
    Class *Class::create(QQmlEngine *, QJSEngine *)                                                                    \
    {                                                                                                                  \
        QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);                                          \
        return instance();                                                                                             \
    }

namespace
{
QString stateDir(const QString &sub)
{
    const QString dir = QStandardPaths::writableLocation(QStandardPaths::GenericStateLocation) + QLatin1Char('/') + sub;
    QDir().mkpath(dir);
    QFile::setPermissions(dir, QFileDevice::ReadOwner | QFileDevice::WriteOwner | QFileDevice::ExeOwner);
    return dir;
}
QVariantMap appMap(const KService::Ptr &s)
{
    return {{QStringLiteral("storageId"), s->storageId()}, {QStringLiteral("name"), s->name()}, {QStringLiteral("icon"), s->icon()}};
}
// "All apps" groups, in this order (arc/menulayouts/windowsStartHome.js:119).
const QList<QPair<QString, QRegularExpression>> &groupRules()
{
    static const QList<QPair<QString, QRegularExpression>> rules{
        {QStringLiteral("Productivity"), QRegularExpression(QStringLiteral("Office|Finance"))},
        {QStringLiteral("Social"), QRegularExpression(QStringLiteral("Network|Chat|Email"))},
        {QStringLiteral("Creativity"), QRegularExpression(QStringLiteral("Graphics|AudioVideo"))},
        {QStringLiteral("Utilities & Tools"), QRegularExpression(QStringLiteral("Settings|System|Utility"))},
        {QStringLiteral("Games"), QRegularExpression(QStringLiteral("Game"))},
        {QStringLiteral("Other"), QRegularExpression(QStringLiteral(".*"))},
    };
    return rules;
}
// Default Start pins: dconf/local.d/00-fenestra (ArcMenu pinned-apps).
const QStringList kDefaultStartPins{
    QStringLiteral("org.gnome.Nautilus.desktop"), QStringLiteral("org.mozilla.firefox.desktop"), QStringLiteral("fenestra-settings.desktop"),
    QStringLiteral("org.gnome.Software.desktop"), QStringLiteral("org.fenestra.Notepad.desktop"), QStringLiteral("org.fenestra.Paint.desktop"),
    QStringLiteral("org.gnome.Calculator.desktop"), QStringLiteral("org.gnome.Calendar.desktop"), QStringLiteral("org.gnome.clocks.desktop"),
    QStringLiteral("org.gnome.Snapshot.desktop"), QStringLiteral("org.gnome.Loupe.desktop"), QStringLiteral("org.gnome.Contacts.desktop"),
    QStringLiteral("org.gnome.Weather.desktop"), QStringLiteral("org.gnome.Maps.desktop"), QStringLiteral("libreoffice-writer.desktop")};
}

// ---- AllApps ---------------------------------------------------------------------------------
SINGLETON(AllApps)

AllApps::AllApps(QObject *parent)
    : QAbstractListModel(parent)
{
    connect(KSycoca::self(), &KSycoca::databaseChanged, this, &AllApps::reload);
    reload();
}

void AllApps::reload()
{
    QList<App> apps;
    const auto services = KApplicationTrader::query([](const KService::Ptr &s) { return s->showInCurrentDesktop() && !s->noDisplay(); });
    for (const KService::Ptr &s : services) {
        const QString cats = s->categories().join(QLatin1Char(';'));
        QString group;
        for (const auto &[name, rx] : groupRules())
            if (rx.match(cats).hasMatch()) {
                group = name;
                break;
            }
        apps.append({s->storageId(), s->name(), s->icon(), group, s->genericName(), s->keywords().join(QLatin1Char(' ')), s->comment()});
    }
    QCollator collator;
    collator.setCaseSensitivity(Qt::CaseInsensitive);
    std::sort(apps.begin(), apps.end(), [&collator](const App &a, const App &b) { return collator.compare(a.name, b.name) < 0; });
    beginResetModel();
    m_apps = apps;
    endResetModel();
    Q_EMIT countChanged();
}

int AllApps::rowCount(const QModelIndex &parent) const
{
    return parent.isValid() ? 0 : m_apps.size();
}

QVariant AllApps::data(const QModelIndex &index, int role) const
{
    if (!index.isValid() || index.row() >= m_apps.size())
        return {};
    const App &a = m_apps.at(index.row());
    switch (role) {
    case StorageIdRole: return a.storageId;
    case Qt::DisplayRole:
    case NameRole: return a.name;
    case IconRole: return a.icon;
    case GroupRole: return a.group;
    case LetterRole: {
        const QChar c = a.name.isEmpty() ? QLatin1Char('#') : a.name.at(0).toUpper();
        return c.isLetter() ? QString(c) : QStringLiteral("#");
    }
    case GenericNameRole: return a.genericName;
    case KeywordsRole: return a.keywords;
    case CommentRole: return a.comment;
    }
    return {};
}

QHash<int, QByteArray> AllApps::roleNames() const
{
    return {{StorageIdRole, "storageId"}, {NameRole, "name"}, {IconRole, "icon"}, {GroupRole, "group"}, {LetterRole, "letter"},
            {GenericNameRole, "genericName"}, {KeywordsRole, "keywords"}, {CommentRole, "comment"}};
}

QVariantList AllApps::groups() const
{
    QVariantList out;
    for (const auto &[name, rx] : groupRules()) {
        QVariantList apps;
        for (const App &a : m_apps)
            if (a.group == name)
                apps.append(QVariantMap{{QStringLiteral("storageId"), a.storageId}, {QStringLiteral("name"), a.name}, {QStringLiteral("icon"), a.icon}});
        if (!apps.isEmpty())
            out.append(QVariantMap{{QStringLiteral("name"), name}, {QStringLiteral("apps"), apps}});
    }
    return out;
}

// ---- StartPins -------------------------------------------------------------------------------
SINGLETON(StartPins)

StartPins::StartPins(QObject *parent)
    : QObject(parent)
{
    connect(ShellSettings::instance(), &ShellSettings::fileChanged, this, &StartPins::changed);
    connect(KSycoca::self(), &KSycoca::databaseChanged, this, &StartPins::changed);
}

QStringList StartPins::ids() const
{
    // A present but empty key (@Invalid() in QSettings) means "no pins", not the defaults.
    QSettings s(ShellSettings::path(), QSettings::IniFormat);
    if (!s.contains(QStringLiteral("Start/Pinned")))
        return kDefaultStartPins;
    return s.value(QStringLiteral("Start/Pinned")).toStringList();
}

QVariantList StartPins::apps() const
{
    QVariantList out;
    for (const QString &id : ids())
        if (const KService::Ptr s = Apps::instance()->service(id))
            out.append(appMap(s));
    return out;
}

bool StartPins::isPinned(const QString &storageId) const
{
    return ids().contains(storageId);
}

void StartPins::save(const QStringList &ids)
{
    ShellSettings::instance()->setValue(QStringLiteral("Start/Pinned"), ids);
}

void StartPins::pin(const QString &storageId)
{
    QStringList list = ids();
    if (!storageId.isEmpty() && !list.contains(storageId))
        save(list << storageId);
}

void StartPins::unpin(const QString &storageId)
{
    QStringList list = ids();
    if (list.removeAll(storageId))
        save(list);
}

void StartPins::move(int from, int to)
{
    QStringList list = ids();
    if (from >= 0 && to >= 0 && from < list.size() && to < list.size() && from != to) {
        list.move(from, to);
        save(list);
    }
}

// ---- RecentFiles -----------------------------------------------------------------------------
SINGLETON(RecentFiles)

namespace
{
QString xbelPath()
{
    return QStandardPaths::writableLocation(QStandardPaths::GenericDataLocation) + QStringLiteral("/recently-used.xbel");
}
}

RecentFiles::RecentFiles(QObject *parent)
    : QObject(parent)
{
    const QString dir = QFileInfo(xbelPath()).absolutePath();
    QDir().mkpath(dir);
    m_watcher.addPath(dir);
    connect(&m_watcher, &QFileSystemWatcher::directoryChanged, this, &RecentFiles::reload);
    connect(&m_watcher, &QFileSystemWatcher::fileChanged, this, &RecentFiles::reload);
    reload();
}

void RecentFiles::reload()
{
    QFile f(xbelPath());
    QList<QPair<QDateTime, QVariantMap>> found;
    if (f.open(QIODevice::ReadOnly)) {
        if (!m_watcher.files().contains(f.fileName()))
            m_watcher.addPath(f.fileName());
        QXmlStreamReader xml(&f);
        QMimeDatabase mimes;
        while (!xml.atEnd()) {
            if (xml.readNext() != QXmlStreamReader::StartElement || xml.name() != QLatin1String("bookmark"))
                continue;
            const QUrl url(xml.attributes().value(QLatin1String("href")).toString());
            QDateTime when = QDateTime::fromString(xml.attributes().value(QLatin1String("visited")).toString(), Qt::ISODateWithMs);
            if (!when.isValid())
                when = QDateTime::fromString(xml.attributes().value(QLatin1String("modified")).toString(), Qt::ISODateWithMs);
            if (!url.isLocalFile() || !QFileInfo::exists(url.toLocalFile()))
                continue;
            const QMimeType mime = mimes.mimeTypeForFile(url.toLocalFile());
            found.append({when, QVariantMap{{QStringLiteral("uri"), url.toString()}, {QStringLiteral("name"), url.fileName()},
                                            {QStringLiteral("path"), url.toLocalFile()}, {QStringLiteral("icon"), mime.iconName()},
                                            {QStringLiteral("mime"), mime.name()}, {QStringLiteral("modified"), when}}});
        }
    }
    std::sort(found.begin(), found.end(), [](const auto &a, const auto &b) { return a.first > b.first; });
    QVariantList items;
    for (int i = 0; i < found.size() && i < 50; ++i) {
        QVariantMap m = found.at(i).second;
        m.insert(QStringLiteral("age"), ageText(found.at(i).first));
        items.append(m);
    }
    m_items = items;
    Q_EMIT changed();
}

QString RecentFiles::ageText(const QDateTime &when)
{
    // Windows 11 26100's Recommended: «Hace 8 m», «Hace 2 h», then «Ayer a las 19:02» and the date
    // (dark-100-06-start; English: «8m ago», «2h ago», «Yesterday at 7:02 PM»).
    const bool es = QLocale().name().startsWith(QLatin1String("es"));
    const QDateTime local = when.toLocalTime();
    const qint64 mins = std::max<qint64>(0, local.secsTo(QDateTime::currentDateTime()) / 60);
    const qint64 days = local.date().daysTo(QDate::currentDate());
    if (mins < 1)
        return es ? QStringLiteral("Justo ahora") : QStringLiteral("Just now");
    if (mins < 60)
        return (es ? QStringLiteral("Hace %1 m") : QStringLiteral("%1m ago")).arg(mins);
    if (days <= 0)
        return (es ? QStringLiteral("Hace %1 h") : QStringLiteral("%1h ago")).arg(mins / 60);
    const QString time = QLocale().toString(local.time(), QLocale::ShortFormat);
    if (days == 1)
        return (es ? QStringLiteral("Ayer a las %1") : QStringLiteral("Yesterday at %1")).arg(time);
    return QLocale().toString(local.date(), es ? QStringLiteral("d 'de' MMMM") : QStringLiteral("MMMM d"));
}

void RecentFiles::open(const QString &uri) const
{
    auto *job = new KIO::OpenUrlJob(QUrl(uri));
    job->start();
}

void RecentFiles::openLocation(const QString &uri) const
{
    // org.freedesktop.FileManager1.ShowItems: the file manager selects the file in its folder.
    QDBusMessage msg = QDBusMessage::createMethodCall(QStringLiteral("org.freedesktop.FileManager1"), QStringLiteral("/org/freedesktop/FileManager1"),
                                                      QStringLiteral("org.freedesktop.FileManager1"), QStringLiteral("ShowItems"));
    msg << QStringList{uri} << QString();
    QDBusConnection::sessionBus().asyncCall(msg);
}

// ---- Usage -----------------------------------------------------------------------------------
SINGLETON(Usage)

namespace
{
QString countsPath() { return stateDir(QStringLiteral("fenestra")) + QStringLiteral("/app-usage.json"); }
QString historyPath() { return stateDir(QStringLiteral("windows-search")) + QStringLiteral("/history.json"); }
void writePrivate(const QString &path, const QJsonDocument &doc)
{
    QSaveFile f(path);
    if (f.open(QIODevice::WriteOnly)) {
        f.setPermissions(QFileDevice::ReadOwner | QFileDevice::WriteOwner);
        f.write(doc.toJson(QJsonDocument::Compact));
        f.commit();
    }
}
}

Usage::Usage(QObject *parent)
    : QObject(parent)
{
    QFile c(countsPath());
    if (c.open(QIODevice::ReadOnly)) {
        const QJsonObject o = QJsonDocument::fromJson(c.readAll()).object();
        for (auto it = o.begin(); it != o.end(); ++it)
            m_counts.insert(it.key(), it.value().toInt());
    }
    QFile h(historyPath());
    if (h.open(QIODevice::ReadOnly)) {
        const QJsonDocument doc = QJsonDocument::fromJson(h.readAll());
        const QJsonObject o = doc.object();
        for (const QJsonValue &v : doc.isArray() ? doc.array() : o.value(QStringLiteral("queries")).toArray())
            if (v.isString() && m_queries.size() < 8)
                m_queries << v.toString();
        for (const QJsonValue &v : o.value(QStringLiteral("apps")).toArray())
            if (v.isString() && m_apps.size() < 10)
                m_apps << v.toString();
        for (const QJsonValue &v : o.value(QStringLiteral("entries")).toArray()) {
            const QJsonObject e = v.toObject();
            const QString kind = e.value(QStringLiteral("kind")).toString();
            if ((kind == QLatin1String("app") || kind == QLatin1String("query")) && e.value(QStringLiteral("value")).isString() && m_entries.size() < 10)
                m_entries.append(e.toVariantMap());
        }
    }
    connect(Apps::instance(), &Apps::launched, this, [this](const QString &id) {
        m_counts[id] += 1;
        saveCounts();
    });
}

void Usage::saveCounts() const
{
    QJsonObject o;
    for (auto it = m_counts.begin(); it != m_counts.end(); ++it)
        o.insert(it.key(), it.value());
    writePrivate(countsPath(), QJsonDocument(o));
}

void Usage::saveHistory() const
{
    QJsonArray entries;
    for (const QVariantMap &e : m_entries)
        entries.append(QJsonObject::fromVariantMap(e));
    writePrivate(historyPath(), QJsonDocument(QJsonObject{{QStringLiteral("queries"), QJsonArray::fromStringList(m_queries)},
                                                          {QStringLiteral("apps"), QJsonArray::fromStringList(m_apps)},
                                                          {QStringLiteral("entries"), entries}}));
}

QVariantList Usage::topApps(int count) const
{
    QStringList ids = m_counts.keys();
    std::sort(ids.begin(), ids.end(), [this](const QString &a, const QString &b) { return m_counts.value(a) > m_counts.value(b); });
    for (const QString &id : StartPins::instance()->ids())
        if (!ids.contains(id))
            ids << id;
    QVariantList out;
    for (const QString &id : ids) {
        if (out.size() >= count)
            break;
        if (const KService::Ptr s = Apps::instance()->service(id))
            out.append(appMap(s));
    }
    return out;
}

QVariantList Usage::suggested(int count, const QStringList &exclude) const
{
    const bool es = QLocale().name().startsWith(QLatin1String("es"));
    QVariantList out;
    QStringList seen = exclude;
    auto addApp = [&](const KService::Ptr &s) {
        if (!s || seen.contains(s->storageId()) || out.size() >= count)
            return false;
        seen << s->storageId();
        out.append(QVariantMap{{QStringLiteral("kind"), QStringLiteral("app")}, {QStringLiteral("value"), s->storageId()},
                               {QStringLiteral("name"), s->name()}, {QStringLiteral("icon"), s->icon()}});
        return true;
    };
    auto firstOf = [&](std::initializer_list<const char *> ids) {
        for (const char *id : ids)
            if (addApp(Apps::instance()->service(QLatin1String(id))))
                return;
    };
    auto setting = [&](const char *page, const char *en, const char *esText, const char *glyph) {
        if (out.size() < count)
            out.append(QVariantMap{{QStringLiteral("kind"), QStringLiteral("setting")}, {QStringLiteral("value"), QLatin1String(page)},
                                   {QStringLiteral("name"), QString::fromUtf8(es ? esText : en)}, {QStringLiteral("icon"), QString()},
                                   {QStringLiteral("glyph"), QLatin1String(glyph)}});
    };
    // Apps opened from Search, newest first.
    for (const QVariantMap &e : m_entries)
        if (e.value(QStringLiteral("kind")) == QLatin1String("app"))
            addApp(Apps::instance()->service(e.value(QStringLiteral("value")).toString()));
    // Windows 11 26100's list (dark-100-10-search), with this system's equivalents; Get Started and
    // OneDrive have none.
    addApp(KApplicationTrader::preferredService(QStringLiteral("x-scheme-handler/https")));
    setting("fx-online-accounts", "Email & accounts", "Correo electrónico y cuentas", "mail");
    firstOf({"org.kde.spectacle.desktop", "org.gnome.Screenshot.desktop"});
    setting("update", "Check for updates", "Buscar actualizaciones", "sync");
    firstOf({"org.fenestra.Paint.desktop"});
    setting("themes", "Themes and related settings", "Temas y configuración relacionada", "brush");
    firstOf({"org.gnome.Calculator.desktop", "org.kde.kcalc.desktop", "gnome-calculator.desktop"});
    setting("devices", "Bluetooth and other devices settings", "Configuración de Bluetooth y otros dispositivos", "devices");
    firstOf({"org.gnome.Nautilus.desktop", "org.kde.dolphin.desktop"});
    // Then the most used apps.
    for (const QVariant &a : topApps(count + exclude.size() + 8))
        addApp(Apps::instance()->service(a.toMap().value(QStringLiteral("storageId")).toString()));
    return out;
}

QVariantList Usage::recentSearches() const
{
    QVariantList out;
    for (const QVariantMap &e : m_entries) {
        QVariantMap m = e;
        if (e.value(QStringLiteral("kind")) == QLatin1String("app")) {
            const KService::Ptr s = Apps::instance()->service(e.value(QStringLiteral("value")).toString());
            if (!s)
                continue;
            m.insert(QStringLiteral("name"), s->name());
            m.insert(QStringLiteral("icon"), s->icon());
        } else {
            m.insert(QStringLiteral("name"), e.value(QStringLiteral("value")));
            m.insert(QStringLiteral("icon"), QString());
        }
        const QVariant at = e.value(QStringLiteral("at"));
        m.insert(QStringLiteral("age"), at.isValid() && !at.isNull() ? ageText(at.toLongLong()) : QString());
        out.append(m);
    }
    return out;
}

QString Usage::ageText(qint64 msecs)
{
    const bool es = QLocale().name().startsWith(QLatin1String("es"));
    const qint64 m = std::max<qint64>(0, (QDateTime::currentMSecsSinceEpoch() - msecs) / 60000);
    auto unit = [es](qint64 n, const char *en, const char *enPl, const char *esS, const char *esPl) {
        return es ? QStringLiteral("Hace %1 %2").arg(n).arg(QLatin1String(n == 1 ? esS : esPl))
                  : QStringLiteral("%1 %2 ago").arg(n).arg(QLatin1String(n == 1 ? en : enPl));
    };
    if (m < 1)
        return es ? QStringLiteral("Justo ahora") : QStringLiteral("Just now");
    if (m < 60)
        return unit(m, "minute", "minutes", "minuto", "minutos");
    if (m < 60 * 24)
        return unit(m / 60, "hour", "hours", "hora", "horas");
    return unit(m / 60 / 24, "day", "days", "día", "días");
}

void Usage::rememberQuery(const QString &query)
{
    const QString q = query.trimmed();
    if (q.isEmpty() || q.size() > 200)
        return;
    m_queries.removeAll(q);
    m_queries.prepend(q);
    while (m_queries.size() > 8)
        m_queries.removeLast();
    m_entries.erase(std::remove_if(m_entries.begin(), m_entries.end(), [&q](const QVariantMap &e) {
        return e.value(QStringLiteral("kind")) == QLatin1String("query") && e.value(QStringLiteral("value")) == q; }), m_entries.end());
    m_entries.prepend({{QStringLiteral("kind"), QStringLiteral("query")}, {QStringLiteral("value"), q}, {QStringLiteral("at"), QDateTime::currentMSecsSinceEpoch()}});
    while (m_entries.size() > 10)
        m_entries.removeLast();
    saveHistory();
    Q_EMIT changed();
}

void Usage::rememberApp(const QString &storageId)
{
    m_apps.removeAll(storageId);
    m_apps.prepend(storageId);
    while (m_apps.size() > 10)
        m_apps.removeLast();
    m_entries.erase(std::remove_if(m_entries.begin(), m_entries.end(), [&storageId](const QVariantMap &e) {
        return e.value(QStringLiteral("kind")) == QLatin1String("app") && e.value(QStringLiteral("value")) == storageId; }), m_entries.end());
    m_entries.prepend({{QStringLiteral("kind"), QStringLiteral("app")}, {QStringLiteral("value"), storageId}, {QStringLiteral("at"), QDateTime::currentMSecsSinceEpoch()}});
    while (m_entries.size() > 10)
        m_entries.removeLast();
    saveHistory();
    Q_EMIT changed();
}

// ---- UserInfo --------------------------------------------------------------------------------
SINGLETON(UserInfo)

UserInfo::UserInfo(QObject *parent)
    : QObject(parent)
{
    QDBusMessage find = QDBusMessage::createMethodCall(QStringLiteral("org.freedesktop.Accounts"), QStringLiteral("/org/freedesktop/Accounts"),
                                                       QStringLiteral("org.freedesktop.Accounts"), QStringLiteral("FindUserById"));
    find << qlonglong(getuid());
    QDBusReply<QDBusObjectPath> path = QDBusConnection::systemBus().call(find, QDBus::Block, 2000);
    if (path.isValid()) {
        m_path = path.value().path();
        QDBusConnection::systemBus().connect(QStringLiteral("org.freedesktop.Accounts"), m_path, QStringLiteral("org.freedesktop.Accounts.User"),
                                             QStringLiteral("Changed"), this, SLOT(reload()));
    }
    reload();
}

void UserInfo::reload()
{
    QString full, picture;
    if (!m_path.isEmpty()) {
        QDBusInterface user(QStringLiteral("org.freedesktop.Accounts"), m_path, QStringLiteral("org.freedesktop.Accounts.User"),
                            QDBusConnection::systemBus());
        full = user.property("RealName").toString();
        const QString icon = user.property("IconFile").toString();
        if (!icon.isEmpty() && QFileInfo(icon).isReadable() && QFileInfo(icon).size() > 0)
            picture = QUrl::fromLocalFile(icon).toString();
        if (full.isEmpty())
            full = user.property("UserName").toString();
    }
    if (full.isEmpty())
        full = qEnvironmentVariable("USER");
    m_fullName = full;
    m_picture = picture;
    Q_EMIT changed();
}

QString UserInfo::name() const
{
    // Start footer: the first two words of the name (arc/menulayouts/eleven.js).
    return m_fullName.split(QLatin1Char(' '), Qt::SkipEmptyParts).mid(0, 2).join(QLatin1Char(' '));
}

// ---- Session ---------------------------------------------------------------------------------
SINGLETON(Session)

Session::Session(QObject *parent)
    : QObject(parent)
{
}

void Session::login1(const QString &method, const QVariantList &args)
{
    QDBusMessage msg = QDBusMessage::createMethodCall(QStringLiteral("org.freedesktop.login1"), QStringLiteral("/org/freedesktop/login1"),
                                                      QStringLiteral("org.freedesktop.login1.Manager"), method);
    msg.setArguments(args);
    QDBusConnection::systemBus().asyncCall(msg);
}

bool Session::canSuspend() const
{
    QDBusMessage msg = QDBusMessage::createMethodCall(QStringLiteral("org.freedesktop.login1"), QStringLiteral("/org/freedesktop/login1"),
                                                      QStringLiteral("org.freedesktop.login1.Manager"), QStringLiteral("CanSuspend"));
    QDBusReply<QString> r = QDBusConnection::systemBus().call(msg, QDBus::Block, 1000);
    return r.isValid() && (r.value() == QLatin1String("yes") || r.value() == QLatin1String("challenge"));
}

void Session::lock()
{
    // logind asks the session's locker (kscreenlocker, H8) to lock.
    QProcess::startDetached(QStringLiteral("loginctl"), {QStringLiteral("lock-session")});
}

void Session::suspend() { login1(QStringLiteral("Suspend"), {true}); }
void Session::powerOff() { login1(QStringLiteral("PowerOff"), {true}); }
void Session::reboot() { login1(QStringLiteral("Reboot"), {true}); }

void Session::logout()
{
    // Ends fenestra-session-inner, then KWin and the session (session/libexec/fenestra-session-inner).
    QProcess::startDetached(QStringLiteral("systemctl"), {QStringLiteral("--user"), QStringLiteral("stop"), QStringLiteral("fenestra-session.target")});
}

void Session::switchUser()
{
    // GDM: a new greeter on another VT, this session stays.
    QDBusMessage msg = QDBusMessage::createMethodCall(QStringLiteral("org.gnome.DisplayManager"), QStringLiteral("/org/gnome/DisplayManager/LocalDisplayFactory"),
                                                      QStringLiteral("org.gnome.DisplayManager.LocalDisplayFactory"), QStringLiteral("CreateTransientDisplay"));
    QDBusConnection::systemBus().asyncCall(msg);
}
