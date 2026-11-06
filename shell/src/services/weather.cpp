// SPDX-License-Identifier: GPL-3.0-or-later
#include "weather.h"

#include "apps.h"

// GLib uses "signals" as a struct member name; Qt defines it as a macro.
#pragma push_macro("signals")
#undef signals
#include <gio/gio.h>
#define GWEATHER_I_KNOW_THIS_IS_UNSTABLE
#include <libgweather/gweather.h>
#pragma pop_macro("signals")

namespace
{
// Forecasts change slowly; this is the refresh GNOME Shell's WeatherClient uses as well.
constexpr int kRefreshMs = 30 * 60 * 1000;
}

Weather *Weather::instance()
{
    static auto *w = new Weather;
    return w;
}

Weather *Weather::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

Weather::Weather(QObject *parent)
    : QObject(parent)
{
    GSettingsSchemaSource *source = g_settings_schema_source_get_default();
    GSettingsSchema *schema = source ? g_settings_schema_source_lookup(source, "org.gnome.Weather", TRUE) : nullptr;
    if (!schema)
        return; // Weather app not installed: the button stays hidden
    g_settings_schema_unref(schema);
    m_settings = g_settings_new("org.gnome.Weather");
    g_signal_connect(m_settings, "changed::locations", G_CALLBACK(onLocationsChanged), this);
    m_refresh.setInterval(kRefreshMs);
    connect(&m_refresh, &QTimer::timeout, this, &Weather::refresh);
    loadLocation();
}

Weather::~Weather()
{
    if (m_info)
        g_object_unref(m_info);
    if (m_settings)
        g_object_unref(m_settings);
}

void Weather::onLocationsChanged(GSettings *, const char *, gpointer self)
{
    static_cast<Weather *>(self)->loadLocation();
}

void Weather::loadLocation()
{
    if (m_info) {
        g_signal_handlers_disconnect_by_data(m_info, this);
        g_object_unref(m_info);
        m_info = nullptr;
    }
    m_refresh.stop();
    GVariant *locations = g_settings_get_value(m_settings, "locations");
    GWeatherLocation *location = nullptr;
    if (g_variant_n_children(locations) > 0) {
        GVariant *boxed = g_variant_get_child_value(locations, 0);
        GVariant *serialized = g_variant_get_variant(boxed);
        GWeatherLocation *world = gweather_location_get_world();
        location = gweather_location_deserialize(world, serialized);
        g_object_unref(world);
        g_variant_unref(serialized);
        g_variant_unref(boxed);
    }
    g_variant_unref(locations);
    if (!location) {
        if (m_available) {
            m_available = false;
            Q_EMIT changed();
        }
        return;
    }
    m_info = gweather_info_new(location);
    g_object_unref(location);
    gweather_info_set_application_id(m_info, "org.fenestra.Shell");
    gweather_info_set_contact_info(m_info, "https://github.com/miguelcoxcaballero/fenestra-os");
    gweather_info_set_enabled_providers(m_info, GWeatherProvider(GWEATHER_PROVIDER_METAR | GWEATHER_PROVIDER_MET_NO));
    g_signal_connect(m_info, "updated", G_CALLBACK(onUpdated), this);
    refresh();
    m_refresh.start();
}

void Weather::refresh()
{
    if (m_info)
        gweather_info_update(m_info);
}

void Weather::onUpdated(GWeatherInfo *info, gpointer self)
{
    auto *w = static_cast<Weather *>(self);
    const bool valid = gweather_info_is_valid(info);
    auto take = [](char *s) { QString r = QString::fromUtf8(s); g_free(s); return r; };
    QString temp, cond;
    if (valid) {
        temp = take(gweather_info_get_temp_summary(info)).remove(QLatin1Char(' ')); // "18°C", not "18 °C"
        GWeatherConditionPhenomenon phenomenon;
        GWeatherConditionQualifier qualifier;
        GWeatherSky sky;
        if (gweather_info_get_value_conditions(info, &phenomenon, &qualifier))
            cond = take(gweather_info_get_conditions(info));
        if ((cond.isEmpty() || cond == QLatin1String("-")) && gweather_info_get_value_sky(info, &sky))
            cond = take(gweather_info_get_sky(info));
        if (cond == QLatin1String("-"))
            cond.clear();
        if (!cond.isEmpty())
            cond[0] = cond[0].toUpper();
    }
    w->m_available = valid && !temp.isEmpty();
    w->m_temp = temp;
    w->m_cond = cond;
    w->m_icon = QString::fromUtf8(gweather_info_get_icon_name(info));
    w->m_symbolic = QString::fromUtf8(gweather_info_get_symbolic_icon_name(info));
    Q_EMIT w->changed();
}

void Weather::openApp()
{
    Apps::instance()->launch(QStringLiteral("org.gnome.Weather.desktop"));
}
