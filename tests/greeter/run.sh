#!/bin/bash
# One headless GNOME Shell run with Fenestra's login / lock extensions, inside the
# fenestra-greeterlab container (see bench.sh, which runs every scenario):
#   EXTSET=system   the laptop's system copies (extras/fedora-upgrade/system-extensions)
#   EXTSET=repo     the repo's fenestra-login / fenestra-spotlight / fenestra-lock-clock
#   EXTSET=broken   the versions before the GNOME 51 fix (/broken, from git): must FAIL
#   SCENARIO=ok     Spotlight background present
#   SCENARIO=nobg   background metadata missing: the extension throws, the fail-safe must
#                   bring back the standard login
#   MODE=gdm        greeter (gnome-shell --mode=gdm, as the greeter user)
#   MODE=user       user session as "alex": locks the screen and checks the unlock dialog
# Prints QA_* lines; QA_RESULT PASS|FAIL is the verdict.
set -u
EXTSET=${EXTSET:-system} SC=${SCENARIO:-ok} MODE=${MODE:-gdm}
SRC=/src
case "$EXTSET" in
    system) LOGIN=single-user-gdm@local SPOT=windows-spotlight@local LOCK=
            DIRS="$SRC/extras/fedora-upgrade/system-extensions/single-user-gdm@local $SRC/extras/fedora-upgrade/system-extensions/windows-spotlight@local" ;;
    repo|broken)
            LOGIN=fenestra-login@fenestra-os.github.io SPOT=fenestra-spotlight@fenestra-os.github.io
            LOCK=fenestra-lock-clock@fenestra-os.github.io
            base=$SRC/desktop/extensions; [ "$EXTSET" = broken ] && base=/broken
            DIRS="$base/$LOGIN $base/$SPOT $base/$LOCK" ;;
    *) echo "unknown EXTSET $EXTSET"; exit 2 ;;
esac
for d in $DIRS; do cp -a "$d" /usr/share/gnome-shell/extensions/; done
cp -a "$SRC/tests/greeter/gdmqa@local" /usr/share/gnome-shell/extensions/
chmod -R a+rX /usr/share/gnome-shell/extensions
# Hello frames (the spotlight extensions read /usr/share/fenestra/assets/hello/frames.json).
install -d /usr/share/fenestra/assets
rm -rf /usr/share/fenestra/assets/hello; cp -a "$SRC/assets/generated/hello" /usr/share/fenestra/assets/hello
# Spotlight picture + metadata for both naming schemes.
H=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
for d in windows-spotlight fenestra-spotlight; do
    install -d /var/lib/$d/images
    python3 -c "from PIL import Image; Image.new('RGB',(1920,1080),(30,90,140)).save('/var/lib/$d/images/$H.jpg')"
    rm -f /var/lib/$d/current.json
    [ "$SC" = ok ] && echo "{\"image\": \"/var/lib/$d/images/$H.jpg\"}" > /var/lib/$d/current.json
done
# Accounts: one real user (shown by AccountsService) and a system greeter user.
id alex >/dev/null 2>&1 || useradd -m -u 1000 -c "Alex Morgan" alex
echo 'alex:fenestra-test' | chpasswd 2>/dev/null
id gdmtest >/dev/null 2>&1 || useradd -r -m -d /home/gdmtest gdmtest
mkdir -p /run/dbus /run/systemd/seats; rm -f /run/dbus/system_bus_socket /run/dbus/pid
dbus-daemon --system --fork; sleep 0.5
python3 "$SRC/tests/greeter/fakelogind.py" & sleep 1
/usr/libexec/accounts-daemon & sleep 2
mkdir -p /out; chmod 777 /out
if [ "$MODE" = gdm ]; then U=gdmtest; MODEARG=--mode=gdm; CLASS=greeter; EXTS="'$LOGIN', '$SPOT'"
else U=alex; MODEARG=; CLASS=user; EXTS="'$SPOT'${LOCK:+, '$LOCK'}"; fi
EXTS=${EXTS_OVERRIDE:-$EXTS}
uid=$(id -u $U); install -d -m700 -o $U /run/user/$uid
runuser -u $U -- env XDG_RUNTIME_DIR=/run/user/$uid HOME=$(getent passwd $U | cut -d: -f6) XDG_SESSION_ID=c1 \
    XDG_SESSION_CLASS=$CLASS QA_LOGIN_EXT="$LOGIN" QA_TESTED="$(echo "$EXTS" | tr -d "',")" dbus-run-session -- bash -c "
dconf write /org/gnome/shell/enabled-extensions \"[$EXTS, 'gdmqa@local']\"
dconf write /org/gnome/shell/disable-user-extensions false
timeout 75 gnome-shell --headless --virtual-monitor=1920x1080 --wayland $MODEARG --wayland-display=gdmqa" > /out/shell.log 2>&1
grep -aE 'QA_|JS ERROR|Fenestra login|TypeError|SyntaxError|ReferenceError|set_file' /out/shell.log | cut -c1-400
