import os, socket, subprocess, sys, time
# tests/plymouth/run.py DIR TAG [WxH]: boot DIR/vmlinuz + DIR/initrd.img (QEMU, UEFI) and save
# DIR/out/TAG-<screen>.ppm for boot, upgrade0/42, updates87, reboot, shutdown. Uses KVM when present.
S, tag = sys.argv[1], sys.argv[2]
W, H = (sys.argv[3] if len(sys.argv) > 3 else '1920x1080').split('x')
os.makedirs(f'{S}/out', exist_ok=True)
import shutil
shutil.copy('/usr/share/OVMF/OVMF_VARS_4M.fd', f'{S}/vars.fd')
ACCEL = 'kvm' if os.access('/dev/kvm', os.W_OK) else 'tcg'
mon = f'{S}/mon.sock'
try: os.remove(mon)
except OSError: pass
q = subprocess.Popen(['qemu-system-x86_64', '-m', '2048', '-smp', '2', '-machine', 'q35', '-accel', ACCEL,
    '-drive', 'if=pflash,format=raw,readonly=on,file=/usr/share/OVMF/OVMF_CODE_4M.fd',
    '-drive', f'if=pflash,format=raw,file={S}/vars.fd',
    '-kernel', f'{S}/vmlinuz', '-initrd', f'{S}/initrd.img',
    '-append', 'quiet splash rhgb console=ttyS0 loglevel=3 rd.udev.log_level=3 plymouth.ignore-serial-consoles rd.shell=0 root=/dev/nonexistent',
    '-vga', 'none', '-device', f'VGA,edid=on,xres={W},yres={H}', '-display', 'none', '-serial', 'stdio', '-monitor', f'unix:{mon},server,nowait', '-no-reboot'],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
def screendump(name):
    s = socket.socket(socket.AF_UNIX); s.connect(mon); s.recv(4096)
    s.sendall(f'screendump {S}/out/{tag}-{name}.ppm\n'.encode()); time.sleep(1.5); s.close()
start = time.time()
for line in q.stdout:
    if 'FENSHOT' in line:
        n = line.split('FENSHOT', 1)[1].strip()
        print(f'{time.time()-start:6.0f}s {n}', flush=True)
        if n == 'done': break
        time.sleep(3)
        screendump(n)
    if time.time() - start > 1500: print('timeout'); break
time.sleep(2); q.kill()
