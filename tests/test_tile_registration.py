"""Installation confirmation with a TV that only answers explicit app-list requests."""
import json
import argparse
import io
import os
import tempfile
import time
import unittest
from contextlib import ExitStack, redirect_stdout
from unittest.mock import patch

import sidee
from core import client, protocol, webui


NUVIO_URL = "https://nuviotvsmart.vercel.app/vidaa.html"
NUVIO = {"appId": "nuviodebug", "name": "Nuvio", "url": NUVIO_URL}
OLD_NUVIO = {**NUVIO, "url": "https://nuviotvsmart.vercel.app/"}
EXISTING = {"appId": "existing", "name": "Existing app"}


class TileConnection:
    def __init__(self):
        self.topics = protocol.tv_topics("test-client")
        self.messages = []
        self.subscriptions = []
        self.published = []
        self.replies = [[EXISTING, NUVIO]]
        self.push_on_install = None
        self.requests = 0
        self.stopped = False

    def start(self):
        return 0

    def subscribe(self, topics):
        self.subscriptions.extend(topics)

    def deliver(self, apps):
        if apps is not None and self.topics["applist_reply"] in self.subscriptions:
            payload = apps if isinstance(apps, str) else json.dumps(apps)
            self.messages.append((self.topics["applist_reply"], payload))

    def publish(self, topic, payload=""):
        self.published.append((topic, payload))
        if topic.endswith("actions/uievent"):
            self.deliver(self.push_on_install)
        elif topic.endswith("actions/applist"):
            self.deliver(self.replies[min(self.requests, len(self.replies) - 1)])
            self.requests += 1

    def wait_for(self, suffix, timeout, since=0):
        for topic, payload in self.messages[since:]:
            if topic.endswith(suffix):
                return payload
        return None

    def stop(self):
        self.stopped = True


class TestTileRegistration(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(client, "_cert_dir", return_value=directory.name))
        stack.enter_context(patch.object(client.Session, "path",
                                         return_value=os.path.join(directory.name, "session.json")))
        stack.enter_context(patch.object(client, "tv_timestamp", return_value=123))
        stack.enter_context(patch.object(client.time, "sleep"))
        self.connection = TileConnection()
        stack.enter_context(patch.object(client, "MqttSession", return_value=self.connection))
        client.Session(host="192.168.1.10", device_uuid="aa:bb:cc:dd:ee:ff",
                       access_token="A", refresh_token="R",
                       expires_at=time.time() + 2 * 86400).save()
        self.handler = object.__new__(webui.Handler)

    def install(self):
        result = self.handler._install({"app": "nuvio"})
        self.assertTrue(self.connection.stopped)
        installs = [t for t, _ in self.connection.published if t.endswith("actions/uievent")]
        self.assertEqual(len(installs), 1)
        return result

    def test_installed_app_confirmed_by_explicit_request_without_automatic_push(self):
        result = self.install()
        self.assertTrue(result["ok"])
        self.assertEqual(self.connection.requests, 1)
        self.assertEqual(self.connection.published[-1],
                         (self.connection.topics["ui"] + "actions/applist", "0"))

    def test_old_push_does_not_hide_successful_registration(self):
        self.connection.push_on_install = [EXISTING]
        self.assertTrue(self.install()["ok"])
        self.assertEqual(self.connection.requests, 1)

    def test_delayed_registration_rechecks_without_sending_install_twice(self):
        self.connection.replies = [[EXISTING], [EXISTING, NUVIO]]
        self.assertTrue(self.install()["ok"])
        self.assertEqual(self.connection.requests, 2)

    def test_missing_app_list_is_unconfirmed_instead_of_failed(self):
        self.connection.replies = [None]
        result = self.install()
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "unconfirmed")
        self.assertIsNone(result["error"])
        self.assertIn("Check Home", result["message"])
        self.assertEqual(self.connection.requests, 2)

    def test_app_absent_from_both_lists_is_not_reported_as_installed(self):
        self.connection.replies = [[EXISTING]]
        result = self.install()
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "unconfirmed")
        self.assertEqual(self.connection.requests, 2)

    def test_invalid_list_is_rechecked(self):
        self.connection.replies = ["not-json", [NUVIO]]
        self.assertTrue(self.install()["ok"])
        self.assertEqual(self.connection.requests, 2)

    def test_existing_id_with_old_address_is_unconfirmed(self):
        self.connection.replies = [[OLD_NUVIO]]
        result = self.install()
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "unconfirmed")
        self.assertIn("current address", result["message"])
        self.assertEqual(self.connection.requests, 2)

    def test_delayed_address_update_is_confirmed_without_reinstall(self):
        self.connection.replies = [[OLD_NUVIO], [NUVIO]]
        self.assertTrue(self.install()["ok"])
        self.assertEqual(self.connection.requests, 2)

    def test_existing_id_without_address_is_unconfirmed(self):
        self.connection.replies = [[{"appId": "nuviodebug", "name": "Nuvio"}]]
        result = self.install()
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "unconfirmed")
        self.assertEqual(self.connection.requests, 2)

    def test_install_requests_the_vidaa_entry(self):
        self.install()
        payload = next(json.loads(p) for t, p in self.connection.published
                       if t.endswith("actions/uievent"))
        self.assertEqual(payload["app_info"]["URL"], NUVIO_URL)


class TestTileAddressConfirmation(unittest.TestCase):
    def test_supported_address_fields(self):
        for field in ("url", "appUrl", "URL"):
            with self.subTest(field=field):
                self.assertTrue(client.tile_matches_request(
                    {"appId": "NUVIODEBUG", field: NUVIO_URL}, "nuviodebug", NUVIO_URL))

    def test_conflicting_addresses_are_not_confirmed(self):
        self.assertFalse(client.tile_matches_request(
            {**NUVIO, "appUrl": OLD_NUVIO["url"]}, "nuviodebug", NUVIO_URL))

    def test_wrong_identity_or_missing_address_is_not_confirmed(self):
        for tile in (None, "invalid", {"appId": "other", "url": NUVIO_URL},
                     {"appId": "nuviodebug", "url": None},
                     {"appId": "nuviodebug", "url": ""}):
            with self.subTest(tile=tile):
                self.assertFalse(client.tile_matches_request(tile, "nuviodebug", NUVIO_URL))

    def test_cli_uses_the_same_address_confirmation(self):
        args = argparse.Namespace(cmd="install", preset="nuvio")
        for tile, expected in ((NUVIO, 0), (OLD_NUVIO, 1),
                               ({"appId": "nuviodebug"}, 1)):
            with self.subTest(tile=tile), patch.object(client.Session, "load"), \
                 patch.object(client, "add_tile", return_value=[tile]), redirect_stdout(io.StringIO()):
                self.assertEqual(sidee.cmd_cli(args), expected)


if __name__ == "__main__":
    unittest.main()
