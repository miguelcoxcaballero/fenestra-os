"""Icon pack validator, safe extraction and per-user installation.

The canonical validator lives in tools/fenestra-import-windows-assets; the
OOBE (fenestra_oobe.iconpack) loads it, so both are exercised here.
Installation runs the importer with --no-apply into a temporary
XDG_DATA_HOME: nothing outside the temp dir is touched.
"""

import importlib.machinery
import importlib.util
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile

import gi

gi.require_version("Gtk", "4.0")

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
IMPORTER = os.path.normpath(os.path.join(HERE, "..", "..", "tools", "fenestra-import-windows-assets"))
os.environ.setdefault("FENESTRA_IMPORTER", IMPORTER)

from fenestra_oobe import iconpack  # noqa: E402

MANIFEST = {"format": "fenestra-icon-pack", "version": 1, "id": "test-pack", "name": "Test pack",
            "source": {"os": "Windows 11", "build": "26200.1"}, "contents": ["icons"]}


def load_importer():
    loader = importlib.machinery.SourceFileLoader("fenestra_importer_under_test", IMPORTER)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def make_zip(path, files, manifest=MANIFEST, symlink=None):
    with zipfile.ZipFile(path, "w") as zf:
        if manifest is not None:
            zf.writestr("fenestra-pack.json", json.dumps(manifest) if isinstance(manifest, dict) else manifest)
        for name, data in files.items():
            zf.writestr(name, data)
        if symlink:
            info = zipfile.ZipInfo(symlink[0])
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            zf.writestr(info, symlink[1])
    return path


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mod = load_importer()

    def tearDown(self):
        self.tmp.cleanup()

    def zip(self, files=None, **kw):
        return make_zip(os.path.join(self.tmp.name, "p.zip"), files or {}, **kw)

    def assertRejected(self, path, fragment):
        with self.assertRaises(self.mod.PackError) as cm:
            self.mod.inspect_pack(path)
        self.assertIn(fragment, str(cm.exception))
        # The OOBE wrapper reports the same reason.
        with self.assertRaises(iconpack.PackError):
            iconpack.inspect(path)

    def test_demo_pack_is_valid(self):
        p = iconpack.make_demo_pack(os.path.join(self.tmp.name, "demo.zip"))
        info = iconpack.inspect(p)
        self.assertEqual(info.kind, "fenestra")
        self.assertEqual(info.name, "Demo icon pack")
        labels = [l for l, *_ in iconpack.previews(info)]
        for want in ("Folder", "This PC", "Start", "Search", "Battery"):
            self.assertIn(want, labels)

    def test_path_traversal(self):
        self.assertRejected(self.zip({"icons/../../evil.sh": b"x"}), "path traversal")
        self.assertRejected(self.zip({"../outside.txt": b"x"}), "path traversal")

    def test_absolute_paths(self):
        self.assertRejected(self.zip({"/etc/passwd": b"x"}), "absolute path")
        self.assertRejected(self.zip({"C:/Windows/evil.dll": b"x"}), "absolute path")
        self.assertRejected(self.zip({"\\\\server\\share\\x": b"x"}), "absolute path")

    def test_symlink_rejected(self):
        self.assertRejected(self.zip({}, symlink=("icons/link", "/etc/passwd")), "symbolic link")

    def test_missing_manifest(self):
        self.assertRejected(self.zip({"readme.txt": b"hi"}, manifest=None), "missing fenestra-pack.json")

    def test_wrong_version(self):
        for v in (2, 0, "1", True, None):
            m = dict(MANIFEST, version=v)
            self.assertRejected(self.zip({}, manifest=m), "unsupported pack version")

    def test_wrong_format_and_bad_json(self):
        self.assertRejected(self.zip({}, manifest=dict(MANIFEST, format="other")), "not a Fenestra icon pack")
        self.assertRejected(self.zip({}, manifest="{not json"), "not valid JSON")
        self.assertRejected(self.zip({}, manifest="[1, 2]"), "JSON object")

    def test_bad_id_and_theme_names(self):
        self.assertRejected(self.zip({}, manifest=dict(MANIFEST, id="../x")), '"id"')
        self.assertRejected(self.zip({}, manifest=dict(MANIFEST, icon_theme="../../etc")), '"icon_theme"')

    def test_size_cap(self):
        p = self.zip({"icons/big.bin": b"\0" * 5000})
        with self.assertRaises(self.mod.PackError):
            self.mod.inspect_pack(p, max_bytes=1000)
        with self.assertRaises(self.mod.PackError):
            self.mod.safe_extract(p, os.path.join(self.tmp.name, "out"), max_bytes=1000)

    def test_not_a_zip(self):
        p = os.path.join(self.tmp.name, "x.zip")
        with open(p, "wb") as fh:
            fh.write(b"definitely not a zip")
        self.assertRejected(p, "not a valid zip")

    def test_generic_icon_theme(self):
        p = self.zip({"My-Icons/index.theme": b"[Icon Theme]\nName=My Icons\nDirectories=48x48/apps\n",
                      "My-Icons/48x48/apps/foo.png": b"png"}, manifest=None)
        info = iconpack.inspect(p)
        self.assertEqual(info.kind, "theme")
        self.assertEqual(info.name, "My Icons")
        self.assertEqual(info.prefix, "My-Icons/")

    def test_manifest_inside_top_folder(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("export/fenestra-pack.json", json.dumps(MANIFEST))
        p = os.path.join(self.tmp.name, "nested.zip")
        with open(p, "wb") as fh:
            fh.write(buf.getvalue())
        self.assertEqual(iconpack.inspect(p).prefix, "export/")

    def test_safe_extract_stays_inside(self):
        p = iconpack.make_demo_pack(os.path.join(self.tmp.name, "demo.zip"))
        out = os.path.join(self.tmp.name, "out")
        self.mod.safe_extract(p, out)
        for root, _dirs, files in os.walk(out):
            for f in files:
                self.assertTrue(os.path.realpath(os.path.join(root, f)).startswith(os.path.realpath(out)))


class InstallTests(unittest.TestCase):
    def run_importer(self, data_home, *args):
        env = dict(os.environ, XDG_DATA_HOME=data_home, GSETTINGS_BACKEND="memory")
        return subprocess.run([sys.executable, IMPORTER, "--no-apply", *args], env=env,
                              capture_output=True, text=True, timeout=120)

    def test_install_fenestra_pack(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = iconpack.make_demo_pack(os.path.join(tmp, "demo.zip"))
            data = os.path.join(tmp, "data")
            res = self.run_importer(data, "--pack", p)
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            index = os.path.join(data, "icons", "Fenestra-Demo", "index.theme")
            with open(index) as fh:
                self.assertIn("Inherits=Fenestra", fh.read())
            self.assertTrue(os.path.exists(os.path.join(data, "fenestra", "assets", "folders", "folder-empty.svg")))
            with open(os.path.join(data, "fenestra", "assets", ".imported-pack")) as fh:
                self.assertEqual(json.load(fh)["id"], "fenestra-demo-pack")

    def test_install_generic_theme(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_zip(os.path.join(tmp, "t.zip"),
                         {"Cool/index.theme": b"[Icon Theme]\nName=Cool\nInherits=Adwaita\n",
                          "Cool/48x48/apps/a.png": b"png"}, manifest=None)
            data = os.path.join(tmp, "data")
            res = self.run_importer(data, "--pack", p)
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            with open(os.path.join(data, "icons", "Cool", "index.theme")) as fh:
                self.assertIn("Inherits=Adwaita", fh.read())

    def test_invalid_pack_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = make_zip(os.path.join(tmp, "bad.zip"), {"../x": b"x"})
            res = self.run_importer(os.path.join(tmp, "data"), "--pack", p)
            self.assertEqual(res.returncode, 2)
            self.assertIn("path traversal", res.stdout)
            self.assertFalse(os.path.exists(os.path.join(tmp, "x")))

    def test_inspect_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = iconpack.make_demo_pack(os.path.join(tmp, "demo.zip"))
            res = self.run_importer(os.path.join(tmp, "data"), "--pack", p, "--inspect")
            self.assertEqual(json.loads(res.stdout)["manifest"]["id"], "fenestra-demo-pack")


class BrowserHelpersTests(unittest.TestCase):
    def test_url_normalisation(self):
        from fenestra_oobe.pages.icons import IconBrowserPage as B
        self.assertEqual(B.normalize("example.com/a.zip"), "https://example.com/a.zip")
        self.assertIsNone(B.normalize("file:///etc/passwd"))
        self.assertIsNone(B.normalize("javascript:alert(1)"))
        self.assertIsNone(B.normalize(""))
        self.assertTrue(B.is_direct_zip("https://x.org/dl/pack.ZIP?dl=1"))
        self.assertFalse(B.is_direct_zip("https://drive.example.com/share/abc"))


if __name__ == "__main__":
    unittest.main()
