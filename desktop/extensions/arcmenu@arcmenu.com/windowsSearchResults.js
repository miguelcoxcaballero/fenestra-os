import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Pango from 'gi://Pango';
import St from 'gi://St';

import {ArcMenuManager} from './arcmenuManager.js';

/*
 * Windows 11 search results: "Best match" column on the left and a
 * preview pane on the right. Data comes from ArcMenu's search providers;
 * only the presentation is replaced.
 */
const FILES = /Nautilus|recent-files|nemo/i;
const SETTINGS = /Settings|ControlCenter/i;
const IMAGE = /^image\//;

const label = (text, cls, ellipsize = true) => {
    const l = new St.Label({text: text ?? '', style_class: cls, y_align: Clutter.ActorAlign.CENTER});
    if (ellipsize)
        l.clutter_text.ellipsize = Pango.EllipsizeMode.END;
    return l;
};
const vbox = (cls, expand = true) => new St.BoxLayout({orientation: Clutter.Orientation.VERTICAL, style_class: cls, x_expand: expand});
const hbox = (cls, expand = true) => new St.BoxLayout({style_class: cls, x_expand: expand});

function fileOf(meta) {
    const id = String(meta.id ?? '');
    try {
        if (/^[a-z][a-z0-9+.-]*:\/\//i.test(id))
            return Gio.File.new_for_uri(id);
        if (id.startsWith('/'))
            return Gio.File.new_for_path(id);
    } catch {}
    return null;
}
function queryInfo(file) {
    if (!file?.is_native())
        return null;
    try {
        return file.query_info('standard::content-type,standard::type,time::modified', Gio.FileQueryInfoFlags.NONE, null);
    } catch {
        return null;
    }
}
function ago(seconds) {
    const d = Math.max(0, Date.now() / 1000 - seconds);
    const u = (n, w) => `${n} ${w}${n === 1 ? '' : 's'} ago`;
    if (d < 3600) return u(Math.max(1, Math.floor(d / 60)), 'minute');
    if (d < 86400) return u(Math.floor(d / 3600), 'hour');
    if (d < 86400 * 30) return u(Math.floor(d / 86400), 'day');
    if (d < 86400 * 365) return u(Math.floor(d / (86400 * 30)), 'month');
    return u(Math.floor(d / (86400 * 365)), 'year');
}
const title = s => s.replace(/\b\w/g, c => c.toUpperCase());
function stamp(seconds) {
    const dt = GLib.DateTime.new_from_unix_local(seconds);
    return dt.format('%d/%m/%Y, %H:%M');
}

export class WindowsSearchResults {
    constructor(helper) {
        this.helper = helper;
        this.layout = helper.layout;
        this.entries = [];
        this.selected = 0;
        this.renderId = 0;

        this.actor = hbox('win-results');
        this.actor.y_expand = true;
        this.actor.visible = false;

        this.scroll = new St.ScrollView({style_class: 'win-results-scroll', x_expand: false, y_expand: true,
            hscrollbar_policy: St.PolicyType.NEVER, vscrollbar_policy: St.PolicyType.EXTERNAL});
        this.list = vbox('win-results-list');
        this.scroll.set_child(this.list);
        this.actor.add_child(this.scroll);

        this.pane = vbox('win-preview', false);
        this.pane.y_expand = true;
        this.actor.add_child(this.pane);

        const sr = this.layout.searchResults;
        this._origUpdate = sr._updateResults;
        const self = this;
        sr._updateResults = async function (...args) {
            try {
                return await self._origUpdate.apply(this, args);
            } finally {
                self.queueRender();
            }
        };
        this._termsId = sr.connect('terms-changed', () => { this.selected = 0; this.queueRender(); });

        // Up/Down/Enter drive our own selection while results are shown.
        this._keyId = this.layout.searchEntry.connect('captured-event', (_a, event) => {
            if (event.type() !== Clutter.EventType.KEY_PRESS || !this.actor.visible || !this.entries.length)
                return Clutter.EVENT_PROPAGATE;
            const sym = event.get_key_symbol();
            if (sym === Clutter.KEY_Down || sym === Clutter.KEY_Up) {
                this.select(Math.max(0, Math.min(this.entries.length - 1, this.selected + (sym === Clutter.KEY_Down ? 1 : -1))));
                return Clutter.EVENT_STOP;
            }
            if (sym === Clutter.KEY_Return || sym === Clutter.KEY_KP_Enter) {
                this.entries[this.selected]?.activate();
                return Clutter.EVENT_STOP;
            }
            return Clutter.EVENT_PROPAGATE;
        });
    }

    get query() {
        return this.layout.searchEntry.getText().trim();
    }

    queueRender() {
        if (this.renderId)
            return;
        this.renderId = GLib.idle_add(GLib.PRIORITY_DEFAULT, () => {
            this.renderId = 0;
            this.render();
            return GLib.SOURCE_REMOVE;
        });
    }

    _collect() {
        const sr = this.layout.searchResults;
        const out = [];
        for (const provider of sr._providers ?? []) {
            const ids = sr._results?.[provider.id];
            const display = provider[sr._displayId];
            if (!ids?.length || !display?._resultDisplays)
                continue;
            for (const id of ids) {
                const item = display._resultDisplays[id];
                if (!item)
                    continue;
                out.push(this._entry(provider, item));
                if (out.length > 60)
                    return out;
            }
        }
        return out;
    }

    _entry(provider, item) {
        const meta = item.metaInfo ?? {};
        const app = item.app ?? null;
        const close = () => this.layout.arcMenu.close();
        const e = {
            provider, item, meta, app,
            name: app ? app.get_name() : String(meta.name ?? '').split('\n')[0],
            activate: () => {
                if (app)
                    this.helper.launch(app);
                else {
                    this.helper.save(this.query);
                    item.activate(Clutter.get_current_event());
                }
            },
        };
        if (app) {
            e.kind = 'app';
            e.type = 'App';
            e.icon = size => app.create_icon_texture(size);
            return e;
        }
        if (FILES.test(provider.id)) {
            const file = fileOf(meta);
            const info = queryInfo(file);
            const ct = info?.get_content_type() ?? (file ? Gio.content_type_guess(file.get_basename(), null)[0] : 'application/octet-stream');
            const isDir = info?.get_file_type() === Gio.FileType.DIRECTORY;
            const handler = isDir ? null : Gio.AppInfo.get_default_for_type(ct, false);
            const desc = isDir ? 'File folder' : title(Gio.content_type_get_description(ct) ?? 'File');
            const ext = file?.get_basename().match(/\.([^.]+)$/)?.[1];
            e.kind = isDir ? 'folder' : IMAGE.test(ct) ? 'photo' : 'file';
            e.file = file;
            e.modified = info?.get_modification_date_time()?.to_unix() ?? null;
            e.type = isDir ? 'File folder' : ext ? ext.toUpperCase() : desc;
            e.subtitle = (handler ? `${handler.get_name()} ${desc}` : desc) + (e.modified ? ` · Last modified ${ago(e.modified)}` : '');
            e.location = file?.get_parent()?.get_path() ?? '';
            e.icon = size => {
                if (e.kind === 'photo' && file)
                    return new St.Icon({gicon: new Gio.FileIcon({file}), icon_size: size});
                const gicon = isDir ? Gio.ThemedIcon.new('folder') : handler?.get_icon() ?? Gio.content_type_get_icon(ct);
                return new St.Icon({gicon, icon_size: size});
            };
            e.openLocation = () => {
                const parent = file?.get_parent();
                if (parent)
                    Gio.AppInfo.launch_default_for_uri(parent.get_uri(), global.create_app_launch_context(0, -1));
                close();
            };
            return e;
        }
        e.kind = SETTINGS.test(provider.id) ? 'settings' : 'other';
        e.type = e.kind === 'settings' ? 'System settings' : provider.appInfo?.get_name() ?? 'Result';
        e.subtitle = e.type;
        e.icon = size => {
            try {
                const icon = meta.createIcon?.(size);
                if (icon)
                    return icon;
            } catch {}
            return new St.Icon({gicon: provider.appInfo?.get_icon() ?? Gio.ThemedIcon.new('system-search-symbolic'), icon_size: size});
        };
        return e;
    }

    _webEntry() {
        const q = this.query;
        return {
            kind: 'web', name: q, type: 'Search the web', subtitle: 'Search the web',
            icon: size => new St.Icon({icon_name: 'system-search-symbolic', icon_size: Math.round(size * 0.625)}),
            activate: () => {
                this.helper.save(q);
                Gio.AppInfo.launch_default_for_uri(`https://www.bing.com/search?q=${encodeURIComponent(q)}`, global.create_app_launch_context(0, -1));
                this.layout.arcMenu.close();
            },
        };
    }

    render() {
        const q = this.query;
        this.list.destroy_all_children();
        if (!q) {
            this.entries = [];
            this.pane.destroy_all_children();
            return;
        }
        const cat = this.helper.category;
        const all = this._collect();
        const wanted = {apps: 'app', files: 'file', folders: 'folder', photos: 'photo', settings: 'settings'}[cat];
        const pool = wanted ? all.filter(e => e.kind === wanted) : cat === 'web' ? [] : all;
        const sections = [];
        if (pool.length)
            sections.push(['Best match', [pool[0]], false]);
        const rest = pool.slice(1);
        const limit = wanted ? 12 : 4;
        const groups = [['Apps', 'app'], ['Documents', 'file'], ['Folders', 'folder'], ['Photos', 'photo'], ['Settings', 'settings']];
        for (const [name, kind] of groups) {
            const items = rest.filter(e => e.kind === kind).slice(0, limit);
            if (items.length)
                sections.push([name, items, true]);
        }
        const others = new Map();
        for (const e of rest.filter(x => x.kind === 'other'))
            others.set(e.type, [...others.get(e.type) ?? [], e]);
        for (const [name, items] of others)
            sections.push([name, items.slice(0, 2), true]);
        if (!wanted)
            sections.push(['Web suggestions', [this._webEntry()], true]);

        this.entries = [];
        this.rows = [];
        sections.forEach(([name, items, more], si) => {
            const head = hbox('win-results-heading-row');
            if (si === 0)
                head.add_style_class_name('first');
            const h = label(name, 'win-results-heading');
            h.x_expand = true;
            head.add_child(h);
            if (more && name !== 'Best match')
                head.add_child(new St.Icon({icon_name: 'pan-end-symbolic', icon_size: 12, style_class: 'win-results-more', y_align: Clutter.ActorAlign.CENTER}));
            this.list.add_child(head);
            for (const e of items) {
                const index = this.entries.length;
                this.entries.push(e);
                this.list.add_child(this._row(e, index, name === 'Best match'));
            }
        });
        this.select(Math.min(this.selected, Math.max(0, this.entries.length - 1)), true);
    }

    _row(e, index, best) {
        const b = new St.Button({can_focus: true, reactive: true, x_expand: true, style_class: best ? 'win-result win-result-best' : 'win-result'});
        const row = hbox('win-result-content');
        row.add_child(new St.Widget({style_class: 'win-result-indicator', y_align: Clutter.ActorAlign.CENTER}));
        const iconBin = new St.Bin({style_class: best ? 'win-result-icon-plain' : 'win-result-icon', y_align: Clutter.ActorAlign.CENTER,
            child: e.icon(best ? 32 : e.kind === 'web' ? 32 : 24)});
        row.add_child(iconBin);
        const text = vbox('win-result-text');
        text.y_align = Clutter.ActorAlign.CENTER;
        const name = label(e.name, 'win-result-name');
        if (e.kind === 'web') {
            const q = GLib.markup_escape_text(e.name, -1);
            name.clutter_text.set_markup(q);
        }
        text.add_child(name);
        text.add_child(label(best ? e.subtitle ?? e.type : e.kind === 'app' ? 'App' : e.subtitle ?? e.type, 'win-result-sub'));
        row.add_child(text);
        b.set_child(row);
        b.connect('clicked', () => { this.select(index); e.activate(); });
        b.connect('key-focus-in', () => this.select(index));
        this.rows.push(b);
        return b;
    }

    select(index, force = false) {
        if (!this.entries.length) {
            this.pane.destroy_all_children();
            return;
        }
        if (index === this.selected && !force && this.pane.get_n_children())
            return;
        this.rows?.[this.selected]?.remove_style_pseudo_class('selected');
        this.selected = index;
        const row = this.rows?.[index];
        row?.add_style_pseudo_class('selected');
        if (row) {
            const adj = this.scroll.vadjustment;
            const box = row.get_allocation_box();
            if (box.y1 < adj.value)
                adj.value = box.y1;
            else if (box.y2 > adj.value + adj.page_size)
                adj.value = box.y2 - adj.page_size;
        }
        this._preview(this.entries[index]);
    }

    _button(text, fn, icon = null) {
        const b = new St.Button({can_focus: true, style_class: 'win-preview-button', x_expand: false});
        const c = hbox('win-preview-button-content', false);
        c.x_align = Clutter.ActorAlign.CENTER;
        c.add_child(label(text, 'win-preview-button-label', false));
        if (icon)
            c.add_child(new St.Icon({icon_name: icon, icon_size: 12, y_align: Clutter.ActorAlign.CENTER}));
        b.set_child(c);
        b.connect('clicked', fn);
        return b;
    }

    _action(text, iconName, fn) {
        const b = new St.Button({can_focus: true, style_class: 'win-preview-action', x_expand: true});
        const c = hbox('win-preview-action-content');
        c.add_child(new St.Icon({icon_name: iconName, icon_size: 16, y_align: Clutter.ActorAlign.CENTER}));
        c.add_child(label(text, 'win-preview-action-label'));
        b.set_child(c);
        b.connect('clicked', fn);
        return b;
    }

    _preview(e) {
        this.pane.destroy_all_children();
        if (!e)
            return;
        if (e.kind === 'file' || e.kind === 'folder' || e.kind === 'photo') {
            this.pane.add_child(label(e.name, 'win-preview-title'));
            this.pane.add_child(label(e.type, 'win-preview-type'));
            const card = new St.Bin({style_class: 'win-preview-card', x_expand: true, child: e.icon(e.kind === 'photo' ? 96 : 64)});
            this.pane.add_child(card);
            const buttons = hbox('win-preview-buttons');
            buttons.add_child(this._button('Open', () => e.activate()));
            const options = this._button('Options', () => this._options(e, options), 'pan-down-symbolic');
            buttons.add_child(options);
            this.pane.add_child(buttons);
            this.pane.add_child(label('Details', 'win-preview-details'));
            const detail = (k, v) => {
                if (!v)
                    return;
                const r = hbox('win-preview-detail');
                if (this.pane.get_last_child()?.has_style_class_name('win-preview-detail'))
                    r.add_style_class_name('next');
                r.add_child(label(k, 'win-preview-detail-key'));
                const value = label(v, 'win-preview-detail-value');
                value.x_expand = true;
                r.add_child(value);
                this.pane.add_child(r);
            };
            detail('Location', e.location);
            detail('Last modified', e.modified ? stamp(e.modified) : null);
            return;
        }
        // Apps, settings and web: centred header + action list, as Windows.
        const head = vbox('win-preview-hero');
        const icon = e.icon(64);
        icon.x_align = Clutter.ActorAlign.CENTER;
        head.add_child(new St.Bin({style_class: 'win-preview-hero-icon', child: icon, x_align: Clutter.ActorAlign.CENTER}));
        const n = label(e.kind === 'web' ? e.name : e.name, 'win-preview-hero-name');
        n.x_align = Clutter.ActorAlign.CENTER;
        head.add_child(n);
        const t = label(e.kind === 'web' ? 'See web results' : e.type, 'win-preview-hero-type');
        t.x_align = Clutter.ActorAlign.CENTER;
        head.add_child(t);
        this.pane.add_child(head);
        this.pane.add_child(new St.Widget({style_class: 'win-preview-separator', x_expand: true}));
        const actions = vbox('win-preview-actions');
        actions.add_child(this._action(e.kind === 'web' ? 'Open results in browser' : 'Open', e.kind === 'web' ? 'web-browser-symbolic' : 'window-new-symbolic', () => e.activate()));
        if (e.kind === 'app') {
            const id = e.app.get_id();
            const pinned = () => ArcMenuManager.settings.get_value('pinned-apps').deepUnpack();
            const isPinned = pinned().some(p => p.id === id);
            actions.add_child(this._action(isPinned ? 'Unpin from Start' : 'Pin to Start', 'view-pin-symbolic', () => {
                const list = pinned().filter(p => p.id !== id);
                if (!isPinned)
                    list.push({id});
                ArcMenuManager.settings.set_value('pinned-apps', new GLib.Variant('aa{ss}', list));
                this._preview(e);
            }));
            const info = e.app.get_app_info();
            for (const action of info.list_actions?.() ?? []) {
                actions.add_child(this._action(info.get_action_name(action), 'go-next-symbolic', () => {
                    info.launch_action(action, global.create_app_launch_context(0, -1));
                    this.layout.arcMenu.close();
                }));
            }
        }
        this.pane.add_child(actions);
    }

    _options(e, source) {
        // Small inline list under the buttons, like Windows' options flyout.
        if (this._optionsBox) {
            this._optionsBox.destroy();
            this._optionsBox = null;
            return;
        }
        const box = vbox('win-preview-options');
        box.add_child(this._action('Open file location', 'folder-open-symbolic', () => e.openLocation?.()));
        box.add_child(this._action('Copy full path', 'edit-copy-symbolic', () => {
            St.Clipboard.get_default().set_text(St.ClipboardType.CLIPBOARD, e.file?.get_path() ?? '');
            this.layout.arcMenu.close();
        }));
        const index = this.pane.get_children().indexOf(source.get_parent());
        this.pane.insert_child_at_index(box, index + 1);
        this._optionsBox = box;
        box.connect('destroy', () => { if (this._optionsBox === box) this._optionsBox = null; });
    }

    destroy() {
        if (this.renderId)
            GLib.source_remove(this.renderId);
        const sr = this.layout.searchResults;
        sr._updateResults = this._origUpdate;
        sr.disconnect(this._termsId);
        this.layout.searchEntry.disconnect(this._keyId);
        this.actor.destroy();
    }
}
