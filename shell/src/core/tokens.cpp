// SPDX-License-Identifier: GPL-3.0-or-later
#include "tokens.h"

#include <QFile>
#include <QJsonDocument>
#include <QStandardPaths>

Tokens *Tokens::instance()
{
    static auto *t = new Tokens;
    return t;
}

Tokens *Tokens::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

Tokens::Tokens(QObject *parent)
    : QObject(parent)
{
    const QStringList files{QStringLiteral(":/design/tokens.json"), QStringLiteral("/usr/share/fenestra/design/tokens.json"),
                            QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation) + QStringLiteral("/fenestra/tokens.json")};
    for (const QString &path : files) {
        QFile f(path);
        if (!f.open(QIODevice::ReadOnly))
            continue;
        const QJsonObject o = QJsonDocument::fromJson(f.readAll()).object();
        for (auto it = o.begin(); it != o.end(); ++it)
            if (!it.key().startsWith(QLatin1Char('_')))
                m_values.insert(it.key(), it.value());
    }
}

QVariant Tokens::v(const QString &key, const QVariant &fallback) const
{
    const auto it = m_values.constFind(key);
    if (it == m_values.constEnd()) {
        qWarning("fenestra-shell: missing design token %s", qPrintable(key));
        return fallback;
    }
    return it->toVariant();
}
