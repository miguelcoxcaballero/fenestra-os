#!/bin/bash
# tests/lockscreen/ctl.sh: drives the greeter-gl.sh container.
#   sync               copy shells/org.fenestra.desktop from the work tree again
#   start [args]       kscreenlocker_greet --testing (log: OUT/greet.log), with the stand-ins of
#                      plasma-nm, plasma5support, keyboardlayout and mpris (mock-qml; MOCK= to drop); stop
#   shot NAME          KWin ScreenShot2, device px -> OUT/NAME.png
#   key CODE... | type TEXT | click X Y | move X Y     input (logical px)
#   face success|fail|wait, finger success|fail|wait   what the PAM stand-ins answer next
#   sh CMD             anything inside
set -u
C=${CONTAINER:-fenestra-lockbench}
x() { podman exec $C bash -c '. /tmp/env; '"$1"; }
case "$1" in
sync) x "rm -rf /usr/share/plasma/shells/org.fenestra.desktop; cp -r /src/shells/org.fenestra.desktop /usr/share/plasma/shells/" ;;
start) shift; x "rm -f /out/greet.log; (QML_IMPORT_PATH=\${MOCK:-/src/tests/lockscreen/mock-qml} QT_FORCE_STDERR_LOGGING=1 QT_LOGGING_RULES=\"qml.debug=true;js.debug=true\" /usr/libexec/kscreenlocker_greet --testing $* > /out/greet.log 2>&1; echo \"EXIT \$?\" >> /out/greet.log) &" ;;
stop) x "pkill -f '^/usr/libexec/kscreenlocker_greet'; sleep 0.5; true" ;;
shot) x "python3 /src/tests/window-frames/shot.py /out/$2.png >/dev/null" ;;
key|type|click|move|down|up) op=$1; shift; podman exec $C bash -c '. /tmp/env; fakeinput "$@"' _ $op "$@" ;;
face|finger) x "echo $2 > /tmp/$1" ;;
sh) shift; x "$*" ;;
esac
