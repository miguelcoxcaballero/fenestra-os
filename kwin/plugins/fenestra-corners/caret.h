/*
    SPDX-License-Identifier: GPL-3.0-or-later

    Where the text cursor is: Windows opens its emoji panel (Win+.) at the caret. Apps tell the
    compositor through the text-input protocol (v3: GTK; v2: Qt), and nobody else; this object
    answers the shell on KWin's session bus connection:
        org.kde.KWin /org/fenestra/TextCaret org.fenestra.KWin.TextCaret.Rect() -> (b, iiii)
    The rectangle is in logical pixels of the whole desktop. False: the focused window has no
    text-input caret (XWayland windows, Chromium without its Wayland IME).
*/
#pragma once

#include <QObject>

namespace KWin
{

class TextCaret : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.fenestra.KWin.TextCaret")

public:
    explicit TextCaret(QObject *parent = nullptr);
    ~TextCaret() override;

public Q_SLOTS:
    bool Rect(int &x, int &y, int &width, int &height);
};

} // namespace KWin
