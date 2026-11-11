"""eduroam CAT (cat.eduroam.org): the institutions and the official settings of their profiles, as
Windows' geteduroam and the CAT installers use them. Network calls: run them off the UI thread."""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

API = "https://cat.eduroam.org/user/API.php"
# EAP types (IANA) and the non-EAP inner methods of eap-config files.
EAP_NAMES = {13: "tls", 21: "ttls", 25: "peap", 52: "pwd", 43: "fast"}
INNER_EAP = {26: "mschapv2", 6: "gtc", 4: "md5"}
INNER_NONEAP = {1: "pap", 2: "chap", 3: "mschap", 4: "mschapv2"}


def _get(params, timeout=25):
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "fenestra-settings"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _data(raw):
    d = json.loads(raw)
    return d.get("data", d) if isinstance(d, dict) else d


def countries(lang="es"):
    """[(code, name)] of the federations."""
    out = [(c.get("federation"), c.get("display")) for c in _data(_get({"action": "listCountries", "lang": lang}))]
    return sorted((c for c in out if c[0]), key=lambda c: c[1] or "")


def institutions(country, lang="es"):
    """[(idp id, name)] in one country."""
    out = [(str(i.get("idp") or i.get("id")), i.get("display") or i.get("title"))
           for i in _data(_get({"action": "listIdentityProviders", "federation": country, "lang": lang}))]
    return sorted(out, key=lambda i: (i[1] or "").lower())


def profiles(idp, lang="es"):
    return [(str(p.get("profile") or p.get("id")), p.get("display"))
            for p in _data(_get({"action": "listProfiles", "idp": idp, "lang": lang}))]


def _text(el, path):
    v = el.find(path)
    return v.text.strip() if v is not None and v.text else ""


def settings(profile, lang="es"):
    """The profile's first method this PC can use, as the dict of pages/wifi_enterprise.py, plus
    'ca_pem' (the CA certificates) and 'hint' (the realm users type after their name)."""
    raw = _get({"action": "downloadInstaller", "device": "eap-config", "profile": profile, "lang": lang}, timeout=40)
    # no namespaces: drop their declarations and the prefixed attributes (xsi:...)
    root = ET.fromstring(re.sub(rb'\s(xmlns(:\w+)?|\w+:\w+)="[^"]*"', b"", raw))
    for m in root.iter("AuthenticationMethod"):
        method = EAP_NAMES.get(int(_text(m, "EAPMethod/Type") or 0))
        if method is None or method == "fast":
            continue
        out = {"method": method, "phase2": "", "ca": "none", "domain": "", "anonymous": ""}
        inner = m.find("InnerAuthenticationMethod")
        if inner is not None:
            eap = _text(inner, "EAPMethod/Type")
            non = _text(inner, "NonEAPAuthMethod/Type")
            if eap and int(eap) in INNER_EAP:
                out["phase2"] = ("eap-" if method == "ttls" else "") + INNER_EAP[int(eap)]
            elif non and int(non) in INNER_NONEAP:
                out["phase2"] = INNER_NONEAP[int(non)]
            if method in ("peap", "ttls") and not out["phase2"]:
                continue
        cas = [re.sub(r"\s", "", c.text or "") for c in m.iter("CA")]
        if cas:
            pem = "".join("-----BEGIN CERTIFICATE-----\n" + "\n".join(c[i:i + 64] for i in range(0, len(c), 64))
                          + "\n-----END CERTIFICATE-----\n" for c in cas if c)
            out["ca"], out["ca_pem"] = "file", pem
        servers = []
        for s in m.iter("ServerID"):
            name = (s.text or "").strip().lstrip("*.")
            if name and name not in servers:
                servers.append(name)
        out["domain"] = ";".join(servers)
        out["anonymous"] = _text(root, ".//OuterIdentity") or _text(m, ".//OuterIdentity")
        out["hint"] = _text(root, ".//InnerIdentitySuffix")
        return out
    raise ValueError("no usable method")


def save_ca(name, pem):
    """Writes the CA bundle where NetworkManager can read it, returns its path."""
    d = os.path.join(os.path.expanduser("~/.local/share/fenestra/certs"))
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, re.sub(r"[^A-Za-z0-9._-]+", "-", name) + ".pem")
    with open(path, "w") as f:
        f.write(pem)
    return path
