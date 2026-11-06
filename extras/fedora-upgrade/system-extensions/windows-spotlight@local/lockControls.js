import * as Main from 'resource:///org/gnome/shell/ui/main.js';
// Keep status controls hidden even when their own visibility bindings update.
export function installLockControls() {
    const controls=new Map();
    const locked=()=>Main.sessionMode.isLocked || Main.sessionMode.isGreeter;
    function sync() {
        for(const name of ['a11y','quickSettings']) {
            const item=Main.panel.statusArea[name];
            const actor=item?.container??item;
            if(actor && !controls.has(actor)) {
                const state={visible:actor.visible,id:0};
                state.id=actor.connect('notify::visible',()=>{if(locked()&&actor.visible)actor.hide();});
                controls.set(actor,state);
            }
        }
        for(const [actor,state] of controls) {
            if(locked()) {if(!state.hidden)state.visible=actor.visible;state.hidden=true;actor.hide();}
            else if(state.hidden) {state.hidden=false;actor.visible=state.visible;}
        }
    }
    const id=Main.sessionMode.connect('updated',sync);sync();
    return ()=>{Main.sessionMode.disconnect(id);for(const [actor,state] of controls){actor.disconnect(state.id);if(state.hidden)actor.visible=state.visible;}controls.clear();};
}
