// SPDX-License-Identifier: GPL-3.0-or-later
#include "testprobe.h"

#include <LayerShellQt/Window>
#include <QDBusConnection>
#include <QDir>
#include <QGuiApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQmlExpression>
#include <QQuickWindow>
#include <QScreen>

void TestProbe::installIfRequested(QQmlApplicationEngine *engine)
{
    if (qEnvironmentVariableIntValue("FENESTRA_SHELL_TEST") != 1)
        return;
    auto *probe = new TestProbe(qApp);
    probe->m_engine = engine;
    auto bus = QDBusConnection::sessionBus();
    bus.registerService(QStringLiteral("org.fenestra.Shell"));
    if (!bus.registerObject(QStringLiteral("/org/fenestra/Shell/Test"), probe, QDBusConnection::ExportScriptableSlots))
        qWarning("fenestra-shell: test probe could not register on the session bus");
}

QString TestProbe::Version()
{
    return QCoreApplication::applicationVersion();
}

QString TestProbe::Eval(const QString &expression)
{
    if (!m_engine || m_engine->rootObjects().isEmpty())
        return QStringLiteral("error: no root object");
    QObject *root = m_engine->rootObjects().first();
    QQmlExpression expr(qmlContext(root), root, expression);
    const QVariant v = expr.evaluate();
    if (expr.hasError())
        return QStringLiteral("error: ") + expr.error().toString();
    return QString::fromUtf8(QJsonDocument::fromVariant(QVariantList{v}).toJson(QJsonDocument::Compact));
}

QStringList TestProbe::Grab(const QString &dir)
{
    QDir().mkpath(dir);
    QStringList files;
    QJsonArray surfaces;
    int n = 0;
    for (QWindow *window : QGuiApplication::topLevelWindows()) {
        auto *quick = qobject_cast<QQuickWindow *>(window);
        if (!quick || !quick->isVisible())
            continue;
        auto *layer = LayerShellQt::Window::get(window);
        const QString scope = layer ? layer->scope() : QStringLiteral("window");
        const QString file = QStringLiteral("%1/%2-%3.png").arg(dir).arg(n++, 2, 10, QLatin1Char('0')).arg(scope);
        quick->grabWindow().save(file);
        files << file;
        const QRect sg = window->screen() ? window->screen()->geometry() : QRect();
        const QMargins m = layer ? layer->margins() : QMargins();
        surfaces.append(QJsonObject{
            {QStringLiteral("file"), file},
            {QStringLiteral("scope"), scope},
            {QStringLiteral("layer"), layer ? int(layer->layer()) : -1},
            {QStringLiteral("anchors"), layer ? int(layer->anchors()) : 0},
            {QStringLiteral("exclusionZone"), layer ? layer->exclusionZone() : 0},
            {QStringLiteral("width"), window->width()},
            {QStringLiteral("height"), window->height()},
            {QStringLiteral("margins"), QJsonArray{m.left(), m.top(), m.right(), m.bottom()}},
            {QStringLiteral("screen"), QJsonArray{sg.x(), sg.y(), sg.width(), sg.height()}},
            {QStringLiteral("dpr"), window->devicePixelRatio()},
        });
    }
    QFile json(dir + QStringLiteral("/surfaces.json"));
    if (json.open(QIODevice::WriteOnly))
        json.write(QJsonDocument(surfaces).toJson());
    files << json.fileName();
    return files;
}
