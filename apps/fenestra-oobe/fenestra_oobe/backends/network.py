"""Network state and Wi-Fi through NetworkManager (nmcli)."""

import subprocess
import time
from dataclasses import dataclass

from . import log


@dataclass
class WifiNetwork:
    ssid: str
    signal: int
    secure: bool
    in_use: bool = False


def _split_terse(line: str) -> list[str]:
    """Split an ``nmcli -t`` line honouring ``\\:`` escapes."""
    fields, cur, esc = [], [], False
    for ch in line:
        if esc:
            cur.append(ch)
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == ":":
            fields.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    fields.append("".join(cur))
    return fields


def _nmcli(*args, input_text=None, timeout=30) -> str:
    res = subprocess.run(["nmcli", *args], input=input_text, capture_output=True, text=True,
                         timeout=timeout)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or f"nmcli exited with {res.returncode}")
    return res.stdout


DEMO_NETWORKS = [
    WifiNetwork("Casa-5G", 92, True),
    WifiNetwork("Fenestra Guest", 74, False),
    WifiNetwork("MOVISTAR_8A21", 61, True),
    WifiNetwork("Vodafone-C0FFEE", 45, True),
    WifiNetwork("DIRECT-LaserJet", 30, True),
]


class NetworkBackend:
    def __init__(self, demo: bool):
        self.demo = demo
        self._demo_connected: str | None = None

    # -- state ---------------------------------------------------------
    def connectivity(self, check: bool = False) -> str:
        """Return 'full', 'limited', 'portal', 'none' or 'unknown'."""
        if self.demo:
            return "full" if self._demo_connected else "none"
        try:
            if check:
                return _nmcli("networking", "connectivity", "check", timeout=20).strip() or "unknown"
            return _nmcli("-t", "-f", "CONNECTIVITY", "general").strip() or "unknown"
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            log.info("connectivity check failed: %s", exc)
            return "unknown"

    def wired_connected(self) -> bool:
        if self.demo:
            return False
        try:
            out = _nmcli("-t", "-f", "TYPE,STATE", "device")
        except (OSError, RuntimeError, subprocess.SubprocessError):
            return False
        for line in out.splitlines():
            f = _split_terse(line)
            if len(f) >= 2 and f[0] == "ethernet" and f[1].startswith("connected"):
                return True
        return False

    def has_wifi(self) -> bool:
        if self.demo:
            return True
        try:
            out = _nmcli("-t", "-f", "TYPE", "device")
        except (OSError, RuntimeError, subprocess.SubprocessError):
            return False
        return any(l.strip() == "wifi" for l in out.splitlines())

    # -- wifi ----------------------------------------------------------
    def scan(self) -> list[WifiNetwork]:
        if self.demo:
            time.sleep(0.4)
            return [WifiNetwork(n.ssid, n.signal, n.secure, n.ssid == self._demo_connected)
                    for n in DEMO_NETWORKS]
        out = _nmcli("-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list",
                     "--rescan", "auto")
        best: dict[str, WifiNetwork] = {}
        for line in out.splitlines():
            f = _split_terse(line)
            if len(f) < 4 or not f[1]:
                continue
            try:
                signal = int(f[2])
            except ValueError:
                signal = 0
            net = WifiNetwork(f[1], signal, f[3] not in ("", "--"), f[0].strip() == "*")
            prev = best.get(net.ssid)
            if prev is None or net.signal > prev.signal or net.in_use:
                net.in_use = net.in_use or (prev.in_use if prev else False)
                best[net.ssid] = net
        return sorted(best.values(), key=lambda n: (not n.in_use, -n.signal))

    def connect(self, ssid: str, password: str | None) -> None:
        """Connect to a Wi-Fi network; raises RuntimeError with a message."""
        if self.demo:
            time.sleep(1.5)
            if password is not None and len(password) < 8:
                raise RuntimeError("The network security key isn't correct.")
            self._demo_connected = ssid
            return
        args = ["--wait", "45"]
        if password:
            # --ask reads the secret from stdin so it never shows up in argv.
            args.append("--ask")
        args += ["device", "wifi", "connect", ssid]
        _nmcli(*args, input_text=(password + "\n") if password else None, timeout=60)
