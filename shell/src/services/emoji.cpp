// SPDX-License-Identifier: GPL-3.0-or-later
#include "emoji.h"

#include "qwayland-fake-input.h"

#include <QClipboard>
#include <QFile>
#include <QGuiApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLocale>
#include <QMimeData>
#include <QSettings>
#include <QStandardPaths>
#include <QTimer>
#include <QWaylandClientExtensionTemplate>
#include <QXmlStreamReader>

// KWin's fake input: only clients whose .desktop file lists org_kde_kwin_fake_input get it.
class FakeInput : public QWaylandClientExtensionTemplate<FakeInput>, public QtWayland::org_kde_kwin_fake_input
{
    Q_OBJECT
public:
    FakeInput()
        : QWaylandClientExtensionTemplate<FakeInput>(4)
    {
        initialize();
    }
    void key(uint code, bool down)
    {
        keyboard_key(code, down ? 1 : 0);
    }
    bool authenticated = false;
};

namespace
{
constexpr int kRecentMax = 24;
constexpr uint kKeyLeftCtrl = 29, kKeyV = 47; // linux/input-event-codes.h
QString stateFile()
{
    return QStandardPaths::writableLocation(QStandardPaths::GenericStateLocation) + QStringLiteral("/fenestra/shell-state.conf");
}
}

Emoji *Emoji::instance()
{
    static auto *i = new Emoji;
    return i;
}

Emoji *Emoji::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

Emoji::Emoji(QObject *parent)
    : QObject(parent)
{
    QFile f(QStringLiteral(":/design/emoji.json"));
    if (f.open(QIODevice::ReadOnly)) {
        const QJsonArray groups = QJsonDocument::fromJson(f.readAll()).array();
        for (const QJsonValue &g : groups) {
            const QJsonObject o = g.toObject();
            const int index = m_groups.size();
            m_groups << o.value(QStringLiteral("group")).toString();
            for (const QJsonValue &it : o.value(QStringLiteral("items")).toArray()) {
                const QJsonArray a = it.toArray();
                m_items.append({a.at(0).toString(), a.at(1).toString(), a.at(1).toString(), index});
            }
        }
    }
    m_recent = QSettings(stateFile(), QSettings::IniFormat).value(QStringLiteral("Emoji/Recent")).toStringList();
    m_fake = new FakeInput;
    connect(m_fake, &FakeInput::activeChanged, this, &Emoji::canTypeChanged);
}

bool Emoji::canType() const
{
    return m_fake && m_fake->isActive();
}

void Emoji::loadNames()
{
    if (m_named)
        return;
    m_named = true;
    // CLDR: <annotation cp="😀">cara | feliz</annotation> (search words) and type="tts" (the name).
    QHash<QString, int> index;
    for (int i = 0; i < m_items.size(); ++i) {
        index.insert(m_items.at(i).e, i);
        QString bare = m_items.at(i).e;
        bare.remove(QChar(0xFE0F)); // CLDR lists them without the variation selector
        index.insert(bare, i);
    }
    const QString lang = QLocale().name().section(QLatin1Char('_'), 0, 0);
    for (const QString &name : {lang, QStringLiteral("en")}) {
        QFile f(QStringLiteral("/usr/share/unicode/cldr/common/annotations/%1.xml").arg(name));
        if (!f.open(QIODevice::ReadOnly))
            continue;
        QXmlStreamReader xml(&f);
        while (!xml.atEnd()) {
            if (xml.readNext() != QXmlStreamReader::StartElement || xml.name() != QLatin1String("annotation"))
                continue;
            const auto it = index.constFind(xml.attributes().value(QLatin1String("cp")).toString());
            const bool tts = xml.attributes().value(QLatin1String("type")) == QLatin1String("tts");
            const QString text = xml.readElementText();
            if (it == index.constEnd())
                continue;
            Item &item = m_items[it.value()];
            if (tts && name == lang)
                item.name = text;
            item.words += QLatin1Char(' ') + text;
        }
        if (name == QLatin1String("en"))
            break;
    }
}

QVariantList Emoji::recent() const
{
    QVariantList out;
    for (const QString &e : m_recent)
        out << QVariantMap{{QStringLiteral("e"), e}, {QStringLiteral("name"), QString()}};
    return out;
}

QVariantList Emoji::items(int group, const QString &query)
{
    loadNames();
    const QStringList words = query.simplified().split(QLatin1Char(' '), Qt::SkipEmptyParts);
    QVariantList out;
    for (const Item &item : std::as_const(m_items)) {
        if (words.isEmpty()) {
            if (item.group != group)
                continue;
        } else {
            bool all = true;
            for (const QString &w : words)
                all = all && item.words.contains(w, Qt::CaseInsensitive);
            if (!all)
                continue;
        }
        out << QVariantMap{{QStringLiteral("e"), item.e}, {QStringLiteral("name"), item.name}};
        if (!words.isEmpty() && out.size() >= 160)
            break;
    }
    return out;
}

void Emoji::type(const QString &emoji)
{
    if (emoji.isEmpty())
        return;
    m_recent.removeAll(emoji);
    m_recent.prepend(emoji);
    while (m_recent.size() > kRecentMax)
        m_recent.removeLast();
    QSettings(stateFile(), QSettings::IniFormat).setValue(QStringLiteral("Emoji/Recent"), m_recent);
    Q_EMIT recentChanged();

    QClipboard *clipboard = QGuiApplication::clipboard();
    // What the clipboard held, to put it back: text and URLs (pictures are not copied around).
    const QMimeData *old = clipboard->mimeData();
    const QString oldText = old && old->hasText() ? old->text() : QString();
    const bool restore = canType() && old && old->hasText() && !old->hasImage();
    clipboard->setText(emoji);
    if (!canType())
        return; // the emoji stays on the clipboard: Ctrl+V pastes it
    if (!m_fake->authenticated) {
        m_fake->authenticate(QStringLiteral("Fenestra Shell"), QStringLiteral("emoji panel"));
        m_fake->authenticated = true;
    }
    // The panel has just closed: the window under it gets the focus back first.
    QTimer::singleShot(120, this, [this] {
        m_fake->key(kKeyLeftCtrl, true);
        m_fake->key(kKeyV, true);
        m_fake->key(kKeyV, false);
        m_fake->key(kKeyLeftCtrl, false);
    });
    if (restore)
        QTimer::singleShot(900, this, [clipboard, emoji, oldText] {
            if (clipboard->text() == emoji)
                clipboard->setText(oldText);
        });
}

#include "emoji.moc"
