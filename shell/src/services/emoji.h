// SPDX-License-Identifier: GPL-3.0-or-later
// The emoji panel's data and actions (Win+.): Unicode's list by group (design/emoji.json, built in;
// tools/generate-emoji.py), names and search words in the user's language from CLDR's annotations
// when installed (cldr-emoji-annotation), the recently used ones, and typing the chosen emoji into
// the window that had the focus: it goes to the clipboard, Ctrl+V is pressed through KWin's fake
// input (org_kde_kwin_fake_input, listed in the shell's .desktop file) and the clipboard's previous
// content is put back. Without fake input the emoji stays on the clipboard.
#pragma once

#include <QHash>
#include <QObject>
#include <QQmlEngine>
#include <QRect>
#include <QVariantList>

class FakeInput;

class Emoji : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(QStringList groups READ groups CONSTANT)
    Q_PROPERTY(QVariantList recent READ recent NOTIFY recentChanged)
    Q_PROPERTY(bool canType READ canType NOTIFY canTypeChanged)
public:
    static Emoji *instance();
    static Emoji *create(QQmlEngine *, QJSEngine *);
    QStringList groups() const { return m_groups; }
    QVariantList recent() const;
    bool canType() const;
    // [{e, name}] of a group (index into groups) or, with a query, of every group.
    Q_INVOKABLE QVariantList items(int group, const QString &query = QString());
    // After the panel has closed: type `emoji` into the focused window.
    Q_INVOKABLE void type(const QString &emoji);
    // Where the focused window's text cursor is (desktop coordinates), asked from Fenestra's KWin
    // plugin (kwin/plugins/fenestra-corners/caret.h) before the panel takes the focus: answers
    // with caretFound, `known` false when the app doesn't tell the compositor or the plugin is old.
    Q_INVOKABLE void findCaret();
Q_SIGNALS:
    void caretFound(bool known, const QRect &rect);
    void recentChanged();
    void canTypeChanged();
private:
    explicit Emoji(QObject *parent = nullptr);
    void loadNames();
    struct Item { QString e, name, words; int group; };
    QList<Item> m_items;
    QStringList m_groups, m_recent;
    bool m_named = false;
    FakeInput *m_fake = nullptr;
};
