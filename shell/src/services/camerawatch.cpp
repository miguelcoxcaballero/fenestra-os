// SPDX-License-Identifier: GPL-3.0-or-later
#include "camerawatch.h"

#include <QMetaObject>
#include <pipewire/pipewire.h>
#include <spa/utils/dict.h>
#include <unordered_map>

namespace
{
struct NodeWatch {
    pw_proxy *proxy = nullptr;
    spa_hook listener{};
    bool running = false;
};
struct State {
    CameraWatch *owner = nullptr;
    pw_registry *registry = nullptr;
    spa_hook registryListener{};
    std::unordered_map<uint32_t, NodeWatch *> nodes;
};
State g_state;

void publish()
{
    int count = 0;
    for (const auto &[id, n] : g_state.nodes)
        count += n->running ? 1 : 0;
    g_state.owner->setRunningCount(count);
}

void nodeInfo(void *data, const pw_node_info *info)
{
    auto *n = static_cast<NodeWatch *>(data);
    const bool running = info->state == PW_NODE_STATE_RUNNING;
    if (running != n->running) {
        n->running = running;
        publish();
    }
}

const pw_node_events kNodeEvents = {.version = PW_VERSION_NODE_EVENTS, .info = nodeInfo};

void globalAdded(void *, uint32_t id, uint32_t, const char *type, uint32_t, const spa_dict *props)
{
    if (strcmp(type, PW_TYPE_INTERFACE_Node) != 0 || !props)
        return;
    const char *cls = spa_dict_lookup(props, PW_KEY_MEDIA_CLASS);
    // Cameras: video sources from devices (v4l2 / libcamera), not screen casts.
    if (!cls || strcmp(cls, "Video/Source") != 0)
        return;
    auto *n = new NodeWatch;
    n->proxy = static_cast<pw_proxy *>(pw_registry_bind(g_state.registry, id, PW_TYPE_INTERFACE_Node, PW_VERSION_NODE, 0));
    pw_node_add_listener(reinterpret_cast<pw_node *>(n->proxy), &n->listener, &kNodeEvents, n);
    g_state.nodes[id] = n;
}

void globalRemoved(void *, uint32_t id)
{
    auto it = g_state.nodes.find(id);
    if (it == g_state.nodes.end())
        return;
    spa_hook_remove(&it->second->listener);
    pw_proxy_destroy(it->second->proxy);
    delete it->second;
    g_state.nodes.erase(it);
    publish();
}

const pw_registry_events kRegistryEvents = {.version = PW_VERSION_REGISTRY_EVENTS, .global = globalAdded, .global_remove = globalRemoved};
}

CameraWatch *CameraWatch::instance()
{
    static auto *c = new CameraWatch;
    return c;
}

CameraWatch *CameraWatch::create(QQmlEngine *, QJSEngine *)
{
    QQmlEngine::setObjectOwnership(instance(), QQmlEngine::CppOwnership);
    return instance();
}

CameraWatch::CameraWatch(QObject *parent)
    : QObject(parent)
{
    pw_init(nullptr, nullptr);
    m_loop = pw_thread_loop_new("fenestra-camera", nullptr);
    if (!m_loop)
        return;
    m_context = pw_context_new(pw_thread_loop_get_loop(m_loop), nullptr, 0);
    pw_thread_loop_lock(m_loop);
    m_core = m_context ? pw_context_connect(m_context, nullptr, 0) : nullptr;
    if (m_core) {
        g_state.owner = this;
        m_registry = pw_core_get_registry(m_core, PW_VERSION_REGISTRY, 0);
        g_state.registry = m_registry;
        pw_registry_add_listener(m_registry, &g_state.registryListener, &kRegistryEvents, nullptr);
        pw_thread_loop_start(m_loop);
    }
    // No PipeWire (e.g. a container): the glyph just never shows.
    pw_thread_loop_unlock(m_loop);
}

CameraWatch::~CameraWatch()
{
    if (m_loop)
        pw_thread_loop_stop(m_loop);
    if (m_core)
        pw_core_disconnect(m_core);
    if (m_context)
        pw_context_destroy(m_context);
    if (m_loop)
        pw_thread_loop_destroy(m_loop);
}

void CameraWatch::setRunningCount(int count)
{
    QMetaObject::invokeMethod(this, [this, count] {
        if (count == m_running)
            return;
        m_running = count;
        Q_EMIT changed();
    }, Qt::QueuedConnection);
}
