import * as LoginManager from 'resource:///org/gnome/shell/misc/loginManager.js';

// Only coalesce authenticated GDM conversations from the same login attempt.
// Existing desktop sessions still go through GNOME's conflict checks.
export function installLoginRaceGuard(injections, LoginDialog) {
    const attempts=new WeakMap();
    injections.overrideMethod(LoginDialog.prototype,'_onReset',original=>function(...args){
        attempts.delete(this);
        return original.apply(this,args);
    });
    injections.overrideMethod(LoginDialog.prototype,'_onSessionOpened',original=>function(client,service,id){
        if(!['gdm-password','gdm-fingerprint'].includes(service))
            return original.call(this,client,service,id);
        let attempt=attempts.get(this);
        if(!attempt) {
            attempt={service,ids:new Set(),handling:false,started:false};
            attempts.set(this,attempt);
        }
        if(id)attempt.ids.add(id);
        if(attempt.handling)return;
        attempt.handling=true;
        return original.call(this,client,service,id);
    });
    injections.overrideMethod(LoginDialog.prototype,'_findConflictingSession',original=>async function(id){
        const attempt=attempts.get(this);
        if(!attempt?.ids.has(id))return original.call(this,id);
        const manager=LoginManager.getLoginManager();
        const sessions=await manager.listSessions();
        const starting=sessions.find(([sessionId])=>sessionId===id);
        if(!starting)throw Error('Authenticated session disappeared before startup');
        for(const [sessionId,,user,,path] of sessions) {
            // ids contains only session-opened signals from this GDM verifier.
            // GDM cancels the other conversation when it starts the winner.
            if(attempt.ids.has(sessionId) || user!==starting[2])continue;
            const session=manager.getSession(path);
            if(!['wayland','x11'].includes(session.Type))continue;
            if(['active','online'].includes(session.State))return session;
        }
        return null;
    });
    injections.overrideMethod(LoginDialog.prototype,'_startSession',original=>function(service){
        const attempt=attempts.get(this);
        if(attempt) {
            if(attempt.started || service!==attempt.service)return;
            attempt.started=true;
        }
        return original.call(this,service);
    });
    return dialog=>{
        dialog._authPrompt.connectObject('reset',()=>attempts.delete(dialog),dialog);
        if(dialog._greeter) {
            dialog._greeter.disconnectObject(dialog);
            dialog._greeter=null;
            dialog._ensureGreeterProxy();
        }
    };

}
