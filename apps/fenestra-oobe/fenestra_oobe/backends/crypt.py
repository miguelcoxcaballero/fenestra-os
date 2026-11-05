"""SHA-512 crypt(3) hashing without the removed ``crypt`` module.

Uses libxcrypt through ctypes (``crypt_gensalt`` + ``crypt``) and falls back
to ``openssl passwd -6`` when libcrypt cannot be loaded.
"""

import ctypes
import ctypes.util
import subprocess

_lib = None


def _libcrypt():
    global _lib
    if _lib is None:
        name = ctypes.util.find_library("crypt") or "libcrypt.so.2"
        try:
            lib = ctypes.CDLL(name)
        except OSError:
            try:
                lib = ctypes.CDLL("libcrypt.so.2")
            except OSError:
                _lib = False
                return None
        lib.crypt.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        lib.crypt.restype = ctypes.c_char_p
        if hasattr(lib, "crypt_gensalt"):
            lib.crypt_gensalt.argtypes = [ctypes.c_char_p, ctypes.c_ulong, ctypes.c_char_p, ctypes.c_int]
            lib.crypt_gensalt.restype = ctypes.c_char_p
        _lib = lib
    return _lib or None


def _crypt(password: str, setting: str) -> str | None:
    lib = _libcrypt()
    if lib is None:
        return None
    out = lib.crypt(password.encode("utf-8"), setting.encode("ascii"))
    if not out or out.startswith(b"*"):
        return None
    return out.decode("ascii")


def hash_password(password: str) -> str:
    """Return a ``$6$`` (SHA-512) crypt hash for ``password``."""
    lib = _libcrypt()
    if lib is not None and hasattr(lib, "crypt_gensalt"):
        salt = lib.crypt_gensalt(b"$6$", 0, None, 0)
        if salt:
            hashed = _crypt(password, salt.decode("ascii"))
            if hashed and hashed.startswith("$6$"):
                return hashed
    # Fallback: OpenSSL (reads the password from stdin so it never hits argv).
    proc = subprocess.run(
        ["openssl", "passwd", "-6", "-stdin"],
        input=password + "\n", capture_output=True, text=True, check=True,
    )
    hashed = proc.stdout.strip()
    if not hashed.startswith("$6$"):
        raise RuntimeError("openssl produced an unexpected hash")
    return hashed


def verify_password(password: str, hashed: str) -> bool:
    result = _crypt(password, hashed)
    if result is None:
        # Fallback verification via openssl using the existing salt.
        parts = hashed.split("$")
        if len(parts) < 4:
            return False
        proc = subprocess.run(
            ["openssl", "passwd", "-6", "-salt", parts[2], "-stdin"],
            input=password + "\n", capture_output=True, text=True,
        )
        result = proc.stdout.strip()
    return result == hashed
