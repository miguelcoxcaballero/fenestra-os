// SPDX-License-Identifier: GPL-3.0-or-later
// Window list and control through KWin's org_kde_plasma_window_management protocol.
#pragma once

#include <QAbstractListModel>
#include <QPointer>
#include <QQmlEngine>
#include <QtWaylandClient/QWaylandClientExtension>

#include "qwayland-plasma-window-management.h"

class WindowsModel;

class PlasmaWindow : public QObject, public QtWayland::org_kde_plasma_window
{
    Q_OBJECT
public:
    PlasmaWindow(WindowsModel *model, const QString &uuid, ::org_kde_plasma_window *object);
    ~PlasmaWindow() override;

    QString uuid;
    QString title;
    QString appId;
    QString iconName;
    quint32 state = 0;
    quint32 pid = 0;
    bool ready = false; // initial_state received: every property is known

Q_SIGNALS:
    void changed();
    void gone();

protected:
    void org_kde_plasma_window_title_changed(const QString &title) override;
    void org_kde_plasma_window_app_id_changed(const QString &appId) override;
    void org_kde_plasma_window_state_changed(uint32_t flags) override;
    void org_kde_plasma_window_themed_icon_name_changed(const QString &name) override;
    void org_kde_plasma_window_pid_changed(uint32_t pid) override;
    void org_kde_plasma_window_initial_state() override;
    void org_kde_plasma_window_unmapped() override;
};

class WindowManagement : public QWaylandClientExtensionTemplate<WindowManagement>,
                         public QtWayland::org_kde_plasma_window_management
{
    Q_OBJECT
public:
    explicit WindowManagement(WindowsModel *model);
    bool showingDesktop = false;

Q_SIGNALS:
    void showingDesktopChanged();

protected:
    void org_kde_plasma_window_management_window_with_uuid(uint32_t id, const QString &uuid) override;
    void org_kde_plasma_window_management_show_desktop_changed(uint32_t state) override;

private:
    WindowsModel *m_model;
};

class WindowsModel : public QAbstractListModel
{
    Q_OBJECT
    QML_ELEMENT
    QML_SINGLETON
    Q_PROPERTY(bool available READ available NOTIFY availableChanged)
    Q_PROPERTY(bool showingDesktop READ showingDesktop NOTIFY showingDesktopChanged)
    Q_PROPERTY(int count READ rowCount NOTIFY countChanged)
public:
    enum Roles { TitleRole = Qt::UserRole + 1, AppIdRole, IconNameRole, ActiveRole, MinimizedRole,
                 MaximizedRole, DemandsAttentionRole, UuidRole, PidRole };

    static WindowsModel *instance();
    static WindowsModel *create(QQmlEngine *, QJSEngine *);

    // C++ access for TaskbarModel (grouping by app).
    const QList<PlasmaWindow *> &windows() const { return m_windows; }
    int rowOf(const PlasmaWindow *w) const { return m_windows.indexOf(const_cast<PlasmaWindow *>(w)); }

    int rowCount(const QModelIndex &parent = {}) const override;
    QVariant data(const QModelIndex &index, int role) const override;
    QHash<int, QByteArray> roleNames() const override;

    bool available() const;
    bool showingDesktop() const;

    // Taskbar click: activate, or minimize when it is already the active window.
    Q_INVOKABLE void activateOrMinimize(int row);
    Q_INVOKABLE void activate(int row);
    Q_INVOKABLE void close(int row);
    Q_INVOKABLE void toggleShowDesktop();

    void addWindow(const QString &uuid, ::org_kde_plasma_window *object);

Q_SIGNALS:
    void availableChanged();
    void showingDesktopChanged();
    void countChanged();
    void windowsChanged(); // any window added, removed or changed

private:
    explicit WindowsModel(QObject *parent = nullptr);
    void windowReady(PlasmaWindow *w);
    void windowChanged(PlasmaWindow *w);
    void windowGone(PlasmaWindow *w);
    void setState(int row, quint32 flags, bool on);

    WindowManagement *m_management;
    QList<PlasmaWindow *> m_pending; // mapped but initial_state not received yet
    QList<PlasmaWindow *> m_windows; // shown in the model, in mapping order
};
