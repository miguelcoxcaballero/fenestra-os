// SPDX-License-Identifier: GPL-3.0-or-later
// Test probe (only with FENESTRA_SHELL_TEST=1): D-Bus org.fenestra.Shell.Test on the session bus.
// The headless bench runs KWin with QPainter compositing, where KWin's own screenshot API is not
// usable, so the shell saves each of its surfaces with its layer-shell placement instead.
#pragma once

#include <QObject>
#include <QStringList>

class TestProbe : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.fenestra.Shell.Test")
public:
    static void installIfRequested();

public Q_SLOTS:
    // Saves every visible shell surface as DIR/NN-scope.png and DIR/surfaces.json
    // (scope, layer, anchors, size, margins, screen geometry). Returns the files written.
    Q_SCRIPTABLE QStringList Grab(const QString &dir);
    Q_SCRIPTABLE QString Version();

private:
    using QObject::QObject;
};
