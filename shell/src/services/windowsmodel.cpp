// SPDX-License-Identifier: GPL-3.0-or-later
#include "windowsmodel.h"

namespace
{
using WM = QtWayland::org_kde_plasma_window_management;
constexpr int kProtocolVersion = 16; // window_with_uuid (13), resource_name (16); KWin 6.8 offers 21
}

PlasmaWindow::PlasmaWindow(WindowsModel *, const QString &uuid_, ::org_kde_plasma_window *object)
    : QtWayland::org_kde_plasma_window(object)
    , uuid(uuid_)
{
}

PlasmaWindow::~PlasmaWindow()
{
    destroy();
}

void PlasmaWindow::org_kde_plasma_window_title_changed(const QString &t)
{
    title = t;
    Q_EMIT changed();
}

void PlasmaWindow::org_kde_plasma_window_app_id_changed(const QString &a)
{
    appId = a;
    Q_EMIT changed();
}

void PlasmaWindow::org_kde_plasma_window_state_changed(uint32_t flags)
{
    state = flags;
    Q_EMIT changed();
}

void PlasmaWindow::org_kde_plasma_window_themed_icon_name_changed(const QString &name)
{
    iconName = name;
    Q_EMIT changed();
}

void PlasmaWindow::org_kde_plasma_window_pid_changed(uint32_t p)
{
    pid = p;
    Q_EMIT changed();
}

void PlasmaWindow::org_kde_plasma_window_initial_state()
{
    ready = true;
    Q_EMIT changed();
}

void PlasmaWindow::org_kde_plasma_window_unmapped()
{
    Q_EMIT gone();
}

WindowManagement::WindowManagement(WindowsModel *model)
    : QWaylandClientExtensionTemplate<WindowManagement>(kProtocolVersion)
    , m_model(model)
{
    initialize();
}

void WindowManagement::org_kde_plasma_window_management_window_with_uuid(uint32_t, const QString &uuid)
{
    m_model->addWindow(uuid, get_window_by_uuid(uuid));
}

void WindowManagement::org_kde_plasma_window_management_show_desktop_changed(uint32_t state)
{
    showingDesktop = state == WM::show_desktop_enabled;
    Q_EMIT showingDesktopChanged();
}

WindowsModel *WindowsModel::instance()
{
    static auto *m = new WindowsModel;
    return m;
}

WindowsModel *WindowsModel::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

WindowsModel::WindowsModel(QObject *parent)
    : QAbstractListModel(parent)
    , m_management(new WindowManagement(this))
{
    connect(m_management, &WindowManagement::activeChanged, this, &WindowsModel::availableChanged);
    connect(m_management, &WindowManagement::showingDesktopChanged, this, &WindowsModel::showingDesktopChanged);
    connect(this, &WindowsModel::countChanged, this, &WindowsModel::windowsChanged);
    connect(this, &QAbstractItemModel::dataChanged, this, &WindowsModel::windowsChanged);
}

bool WindowsModel::available() const
{
    return m_management->isActive();
}

bool WindowsModel::showingDesktop() const
{
    return m_management->showingDesktop;
}

void WindowsModel::addWindow(const QString &uuid, ::org_kde_plasma_window *object)
{
    auto *w = new PlasmaWindow(this, uuid, object);
    m_pending.append(w);
    connect(w, &PlasmaWindow::changed, this, [this, w] {
        if (m_pending.contains(w)) {
            if (w->ready)
                windowReady(w);
        } else {
            windowChanged(w);
        }
    });
    connect(w, &PlasmaWindow::gone, this, [this, w] { windowGone(w); });
}

void WindowsModel::windowReady(PlasmaWindow *w)
{
    m_pending.removeOne(w);
    beginInsertRows({}, m_windows.size(), m_windows.size());
    m_windows.append(w);
    endInsertRows();
    Q_EMIT countChanged();
}

void WindowsModel::windowChanged(PlasmaWindow *w)
{
    const int row = m_windows.indexOf(w);
    if (row >= 0)
        Q_EMIT dataChanged(index(row), index(row));
}

void WindowsModel::windowGone(PlasmaWindow *w)
{
    if (m_pending.removeOne(w)) {
        w->deleteLater();
        return;
    }
    const int row = m_windows.indexOf(w);
    if (row < 0)
        return;
    beginRemoveRows({}, row, row);
    m_windows.removeAt(row);
    endRemoveRows();
    Q_EMIT countChanged();
    w->deleteLater();
}

int WindowsModel::rowCount(const QModelIndex &parent) const
{
    return parent.isValid() ? 0 : m_windows.size();
}

QVariant WindowsModel::data(const QModelIndex &index, int role) const
{
    if (!index.isValid() || index.row() >= m_windows.size())
        return {};
    const PlasmaWindow *w = m_windows.at(index.row());
    switch (role) {
    case Qt::DisplayRole:
    case TitleRole:
        return w->title;
    case AppIdRole:
        return w->appId;
    case IconNameRole:
        return w->iconName;
    case ActiveRole:
        return bool(w->state & WM::state_active);
    case MinimizedRole:
        return bool(w->state & WM::state_minimized);
    case MaximizedRole:
        return bool(w->state & WM::state_maximized);
    case DemandsAttentionRole:
        return bool(w->state & WM::state_demands_attention);
    case UuidRole:
        return w->uuid;
    case PidRole:
        return w->pid;
    }
    return {};
}

QHash<int, QByteArray> WindowsModel::roleNames() const
{
    return {{TitleRole, "title"}, {AppIdRole, "appId"}, {IconNameRole, "iconName"},
            {ActiveRole, "active"}, {MinimizedRole, "minimized"}, {MaximizedRole, "maximized"},
            {DemandsAttentionRole, "demandsAttention"}, {UuidRole, "uuid"}, {PidRole, "pid"}};
}

void WindowsModel::setState(int row, quint32 flags, bool on)
{
    if (row < 0 || row >= m_windows.size())
        return;
    m_windows.at(row)->set_state(flags, on ? flags : 0);
}

void WindowsModel::activate(int row)
{
    // Clearing "minimized" and setting "active" restores and raises the window.
    if (row < 0 || row >= m_windows.size())
        return;
    m_windows.at(row)->set_state(WM::state_minimized | WM::state_active, WM::state_active);
}

void WindowsModel::activateOrMinimize(int row)
{
    if (row < 0 || row >= m_windows.size())
        return;
    const quint32 s = m_windows.at(row)->state;
    if ((s & WM::state_active) && !(s & WM::state_minimized))
        setState(row, WM::state_minimized, true);
    else
        activate(row);
}

void WindowsModel::close(int row)
{
    if (row >= 0 && row < m_windows.size())
        m_windows.at(row)->close();
}

void WindowsModel::toggleShowDesktop()
{
    m_management->show_desktop(m_management->showingDesktop ? WM::show_desktop_disabled : WM::show_desktop_enabled);
}
