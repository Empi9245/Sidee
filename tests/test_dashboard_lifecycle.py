"""Real local HTTP lifecycle and launcher regression checks; no TV access."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from core import webui
import macos_launcher
import sidee
from tools.smoke_test import request, smoke


class TestDashboardLifecycle(unittest.TestCase):
    def test_startup_does_not_wait_for_hostname_dns(self):
        with patch("socket.getfqdn", side_effect=AssertionError("reverse DNS used")):
            dashboard = webui.Dashboard(port=0)
            self.assertEqual(dashboard.server.server_name, "localhost")
            dashboard.server.server_close()

    def test_headless_real_process_startup_and_shutdown(self):
        import sys
        root = Path(__file__).resolve().parent.parent
        smoke([sys.executable, str(root / "sidee.py")])

    def test_gui_server_has_no_remote_shutdown_endpoint(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict(os.environ, {"SIDEE_STATE_DIR": directory}):
            dashboard = webui.Dashboard(port=0)
            try:
                dashboard.start()
                status, _, body = request(dashboard.port, "/api/shutdown?key=" +
                                         webui.ACCESS_KEY, "POST", "{}")
                self.assertEqual(status, 404)
                self.assertFalse(dashboard.stop_event.is_set())
                self.assertEqual(json.loads(body), {"error": "not found"})
            finally:
                dashboard.close()
            self.assertFalse((Path(directory) / "runtime" / "dashboard.json").exists())

    def test_failed_state_write_closes_bound_socket(self):
        dashboard = webui.Dashboard(port=0)
        port = dashboard.port
        with patch.object(webui, "_remember_dashboard", side_effect=OSError("read only")), \
                patch.object(webui, "_forget_dashboard"):
            with self.assertRaises(OSError):
                dashboard.start()
        import socket
        with socket.socket() as probe:
            self.assertNotEqual(probe.connect_ex(("127.0.0.1", port)), 0)

    def test_headless_cli_never_opens_browser(self):
        with patch("sys.argv", ["sidee.py", "--headless", "--port", "0"]), \
                patch.object(webui, "serve") as serve:
            self.assertEqual(sidee.main(), 0)
        serve.assert_called_once_with(open_browser=False, port=0, headless=True)

    def test_ci_environment_disables_gui_and_browser(self):
        with patch("sys.argv", ["Sidee"]), \
                patch.dict(os.environ, {"SIDEE_CI": "1"}), \
                patch.object(macos_launcher, "run_gui") as gui, \
                patch.object(webui, "serve") as serve:
            self.assertEqual(macos_launcher.main(), 0)
        gui.assert_not_called()
        serve.assert_called_once_with(open_browser=False, port=None, headless=True)

    def test_headless_failure_never_opens_an_error_dialog(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch("sys.argv", ["Sidee", "--self-test"]), \
                patch.dict(os.environ, {"SIDEE_STATE_DIR": directory}), \
                patch.object(sidee, "main", side_effect=OSError("startup fixture")), \
                patch.object(macos_launcher, "run_gui") as gui, \
                patch.object(macos_launcher, "_fallback_error") as dialog:
            self.assertEqual(macos_launcher.main(), 1)
            self.assertIn("startup fixture", (Path(directory) / "logs" / "sidee.log").read_text())
        gui.assert_not_called()
        dialog.assert_not_called()

    def test_pending_pairing_wakes_on_application_close(self):
        from core.pairing import PairingFlow
        flow = PairingFlow()
        attempt = flow.attempt = Mock()
        flow.close()
        attempt.cancel.assert_called_once_with()
        attempt.done.wait.assert_called_once_with(timeout=1)


if __name__ == "__main__":
    unittest.main()
