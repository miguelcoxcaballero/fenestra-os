// Keep the native panel unpainted while Dash to Panel rebuilds after unlock.
// Visibility remains true during layout, so allocation and struts can settle.
export function installPanelGuard({Main, GLib, St, shellGlobal}) {
    const panel = Main.panel;
    let saved = null;
    let timer = 0;
    let pending = false;
    let stable = 0;
    let lastGeometry = '';
    let started = 0;
    const locked = () => Main.sessionMode.isGreeter || Main.sessionMode.isLocked;
    const cancel = () => {
        if (timer) GLib.source_remove(timer);
        timer = 0;
        pending = false;
        stable = 0;
        lastGeometry = '';
    };
    const restore = () => {
        const state = saved;
        saved = null;
        pending = false;
        if (state) {
            panel.opacity = state.opacity;
            panel.visible = state.visible;
        }
    };
    const sync = () => {
        if (locked()) {
            cancel();
            if (!saved) saved = {visible: panel.visible, opacity: panel.opacity};
            if (panel.visible) panel.hide();
            return;
        }
        if (!saved) return;
        if (pending) {
            if (panel.opacity !== 0) panel.opacity = 0;
            return;
        }
        pending = true;
        panel.opacity = 0;
        panel.visible = saved.visible;
        started = GLib.get_monotonic_time();
        timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 50, () => {
            if (locked()) { timer = 0; sync(); return GLib.SOURCE_REMOVE; }
            const dtp = shellGlobal.dashToPanel?.panels?.find(p => p.panel === panel);
            const monitor = dtp?.monitor;
            const [x, y] = panel.get_transformed_position();
            const geometry = `${x},${y},${panel.width},${panel.height}`;
            const ready = dtp && dtp.getPosition() === St.Side.BOTTOM &&
                panel.has_allocation() && panel.height > 0 && monitor &&
                y >= monitor.y + monitor.height / 2;
            stable = ready && geometry === lastGeometry ? stable + 1 : 0;
            lastGeometry = geometry;
            const elapsed = GLib.get_monotonic_time() - started;
            // A bounded fallback preserves access if Dash to Panel was disabled
            // or failed. Never leave the user's panel permanently invisible.
            if (stable >= 2 || elapsed >= 3000000) {
                timer = 0;
                restore();
                return GLib.SOURCE_REMOVE;
            }
            return GLib.SOURCE_CONTINUE;
        });
    };
    const sessionId = Main.sessionMode.connect('updated', sync);
    const visibleId = panel.connect('notify::visible', sync);
    const opacityId = panel.connect('notify::opacity', () => {
        if (pending && panel.opacity !== 0) panel.opacity = 0;
    });
    sync();
    return () => {
        Main.sessionMode.disconnect(sessionId);
        panel.disconnect(visibleId);
        panel.disconnect(opacityId);
        cancel();
        restore();
    };
}
