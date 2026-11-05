import St from 'gi://St';
import Clutter from 'gi://Clutter';
import Pango from 'gi://Pango';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
const fenestraAsset=rel=>{for(const base of [GLib.build_filenamev([GLib.get_user_data_dir(),'fenestra','assets']),'/usr/share/fenestra/assets']){const p=GLib.build_filenamev([base,rel]);if(GLib.file_test(p,GLib.FileTest.EXISTS))return p;}return GLib.build_filenamev(['/usr/share/fenestra/assets',rel]);};

const _LANG=(GLib.getenv('LANGUAGE')||GLib.getenv('LC_MESSAGES')||GLib.getenv('LANG')||'en').split(':')[0].slice(0,2);
const _ES={'User Account Control':'Control de cuentas de usuario','Cancel':'Cancelar','Do you want to allow this app to make changes to your device?':'¿Quieres permitir que esta aplicación haga cambios en el dispositivo?','Show more details':'Mostrar detalles','Hide details':'Ocultar detalles','Action ID: %s':'Identificador de la acción: %s','Yes':'Sí','No':'No'};
const _=t=>(_LANG==='es'&&_ES[t])||t;

function label(text,style) {
 const item=new St.Label({text,style_class:style,x_expand:true,request_mode:Clutter.RequestMode.HEIGHT_FOR_WIDTH});
 item.clutter_text.line_wrap=true;item.clutter_text.line_wrap_mode=Pango.WrapMode.WORD_CHAR;item.clutter_text.ellipsize=Pango.EllipsizeMode.NONE;
 return item;
}
export function styleAuthorization(d,path) {
 if(d._windowsPresentation)return;
 d._windowsPresentation=true;
 d.dialogLayout.add_style_class_name('windows-consent-dialog');
 d.contentLayout.add_style_class_name('windows-consent-content');
 d.buttonLayout.add_style_class_name('windows-consent-buttons');
 const nativeHeader=d.contentLayout.get_child_at_index(0);nativeHeader.hide();
 const top=new St.BoxLayout({orientation:Clutter.Orientation.VERTICAL,style_class:'windows-consent-heading'});
 const titlebar=new St.BoxLayout({style_class:'windows-consent-titlebar'});
 titlebar.add_child(label(_('User Account Control'),'windows-consent-caption'));
 const close=new St.Button({style_class:'windows-consent-close',accessible_name:_('Cancel'),can_focus:true});
 close.set_child(new St.Icon({gicon:new Gio.FileIcon({file:Gio.File.new_for_path(fenestraAsset('consent/close.svg'))}),icon_size:10}));
 close.connect('clicked',()=>d.cancel());titlebar.add_child(close);top.add_child(titlebar);
 top.add_child(label(_('Do you want to allow this app to make changes to your device?'),'windows-consent-question'));
 const body=new St.BoxLayout({orientation:Clutter.Orientation.VERTICAL,style_class:'windows-consent-body'});
 const row=new St.BoxLayout({style_class:'windows-consent-app',request_mode:Clutter.RequestMode.HEIGHT_FOR_WIDTH});
 row.add_child(new St.Icon({gicon:new Gio.FileIcon({file:Gio.File.new_for_path(fenestraAsset('consent/shield.svg'))}),icon_size:32,y_align:Clutter.ActorAlign.CENTER}));
 // Show the genuine polkit action description. Never invent publisher trust.
 row.add_child(label(d.message,'windows-consent-action'));body.add_child(row);
 const details=new St.Button({label:_('Show more details'),style_class:'windows-consent-details',x_align:Clutter.ActorAlign.START,can_focus:true});
 const action=label(_('Action ID: %s').replace('%s',d.actionId),'windows-consent-action-id');action.hide();
 details.connect('clicked',()=>{action.visible=!action.visible;details.label=action.visible?_('Hide details'):_('Show more details');});
 body.add_child(details);body.add_child(action);
 d.contentLayout.insert_child_at_index(top,0);d.contentLayout.insert_child_at_index(body,1);
 // Native password/error controls remain available if policy requires them.
 d._userAvatar.get_parent().add_style_class_name('windows-consent-native-user');
 d._nullMessageLabel?.hide();
}
// Fenestra always keeps the native password prompt (no password-less consent):
// only the buttons get the Windows wording.
export function setConsentMode(d) {
 d._passwordEntry.get_parent().show();d._userAvatar.get_parent().show();
 d._okButton.label=_('Yes');d._cancelButton.label=_('No');
}
