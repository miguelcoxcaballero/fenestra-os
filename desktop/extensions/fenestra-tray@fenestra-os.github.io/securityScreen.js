import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Meta from 'gi://Meta';
import Shell from 'gi://Shell';
import St from 'gi://St';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import * as GnomeSession from 'resource:///org/gnome/shell/misc/gnomeSession.js';
import * as LoginManager from 'resource:///org/gnome/shell/misc/loginManager.js';
import * as SystemActions from 'resource:///org/gnome/shell/misc/systemActions.js';
import * as Util from 'resource:///org/gnome/shell/misc/util.js';

// Windows 11 Ctrl+Alt+Del security screen.
//
// Robustness: the shortcut is a compositor keybinding (works in every action
// mode, ignores autorepeat and cannot be inhibited by apps that grab the
// keyboard), the whole screen is built once at enable() and only shown/hidden,
// and it lives directly on the stage above every other shell layer.
const LANG = (GLib.getenv('LANGUAGE') || GLib.getenv('LC_MESSAGES') || GLib.getenv('LANG') || 'en').split(':')[0].slice(0, 2);
const ES = {
    'Lock': 'Bloquear', 'Switch user': 'Cambiar de usuario', 'Sign out': 'Cerrar sesión',
    'Change a password': 'Cambiar una contraseña', 'Task Manager': 'Administrador de tareas', 'Cancel': 'Cancelar',
    'Sleep': 'Suspender', 'Shut down': 'Apagar', 'Restart': 'Reiniciar', 'Magnifier': 'Lupa', 'Narrator': 'Narrador',
    'On-screen keyboard': 'Teclado en pantalla', 'Sticky keys': 'Teclas especiales', 'High contrast': 'Contraste alto',
    'Wi-Fi': 'Wi-Fi', 'Connected': 'Conectado', 'No internet access': 'Sin acceso a Internet',
    'Not connected': 'No conectado', 'On': 'Activado', 'Off': 'Desactivado', 'Network': 'Red',
    'Accessibility': 'Accesibilidad', 'Power': 'Inicio/Apagado',
};
const _ = s => (LANG === 'es' && ES[s]) || s;
export const KEY = 'security-screen';

// Geometry measured on a 1920x1080 Windows 11 capture, relative to the
// primary monitor centre (list/cancel) and bottom-right corner (buttons).
const G = {itemX: -72, itemW: 139, itemY: -177, itemH: 44, cancelX: -63, cancelY: 83, cancelW: 120, cancelH: 32,
    btn: 40, btnRight: [168, 120, 72], btnBottom: 62};

export class SecurityScreen {
    constructor(settings, asset) {
        this._settings = settings;
        this._asset = asset;
        this._grab = null;
        this._menu = null;
        this._pendingConfirm = null;
        this._build();
        this._session = null;
        // Async proxy so enable() never blocks on D-Bus.
        GnomeSession.SessionManager((proxy, error) => { if (!error) this._session = proxy; });
        this._a11y = {
            apps: new Gio.Settings({schema_id: 'org.gnome.desktop.a11y.applications'}),
            iface: new Gio.Settings({schema_id: 'org.gnome.desktop.a11y.interface'}),
            keyboard: new Gio.Settings({schema_id: 'org.gnome.desktop.a11y.keyboard'}),
        };
        Main.wm.addKeybinding(KEY, settings,
            Meta.KeyBindingFlags.IGNORE_AUTOREPEAT | Meta.KeyBindingFlags.NON_MASKABLE,
            Shell.ActionMode.ALL, () => this.open());
        this._sessionId = Main.sessionMode.connect('updated', () => { if (Main.sessionMode.isLocked) this.close(); });
        this._monitorsId = Main.layoutManager.connect('monitors-changed', () => this._layout());
        // Shut down / Restart from this screen skip GNOME's 60 s confirmation, like Windows.
        const dialog = Main.endSessionDialog, screen = this;
        if (dialog) {
            this._ownOpen = Object.hasOwn(dialog, 'OpenAsync');
            this._origOpen = dialog.OpenAsync;
            dialog.OpenAsync = async function (...args) {
                const result = await screen._origOpen.apply(this, args);
                if (screen._pendingConfirm) {
                    const signal = screen._pendingConfirm;
                    screen._pendingConfirm = null;
                    this._confirm(signal).catch(logError);
                }
                return result;
            };
        }
    }

    _icon(rel) {
        return new St.Icon({gicon: new Gio.FileIcon({file: Gio.File.new_for_path(this._asset(rel))}), icon_size: 16});
    }

    _build() {
        this._root = new St.Widget({name: 'fenestraSecurityScreen', style_class: 'fenestra-cad', reactive: true,
            can_focus: true, visible: false, layout_manager: new Clutter.FixedLayout()});
        this._root.connect('key-press-event', (_a, event) => this._onKey(event));
        this._root.connect('button-press-event', () => { this._closeMenu(); return Clutter.EVENT_STOP; });

        const actions = [
            ['Lock', () => this._lock()],
            ['Switch user', () => this._switchUser()],
            ['Sign out', () => this._signOut()],
            ['Change a password', () => this._changePassword()],
            ['Task Manager', () => this._taskManager()],
        ];
        this._targets = [];
        for (const [label, run] of actions) {
            const button = new St.Button({style_class: 'fenestra-cad-item', label: _(label), reactive: true,
                x_align: Clutter.ActorAlign.START});
            button.get_child().x_align = Clutter.ActorAlign.START;
            button.get_child().y_align = Clutter.ActorAlign.CENTER;
            button.connect('clicked', () => this._activate(run));
            this._root.add_child(button);
            this._targets.push({actor: button, run, kind: 'item'});
        }
        this._cancel = new St.Button({style_class: 'fenestra-cad-cancel', label: _('Cancel'), reactive: true});
        this._cancel.connect('clicked', () => this.close());
        this._root.add_child(this._cancel);
        this._targets.push({actor: this._cancel, run: () => this.close(), kind: 'button'});

        this._netIcon = this._icon('security/network-offline.svg');
        const corner = [
            [this._netIcon, 'Network', () => this._networkMenu()],
            [this._icon('security/accessibility.svg'), 'Accessibility', () => this._a11yMenu()],
            [this._icon('security/power.svg'), 'Power', () => this._powerMenu()],
        ];
        this._corner = [];
        for (const [icon, name, open] of corner) {
            const button = new St.Button({style_class: 'fenestra-cad-corner', child: icon, reactive: true,
                accessible_name: _(name)});
            button.connect('clicked', () => this._toggleMenu(button, open));
            this._root.add_child(button);
            this._corner.push(button);
            this._targets.push({actor: button, run: () => this._toggleMenu(button, open), kind: 'corner'});
        }
        this._focusRect = new St.Widget({style_class: 'fenestra-cad-focus', reactive: false});
        this._root.add_child(this._focusRect);
        global.stage.add_child(this._root);
        this._layout();
    }

    _layout() {
        const m = Main.layoutManager.primaryMonitor;
        if (!m) return;
        const s = St.ThemeContext.get_for_stage(global.stage).scale_factor;
        this._root.set_position(0, 0);
        this._root.set_size(global.stage.width, global.stage.height);
        const cx = m.x + Math.floor(m.width / 2), cy = m.y + Math.floor(m.height / 2);
        // The list is as wide as its longest entry (Windows: text + 9 px left, 10 px right).
        let w = G.itemW * s;
        for (const t of this._targets.filter(t => t.kind === 'item'))
            w = Math.max(w, t.actor.get_preferred_width(-1)[1]);
        this._targets.filter(t => t.kind === 'item').forEach((t, i) => {
            t.actor.set_position(cx + G.itemX * s, cy + (G.itemY + G.itemH * i) * s);
            t.actor.set_size(w, G.itemH * s);
        });
        this._cancel.set_position(cx + G.cancelX * s, cy + G.cancelY * s);
        this._cancel.set_size(G.cancelW * s, G.cancelH * s);
        this._corner.forEach((b, i) => {
            b.set_position(m.x + m.width - G.btnRight[i] * s, m.y + m.height - G.btnBottom * s);
            b.set_size(G.btn * s, G.btn * s);
        });
        if (this._focus !== undefined) this._setFocus(this._focus);
    }

    _setFocus(index) {
        const n = this._targets.length;
        this._focus = (index + n) % n;
        const a = this._targets[this._focus].actor;
        const s = St.ThemeContext.get_for_stage(global.stage).scale_factor;
        // Items: 2 px outline 3 px above/below the row; buttons: 3 px around.
        const pad = this._targets[this._focus].kind === 'item' ? [0, 3 * s] : [3 * s, 3 * s];
        this._focusRect.set_position(a.x - pad[0], a.y - pad[1]);
        this._focusRect.set_size(a.width + 2 * pad[0], a.height + 2 * pad[1]);
        this._root.set_child_above_sibling(this._focusRect, null);
        if (this._menu) this._root.set_child_above_sibling(this._menu.actor, null);
    }

    open() {
        if (this._grab || Main.sessionMode.isLocked || Main.sessionMode.isGreeter)
            return;
        // Nothing expensive here: everything already exists.
        this._closeMenu();
        global.stage.set_child_above_sibling(this._root, null);
        this._root.opacity = 255;
        this._root.show();
        this._grab = Main.pushModal(this._root, {actionMode: Shell.ActionMode.SYSTEM_MODAL});
        this._setFocus(0);
        this._root.grab_key_focus();
        // Cheap state refresh after the frame is queued.
        GLib.idle_add(GLib.PRIORITY_HIGH_IDLE, () => { this._syncNetwork(); return GLib.SOURCE_REMOVE; });
    }

    close() {
        this._closeMenu();
        if (this._grab) {
            Main.popModal(this._grab);
            this._grab = null;
        }
        this._root.hide();
    }

    get visible() {
        return this._root.visible;
    }

    _activate(run) {
        this.close();
        try {
            run();
        } catch (e) {
            logError(e, 'Fenestra security screen');
        }
    }

    _onKey(event) {
        const key = event.get_key_symbol();
        const shift = event.get_state() & Clutter.ModifierType.SHIFT_MASK;
        if (this._menu) return this._menuKey(key);
        const listEnd = this._targets.findIndex(t => t.kind === 'corner');
        switch (key) {
        case Clutter.KEY_Escape:
            this.close();
            return Clutter.EVENT_STOP;
        case Clutter.KEY_Up: case Clutter.KEY_KP_Up:
            if (this._focus < listEnd) this._setFocus(this._focus === 0 ? listEnd - 1 : this._focus - 1);
            else this._setFocus(this._focus - 1 < listEnd ? this._targets.length - 1 : this._focus - 1);
            return Clutter.EVENT_STOP;
        case Clutter.KEY_Down: case Clutter.KEY_KP_Down:
            if (this._focus < listEnd) this._setFocus(this._focus + 1 >= listEnd ? 0 : this._focus + 1);
            else this._setFocus(this._focus + 1 >= this._targets.length ? listEnd : this._focus + 1);
            return Clutter.EVENT_STOP;
        case Clutter.KEY_Left: case Clutter.KEY_Right:
            if (this._focus >= listEnd) this._setFocus(this._focus + (key === Clutter.KEY_Left ? -1 : 1) < listEnd
                ? this._targets.length - 1 : this._focus + (key === Clutter.KEY_Left ? -1 : 1));
            return Clutter.EVENT_STOP;
        case Clutter.KEY_Tab: case Clutter.KEY_ISO_Left_Tab: case Clutter.KEY_KP_Tab:
            this._setFocus(this._focus + (shift || key === Clutter.KEY_ISO_Left_Tab ? -1 : 1));
            return Clutter.EVENT_STOP;
        case Clutter.KEY_Return: case Clutter.KEY_KP_Enter: case Clutter.KEY_ISO_Enter: case Clutter.KEY_space: {
            const t = this._targets[this._focus];
            if (t.kind === 'item') this._activate(t.run);
            else t.run();
            return Clutter.EVENT_STOP;
        }
        }
        return Clutter.EVENT_STOP; // swallow everything else while the screen is up
    }

    // ---- menus (network / accessibility / power) ----
    _toggleMenu(button, open) {
        const same = this._menu?.button === button;
        this._closeMenu();
        if (!same) open();
        const i = this._targets.findIndex(t => t.actor === button);
        if (i >= 0) this._setFocus(i);
    }

    _closeMenu() {
        if (!this._menu) return;
        this._menu.actor.destroy();
        this._menu.button.remove_style_pseudo_class('checked');
        this._menu = null;
    }

    _showMenu(button, rows) {
        const box = new St.BoxLayout({style_class: 'fenestra-cad-menu', orientation: Clutter.Orientation.VERTICAL,
            reactive: true});
        box.connect('button-press-event', () => Clutter.EVENT_STOP);
        const items = [];
        for (const row of rows) {
            if (row.header) {
                const h = new St.BoxLayout({style_class: 'fenestra-cad-menu-header'});
                if (row.icon) h.add_child(this._icon(row.icon));
                const col = new St.BoxLayout({orientation: Clutter.Orientation.VERTICAL, y_align: Clutter.ActorAlign.CENTER});
                col.add_child(new St.Label({text: row.header, style_class: 'fenestra-cad-menu-title'}));
                if (row.sub) col.add_child(new St.Label({text: row.sub, style_class: 'fenestra-cad-menu-sub'}));
                h.add_child(col);
                box.add_child(h);
                continue;
            }
            const item = new St.Button({style_class: 'fenestra-cad-menu-item', reactive: true, x_expand: true});
            const content = new St.BoxLayout({x_expand: true});
            if (row.icon) content.add_child(this._icon(row.icon));
            content.add_child(new St.Label({text: row.label, x_expand: true, y_align: Clutter.ActorAlign.CENTER,
                style_class: 'fenestra-cad-menu-label'}));
            let sw = null;
            if (row.toggle) {
                sw = new PopupMenu.Switch(row.toggle.get());
                sw.y_align = Clutter.ActorAlign.CENTER;
                content.add_child(sw);
            }
            item.set_child(content);
            const run = () => {
                if (row.toggle) { row.toggle.set(!row.toggle.get()); sw.state = row.toggle.get(); return; }
                this._activate(row.run);
            };
            item.connect('clicked', run);
            box.add_child(item);
            items.push({actor: item, run});
        }
        this._root.add_child(box);
        const m = Main.layoutManager.primaryMonitor;
        const [, w] = box.get_preferred_width(-1), [, h] = box.get_preferred_height(w);
        const x = Math.min(m.x + m.width - w - 12, Math.max(m.x + 12, button.x + button.width / 2 - w / 2));
        box.set_position(Math.round(x), Math.round(button.y - h - 8));
        button.add_style_pseudo_class('checked');
        this._menu = {actor: box, button, items, focus: 0};
        this._menuFocus(0);
    }

    _menuFocus(i) {
        const menu = this._menu;
        if (!menu.items.length) return;
        menu.items[menu.focus]?.actor.remove_style_pseudo_class('focus');
        menu.focus = (i + menu.items.length) % menu.items.length;
        menu.items[menu.focus].actor.add_style_pseudo_class('focus');
    }

    _menuKey(key) {
        const menu = this._menu;
        switch (key) {
        case Clutter.KEY_Escape: this._closeMenu(); break;
        case Clutter.KEY_Up: case Clutter.KEY_KP_Up: case Clutter.KEY_ISO_Left_Tab: this._menuFocus(menu.focus - 1); break;
        case Clutter.KEY_Down: case Clutter.KEY_KP_Down: case Clutter.KEY_Tab: this._menuFocus(menu.focus + 1); break;
        case Clutter.KEY_Return: case Clutter.KEY_KP_Enter: case Clutter.KEY_space: menu.items[menu.focus]?.run(); break;
        }
        return Clutter.EVENT_STOP;
    }

    _nm() {
        return Main.panel.statusArea.quickSettings?._network?._client ?? null;
    }

    _syncNetwork() {
        const nm = this._nm();
        const conn = nm?.primary_connection;
        const type = conn?.get_connection_type?.() ?? '';
        const online = nm && nm.connectivity === 4; // NM.ConnectivityState.FULL
        const rel = !conn || !online ? 'security/network-offline.svg'
            : /wireless/.test(type) ? 'security/network-wifi.svg' : 'security/network-wired.svg';
        this._netIcon.gicon = new Gio.FileIcon({file: Gio.File.new_for_path(this._asset(rel))});
        return {nm, conn, online, type};
    }

    _networkMenu() {
        const {nm, conn, online, type} = this._syncNetwork();
        const rows = [{header: conn?.get_id?.() ?? _('Network'),
            sub: conn ? (online ? _('Connected') : _('No internet access')) : _('Not connected'),
            icon: !conn || !online ? 'security/network-offline.svg' : /wireless/.test(type) ? 'security/network-wifi.svg' : 'security/network-wired.svg'}];
        if (nm) {
            rows.push({label: _('Wi-Fi'), toggle: {get: () => nm.wireless_enabled,
                set: v => { nm.wireless_enabled = v; }}});
        }
        this._showMenu(this._corner[0], rows);
    }

    _a11yMenu() {
        const flag = (settings, key) => ({get: () => settings.get_boolean(key), set: v => settings.set_boolean(key, v)});
        const {apps, iface, keyboard} = this._a11y;
        this._showMenu(this._corner[1], [
            {label: _('Magnifier'), toggle: flag(apps, 'screen-magnifier-enabled')},
            {label: _('Narrator'), toggle: flag(apps, 'screen-reader-enabled')},
            {label: _('On-screen keyboard'), toggle: flag(apps, 'screen-keyboard-enabled')},
            {label: _('Sticky keys'), toggle: flag(keyboard, 'stickykeys-enable')},
            {label: _('High contrast'), toggle: flag(iface, 'high-contrast')},
        ]);
    }

    _powerMenu() {
        this._showMenu(this._corner[2], [
            {label: _('Sleep'), icon: 'security/sleep.svg', run: () => LoginManager.getLoginManager().suspend()},
            {label: _('Shut down'), icon: 'security/power.svg', run: () => this._endSession('Shutdown', 'ConfirmedShutdown')},
            {label: _('Restart'), icon: 'security/restart.svg', run: () => this._endSession('Reboot', 'ConfirmedReboot')},
        ]);
    }

    // ---- actions ----
    _lock() {
        Main.screenShield?.lock(true);
    }

    _switchUser() {
        const actions = SystemActions.getDefault();
        try {
            actions.activateSwitchUser();
        } catch {
            Main.screenShield?.lock(false);
            Util.trySpawn(['gdmflexiserver']);
        }
    }

    _signOut() {
        Main.overview.hide();
        // 1 = GSM_MANAGER_LOGOUT_MODE_NO_CONFIRMATION
        if (this._session) this._session.LogoutAsync(1).catch(logError);
        else Util.trySpawn(['gnome-session-quit', '--logout', '--no-prompt']);
    }

    _endSession(method, signal) {
        if (!this._session) return;
        this._pendingConfirm = signal;
        this._session[`${method}Async`]().catch(e => { this._pendingConfirm = null; logError(e); });
    }

    _changePassword() {
        if (GLib.find_program_in_path('fenestra-settings'))
            Util.trySpawn(['fenestra-settings', '--page', 'signin']);
        else
            Util.trySpawn(['gnome-control-center', 'system', 'users']);
    }

    _taskManager() {
        const apps = Shell.AppSystem.get_default();
        for (const id of ['net.nokyan.Resources.desktop', 'org.gnome.SystemMonitor.desktop', 'gnome-system-monitor.desktop']) {
            const app = apps.lookup_app(id);
            if (app) { app.activate(); return; }
        }
        Util.trySpawn(['gnome-system-monitor']);
    }

    destroy() {
        this.close();
        Main.wm.removeKeybinding(KEY);
        Main.sessionMode.disconnect(this._sessionId);
        Main.layoutManager.disconnect(this._monitorsId);
        if (this._origOpen) {
            if (this._ownOpen) Main.endSessionDialog.OpenAsync = this._origOpen;
            else delete Main.endSessionDialog.OpenAsync;
        }
        this._root.destroy();
    }
}
