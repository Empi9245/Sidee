"""Renaming Sidee must preserve the user's saved TV pairing."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core import client


class TestSideeStorage(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.home = Path(folder.name)
        home = patch.object(client.os.path, "expanduser", return_value=str(self.home))
        home.start()
        self.addCleanup(home.stop)

    def save_fixture(self, folder, device_uuid):
        target = self.home / folder / "session.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        state = client.Session(host="192.168.1.10", device_uuid=device_uuid,
                               access_token="test-access", refresh_token="test-refresh")
        target.write_text(json.dumps(state.__dict__), encoding="utf-8")
        return target

    def test_fresh_install_uses_sidee_profile(self):
        self.assertEqual(Path(client._cert_dir()), self.home / ".sidee")
        self.assertTrue((self.home / ".sidee").is_dir())

    def test_existing_pairing_is_loaded_with_the_same_tokens_and_uuid(self):
        original = self.save_fixture(".vidaa-tile", "aa:bb:cc:dd:ee:ff")
        before = original.read_bytes()
        loaded = client.Session.load()
        self.assertEqual(loaded.access_token, "test-access")
        self.assertEqual(loaded.refresh_token, "test-refresh")
        self.assertEqual(client._stored_uuid(), "aa:bb:cc:dd:ee:ff")
        self.assertEqual(original.read_bytes(), before)

    def test_newer_sidee_pairing_takes_precedence_over_legacy_data(self):
        self.save_fixture(".vidaa-tile", "old-device")
        self.save_fixture(".sidee", "current-device")
        self.assertEqual(client.Session.load().device_uuid, "current-device")


if __name__ == "__main__":
    unittest.main()
