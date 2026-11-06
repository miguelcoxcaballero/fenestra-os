// SPDX-License-Identifier: GPL-3.0-or-later
// Test probe (only with FENESTRA_SHELL_TEST=1): D-Bus org.fenestra.Shell.Test on the session bus.
// The headless bench runs KWin with QPainter compositing, where KWin's own screenshot API is not
// usable, so the shell saves each of its surfaces with its layer-shell placement instead.
#pragma once

#include <QObject>
#include <QPointer>
#include <QStringList>

class QQmlApplicationEngine;

class TestProbe : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.fenestra.Shell.Test")
public:
    static void installIfRequested(QQmlApplicationEngine *engine);

public Q_SLOTS:
    // Saves every visible shell surface as DIR/NN-scope.png and DIR/surfaces.json
    // (scope, layer, anchors, size, margins, screen geometry). Returns the files written.
    Q_SCRIPTABLE QStringList Grab(const QString &dir);
    Q_SCRIPTABLE QString Version();
    // Evaluates a QML expression in the root object's context (open a menu, click a button,
    // read a model) and returns the result as text.
    Q_SCRIPTABLE QString Eval(const QString &expression);

private:
    using QObject::QObject;
    QPointer<QQmlApplicationEngine> m_engine;
};
