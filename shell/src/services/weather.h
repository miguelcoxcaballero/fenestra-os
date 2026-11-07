// SPDX-License-Identifier: GPL-3.0-or-later
// Taskbar weather (B05): libgweather with the location chosen in the Weather app
// (org.gnome.Weather "locations"), as GNOME Shell's WeatherClient did.
#pragma once

#include <QObject>
#include <QQmlEngine>
#include <QTimer>

typedef struct _GWeatherInfo GWeatherInfo;
typedef struct _GSettings GSettings;
typedef void *gpointer;

class Weather : public QObject
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(bool available READ available NOTIFY changed)
    Q_PROPERTY(QString temperature READ temperature NOTIFY changed)  // "18°C"
    Q_PROPERTY(QString condition READ condition NOTIFY changed)      // "Partly cloudy"
    Q_PROPERTY(QString iconName READ iconName NOTIFY changed)
    Q_PROPERTY(QString symbolicIconName READ symbolicIconName NOTIFY changed)
    // The Widgets board's weather card.
    Q_PROPERTY(QString location READ location NOTIFY changed)       // "Madrid"
    Q_PROPERTY(QString feelsLike READ feelsLike NOTIFY changed)     // "16°C"
    Q_PROPERTY(QString humidity READ humidity NOTIFY changed)       // "60%"
    Q_PROPERTY(QString wind READ wind NOTIFY changed)               // "12 km/h"
public:
    static Weather *instance();
    static Weather *create(QQmlEngine *, QJSEngine *);
    ~Weather() override;

    bool available() const { return m_available; }
    QString temperature() const { return m_temp; }
    QString condition() const { return m_cond; }
    QString iconName() const { return m_icon; }
    QString symbolicIconName() const { return m_symbolic; }
    QString location() const { return m_location; }
    QString feelsLike() const { return m_feels; }
    QString humidity() const { return m_humidity; }
    QString wind() const { return m_wind; }

    Q_INVOKABLE void openApp();

Q_SIGNALS:
    void changed();

private:
    explicit Weather(QObject *parent = nullptr);
    void loadLocation();
    void refresh();
    static void onUpdated(GWeatherInfo *info, gpointer self);
    static void onLocationsChanged(GSettings *, const char *, gpointer self);

    GSettings *m_settings = nullptr;
    GWeatherInfo *m_info = nullptr;
    QTimer m_refresh;
    bool m_available = false;
    QString m_temp, m_cond, m_icon, m_symbolic, m_location, m_feels, m_humidity, m_wind;
};
