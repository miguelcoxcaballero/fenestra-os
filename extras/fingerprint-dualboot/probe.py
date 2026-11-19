#!/usr/bin/python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""probe.py PHASE: talks to the fingerprint reader through libfprint directly (root, fprintd stopped).
  list      open, list the templates stored on the sensor, close
  stored    the prints fprintd keeps in /var/lib/fprint (what Linux believes is enrolled)
  identify  open, wait up to 15 s for a finger, say which template the sensor matched
  adopt USER  use the fingerprints Windows Hello keeps on the sensor for USER: each touch is
            identified among the sensor's templates and written to fprintd's storage under the
            next free finger, nothing is enrolled (Windows deletes the templates it did not make)
  stress    what the lock screen does all day, in one process as fprintd: six times open, start
            reading, cancel after 1.2 s without a finger, close; then open and list. Every round
            must end "cancelled" and the last list must work (prints STRESS PASS / FAIL)
Everything goes to stdout/stderr; doctor.sh collects it with libfprint's debug output."""
import glob
import sys
import threading

import gi
gi.require_version("FPrint", "2.0")
from gi.repository import FPrint, Gio, GLib


def describe(p, origin):
    data = None
    try:
        data = p.get_property("fpi-data")
    except Exception as e:  # noqa: BLE001
        data = f"<{e}>"
    date = p.get_enroll_date()
    print(f"PRINT origin={origin} finger={p.get_finger().value_nick} user={p.get_username()!r} "
          f"description={p.get_description()!r} date={date.get_year() if date else None}-"
          f"{date.get_month() if date else ''}-{date.get_day() if date else ''} device_stored={p.get_device_stored()} "
          f"driver={p.get_driver()} device_id={p.get_device_id()} data={data.print_(True) if hasattr(data, 'print_') else data}",
          flush=True)


def stored():
    out = []
    for path in sorted(glob.glob(STORE + "/*/*/*/*")):
        try:
            with open(path, "rb") as f:
                p = FPrint.Print.deserialize(f.read())
            print(f"FILE {path}", flush=True)
            describe(p, "fprintd")
            out.append(p)
        except Exception as e:  # noqa: BLE001
            print(f"FILE {path} unreadable: {e}", flush=True)
    return out


STORE = __import__("os").environ.get("FENESTRA_FPRINT_DIR", "/var/lib/fprint")   # tests: another folder
CONTEXT = None   # must outlive the device: a collected context takes libusb down with it


def device():
    global CONTEXT
    CONTEXT = FPrint.Context()
    devs = CONTEXT.get_devices()
    if not devs:
        print("NO DEVICE", flush=True)
        sys.exit(3)
    d = devs[0]
    print(f"DEVICE name={d.get_name()!r} driver={d.get_driver()} id={d.get_device_id()} features={d.get_features()}", flush=True)
    return d


def stress():
    d = device()
    ok = True
    gallery = None
    for i in range(6):
        d.open_sync()
        if gallery is None:
            gallery = d.list_prints_sync()
        cancel = Gio.Cancellable()
        threading.Timer(1.2, cancel.cancel).start()
        try:
            d.identify_sync(gallery, cancel, None, None)
            print(f"ROUND {i}: identify returned without a finger?", flush=True)
            ok = False
        except GLib.Error as e:
            cancelled = e.matches(Gio.io_error_quark(), Gio.IOErrorEnum.CANCELLED)
            print(f"ROUND {i}: {'cancelled' if cancelled else 'ERROR ' + e.message}", flush=True)
            ok = ok and cancelled
        d.close_sync()
    d.open_sync()
    n = len(d.list_prints_sync())
    d.close_sync()
    print(f"FINAL list: {n} templates", flush=True)
    print("STRESS PASS" if ok and n == len(gallery) else "STRESS FAIL", flush=True)
    return ok


FINGERS = ["RIGHT_INDEX", "RIGHT_MIDDLE", "LEFT_INDEX", "LEFT_MIDDLE", "RIGHT_THUMB", "LEFT_THUMB",
           "RIGHT_RING", "LEFT_RING", "RIGHT_LITTLE", "LEFT_LITTLE"]


def adopt(user):
    import os
    d = device()
    d.open_sync()
    try:
        on_sensor = d.list_prints_sync()
        known = stored()
        known_data = [str(k.get_property("fpi-data")) for k in known]
        free = [p for p in on_sensor if str(p.get_property("fpi-data")) not in known_data]
        print(f"ADOPT sensor templates {len(on_sensor)}, already in fprintd {len(on_sensor) - len(free)}, candidates {len(free)}", flush=True)
        if not free:
            print("ADOPT NONE", flush=True)
            return 6 if on_sensor else 4      # 6: every print on the sensor is already in use here
        used = {k.get_finger().value_nick for k in known if k.get_username() == user}
        adopted = 0
        while free:
            say(">>> PON UN DEDO REGISTRADO EN WINDOWS HELLO EN EL LECTOR (15 s) <<<" if adopted == 0 else
                ">>> OTRO DEDO DE WINDOWS HELLO, O ESPERA 15 s PARA TERMINAR <<<")
            cancel = Gio.Cancellable()
            threading.Timer(15, cancel.cancel).start()
            try:
                match, _seen = d.identify_sync(free, cancel, None, None)
            except GLib.Error as e:
                print(f"ADOPT identify ended: {e.message}", flush=True)
                break
            if match is None:
                say("Ese dedo no está registrado en Windows Hello en este lector.")
                print("ADOPT no match", flush=True)
                continue
            finger = next((f for f in FINGERS if getattr(FPrint.Finger, f).value_nick not in used), None)
            if finger is None:
                break
            match.set_username(user)
            match.set_finger(getattr(FPrint.Finger, finger))
            match.set_description("Windows Hello")
            match.set_property("device-stored", True)     # as fprintd's own enrolments on this sensor
            data = match.serialize()
            folder = f"{STORE}/{user}/{d.get_driver()}/{d.get_device_id()}"
            os.makedirs(folder, mode=0o700, exist_ok=True)
            path = f"{folder}/{int(getattr(FPrint.Finger, finger))}"
            with open(path + ".tmp", "wb") as f:
                f.write(bytes(data))
            os.chmod(path + ".tmp", 0o600)
            os.replace(path + ".tmp", path)
            used.add(getattr(FPrint.Finger, finger).value_nick)
            free = [p for p in free if str(p.get_property("fpi-data")) != str(match.get_property("fpi-data"))]
            adopted += 1
            say(f"Huella adoptada ({adopted}).")
            print(f"ADOPT wrote {path} as {finger}", flush=True)
        print(f"ADOPT DONE {adopted}", flush=True)
        return 0 if adopted else 5
    finally:
        d.close_sync()


def say(text):
    try:
        with open("/dev/tty", "w") as t:
            t.write(text + "\n")
    except OSError:
        print(text, flush=True)


def main():
    phase = sys.argv[1]
    if phase == "adopt":
        sys.exit(adopt(sys.argv[2]))
    if phase == "stored":
        stored()
        return
    if phase == "stress":
        sys.exit(0 if stress() else 1)
    d = device()
    print("OPEN...", flush=True)
    d.open_sync()
    print("OPEN ok", flush=True)
    try:
        prints = d.list_prints_sync()
        print(f"LIST ok: {len(prints)} templates on the sensor", flush=True)
        for p in prints:
            describe(p, "sensor")
        if phase == "identify":
            gallery = list(prints)
            known = stored()
            cancel = Gio.Cancellable()
            threading.Timer(15, cancel.cancel).start()
            print("IDENTIFY: waiting for a finger (15 s)...", flush=True)
            try:
                match, seen = d.identify_sync(gallery + known, cancel, None, None)
                print(f"IDENTIFY result: match={'yes' if match else 'no'}", flush=True)
                if match:
                    describe(match, "matched")
                    print("MATCHED is in fprintd's storage: "
                          + str(any(k.equal(match) for k in known)), flush=True)
            except GLib.Error as e:
                print(f"IDENTIFY error: {e.message} (domain {e.domain}, code {e.code})", flush=True)
    finally:
        print("CLOSE...", flush=True)
        d.close_sync()
        print("CLOSE ok", flush=True)


if __name__ == "__main__":
    try:
        main()
    except GLib.Error as e:
        print(f"ERROR: {e.message} (domain {e.domain}, code {e.code})", flush=True)
        sys.exit(1)
