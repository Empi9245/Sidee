"""Browser PIN handoff tests using the real pairing logic and simulated TV."""
import io
import json
import os
import tempfile
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from core import client, protocol, webui
from core.pairing import PairingFlow


class TvConnection:
    def __init__(self, host, device_uuid, timestamp, token=None):
        self.host = host
        self.client_id = "test-client"
        self.username = "test-user"
        self.topics = protocol.tv_topics(self.client_id)
        self.messages = []
        self.published = []
        self.subscriptions = []
        self.stopped = False
        self.pin_reply = '{"result": 1}'
        self.token_reply = json.dumps({"accesstoken": "test-access",
                                       "refreshtoken": "test-refresh"})

    def start(self):
        return 0

    def subscribe(self, topics):
        self.subscriptions.extend(topics)

    def deliver(self, topic, payload):
        if topic in self.subscriptions and payload is not None:
            self.messages.append((topic, payload))

    def publish(self, topic, payload=""):
        self.published.append((topic, json.loads(payload) if payload else ""))
        if topic.endswith("actions/vidaa_app_connect"):
            self.deliver(self.topics["mobile"] + "ui_service/data/authentication", "")
        elif topic.endswith("actions/authenticationcode"):
            self.deliver(self.topics["mobile"] + "ui_service/data/authenticationcode",
                         self.pin_reply)
        elif topic.endswith("data/gettoken"):
            # Measured VIDAA behavior: accepting the PIN alone issues no token.
            self.deliver(self.topics["token_reply"], self.token_reply)

    def wait_for(self, suffix, timeout, since=0):
        for topic, payload in self.messages[since:]:
            if topic.endswith(suffix):
                return payload
        return None

    def stop(self):
        self.stopped = True


class TestBrowserPairing(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = os.path.join(temp.name, "session.json")
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(client, "_cert_dir", return_value=temp.name))
        stack.enter_context(patch.object(client.Session, "path", return_value=self.path))
        stack.enter_context(patch.object(client, "tv_timestamp", return_value=123))
        stack.enter_context(patch.object(client.time, "sleep"))
        self.connections = []

        def connect(*args, **kwargs):
            connection = TvConnection(*args, **kwargs)
            self.connections.append(connection)
            return connection

        stack.enter_context(patch.object(client, "MqttSession", side_effect=connect))
        self.flow = PairingFlow()
        self.addCleanup(self.finish_pending)

    def finish_pending(self):
        if self.flow.attempt:
            self.flow.attempt.cancel()
            self.assertTrue(self.flow.attempt.done.wait(2))

    def test_request_keeps_connection_open_until_browser_submits_pin(self):
        response = self.flow.start("192.168.1.10")
        self.assertTrue(response["ok"])
        self.assertGreater(response["expires_in"], 0)
        self.assertLessEqual(response["expires_in"], 60)
        connection = self.connections[0]
        self.assertFalse(connection.stopped)
        self.assertIn(connection.topics["token_reply"], connection.subscriptions)
        self.assertEqual(len(connection.published), 1)
        self.assertTrue(connection.published[0][0].endswith("actions/vidaa_app_connect"))
        self.assertFalse(os.path.exists(self.path))

        result = self.flow.confirm(response["pairing_id"], "0012")
        self.assertTrue(result["ok"])
        self.assertEqual(len(self.connections), 1)
        self.assertTrue(connection.stopped)
        self.assertEqual(connection.published[1][1], {"authNum": 12})
        self.assertEqual(connection.published[2],
                         (connection.topics["platform"] + "data/gettoken",
                          {"refreshtoken": ""}))
        self.assertEqual(connection.published[3],
                         (connection.topics["ui"] + "actions/authenticationcodeclose", ""))
        self.assertEqual(client.Session.load().host, "192.168.1.10")
        with open(self.path, encoding="utf-8") as saved:
            self.assertNotIn("0012", saved.read())
        self.assertEqual(self.flow.attempt.pin, "")

    def test_invalid_or_stale_pin_does_not_get_sent(self):
        response = self.flow.start("192.168.1.10")
        for pairing_id, pin in ((response["pairing_id"], "123"), ("old-request", "1234")):
            with self.assertRaises(ValueError):
                self.flow.confirm(pairing_id, pin)
        self.assertEqual(len(self.connections[0].published), 1)
        self.assertTrue(self.flow.confirm(response["pairing_id"], "1234")["ok"])

    def test_requesting_new_code_cancels_old_connection_without_bad_uuid_count(self):
        client.Session(host="192.168.1.10", device_uuid="old-device",
                       access_token="A", refresh_token="R").save()
        first = self.flow.start("192.168.1.10")
        second = self.flow.start("192.168.1.10")
        self.assertNotEqual(first["pairing_id"], second["pairing_id"])
        self.assertTrue(self.connections[0].stopped)
        self.assertEqual(client.Session.load().pair_failures, 0)
        with self.assertRaises(ValueError):
            self.flow.confirm(first["pairing_id"], "1234")
        self.assertTrue(self.flow.confirm(second["pairing_id"], "1234")["ok"])

    def test_duplicate_confirmation_does_not_publish_twice(self):
        response = self.flow.start("192.168.1.10")
        self.flow.confirm(response["pairing_id"], "1234")
        self.assertTrue(self.flow.confirm(response["pairing_id"], "1234")["ok"])
        self.assertEqual(len(self.connections[0].published), 4)

    def test_tv_rejects_pin_without_requesting_tokens_or_saving_session(self):
        response = self.flow.start("192.168.1.10")
        connection = self.connections[0]
        connection.pin_reply = '{"result": 100, "info": "illegal authNum!!"}'
        result = self.flow.confirm(response["pairing_id"], "1234")
        self.assertFalse(result["ok"])
        self.assertIn("PIN expired or incorrect", result["error"])
        self.assertEqual(len(connection.published), 2)
        self.assertTrue(connection.stopped)
        self.assertFalse(os.path.exists(self.path))

    def test_missing_pin_reply_does_not_use_an_old_acceptance(self):
        response = self.flow.start("192.168.1.10")
        connection = self.connections[0]
        connection.deliver(connection.topics["mobile"] +
                           "ui_service/data/authenticationcode", '{"result": 1}')
        connection.pin_reply = None
        result = self.flow.confirm(response["pairing_id"], "1234")
        self.assertFalse(result["ok"])
        self.assertIn("did not confirm the PIN", result["error"])
        self.assertEqual(len(connection.published), 2)
        self.assertTrue(connection.stopped)
        self.assertFalse(os.path.exists(self.path))

    def test_malformed_pin_reply_does_not_request_tokens(self):
        for reply in ("not-json", "[]", "null", "{}"):
            with self.subTest(reply=reply):
                response = self.flow.start("192.168.1.10")
                connection = self.connections[-1]
                connection.pin_reply = reply
                result = self.flow.confirm(response["pairing_id"], "1234")
                self.assertFalse(result["ok"])
                self.assertIn("invalid PIN response", result["error"])
                self.assertEqual(len(connection.published), 2)
                self.assertTrue(connection.stopped)
                self.assertFalse(os.path.exists(self.path))

    def test_missing_token_after_accepted_pin_has_a_separate_error(self):
        response = self.flow.start("192.168.1.10")
        connection = self.connections[0]
        connection.token_reply = None
        result = self.flow.confirm(response["pairing_id"], "1234")
        self.assertFalse(result["ok"])
        self.assertIn("PIN accepted", result["error"])
        self.assertEqual(len(connection.published), 4)
        self.assertTrue(connection.stopped)
        self.assertFalse(os.path.exists(self.path))

    def test_expired_code_cannot_be_submitted(self):
        response = self.flow.start("192.168.1.10")
        self.flow.attempt.deadline = 0
        with self.assertRaisesRegex(ValueError, "expired"):
            self.flow.confirm(response["pairing_id"], "1234")
        self.assertEqual(len(self.connections[0].published), 1)

    def test_failed_request_closes_connection_and_reports_error(self):
        with patch.object(TvConnection, "start", return_value=5):
            response = self.flow.start("192.168.1.10")
        self.assertFalse(response["ok"])
        self.assertIn("refused", response["error"])
        self.assertTrue(self.connections[0].stopped)

    def post(self, path, data, authorized=True):
        handler = object.__new__(webui.Handler)
        handler.path = path + ("?key=" + webui.ACCESS_KEY if authorized else "")
        body = json.dumps(data).encode()
        handler.headers = {"Content-Length": str(len(body))}
        handler.rfile = io.BytesIO(body)
        handler._json = Mock()
        with patch.object(webui, "PAIRING", self.flow):
            handler.do_POST()
        return handler._json.call_args.args

    def test_dashboard_routes_request_and_confirm_the_same_connection(self):
        response = self.post("/api/pair/start", {"host": "192.168.1.10"})[0]
        self.assertTrue(response["ok"])
        result = self.post("/api/pair", {"pairing_id": response["pairing_id"], "pin": "1234"})[0]
        self.assertTrue(result["ok"])
        self.assertEqual(len(self.connections), 1)

    def test_unauthorized_or_invalid_request_does_not_contact_tv(self):
        response, status = self.post("/api/pair/start", {"host": "192.168.1.10"}, False)
        self.assertEqual(status, 403)
        self.assertFalse(self.post("/api/pair/start", {"host": "999.168.1.10"})[0]["ok"])
        self.assertEqual(self.connections, [])


class TestMqttCertificate(unittest.TestCase):
    def test_tv_connection_loads_client_certificate_and_removes_plaintext_files(self):
        context = Mock()
        paths = []

        def inspect(cert_path, key_path):
            paths.extend((cert_path, key_path))
            for path, expected in ((cert_path, b"certificate"), (key_path, b"private key")):
                with open(path, "rb") as f:
                    self.assertEqual(f.read(), expected)

        context.load_cert_chain.side_effect = inspect
        with patch.object(client, "_load_client_pem_key", return_value=(b"certificate", b"private key")), \
                patch.object(client.ssl, "SSLContext", return_value=context), \
                patch.object(client.mqtt, "Client") as mqtt:
            client.MqttSession("192.168.1.10", "aa:bb:cc:dd:ee:ff", 123)
        mqtt.return_value.tls_set_context.assert_called_once_with(context)
        self.assertEqual(len(paths), 2)
        self.assertTrue(all(not os.path.exists(path) for path in paths))


if __name__ == "__main__":
    unittest.main()
