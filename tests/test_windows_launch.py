"""New-user distribution and dashboard reopening regression checks."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

from core import client, webui
from tools.build_windows_release import build


class TestWindowsDownload(unittest.TestCase):
    def test_release_includes_launcher_and_connection_bundle_without_local_state(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = build(Path(directory) / "download.zip")
            with zipfile.ZipFile(archive) as downloaded:
                files = downloaded.namelist()
                for name in ("start-windows.bat", "start-windows.ps1", "sidee.py",
                             "core/tv-client.bundle", "core/dashboard.html",
                             "core/phone.py", "core/_qrcodegen.py"):
                    self.assertIn("Sidee/" + name, files)
                self.assertFalse(any(part in filestring for filestring in files
                                     for part in ("session.json", "dashboard.json", ".sidee/",
                                                  ".runtime/", ".venv/", ".git/")))

    def test_fresh_download_can_load_tls_identity_without_user_certificate(self):
        source = Path(client.__file__).with_name("tv-client.bundle")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "core").mkdir()
            (root / "user").mkdir()
            shutil.copyfile(source, root / "core" / "tv-client.bundle")
            with patch.object(client, "__file__", str(root / "core" / "client.py")), \
                    patch.object(client, "_cert_dir", return_value=str(root / "user")), \
                    patch.object(client.mqtt, "Client"):
                connection = client.MqttSession("192.168.1.10", "test-device", 123)
                connection.client.tls_set_context.assert_called_once()
                self.assertFalse((root / "user" / "certs.bin.k").exists())


class TestReopenDashboard(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = os.path.join(temp.name, "dashboard.json")
        patcher = patch.object(webui, "_dashboard_state_path", return_value=self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def remember(self):
        webui._remember_dashboard(8787)

    def test_second_launch_opens_authenticated_existing_dashboard(self):
        self.remember()
        connection = Mock()
        connection.getresponse.return_value.status = 200
        connection.getresponse.return_value.getheader.return_value = "2"
        with patch.object(webui.http.client, "HTTPConnection", return_value=connection), \
                patch.object(webui.webbrowser, "open") as opened:
            self.assertTrue(webui._reopen_dashboard(True))
            opened.assert_called_once_with(f"http://127.0.0.1:8787/?key={webui.ACCESS_KEY}")
        connection.close.assert_called_once()

    def test_stale_or_unrelated_server_does_not_reopen(self):
        self.remember()
        for status, header in ((403, "2"), (200, None), (200, "1")):
            with self.subTest(status=status, header=header):
                connection = Mock()
                connection.getresponse.return_value.status = status
                connection.getresponse.return_value.getheader.return_value = header
                with patch.object(webui.http.client, "HTTPConnection", return_value=connection), \
                        patch.object(webui.webbrowser, "open") as opened:
                    self.assertFalse(webui._reopen_dashboard(True))
                    opened.assert_not_called()
        with patch.object(webui.http.client, "HTTPConnection", side_effect=OSError("offline")):
            self.assertFalse(webui._reopen_dashboard(True))

    def test_cleanup_only_removes_own_dashboard_record(self):
        self.remember()
        webui._forget_dashboard()
        self.assertFalse(os.path.exists(self.path))
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"pid": -1, "key": "other-instance"}, f)
        webui._forget_dashboard()
        self.assertTrue(os.path.exists(self.path))

    def test_invalid_state_is_ignored(self):
        for state in (None, [], {}, {"port": True, "key": "x"},
                      {"port": 99999, "key": "x"}, {"port": 8787, "key": ""}):
            with self.subTest(state=state):
                with open(self.path, "w", encoding="utf-8") as f:
                    json.dump(state, f)
                self.assertFalse(webui._reopen_dashboard(True))


if __name__ == "__main__":
    unittest.main()
