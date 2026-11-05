import GUdev from 'gi://GUdev';

// A known offline adapter wins over UPower's briefly stale CHARGING state.
export function externalPower(devices) {
    const supplies = devices.filter(d => d.type !== 'Battery' && (d.online === '0' || d.online === '1'));
    return supplies.length ? supplies.some(d => d.online === '1') : null;
}

export function watchExternalPower(changed) {
    const client = new GUdev.Client({subsystems: ['power_supply']});
    let online = null;
    function refresh() {
        const next = externalPower(client.query_by_subsystem('power_supply').map(d => ({
            type: d.get_sysfs_attr('type'), online: d.get_sysfs_attr('online'),
        })));
        if (next !== online) { online = next; changed(); }
    }
    const id = client.connect('uevent', refresh);
    refresh();
    return {get online() { return online; }, destroy() { client.disconnect(id); }};
}
