// SPDX-License-Identifier: GPL-3.0-or-later
// Banners on the lock screen. While the session is locked KWin shows only the lock screen, so the
// shell's own banners (volume, brightness, keyboard light, performance mode) are invisible there.
// kscreenlocker's greeter listens to org.kde.osdService's osdProgress / osdText signals from the
// bus name org.kde.plasmashell and hands them to the lock screen's "onScreenDisplay" item, which
// Fenestra's lock screen draws as Windows does. Fenestra has no plasmashell, so the shell takes that
// name while the screen is locked (and only then: nothing else sees a "plasmashell" in the session)
// and repeats each banner as those signals.
// The icon string carries Fenestra's kind: "fenestra-volume", "fenestra-volume-muted",
// "fenestra-brightness", "fenestra-keyboard", "fenestra-performance:<glyph>",
// "fenestra-oem:<glyph>:<image path>".
#pragma once

#include <QObject>
#include <QQmlEngine>

class LockOsd : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(bool locked READ locked NOTIFY lockedChanged)
public:
    static LockOsd *instance();
    static LockOsd *create(QQmlEngine *, QJSEngine *);
    bool locked() const { return m_locked; }
    // A value banner (volume / brightness / keyboard: 0-100; volume -1 = muted).
    Q_INVOKABLE void progress(const QString &kind, int value);
    // A text banner (performance mode, the maker's banners): label, Segoe Fluent glyph, image.
    Q_INVOKABLE void text(const QString &kind, const QString &label, const QString &glyph, const QString &image = QString());
Q_SIGNALS:
    void lockedChanged();
    // org.kde.osdService (exported on /org/kde/osdService while locked).
    void osdProgress(const QString &icon, int percent, int maximumPercent, const QString &additionalText);
    void osdText(const QString &icon, const QString &label);

private Q_SLOTS:
    void activeChanged(bool active);

private:
    explicit LockOsd(QObject *parent = nullptr);
    void setLocked(bool locked);
    bool m_locked = false;
    bool m_owned = false;
};
