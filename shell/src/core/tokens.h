// SPDX-License-Identifier: GPL-3.0-or-later
// design/tokens.json: sizes, radii and timings of every shell surface. Built into the binary; a
// tokens.json in /usr/share/fenestra/design or ~/.config/fenestra overrides keys (visual tuning
// without rebuilding).
#pragma once

#include <QJsonObject>
#include <QObject>
#include <QQmlEngine>

class Tokens : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
public:
    static Tokens *instance();
    static Tokens *create(QQmlEngine *, QJSEngine *);
    Q_INVOKABLE QVariant v(const QString &key, const QVariant &fallback = {}) const;
    // A value that only some variants define (a recipe's own noise or veil): no warning without it.
    Q_INVOKABLE QVariant opt(const QString &key, const QVariant &fallback = {}) const { return m_values.contains(key) ? m_values.value(key).toVariant() : fallback; }
    Q_INVOKABLE int px(const QString &key, int fallback = 0) const { return v(key, fallback).toInt(); }
private:
    explicit Tokens(QObject *parent = nullptr);
    QJsonObject m_values;
};
