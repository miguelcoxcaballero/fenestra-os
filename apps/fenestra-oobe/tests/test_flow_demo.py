"""Drive the complete --demo flow programmatically (needs a display).

Run:  python3 -m unittest tests.test_flow_demo
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Never open windows on the real desktop: run against a headless compositor
# socket (default "fenestra-test", override with OOBE_WAYLAND_DISPLAY).
_SOCK = os.environ.get("OOBE_WAYLAND_DISPLAY", "fenestra-test")
_RUNTIME = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
HAVE_DISPLAY = os.path.exists(os.path.join(_RUNTIME, _SOCK))
if HAVE_DISPLAY:
    os.environ["WAYLAND_DISPLAY"] = _SOCK
    os.environ["GDK_BACKEND"] = "wayland"
    os.environ.pop("DISPLAY", None)


@unittest.skipUnless(HAVE_DISPLAY, "needs a headless wayland compositor socket")
class DemoFlowTest(unittest.TestCase):
    def test_full_demo_flow(self):
        from gi.repository import GLib

        from fenestra_oobe import app as app_mod
        from fenestra_oobe import i18n

        i18n.set_language("en")
        args = app_mod.parse_args(["fenestra-oobe", "--demo", "--windowed", "--size", "1280x800"])
        app = app_mod.OobeApp(args)
        visited = []
        acted = set()
        state = {"finale": False}

        def act():
            win = app.window
            if win is None:
                return True
            if win.root.get_visible_child_name() == "finale":
                state["finale"] = True
                return True
            page = win.current_page
            if page is None:
                return True
            pid = page.page_id
            if not visited or visited[-1] != pid:
                visited.append(pid)
            key = (pid, len(visited))
            if key in acted:
                return True
            acted.add(key)
            if pid == "keyboard-second":
                page.on_primary()  # Add layout
            elif pid == "keyboard-pick":
                page.picker.select("us")
                page.on_primary()
            elif pid == "network":
                page.on_link()  # I don't have internet
            elif pid == "network-offline":
                page.on_secondary()  # continue with limited setup
            elif pid == "device-name":
                page.entry.set_text("my pc")
                assert not page.primary_sensitive
                page.entry.set_text("ALEX-LAPTOP")
                win._primary()
            elif pid == "account-name":
                page.entry.set_text("Álex Rivera")
                win._primary()
            elif pid == "account-password":
                page.entry.set_text("s3cret-pass")
                win._primary()
            elif pid == "account-confirm":
                page.entry.set_text("s3cret-pass")
                win._primary()
            elif pid == "account-hint":
                page.entry.set_text("my usual")
                win._primary()
            elif pid in ("applying", "updates"):
                acted.discard(key)  # wait for it to finish
            elif pid == "import":
                page.on_secondary()
            else:
                win._primary()
            return True

        GLib.timeout_add(350, act)
        GLib.timeout_add_seconds(60, lambda: (app.quit(), False)[1])
        app.run(["fenestra-oobe"])

        st = app.window.state
        self.assertEqual(visited[:3], ["region", "keyboard", "keyboard-second"])
        for pid in ("keyboard-pick", "network", "network-offline", "device-name", "account-name",
                    "account-password", "account-confirm", "account-hint", "applying", "privacy",
                    "customize", "import"):
            self.assertIn(pid, visited)
        self.assertNotIn("updates", visited)  # offline: skipped
        self.assertTrue(state["finale"])
        self.assertTrue(app.window.finished)
        self.assertEqual(st.hostname, "ALEX-LAPTOP")
        self.assertEqual(st.username, "alex")
        self.assertEqual(st.full_name, "Álex Rivera")
        self.assertEqual(st.hint, "my usual")
        self.assertEqual(st.password, "")  # forgotten after account creation
        self.assertEqual(len(st.layouts), 2)
        self.assertIn("location", st.privacy)


if __name__ == "__main__":
    unittest.main()
