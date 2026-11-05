import St from 'gi://St';
import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

// Windows 11 notification centre + calendar flyout: two independent cards
// stacked above the clock, no shared surface behind them.

const _envLocale = (GLib.getenv('LC_ALL') || GLib.getenv('LC_TIME') || GLib.getenv('LANG') || 'en_US').split('.')[0].replace('_', '-');
const LOCALE = (() => { try { return Intl.DateTimeFormat.supportedLocalesOf([_envLocale]).length ? _envLocale : 'en-US'; } catch { return 'en-US'; } })();
const _LANG = (GLib.getenv('LANGUAGE') || GLib.getenv('LC_MESSAGES') || GLib.getenv('LANG') || 'en').split(':')[0].slice(0, 2);
const _ES = {
    'Notifications': 'Notificaciones', 'Clear all': 'Borrar todo', 'No new notifications': 'No hay notificaciones nuevas',
    'Do not disturb': 'No molestar', 'Show or hide calendar': 'Mostrar u ocultar calendario',
    'Decrease duration': 'Reducir duración', 'Increase duration': 'Aumentar duración', 'Focus': 'Concentración',
    'End session': 'Finalizar sesión', 'mins': 'min', 'Previous month': 'Mes anterior', 'Next month': 'Mes siguiente',
};
const _t = t => (_LANG === 'es' && _ES[t]) || t;
const GAP = 12; // between cards and above the taskbar / below the top edge

const iconButton = (icon, action, name, extra = '', size = 16) => {
    const b = new St.Button({style_class: `windows-panel-icon-button ${extra}`, can_focus: true, accessible_name: name, y_align: Clutter.ActorAlign.CENTER});
    b.set_child(new St.Icon({icon_name: icon, icon_size: size}));
    b.connect('clicked', action);
    return b;
};
const sameDay = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

// Blur my Shell blurs the whole menu box; retarget its blur at each card.
function bmsPopup() {
    const p = Main.extensionManager.lookup('blur-my-shell@aunetx')?.stateObj?._popup;
    return p?.enabled && typeof p.try_blur === 'function' ? p : null;
}

let calendarCollapsed = false;

export function installCalendarPanel() {
    const d = Main.panel.statusArea.dateMenu, menu = d.menu, list = d._messageList, area = list.get_parent();
    const column = d._calendar.get_parent(), cal = d._calendar;
    const settings = new Gio.Settings({schema_id: 'org.gnome.desktop.notifications'});
    const cleanups = [];
    const old = {
        orientation: area.orientation, layout: column.layout_manager, dateVisible: d._date.visible,
        displaysVisible: d._displaysSection.visible, iconVisible: list._placeholder._icon.visible,
        placeholder: list._placeholder._label.text, clearLabel: list._clearButton.label,
        clearParent: list._clearButton.get_parent(), clearXExpand: list._clearButton.x_expand,
        backIcon: cal._backButton.icon_name, forwardIcon: cal._forwardButton.icon_name,
        monthAlign: cal._monthLabel.x_align,
    };

    // ---- container: no surface of its own -------------------------------------------
    menu.actor.add_style_class_name('windows-calendar-menu');
    menu.box.remove_style_class_name('popup-menu-content');
    area.orientation = Clutter.Orientation.VERTICAL;
    area.add_style_class_name('windows-calendar-stack');

    // ---- notifications card -----------------------------------------------------------
    const notifications = new St.BoxLayout({orientation: Clutter.Orientation.VERTICAL, x_expand: true,
        style_class: 'popup-menu-content windows-notification-card'});
    area.remove_child(list);
    area.insert_child_at_index(notifications, 0);
    const head = new St.BoxLayout({style_class: 'windows-notification-heading'});
    head.add_child(new St.Label({text: _t('Notifications'), x_expand: true, y_align: Clutter.ActorAlign.CENTER, style_class: 'windows-notification-title'}));
    const dnd = iconButton('notifications-disabled-symbolic', () => settings.set_boolean('show-banners', !settings.get_boolean('show-banners')), _t('Do not disturb'));
    dnd.toggle_mode = false;
    head.add_child(dnd);
    const clear = list._clearButton;
    old.clearParent.remove_child(clear);
    clear.label = _t('Clear all');
    clear.x_expand = false;
    clear.add_style_class_name('windows-clear-all');
    head.add_child(clear);
    notifications.add_child(head);
    notifications.add_child(list);
    old.clearParent.hide();
    const syncClear = () => { clear.visible = clear.reactive && !list._placeholder.visible; };
    const clearIds = [clear.connect('notify::reactive', syncClear), clear.connect('notify::visible', () => { if (clear.visible && list._placeholder.visible) clear.visible = false; })];
    const placeholderId = list._placeholder.connect('notify::visible', syncClear);
    cleanups.push(() => { clearIds.forEach(id => clear.disconnect(id)); list._placeholder.disconnect(placeholderId); clear.visible = !list._placeholder.visible; });
    syncClear();
    const syncDnd = () => dnd.set_checked(!settings.get_boolean('show-banners'));
    cleanups.push(() => settings.disconnect(settings.connect('changed::show-banners', syncDnd)));
    syncDnd();
    list._placeholder._icon.hide();
    list._placeholder._label.text = _t('No new notifications');

    // ---- calendar card ------------------------------------------------------------------
    column.layout_manager = new Clutter.BoxLayout({orientation: Clutter.Orientation.VERTICAL});
    column.add_style_class_name('popup-menu-content');
    column.add_style_class_name('windows-calendar-card');
    d._date.hide();
    d._displaysSection.hide();

    const header = new St.BoxLayout({style_class: 'windows-calendar-header', x_expand: true});
    const dateLabel = new St.Label({style_class: 'windows-calendar-date', x_expand: true, y_align: Clutter.ActorAlign.CENTER});
    header.add_child(dateLabel);
    const collapse = iconButton('pan-down-symbolic', () => setCollapsed(!calendarCollapsed), _t('Show or hide calendar'), 'windows-calendar-collapse', 12);
    collapse.y_align = Clutter.ActorAlign.CENTER;
    header.add_child(collapse);
    column.insert_child_at_index(header, 0);

    const updateDate = () => {
        dateLabel.text = new Intl.DateTimeFormat(LOCALE, {weekday: 'long', month: 'long', day: 'numeric'}).format(new Date());
    };

    // Month header: "November 2026" on the left, ▲ ▼ on the right.
    cal._topBox.set_child_at_index(cal._monthLabel, 0);
    cal._monthLabel.x_align = Clutter.ActorAlign.START;
    const arrows = [];
    for (const [btn, glyph, name] of [[cal._backButton, '▲', 'Previous month'], [cal._forwardButton, '▼', 'Next month']]) {
        const label = new St.Label({text: glyph, style_class: 'windows-calendar-pager-glyph', y_align: Clutter.ActorAlign.CENTER, x_align: Clutter.ActorAlign.CENTER});
        arrows.push([btn, btn.get_child(), btn.accessible_name]);
        btn.set_child(label);
        btn.accessible_name = _t(name);
    }
    const monthText = () => {
        const t = new Intl.DateTimeFormat(LOCALE, {month: 'long', year: 'numeric'}).format(cal._selectedDate);
        return t.charAt(0).toLocaleUpperCase(LOCALE) + t.slice(1);
    };
    const polishMonth = () => { const t = monthText(); if (cal._monthLabel.text !== t) cal._monthLabel.text = t; };
    const monthId = cal._monthLabel.connect('notify::text', polishMonth);
    polishMonth();

    // Weekday row: the locale's two-letter abbreviations (Su Mo Tu… / lu ma mi…).
    const weekdays = [];
    for (const actor of cal.get_children()) {
        if (!actor.has_style_class_name?.('calendar-day-heading'))
            continue;
        weekdays.push([actor, actor.text]);
        const name = actor.accessible_name ?? actor.text;
        actor.text = name.charAt(0).toLocaleUpperCase(LOCALE) + name.slice(1, 2);
    }

    // Day grid: Windows starts on the week containing the 1st, pads at the end,
    // and prints day numbers without leading zeros.
    const fixGrid = () => {
        const buttons = cal._buttons ?? [];
        if (!buttons.length)
            return;
        const month = cal._selectedDate.getMonth(), now = new Date();
        const shift = buttons[7]?._date?.getDate() === 1 && buttons[7]._date.getMonth() === month ? 7 : 0;
        for (const b of buttons) {
            if (shift) { const n = new Date(b._date); n.setDate(n.getDate() + shift); b._date = n; }
            b.label = String(b._date.getDate());
            const classes = ['calendar-day'];
            if (sameDay(b._date, now)) classes.push('calendar-today');
            else if (b._date.getMonth() !== month) classes.push('calendar-other-month');
            b.style_class = classes.join(' ');
        }
    };
    const origRebuild = Object.hasOwn(cal, '_rebuildCalendar') ? cal._rebuildCalendar : null;
    cal._rebuildCalendar = function (...args) {
        const r = Object.getPrototypeOf(this)._rebuildCalendar.apply(this, args);
        fixGrid();
        return r;
    };
    cal._rebuildCalendar();
    cal._update();

    // ---- Focus footer -------------------------------------------------------------------
    let duration = 30, focusTimer = 0, remaining = 0, priorBanners = true;
    const focusRow = new St.BoxLayout({style_class: 'windows-focus-footer', x_expand: true});
    const durationLabel = new St.Label({style_class: 'windows-focus-duration', y_align: Clutter.ActorAlign.CENTER});
    const showDuration = text => durationLabel.clutter_text.set_markup(text);
    const idleDuration = () => showDuration(`<b>${duration}</b> ${_t('mins')}`);
    const adjust = n => { if (!focusTimer) { duration = Math.max(5, Math.min(240, duration + n)); idleDuration(); } };
    focusRow.add_child(iconButton('list-remove-symbolic', () => adjust(-5), _t('Decrease duration'), '', 12));
    focusRow.add_child(durationLabel);
    focusRow.add_child(iconButton('list-add-symbolic', () => adjust(5), _t('Increase duration'), '', 12));
    focusRow.add_child(new St.Widget({x_expand: true}));
    const focus = new St.Button({can_focus: true, style_class: 'windows-focus-button', y_align: Clutter.ActorAlign.CENTER});
    const focusBox = new St.BoxLayout({style_class: 'windows-focus-button-box'});
    const focusIcon = new St.Icon({icon_name: 'media-playback-start-symbolic', icon_size: 14});
    const focusLabel = new St.Label({text: _t('Focus'), y_align: Clutter.ActorAlign.CENTER});
    focusBox.add_child(focusIcon); focusBox.add_child(focusLabel); focus.set_child(focusBox);
    focusRow.add_child(focus);
    column.add_child(focusRow);
    idleDuration();
    const stop = () => {
        if (focusTimer) GLib.source_remove(focusTimer);
        focusTimer = 0;
        settings.set_boolean('show-banners', priorBanners);
        focusIcon.icon_name = 'media-playback-start-symbolic';
        focusLabel.text = _t('Focus');
        idleDuration();
    };
    focus.connect('clicked', () => {
        if (focusTimer) { stop(); return; }
        priorBanners = settings.get_boolean('show-banners');
        settings.set_boolean('show-banners', false);
        remaining = duration * 60;
        focusIcon.icon_name = 'media-playback-stop-symbolic';
        focusLabel.text = _t('End session');
        const tick = () => showDuration(`<b>${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, '0')}</b>`);
        tick();
        focusTimer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 1, () => {
            remaining--;
            tick();
            if (remaining <= 0) { focusTimer = 0; stop(); return GLib.SOURCE_REMOVE; }
            return GLib.SOURCE_CONTINUE;
        });
    });

    // ---- sizing: the notifications card takes whatever height is left ------------------
    const fit = () => {
        const monitor = Main.layoutManager.primaryMonitor;
        if (!monitor)
            return;
        const work = Main.layoutManager.getWorkAreaForMonitor(monitor.index);
        const scale = St.ThemeContext.get_for_stage(global.stage).scale_factor;
        const [, calH] = column.get_preferred_height(-1);
        const max = Math.max(120 * scale, work.height - calH - 3 * GAP * scale);
        notifications.set_style(`max-height: ${Math.floor(max / scale)}px;`);
    };
    const setCollapsed = value => {
        calendarCollapsed = value;
        cal.visible = !value;
        collapse.child.icon_name = value ? 'pan-up-symbolic' : 'pan-down-symbolic';
        column.remove_style_pseudo_class('collapsed');
        if (value) column.add_style_pseudo_class('collapsed');
        fit();
    };
    setCollapsed(calendarCollapsed);
    updateDate();
    const openId = menu.connect('open-state-changed', (_m, open) => {
        if (open) { updateDate(); polishMonth(); fit(); }
    });

    // ---- blur: one surface per card ----------------------------------------------------
    const bms = bmsPopup();
    if (bms) {
        try {
            bms.destroy_blur(menu.box);
            bms.try_blur(menu.actor);
        } catch (e) { logError(e, 'Fenestra calendar blur'); }
    }

    return () => {
        const blur = bmsPopup();
        if (blur) { try { blur.destroy_blur(notifications); blur.destroy_blur(column); } catch {} }
        menu.disconnect(openId);
        if (focusTimer) stop();
        cleanups.forEach(f => f());
        cal._monthLabel.disconnect(monthId);
        if (origRebuild) cal._rebuildCalendar = origRebuild; else delete cal._rebuildCalendar;
        cal._monthLabel.x_align = old.monthAlign;
        cal._topBox.set_child_at_index(cal._backButton, 0);
        for (const [btn, child, name] of arrows) { btn.set_child(null); btn.accessible_name = name; }
        cal._backButton.icon_name = old.backIcon;
        cal._forwardButton.icon_name = old.forwardIcon;
        for (const [a, t] of weekdays) a.text = t;
        cal._calendarBegin = null;
        cal._rebuildCalendar();
        cal._update();
        cal.show();
        column.remove_style_pseudo_class('collapsed');
        list._placeholder._label.text = old.placeholder;
        list._placeholder._icon.visible = old.iconVisible;
        head.remove_child(clear);
        clear.label = old.clearLabel;
        clear.x_expand = old.clearXExpand;
        clear.remove_style_class_name('windows-clear-all');
        old.clearParent.add_child(clear);
        old.clearParent.show();
        notifications.remove_child(list);
        area.insert_child_at_index(list, 0);
        notifications.destroy();
        header.destroy();
        focusRow.destroy();
        area.orientation = old.orientation;
        area.remove_style_class_name('windows-calendar-stack');
        column.remove_style_class_name('windows-calendar-card');
        column.remove_style_class_name('popup-menu-content');
        column.layout_manager = old.layout;
        d._date.visible = old.dateVisible;
        d._displaysSection.visible = old.displaysVisible;
        menu.box.add_style_class_name('popup-menu-content');
        menu.actor.remove_style_class_name('windows-calendar-menu');
        if (blur) { try { blur.try_blur(menu.actor); } catch {} }
    };
}
