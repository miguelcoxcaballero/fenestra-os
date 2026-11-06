// SPDX-License-Identifier: GPL-3.0-or-later
// Colours of the shell surfaces for the current scheme and accent. The accent derivation is the
// one of the GNOME layer (fenestra-tray/appearance.js palette(), tools/build-gtk-themes.py).
#pragma once

#include <QColor>
#include <QObject>
#include <QQmlEngine>

class Theme : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(bool dark READ dark NOTIFY changed)
    Q_PROPERTY(QColor accent READ accent NOTIFY changed)          // base accent
    Q_PROPERTY(QColor accentFill READ accentFill NOTIFY changed)  // fills, indicators, toggles
    Q_PROPERTY(QColor accentOn READ accentOn NOTIFY changed)      // text/glyphs on accentFill
    Q_PROPERTY(QColor accentText READ accentText NOTIFY changed)  // accent text on the surface
    Q_PROPERTY(QColor accentHover READ accentHover NOTIFY changed)
    Q_PROPERTY(QColor accentPress READ accentPress NOTIFY changed)
    // Taskbar: #000402 / #f3f3f3 at 63 % (dconf trans-bg-color, trans-panel-opacity).
    Q_PROPERTY(QColor taskbar READ taskbar NOTIFY changed)
    Q_PROPERTY(QColor taskbarBorder READ taskbarBorder NOTIFY changed)
    // Flyouts and menus: rgba(32,32,36,.80) / rgba(249,249,249,.85), border .10 / .08 (stylesheet.css, light.css).
    Q_PROPERTY(QColor flyout READ flyout NOTIFY changed)
    Q_PROPERTY(QColor flyoutBorder READ flyoutBorder NOTIFY changed)
    Q_PROPERTY(QColor text READ text NOTIFY changed)
    Q_PROPERTY(QColor textSecondary READ textSecondary NOTIFY changed)
    Q_PROPERTY(QColor textDisabled READ textDisabled NOTIFY changed)
    Q_PROPERTY(QColor hover READ hover NOTIFY changed)     // subtle fill of hovered items
    Q_PROPERTY(QColor pressed READ pressed NOTIFY changed)
    Q_PROPERTY(QColor separator READ separator NOTIFY changed)

public:
    static Theme *instance();
    static Theme *create(QQmlEngine *, QJSEngine *);

    bool dark() const { return m_dark; }
    QColor accent() const { return m_base; }
    QColor accentFill() const { return m_fill; }
    QColor accentOn() const { return m_on; }
    QColor accentText() const { return m_text; }
    QColor accentHover() const { return m_hover; }
    QColor accentPress() const { return m_press; }
    QColor taskbar() const { return m_dark ? QColor(0, 4, 2, 161) : QColor(0xf3, 0xf3, 0xf3, 161); }
    QColor taskbarBorder() const { return m_dark ? QColor(255, 255, 255, 26) : QColor(0, 0, 0, 20); }
    QColor flyout() const { return m_dark ? QColor(32, 32, 36, 204) : QColor(249, 249, 249, 217); }
    QColor flyoutBorder() const { return m_dark ? QColor(255, 255, 255, 26) : QColor(0, 0, 0, 20); }
    QColor text() const { return m_dark ? QColor(Qt::white) : QColor(0x1a, 0x1a, 0x1a); }
    QColor textSecondary() const { return m_dark ? QColor(255, 255, 255, 200) : QColor(0, 0, 0, 158); }
    QColor textDisabled() const { return m_dark ? QColor(255, 255, 255, 93) : QColor(0, 0, 0, 92); }
    QColor hover() const { return m_dark ? QColor(255, 255, 255, 20) : QColor(0, 0, 0, 10); }
    QColor pressed() const { return m_dark ? QColor(255, 255, 255, 13) : QColor(0, 0, 0, 6); }
    QColor separator() const { return m_dark ? QColor(255, 255, 255, 21) : QColor(0, 0, 0, 20); }

    // Exposed for tests: fill/on/text of an accent in a scheme.
    struct Palette { QColor base, fill, on, text, hover, press; };
    static Palette palette(const QString &accent, bool dark);

Q_SIGNALS:
    void changed();

private:
    explicit Theme(QObject *parent = nullptr);
    void update();
    bool m_dark = true;
    QColor m_base, m_fill, m_on, m_text, m_hover, m_press;
};
