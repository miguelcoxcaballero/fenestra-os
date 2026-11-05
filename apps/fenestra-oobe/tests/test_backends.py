"""Unit checks for validation, username derivation and password hashing."""

import os
import sys
import unittest

import gi

gi.require_version("Gtk", "4.0")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fenestra_oobe.backends import accounts, crypt, hostname, locale  # noqa: E402
from fenestra_oobe.backends.network import _split_terse  # noqa: E402


class HostnameTests(unittest.TestCase):
    def test_valid(self):
        for name in ("DESKTOP-1", "pc", "Fenestra-Lap01", "a" * 15):
            self.assertIsNone(hostname.validate_hostname(name), name)

    def test_invalid(self):
        cases = {
            "": "empty",
            "my pc": "spaces",
            "a" * 16: "too-long",
            "pc_1": "invalid-chars",
            "pc.local": "invalid-chars",
            "ñandú": "invalid-chars",
            "12345": "only-numbers",
            "-pc": "hyphen-edge",
            "pc-": "hyphen-edge",
        }
        for name, err in cases.items():
            self.assertEqual(hostname.validate_hostname(name), err, name)

    def test_suggestion_is_valid(self):
        for _ in range(20):
            self.assertIsNone(hostname.validate_hostname(hostname.suggest_hostname()))


class UsernameTests(unittest.TestCase):
    def test_derivation(self):
        none_taken = lambda n: False  # noqa: E731
        self.assertEqual(accounts.derive_username("Miguel Cox Caballero", none_taken), "miguel")
        self.assertEqual(accounts.derive_username("  José Ñúñez ", none_taken), "jose")
        self.assertEqual(accounts.derive_username("ALEX", none_taken), "alex")
        self.assertEqual(accounts.derive_username("Ægir Strauß", none_taken), "aegir")
        self.assertEqual(accounts.derive_username("2pac", none_taken), "user2pac")
        self.assertIsNone(accounts.derive_username("!!!", none_taken))
        self.assertIsNone(accounts.derive_username("北京", none_taken))

    def test_no_spaces_lowercase(self):
        name = accounts.derive_username("Ana María de la Peña", lambda n: False)
        self.assertEqual(name, name.lower())
        self.assertNotIn(" ", name)
        self.assertIsNone(accounts.validate_username(name, lambda n: False))

    def test_collision(self):
        taken = {"miguel", "miguelcaballero"}
        self.assertEqual(accounts.derive_username("Miguel Cox Caballero", taken.__contains__), "mcaballero")
        taken = {"alex"}
        self.assertEqual(accounts.derive_username("Alex", taken.__contains__), "alex2")
        taken = {"alex", "alex2", "alex3"}
        self.assertEqual(accounts.derive_username("Alex", taken.__contains__), "alex4")

    def test_reserved_and_system_users(self):
        self.assertEqual(accounts.derive_username("Root", lambda n: False), "root2")
        # "root" exists on every system: real lookup must report it taken.
        self.assertTrue(accounts.system_name_taken("root"))
        self.assertEqual(accounts.validate_username("root"), "reserved")
        self.assertEqual(accounts.validate_username("Bad Name", lambda n: False), "invalid-chars")
        self.assertEqual(accounts.validate_username("x" * 33, lambda n: False), "too-long")


class CryptTests(unittest.TestCase):
    def test_sha512_hash(self):
        h = crypt.hash_password("correct horse battery staple")
        self.assertTrue(h.startswith("$6$"), h)
        parts = h.split("$")
        self.assertEqual(len(parts), 4)
        self.assertEqual(len(parts[3]), 86)
        self.assertTrue(crypt.verify_password("correct horse battery staple", h))
        self.assertFalse(crypt.verify_password("wrong", h))

    def test_salts_differ(self):
        self.assertNotEqual(crypt.hash_password("x"), crypt.hash_password("x"))

    def test_unicode_password(self):
        h = crypt.hash_password("contraseña-ñ€")
        self.assertTrue(crypt.verify_password("contraseña-ñ€", h))

    def test_matches_openssl(self):
        import shutil
        import subprocess
        if not shutil.which("openssl"):
            self.skipTest("openssl missing")
        h = crypt.hash_password("abc123")
        salt = h.split("$")[2]
        out = subprocess.run(["openssl", "passwd", "-6", "-salt", salt, "abc123"],
                             capture_output=True, text=True).stdout.strip()
        self.assertEqual(out, h)


class LocaleTests(unittest.TestCase):
    def test_countries_and_layouts(self):
        countries = locale.load_countries("en")
        codes = {c.code for c in countries}
        self.assertIn("ES", codes)
        self.assertIn("US", codes)
        es = {c.code: c.label for c in locale.load_countries("es")}
        self.assertEqual(es["ES"], "España")
        layouts = locale.load_layouts("en")
        self.assertIn("us", {l.id for l in layouts})
        self.assertIn("es", {l.id for l in layouts})

    def test_defaults_for_country(self):
        self.assertEqual(locale.timezone_for_country("ES", current="America/New_York"), "Europe/Madrid")
        self.assertEqual(locale.timezone_for_country("ES", current="Atlantic/Canary"), "Atlantic/Canary")
        self.assertEqual(locale.timezone_for_country("US", current="UTC"), "America/New_York")
        self.assertEqual(locale.keyboard_for_country("MX"), ("latam", ""))
        locs = {"en_GB.UTF-8", "es_ES.UTF-8", "es_MX.UTF-8", "an_ES.UTF-8"}
        self.assertEqual(locale.formats_for_country("ES", "en", locs), "es_ES.UTF-8")
        self.assertEqual(locale.formats_for_country("GB", "en", locs), "en_GB.UTF-8")
        self.assertEqual(locale.guess_country("en_GB.UTF-8", "Europe/Madrid"), "ES")
        self.assertEqual(locale.guess_country("en_GB.UTF-8", "UTC"), "GB")


class NmcliParsingTests(unittest.TestCase):
    def test_escaped_colons(self):
        self.assertEqual(_split_terse(r"*:My\:Net:80:WPA2"), ["*", "My:Net", "80", "WPA2"])
        self.assertEqual(_split_terse(r" :Back\\slash:5:"), [" ", "Back\\slash", "5", ""])


if __name__ == "__main__":
    unittest.main()


class TranslationTests(unittest.TestCase):
    def test_every_ui_string_has_spanish(self):
        import ast
        import glob
        from fenestra_oobe.translations.es import MESSAGES
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        missing = []
        for f in glob.glob(os.path.join(root, "fenestra_oobe", "**", "*.py"), recursive=True):
            with open(f, encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "_" and node.args
                        and isinstance(node.args[0], ast.Constant)):
                    if node.args[0].value not in MESSAGES:
                        missing.append(node.args[0].value)
        from fenestra_oobe.pages.account import HOSTNAME_ERRORS
        from fenestra_oobe.iconpack import PREVIEW_RULES, THEME_RULES
        from fenestra_oobe.pages.personal import INTERESTS
        extra = list(HOSTNAME_ERRORS.values()) + [t for i in INTERESTS for t in i[2:4]]
        extra += [r[0] for r in PREVIEW_RULES + THEME_RULES]
        missing += [s for s in extra if s not in MESSAGES]
        self.assertEqual(missing, [])

    def test_no_forbidden_brand_words(self):
        import glob
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        from fenestra_oobe.translations.es import MESSAGES
        # "Windows" may only appear where the user's own Windows installation is
        # meant (icon import step); never as Fenestra's own branding.
        allowed = ("windows partition", "windows pc", "windows installation", "partición de windows",
                   "pc con windows", "instalación de windows")
        for text in list(MESSAGES) + list(MESSAGES.values()):
            low = text.lower()
            self.assertNotIn("microsoft", low)
            if "windows" in low:
                self.assertTrue(any(a in low for a in allowed), text)
        for f in glob.glob(os.path.join(root, "data", "**", "*.svg"), recursive=True):
            with open(f, encoding="utf-8") as fh:
                low = fh.read().lower()
            self.assertNotIn("windows", low)
            self.assertNotIn("microsoft", low)
