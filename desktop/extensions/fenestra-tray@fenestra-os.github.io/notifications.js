import Clutter from 'gi://Clutter';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

// Anchor the native tray to the work-area's bottom-right corner. Notification
// policy, urgency, focus, timeout, actions and lock-screen privacy stay native.
export function installNotificationPosition() {
    const bin = Main.messageTray._bannerBin;
    const old = {x_align: bin.x_align, y_align: bin.y_align,
        translation_x: bin.translation_x, translation_y: bin.translation_y};
    const apply = () => {
        if (bin.x_align !== Clutter.ActorAlign.END) bin.x_align = Clutter.ActorAlign.END;
        if (bin.y_align !== Clutter.ActorAlign.END) bin.y_align = Clutter.ActorAlign.END;
        bin.translation_x = -12;
        bin.translation_y = -12;
    };
    // The stock panel resets alignment when session mode changes; reapply it.
    const ids = ['notify::x-align', 'notify::y-align'].map(signal => bin.connect(signal, apply));
    apply();
    return () => {
        ids.forEach(id => bin.disconnect(id));
        Object.assign(bin, old);
    };
}
