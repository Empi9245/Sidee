"""Installation confirmation with a TV that only answers explicit app-list requests."""
import json
import os
import tempfile
import time
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from core import client, protocol, webui


NUVIO = {"appId": "nuviodebug", "name": "Nuvio"}
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


if __name__ == "__main__":
    unittest.main()
