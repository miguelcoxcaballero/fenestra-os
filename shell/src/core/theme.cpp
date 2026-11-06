// SPDX-License-Identifier: GPL-3.0-or-later
#include "theme.h"

#include "shellsettings.h"

#include <QHash>
#include <cmath>

namespace
{
double channel(double v)
{
    v /= 255.0;
    return v <= 0.04045 ? v / 12.92 : std::pow((v + 0.055) / 1.055, 2.4);
}
double luminance(const QColor &c)
{
    return 0.2126 * channel(c.red()) + 0.7152 * channel(c.green()) + 0.0722 * channel(c.blue());
}
double contrast(const QColor &a, const QColor &b)
{
    double x = luminance(a), y = luminance(b);
    if (x < y)
        std::swap(x, y);
    return (x + 0.05) / (y + 0.05);
}
QColor mix(const QColor &a, const QColor &b, double t)
{
    return QColor::fromRgbF(a.redF() + (b.redF() - a.redF()) * t, a.greenF() + (b.greenF() - a.greenF()) * t,
                            a.blueF() + (b.blueF() - a.blueF()) * t);
}
QColor hsl(double h, double s, double l)
{
    return QColor::fromHslF(h < 0 ? 0 : h, std::clamp(s, 0.0, 1.0), std::clamp(l, 0.0, 1.0)).toRgb();
}
QColor darker(const QColor &c)
{
    float h, s, l;
    c.toHsl().getHslF(&h, &s, &l);
    double ll = l - 0.08;
    QColor out = hsl(h, s, ll);
    while (ll > 0.05 && contrast(out, Qt::white) < 4.5) {
        ll -= 0.01;
        out = hsl(h, s, ll);
    }
    return out;
}
QColor lighter(const QColor &c, double target = 0.72)
{
    float h, s, l;
    c.toHsl().getHslF(&h, &s, &l);
    return l >= target ? c : hsl(h, std::min(1.0, s * 1.5), target);
}
// GNOME accent names -> [base, fill on dark, fill on light] (appearance.js ENUM).
const QHash<QString, std::array<const char *, 3>> kNamed{
    {QStringLiteral("blue"), {"#0078d4", "#4cc2ff", "#005fb8"}},   {QStringLiteral("teal"), {"#038387", "#4fd6cb", "#00777b"}},
    {QStringLiteral("green"), {"#107c10", "#6ccb5f", "#0f7b0f"}},  {QStringLiteral("yellow"), {"#ffb900", "#ffd75e", "#9d5d00"}},
    {QStringLiteral("orange"), {"#ca5010", "#ff9a5c", "#bc4b09"}}, {QStringLiteral("red"), {"#e81123", "#ff99a4", "#c42b1c"}},
    {QStringLiteral("pink"), {"#e3008c", "#f7a2cf", "#bf0077"}},   {QStringLiteral("purple"), {"#744da9", "#d6a4f2", "#8764b8"}},
    {QStringLiteral("slate"), {"#68768a", "#a8bccf", "#515c6b"}},
};
}

Theme::Palette Theme::palette(const QString &accent, bool dark)
{
    QColor base, darkFill, lightFill;
    // #0078D4 is the default accent: use the named fills, exactly as the GNOME layer.
    QString key = accent.toLower();
    if (key == QLatin1String("#0078d4"))
        key = QStringLiteral("blue");
    if (auto it = kNamed.constFind(key); it != kNamed.constEnd()) {
        base = QColor(QLatin1String((*it)[0]));
        darkFill = QColor(QLatin1String((*it)[1]));
        lightFill = QColor(QLatin1String((*it)[2]));
    } else {
        base = darkFill = QColor(accent);
        for (int i = 0; i < 20 && contrast(darkFill, QColor(0x20, 0x20, 0x20)) < 3; ++i)
            darkFill = mix(darkFill, Qt::white, 0.1);
        lightFill = darker(base);
    }
    const QColor fill = dark ? darkFill : lightFill;
    return {base, fill, luminance(fill) > 0.25 ? QColor(Qt::black) : QColor(Qt::white), dark ? lighter(darkFill) : lightFill,
            dark ? mix(fill, Qt::white, 0.15) : mix(fill, Qt::white, 0.1),
            dark ? mix(fill, Qt::black, 0.14) : mix(fill, Qt::white, 0.2)};
}

Theme *Theme::instance()
{
    static auto *t = new Theme;
    return t;
}

Theme *Theme::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

Theme::Theme(QObject *parent)
    : QObject(parent)
{
    connect(ShellSettings::instance(), &ShellSettings::changed, this, &Theme::update);
    update();
}

void Theme::update()
{
    auto *s = ShellSettings::instance();
    const bool dark = s->colorScheme() != QLatin1String("light");
    const Palette p = palette(s->accentColor(), dark);
    if (dark == m_dark && p.base == m_base && p.fill == m_fill && m_on.isValid())
        return;
    m_dark = dark;
    m_base = p.base;
    m_fill = p.fill;
    m_on = p.on;
    m_text = p.text;
    m_hover = p.hover;
    m_press = p.press;
    Q_EMIT changed();
}
