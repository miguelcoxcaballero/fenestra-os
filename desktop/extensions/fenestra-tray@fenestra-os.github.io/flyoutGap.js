import St from 'gi://St';
import {BoxPointer} from 'resource:///org/gnome/shell/ui/boxpointer.js';

// Windows 11: every flyout opened from the taskbar — Start, Search, quick
// settings, tray menus, the calendar/notification cards — has no arrow, its
// bottom edge exactly 12 px above the taskbar and at least 13 px between it
// and the screen edge (the calendar cards' measured right margin). GNOME
// places popups from the arrow rise and the source button, which gave a
// different gap for every flyout (1 … 23 px). Here the final position is set
// after GNOME's own placement, for every BoxPointer anchored to the taskbar.
export const FLYOUT_GAP = 12;
export const FLYOUT_EDGE = 13;

function mergeStyle(actor, props) {
    const decls = new Map();
    for (const part of (actor.style ?? '').split(';')) {
        const i = part.indexOf(':');
        if (i > 0)
            decls.set(part.slice(0, i).trim(), part.slice(i + 1).trim());
    }
    for (const [k, v] of Object.entries(props))
        decls.set(k, v);
    const style = [...decls].map(([k, v]) => `${k}: ${v};`).join(' ');
    if (style !== (actor.style ?? ''))
        actor.style = style || null;
}

function taskbarOf(boxPointer) {
    if (boxPointer._arrowSide !== St.Side.BOTTOM)
        return null;
    const source = boxPointer._sourceActor;
    if (!source?.get_stage?.())
        return null;
    // Inside the taskbar, or (ArcMenu's own source actor) centred on it.
    const [sx, sy] = source.get_transformed_position();
    const [sw, sh] = source.get_transformed_size();
    const cx = sx + sw / 2, cy = sy + sh / 2;
    const panel = (global.dashToPanel?.panels ?? []).find(p => {
        if (!p.panelBox)
            return false;
        if (p.panelBox.contains?.(source))
            return true;
        const [px, py] = p.panelBox.get_transformed_position();
        const [pw, ph] = p.panelBox.get_transformed_size();
        return cx >= px && cx <= px + pw && cy >= py - 1 && cy <= py + ph + 1;
    });
    return panel && !panel.geom?.vertical ? panel : null;
}

export function installFlyoutGap(injections) {
    // No arrow and no rise for taskbar flyouts (the rise is empty space).
    injections.overrideMethod(BoxPointer.prototype, 'open', original => function (...args) {
        try {
            if (taskbarOf(this))
                mergeStyle(this, {'-arrow-rise': '0px', '-arrow-base': '0px', '-boxpointer-gap': '0px'});
        } catch (e) {
            console.warn(`Fenestra flyout gap: ${e.message}`);
        }
        return original.apply(this, args);
    });
    injections.overrideMethod(BoxPointer.prototype, '_reposition', original => function (box) {
        original.call(this, box);
        try {
            const panel = taskbarOf(this);
            if (!panel)
                return;
            // The calendar cards place themselves inside a full-height box.
            if (this.has_style_class_name('windows-calendar-menu'))
                return;
            const scale = St.ThemeContext.get_for_stage(global.stage).scale_factor;
            const [, , natWidth, natHeight] = this.get_preferred_size();
            const [, py] = panel.panelBox.get_transformed_position();
            const mon = panel.monitor ?? global.display.get_monitor_geometry(panel.monitor?.index ?? 0);
            let x = box.x1, y = Math.round(py - FLYOUT_GAP * scale - natHeight);
            x = Math.min(x, mon.x + mon.width - FLYOUT_EDGE * scale - natWidth);
            x = Math.max(x, mon.x + FLYOUT_EDGE * scale);
            // allocationBox is in the parent's coordinates (stage for uiGroup children).
            // Like GNOME: walk up until an ancestor can map stage coordinates.
            let parent = this.get_parent(), lx = x, ly = y;
            while (parent) {
                const [ok, px, pyy] = parent.transform_stage_point(x, y);
                if (ok) {
                    [lx, ly] = [px, pyy];
                    break;
                }
                parent = parent.get_parent();
            }
            box.set_origin(Math.floor(lx), Math.floor(ly));
        } catch (e) {
            console.warn(`Fenestra flyout position: ${e.message}`);
        }
    });
    return () => {};
}
