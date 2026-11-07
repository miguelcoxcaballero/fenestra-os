// SPDX-License-Identifier: GPL-3.0-or-later
#include "taskbarmodel.h"

#include "apps.h"
#include "shellsettings.h"
#include "windowsmodel.h"

namespace
{
using WM = QtWayland::org_kde_plasma_window_management;
}

TaskbarModel *TaskbarModel::instance()
{
    static auto *m = new TaskbarModel;
    return m;
}

TaskbarModel *TaskbarModel::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

TaskbarModel::TaskbarModel(QObject *parent)
    : QAbstractListModel(parent)
{
    connect(WindowsModel::instance(), &WindowsModel::windowsChanged, this, &TaskbarModel::rebuild);
    connect(ShellSettings::instance(), &ShellSettings::changed, this, &TaskbarModel::rebuild);
    connect(Apps::instance(), &Apps::databaseChanged, this, &TaskbarModel::rebuild);
    rebuild();
}

void TaskbarModel::rebuild()
{
    QList<Entry> entries;
    auto *apps = Apps::instance();
    for (const QString &id : ShellSettings::instance()->pinnedApps()) {
        const KService::Ptr s = apps->service(id);
        if (!s)
            continue; // uninstalled: keep it in the settings, hide the button
        entries.append({s->storageId(), s->storageId(), s->name(), s->icon(), true, {}});
    }
    for (PlasmaWindow *w : WindowsModel::instance()->windows()) {
        if (w->state & WM::state_skiptaskbar)
            continue;
        const KService::Ptr s = apps->serviceForWindow(w->appId);
        const QString key = s ? s->storageId() : QStringLiteral("window:") + w->uuid;
        auto it = std::find_if(entries.begin(), entries.end(), [&key](const Entry &e) { return e.key == key; });
        if (it == entries.end()) {
            Entry e{key, s ? s->storageId() : QString(), s ? s->name() : w->title,
                    !w->iconName.isEmpty() ? w->iconName : (s ? s->icon() : w->appId), false, {}};
            entries.append(e);
            it = entries.end() - 1;
        }
        it->windows.append(w);
    }

    // Same buttons in the same order: only data changed (no delegate churn, no animation restart).
    bool sameKeys = entries.size() == m_entries.size();
    for (int i = 0; sameKeys && i < entries.size(); ++i)
        sameKeys = entries[i].key == m_entries[i].key;
    if (sameKeys) {
        m_entries = entries;
        if (!m_entries.isEmpty())
            Q_EMIT dataChanged(index(0), index(m_entries.size() - 1));
        return;
    }
    beginResetModel();
    m_entries = entries;
    endResetModel();
}

int TaskbarModel::rowCount(const QModelIndex &parent) const
{
    return parent.isValid() ? 0 : m_entries.size();
}

QVariant TaskbarModel::data(const QModelIndex &index, int role) const
{
    if (!index.isValid() || index.row() >= m_entries.size())
        return {};
    const Entry &e = m_entries.at(index.row());
    switch (role) {
    case Qt::DisplayRole:
    case NameRole:
        return e.name;
    case StorageIdRole:
        return e.storageId;
    case IconRole:
        return e.icon;
    case PinnedRole:
        return e.pinned;
    case WindowCountRole:
        return e.windows.size();
    case ActiveRole:
        return std::any_of(e.windows.begin(), e.windows.end(),
                           [](PlasmaWindow *w) { return (w->state & WM::state_active) && !(w->state & WM::state_minimized); });
    case AttentionRole:
        return std::any_of(e.windows.begin(), e.windows.end(), [](PlasmaWindow *w) { return w->state & WM::state_demands_attention; });
    case WindowsRole: {
        QVariantList list;
        for (PlasmaWindow *w : e.windows)
            list.append(QVariantMap{{QStringLiteral("row"), WindowsModel::instance()->rowOf(w)},
                                    {QStringLiteral("title"), w->title},
                                    {QStringLiteral("active"), bool(w->state & WM::state_active)},
                                    {QStringLiteral("minimized"), bool(w->state & WM::state_minimized)},
                                    {QStringLiteral("width"), w->geometry.width()},
                                    {QStringLiteral("height"), w->geometry.height()}});
        return list;
    }
    }
    return {};
}

QHash<int, QByteArray> TaskbarModel::roleNames() const
{
    return {{StorageIdRole, "storageId"}, {NameRole, "name"}, {IconRole, "icon"}, {PinnedRole, "pinned"},
            {WindowCountRole, "windowCount"}, {ActiveRole, "active"}, {AttentionRole, "demandsAttention"},
            {WindowsRole, "windows"}};
}

void TaskbarModel::activate(int row)
{
    if (row < 0 || row >= m_entries.size())
        return;
    const Entry &e = m_entries.at(row);
    auto *wm = WindowsModel::instance();
    if (e.windows.isEmpty()) {
        Apps::instance()->launch(e.storageId);
        return;
    }
    if (e.windows.size() == 1) {
        wm->activateOrMinimize(wm->rowOf(e.windows.first()));
        return;
    }
    // Several windows: bring the next one forward.
    m_cycle = (m_cycle + 1) % e.windows.size();
    wm->activate(wm->rowOf(e.windows.at(m_cycle)));
}

void TaskbarModel::newInstance(int row)
{
    if (row >= 0 && row < m_entries.size())
        Apps::instance()->launch(m_entries.at(row).storageId);
}

void TaskbarModel::closeAll(int row)
{
    if (row < 0 || row >= m_entries.size())
        return;
    auto *wm = WindowsModel::instance();
    for (PlasmaWindow *w : m_entries.at(row).windows)
        wm->close(wm->rowOf(w));
}

void TaskbarModel::togglePinned(int row)
{
    if (row < 0 || row >= m_entries.size() || m_entries.at(row).storageId.isEmpty())
        return;
    const Entry &e = m_entries.at(row);
    if (e.pinned)
        ShellSettings::instance()->unpin(e.storageId);
    else
        ShellSettings::instance()->pin(e.storageId);
}

void TaskbarModel::movePinned(int from, int to)
{
    QStringList pinned;
    for (const Entry &e : m_entries)
        if (e.pinned)
            pinned << e.storageId;
    if (from < 0 || to < 0 || from >= pinned.size() || to >= pinned.size() || from == to)
        return;
    pinned.move(from, to);
    ShellSettings::instance()->setPinnedApps(pinned);
}
