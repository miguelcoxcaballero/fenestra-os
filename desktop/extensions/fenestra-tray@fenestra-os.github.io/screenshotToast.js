import Clutter from 'gi://Clutter';
import St from 'gi://St';
import * as MessageTray from 'resource:///org/gnome/shell/ui/messageTray.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

// Windows 11 Snipping Tool toast: thumbnail on top, "Snipping Tool" header,
// Windows wording and a full-width "Mark-up and share" button.
const SHOT_TITLES = new Set(['Screenshot captured', 'Captura de pantalla realizada', 'Captura de pantalla tomada']);
export function installScreenshotToast(injections) {
    injections.overrideMethod(MessageTray.Source.prototype, 'addNotification', original => function (notification) {
        if (SHOT_TITLES.has(notification.title) && notification.gicon) {
            notification._windowsShot = notification.gicon;
            this.title = 'Snipping Tool';
            notification.set({title: 'Screenshot copied to clipboard', body: 'Automatically saved to screenshots folder.'});
            const action = notification.actions?.[0];
            if (action) {
                action._label = 'Mark-up and share';
                action._callback = () => notification.activate(); // opens the image, like Windows' editor
            }
        }
        return original.call(this, notification);
    });
    // NotificationMessage uses an ES constructor (no _init), so decorate the banner
    // when the message tray inserts it.
    const decorate = function () {
        const content = this.notification?._windowsShot;
        if (!content) return;
        this.add_style_class_name('windows-shot-toast');
        this._icon.visible = false;
        this._icon.connect('notify::visible', () => { if (this._icon.visible) this._icon.visible = false; });
        const [ok, w, h] = content.get_preferred_size?.() ?? [false, 16, 9];
        const W = 330, H = Math.round(Math.min(160, W * (ok ? h / Math.max(1, w) : 9 / 16)));
        const box = new St.Bin({style_class: 'windows-shot-preview', x_expand: true});
        const image = new St.Widget({content, content_gravity: Clutter.ContentGravity.RESIZE_ASPECT, width: W, height: H,
            x_align: Clutter.ActorAlign.CENTER});
        box.set_child(image);
        this.child.insert_child_at_index(box, 0);
        this._header.timeLabel?.hide();
        // Windows always shows the action button, not only when expanded.
        this.expand?.(false);
    };
    const bin = Main.messageTray._bannerBin;
    const id = bin.connect('child-added', (_b, actor) => { if (!actor._windowsShotDone) { actor._windowsShotDone = true; decorate.call(actor); } });
    return () => bin.disconnect(id);
}
