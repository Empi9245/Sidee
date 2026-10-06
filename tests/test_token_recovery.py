"""Offline regression tests with isolated files and simulated MQTT connections."""
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import client, protocol, webui
import sidee


class TestTokenRecovery(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="sidee-token-test-")
        self.tmp = temp.name
        self.addCleanup(temp.cleanup)
        patches = ExitStack()
        self.addCleanup(patches.close)
        patches.enter_context(patch.object(client, "_cert_dir", return_value=self.tmp))
        patches.enter_context(patch.object(client, "_certificate_path",
                                           return_value=os.path.join(self.tmp, "certs.bin.k")))
        patches.enter_context(patch.object(client.Session, "path",
                                           return_value=os.path.join(self.tmp, "session.json")))

    def session(self, **overrides):
        fields = dict(host="192.168.1.10", device_uuid="aa:bb:cc:dd:ee:ff",
                      access_token="A", refresh_token="R", access_time=int(time.time()),
                      access_days=2, refresh_time=int(time.time()), refresh_days=30,
                      expires_at=time.time() + 2 * 86400)
        fields.update(overrides)
        return client.Session(**fields)

    def tokens(self):
        return json.dumps({"accesstoken": "new-access", "refreshtoken": "new-refresh",
                           "accesstoken_duration_day": 2,
                           "refreshtoken_duration_day": 30})

    def connection(self, rc=0, raw=None):
        mqtt = Mock()
        mqtt.topics = protocol.tv_topics("test-client")
        mqtt.client_id = "test-client"
        mqtt.username = "test-user"
        mqtt.messages = []
        if isinstance(rc, Exception):
            mqtt.start.side_effect = rc
        else:
            mqtt.start.return_value = rc
        mqtt.wait_for.return_value = raw
        return mqtt

    def mqtt_patches(self, connections):
        stack = ExitStack()
        stack.enter_context(patch.object(client, "MqttSession", side_effect=connections))
        stack.enter_context(patch.object(client, "tv_timestamp", return_value=123))
        stack.enter_context(patch.object(client.time, "sleep"))
        stack.enter_context(patch.object(client, "log"))
        return stack

    def test_expired_access_renews_without_pairing(self):
        self.session(expires_at=1).save()
        renewal = self.connection(raw=self.tokens())
        operation = self.connection()
        with self.mqtt_patches([renewal, operation]):
            result, ready = client.run_with_session(lambda *a: "installed")
        self.assertEqual(result, "installed")
        self.assertEqual(ready.access_token, "new-access")
        self.assertEqual(client.Session.load().refresh_token, "new-refresh")
        renewal.stop.assert_called_once()
        operation.stop.assert_called_once()

    def test_failed_connection_closes_before_refresh_and_retry(self):
        for rc in (4, 5, 3, None, OSError("offline")):
            with self.subTest(rc=rc):
                self.session().save()
                failed = self.connection(rc=rc)
                renewal = self.connection(raw=self.tokens())
                operation = self.connection()
                events = []
                failed.stop.side_effect = lambda: events.append("closed")
                renewal.start.side_effect = lambda: events.append("refresh") or 0
                with self.mqtt_patches([failed, renewal, operation]):
                    result, _ = client.run_with_session(lambda *a: "ok")
                self.assertEqual(result, "ok")
                self.assertEqual(events, ["closed", "refresh"])
                for mqtt in (failed, renewal, operation):
                    mqtt.stop.assert_called_once()

    def test_failed_retry_is_bounded_and_closed(self):
        self.session().save()
        failed = self.connection(rc=5)
        renewal = self.connection(raw=self.tokens())
        retry = self.connection(rc=5)
        with self.mqtt_patches([failed, renewal, retry]):
            with self.assertRaises(client.AuthError):
                client.run_with_session(lambda *a: self.fail("operation must not run"))
        for mqtt in (failed, renewal, retry):
            mqtt.stop.assert_called_once()

    def test_operation_exception_closes_without_repeating_install(self):
        self.session().save()
        mqtt = self.connection()
        operation = Mock(side_effect=RuntimeError("install failed"))
        with self.mqtt_patches([mqtt]):
            with self.assertRaises(RuntimeError):
                client.run_with_session(operation)
        mqtt.stop.assert_called_once()
        operation.assert_called_once()

    def test_refresh_failure_keeps_tokens_and_closes_connection(self):
        for rc, raw, exception in ((5, None, client.AuthError),
                                   (3, None, ConnectionError),
                                   (0, None, client.AuthError),
                                   (0, "not-json", client.AuthError),
                                   (OSError("offline"), None, OSError)):
            with self.subTest(rc=rc, raw=raw):
                s = self.session()
                s.save()
                mqtt = self.connection(rc=rc, raw=raw)
                with self.mqtt_patches([mqtt]):
                    with self.assertRaises(exception):
                        client.refresh(s)
                mqtt.stop.assert_called_once()
                self.assertEqual(client.Session.load().access_token, "A")

    def test_refresh_uses_latest_saved_token(self):
        stale = self.session()
        self.session(refresh_token="latest").save()
        mqtt = self.connection(raw=self.tokens())
        with self.mqtt_patches([mqtt]), patch.object(client, "MqttSession",
                                                     return_value=mqtt) as factory:
            client.refresh(stale)
        self.assertEqual(factory.call_args.kwargs["token"], "latest")
        mqtt.publish.assert_called_once_with(
            mqtt.topics["platform"] + "data/gettoken",
            protocol.token_request_payload("latest"))

    def test_invalid_token_payload_does_not_partially_update(self):
        s = self.session()
        before = s.__dict__.copy()
        for tok in ({"accesstoken": "B", "accesstoken_duration_day": "bad"},
                    {"accesstoken": ""},
                    {"accesstoken": "B", "refreshtoken": None},
                    {"accesstoken": "B", "accesstoken_duration_day": -1}):
            with self.subTest(tok=tok):
                with self.assertRaises((ValueError, TypeError)):
                    s.set_tokens(tok)
                self.assertEqual(s.__dict__, before)

    def test_set_tokens_uses_local_clock_and_save_keeps_expiry(self):
        s = self.session()
        with patch.object(client.time, "time", return_value=1000000):
            s.set_tokens({"accesstoken": "B", "accesstoken_time": 1,
                          "accesstoken_duration_day": 2})
        self.assertEqual(s.expires_at, 1000000 + 2 * 86400)
        s.save()
        client._register_pair_failure(True)
        self.assertEqual(client.Session.load().expires_at, s.expires_at)

    def test_corrupt_json_shapes_and_types_are_handled(self):
        for value in ([], None, 1, "session", {"host": "x"},
                      self.session(expires_at="bad").__dict__,
                      self.session(device_uuid=None).__dict__):
            with self.subTest(value=value):
                with open(client.Session.path(), "w") as f:
                    json.dump(value, f)
                self.assertIsNone(client.Session().load_or_none())

    def test_failed_atomic_save_preserves_previous_session(self):
        s = self.session()
        s.save()
        s.access_token = "B"
        with patch.object(client.os, "replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                s.save()
        self.assertEqual(client.Session.load().access_token, "A")
        self.assertEqual(os.listdir(self.tmp), ["session.json"])

    def test_dashboard_reports_expired_access_to_block_installation(self):
        self.session(expires_at=1).save()
        self.assertFalse(client.has_client_certificate())
        status = webui._status()
        self.assertTrue(status["paired"])
        self.assertEqual(status["state"], "expired")
        self.assertEqual(status["expires_at"], 1)
        self.assertIn("expired", status["message"].lower())

    def test_installer_starts_without_a_certificate_file(self):
        self.assertFalse(client.has_client_certificate())
        with patch.object(sys, "argv", ["sidee.py"]), \
                patch.object(webui, "serve") as serve:
            self.assertEqual(sidee.main(), 0)
        serve.assert_called_once_with()

    def test_dashboard_requests_pairing_without_a_certificate_file(self):
        self.assertFalse(client.has_client_certificate())
        status = webui._status()
        self.assertFalse(status["paired"])
        self.assertEqual(status["state"], "needs_pairing")

    def test_dashboard_accepts_valid_pairing_without_a_certificate_file(self):
        self.session().save()
        self.assertFalse(client.has_client_certificate())
        status = webui._status()
        self.assertTrue(status["paired"])
        self.assertEqual(status["state"], "ok")

    def test_pair_start_failure_closes_connection(self):
        mqtt = self.connection(rc=OSError("offline"))
        with self.mqtt_patches([mqtt]):
            with self.assertRaises(OSError):
                client.pair("192.168.1.10", lambda: "1234")
        mqtt.stop.assert_called_once()

    def test_pair_and_refresh_wait_for_running_operation(self):
        self.session().save()
        for name in ("pair", "refresh"):
            with self.subTest(name=name):
                entered = threading.Event()
                connected = threading.Event()
                errors = []
                mqtt = self.connection(raw=self.tokens())
                if name == "pair":
                    mqtt.wait_for.side_effect = ["pin", '{"result": 1}', self.tokens()]
                mqtt.start.side_effect = lambda: connected.set() or 0

                def worker():
                    entered.set()
                    try:
                        if name == "pair":
                            client.pair("192.168.1.10", lambda: "1234")
                        else:
                            client.refresh(self.session())
                    except Exception as e:
                        errors.append(e)

                with self.mqtt_patches([mqtt]):
                    with client._OP_LOCK:
                        thread = threading.Thread(target=worker, daemon=True)
                        thread.start()
                        self.assertTrue(entered.wait(1))
                        blocked = not connected.wait(0.05)
                    thread.join(2)
                self.assertTrue(blocked)
                self.assertFalse(thread.is_alive())
                self.assertEqual(errors, [])
                mqtt.stop.assert_called_once()


class TestMqttCleanup(unittest.TestCase):
    def test_auth_rejection_wakes_start_waiter(self):
        session = object.__new__(client.MqttSession)
        session.connected = threading.Event()
        session._on_connect(None, None, None, 5)
        self.assertTrue(session.connected.is_set())
        self.assertEqual(session.connect_rc, 5)

    def test_stop_always_stops_network_loop(self):
        session = object.__new__(client.MqttSession)
        session.client = Mock()
        session.client.disconnect.side_effect = RuntimeError("disconnect failed")
        with self.assertRaises(RuntimeError):
            session.stop()
        session.client.loop_stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
