"""VIDAA authentication compatibility using a simulated, PIN-gated TV."""
import io
import json
import os
import ssl
import tempfile
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from core import client, protocol, webui
from core.pairing import PairingFlow
from test_browser_pairing import TvConnection


class TestAuthenticationCompatibility(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = os.path.join(directory.name, "session.json")
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(client.Session, "path", return_value=self.path))
        stack.enter_context(patch.object(client, "tv_timestamp", return_value=123))
        stack.enter_context(patch.object(client, "fetch_descriptor", return_value=None))
        stack.enter_context(patch.object(client.time, "sleep"))
        stack.enter_context(patch.object(client, "log"))
        self.connections = []
        self.accepted_profile = "static"
        self.token_reply = None
        self.pin_reply = '{"result": 1}'
        self.apps_reply = "[]"
        self.failure = 5
        self.legacy_pin = True
        self.throttle_on_rejection = False
        self.broker_throttled = False

        def connect(host, device_uuid, timestamp, token=None, **options):
            profile = options.get("auth_profile", "modern")
            connection = TvConnection(host, device_uuid, timestamp, token)
            cid, username, password = protocol.session_credentials(
                device_uuid, timestamp, token, auth_profile=profile)
            connection.client_id = options.get("client_id") or cid
            connection.username = options.get("username") or username
            connection.topics = protocol.tv_topics(connection.client_id)
            connection.password = password
            connection.device_uuid = device_uuid
            connection.profile = profile
            connection.token_reply = self.token_reply
            connection.pin_reply = self.pin_reply

            def start():
                if isinstance(self.failure, Exception):
                    raise self.failure
                if self.broker_throttled:
                    return 5
                rc = 0 if profile == self.accepted_profile else self.failure
                if rc in (4, 5) and self.throttle_on_rejection:
                    self.broker_throttled = True
                return rc

            original_publish = connection.publish

            def publish(topic, payload=""):
                if (profile == "static" and self.legacy_pin
                        and topic.endswith("actions/vidaa_app_connect")):
                    connection.published.append((topic, json.loads(payload)))
                    return
                original_publish(topic, payload)
                if topic.endswith("actions/gettvstate") and self.legacy_pin:
                    connection.deliver(
                        connection.topics["mobile"] + "ui_service/data/authentication", "")
                if topic.endswith("actions/applist"):
                    connection.deliver(connection.topics["applist_reply"], self.apps_reply)

            connection.start = start
            connection.publish = publish
            self.connections.append(connection)
            return connection

        self.factory = stack.enter_context(
            patch.object(client, "MqttSession", side_effect=connect))

    def pair(self):
        return client.pair("192.168.1.10", lambda: "0012", timeout=20)

    def test_static_pairing_survives_reload_and_runs_without_token_refresh(self):
        session = self.pair()
        self.assertEqual([c.profile for c in self.connections], ["static"])
        self.assertTrue(all(c.stopped for c in self.connections))
        self.assertTrue(session.tokenless)
        self.assertEqual(session.expires_at, 0)
        self.assertTrue(client.Session.load().tokenless)
        self.assertEqual(webui._status()["state"], "ok")
        with open(self.path, encoding="utf-8") as saved:
            contents = saved.read()
            self.assertNotIn("0012", contents)
            self.assertNotIn("multimqttservice", contents)
        with patch.object(client, "refresh", side_effect=AssertionError("no refresh")):
            result, ready = client.run_with_session(lambda sess, topics: sess.client_id)
        self.assertEqual(result, session.client_id)
        self.assertTrue(ready.tokenless)
        reconnect = self.connections[-1]
        self.assertEqual(reconnect.profile, "static")
        self.assertEqual(reconnect.username, session.username)
        self.assertEqual(reconnect.password, "multimqttservice")
        self.assertTrue(reconnect.stopped)

    def test_browser_pin_handoff_works_after_static_fallback(self):
        flow = PairingFlow()
        self.addCleanup(flow.close)
        request = flow.start("192.168.1.10")
        self.assertTrue(request["ok"])
        self.assertFalse(self.connections[-1].stopped)
        self.assertTrue(flow.confirm(request["pairing_id"], "0012")["ok"])
        self.assertTrue(client.Session.load().tokenless)

    def test_static_profile_supports_both_pin_request_actions(self):
        for legacy in (True, False):
            with self.subTest(legacy=legacy):
                self.legacy_pin = legacy
                session = self.pair()
                commands = [t.rsplit("/", 1)[-1] for t, _ in self.connections[-1].published]
                self.assertEqual(commands[0], "gettvstate")
                self.assertEqual("vidaa_app_connect" in commands, not legacy)
                self.assertTrue(session.tokenless)

    def test_documented_profiles_match_independent_reference_vectors(self):
        expected = {
            "modern": ("his$6239759786158610217", "07722575957530939102C3C7D25AD28D"),
            "middle": ("his$6239759786158610217", "35755B74F89434975D810C3708695B47"),
            "remotenow": ("his$1791229505", "35755B74F89434975D810C3708695B47"),
            "static": ("hisenseservice", "multimqttservice"),
        }
        # Generated independently with hisense_vidaa's published crypto helper.
        for profile, credentials in expected.items():
            with self.subTest(profile=profile):
                cid, username, password = protocol.session_credentials(
                    "16:1e:d5:d4:61:0d", 1791229505, auth_profile=profile)
                self.assertEqual(cid, "16:1e:d5:d4:61:0d$his$28E305_vidaacommon_001")
                self.assertEqual((username, password), credentials)

    def test_static_profile_can_also_issue_tokens(self):
        self.token_reply = '{"accesstoken": "A", "refreshtoken": "R"}'
        session = self.pair()
        self.assertFalse(session.tokenless)
        self.assertEqual(session.auth_profile, "static")
        self.assertEqual(session.access_token, "A")
        self.assertFalse(any(t.endswith("actions/applist")
                             for t, _ in self.connections[-1].published))
        client.run_with_session(lambda *args: None)
        self.assertEqual(self.connections[-1].password, "A")

    def test_alternative_dynamic_profile_is_saved_and_used_for_refresh(self):
        for profile in ("middle", "remotenow"):
            with self.subTest(profile=profile):
                # New TV: start with the default profile each time.
                self.accepted_profile = profile
                self.token_reply = '{"accesstoken": "A", "refreshtoken": "R"}'
                with patch.object(client.Session, "load_or_none", return_value=None):
                    session = self.pair()
                self.assertEqual(session.auth_profile, profile)
                self.assertEqual(client.Session.load().auth_profile, profile)
                with patch.object(client, "tv_timestamp", return_value=456):
                    client.refresh(session)
                    client.run_with_session(lambda *args: None)
                reconnect = self.connections[-1]
                self.assertEqual(reconnect.profile, profile)
                self.assertEqual(reconnect.username, session.username)
                self.assertEqual(reconnect.client_id, session.client_id)
                self.assertEqual(reconnect.password, "A")

    def test_repair_tries_saved_profile_first_and_reuses_identity(self):
        session = self.pair()
        self.connections.clear()
        again = self.pair()
        self.assertEqual([c.profile for c in self.connections], ["static"])
        self.assertEqual(again.device_uuid, session.device_uuid)
        self.assertEqual(again.client_id, session.client_id)

    def test_all_profiles_rejected_never_request_a_pin_or_save_a_session(self):
        self.accepted_profile = None
        provider = Mock()
        with self.assertRaisesRegex(ConnectionError, "static: rc=5.*modern: rc=5"):
            client.pair("192.168.1.10", provider)
        provider.assert_not_called()
        self.assertEqual(len(self.connections), 4)
        self.assertTrue(all(c.stopped and not c.published for c in self.connections))
        self.assertFalse(os.path.exists(self.path))

    def test_failed_pairing_includes_public_brand_and_protocol_details(self):
        self.accepted_profile = None
        descriptor = client.TvInfo("192.168.1.10", raw_description='''
            <root xmlns="urn:schemas-upnp-org:device-1-0"><device>
            <manufacturer>TOSHIBA</manufacturer><modelName>Z670</modelName>
            <friendlyName>Private nickname</friendlyName><UDN>private-uuid</UDN>
            <modelDescription>brand=tos
transport_protocol=3310
macWifi=private-mac
serialNumber=private-serial</modelDescription></device></root>''')
        with patch.object(client, "fetch_descriptor", return_value=descriptor):
            with self.assertRaises(ConnectionError) as error:
                self.pair()
        message = str(error.exception)
        for field in ("manufacturer=TOSHIBA", "modelName=Z670", "brand=tos",
                      "transport_protocol=3310"):
            self.assertIn(field, message)
        self.assertNotIn("private", message.lower())
        self.assertNotIn("date/time", message)

    def test_protocol_3290_prefers_modern_for_new_pairing(self):
        self.accepted_profile = "modern"
        self.token_reply = '{"accesstoken": "A", "refreshtoken": "R"}'
        descriptor = client.TvInfo(
            "192.168.1.10",
            raw_description="brand=his\\ntransport_protocol=3290",
        )
        with patch.object(client, "fetch_descriptor", return_value=descriptor):
            session = self.pair()
        self.assertEqual([c.profile for c in self.connections], ["modern"])
        self.assertEqual(session.auth_profile, "modern")

    def test_protocol_below_3290_keeps_static_first(self):
        descriptor = client.TvInfo(
            "192.168.1.10",
            raw_description="brand=his\\ntransport_protocol=3285",
        )
        with patch.object(client, "fetch_descriptor", return_value=descriptor):
            session = self.pair()
        self.assertEqual([c.profile for c in self.connections], ["static"])
        self.assertEqual(session.auth_profile, "static")

    def test_saved_profile_overrides_protocol_preference_on_repair(self):
        first = self.pair()
        self.assertEqual(first.auth_profile, "static")
        self.connections.clear()

        descriptor = client.TvInfo(
            "192.168.1.10",
            raw_description="brand=his\\ntransport_protocol=3290",
        )
        with patch.object(client, "fetch_descriptor", return_value=descriptor):
            again = self.pair()

        self.assertEqual([c.profile for c in self.connections], ["static"])
        self.assertEqual(again.device_uuid, first.device_uuid)
        self.assertEqual(again.auth_profile, "static")

    def test_new_pairing_tries_static_before_any_dynamic_rejection(self):
        # Model a broker that refuses every connection after a bad dynamic
        # login. A fresh static connection must reach the PIN without that
        # earlier rejection.
        self.throttle_on_rejection = True
        with self.assertRaises(ConnectionError):
            client._pairing_connection("192.168.1.10", "aa:bb:cc:dd:ee:ff", 123,
                                       preferred="modern")
        self.assertTrue(self.broker_throttled)
        self.broker_throttled = False
        self.connections.clear()
        session = self.pair()
        self.assertEqual([c.profile for c in self.connections], ["static"])
        self.assertTrue(session.tokenless)

    def test_known_modern_pairing_keeps_its_profile_and_topic_identity(self):
        self.accepted_profile = "modern"
        self.token_reply = '{"accesstoken": "A", "refreshtoken": "R"}'
        first = self.pair()
        self.assertEqual([c.profile for c in self.connections], ["static", "modern"])
        self.connections.clear()
        second = self.pair()
        self.assertEqual([c.profile for c in self.connections], ["modern"])
        self.assertEqual(second.client_id, first.client_id)
        self.assertEqual(second.device_uuid, first.device_uuid)

    def test_network_tls_and_broker_errors_do_not_try_other_credentials(self):
        self.accepted_profile = None
        for failure in (None, 3, OSError("offline"), ssl.SSLError("TLS failed")):
            with self.subTest(failure=failure):
                self.connections.clear()
                self.failure = failure
                with self.assertRaises((ConnectionError, OSError)):
                    self.pair()
                self.assertEqual(len(self.connections), 1)
                self.assertTrue(self.connections[0].stopped)

    def test_static_pairing_requires_pin_acceptance_and_a_valid_app_reply(self):
        for pin_reply, apps_reply in ((None, "[]"), ('{"result": 100}', "[]"),
                                      ("null", "[]"), ('{"result": 1}', None),
                                      ('{"result": 1}', "{}")):
            with self.subTest(pin=pin_reply, apps=apps_reply):
                self.pin_reply, self.apps_reply = pin_reply, apps_reply
                with self.assertRaises((ValueError, TimeoutError)):
                    self.pair()
                self.assertFalse(os.path.exists(self.path))
                self.assertTrue(self.connections[-1].stopped)

    def test_invalid_token_reply_cannot_become_a_tokenless_pairing(self):
        for reply in ("not-json", "{}", '{"accesstoken": "A"}'):
            with self.subTest(reply=reply):
                self.token_reply = reply
                with self.assertRaises(ValueError):
                    self.pair()
                self.assertFalse(os.path.exists(self.path))

    def test_lost_static_pairing_requests_new_pin_without_refreshing(self):
        self.pair()
        self.accepted_profile = None
        operation = Mock()
        with patch.object(client, "refresh") as refresh:
            with self.assertRaises(client.AuthError) as error:
                client.run_with_session(operation)
        self.assertEqual(error.exception.kind, "needs_pairing")
        refresh.assert_not_called()
        operation.assert_not_called()
        self.assertTrue(self.connections[-1].stopped)

    def test_dashboard_marks_lost_static_pairing_for_repair(self):
        handler = object.__new__(webui.Handler)
        handler.path = "/api/install?key=" + webui.ACCESS_KEY
        handler.headers = {"Content-Length": "2"}
        handler.rfile = io.BytesIO(b"{}")
        handler._json = Mock()
        with patch.object(handler, "_install", side_effect=client.AuthError(
                "needs_pairing", "request a new code")):
            handler.do_POST()
        self.assertTrue(handler._json.call_args.args[0]["needs_pairing"])

    def test_incomplete_sessions_still_fail_validation(self):
        for data in ({"host": "x", "device_uuid": "d", "auth_profile": "static"},
                     {"host": "x", "device_uuid": "d", "auth_profile": "unknown"},
                     {"host": "x", "device_uuid": "d", "client_id": "id",
                      "username": "user", "auth_profile": "modern"},
                     {"host": "x", "device_uuid": "d", "client_id": "id",
                      "username": "user", "auth_profile": "static", "expires_at": 1}):
            with self.subTest(data=data):
                with open(self.path, "w", encoding="utf-8") as f:
                    json.dump(data, f)
                self.assertIsNone(client.Session().load_or_none())


class TestMqttConnectionIdentity(unittest.TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(client, "_load_client_pem_key",
                                         return_value=(b"cert", b"key")))
        stack.enter_context(patch.object(client.ssl, "SSLContext"))
        self.mqtt = stack.enter_context(patch.object(client.mqtt, "Client"))
        self.uuid = "16:1e:d5:d4:61:0d"

    def test_static_broker_ids_are_short_unique_and_preserve_paired_topics(self):
        paired_id = protocol.session_credentials(self.uuid, 123)[0]
        first = client.MqttSession("192.168.1.10", self.uuid, 123,
                                   auth_profile="static", client_id=paired_id)
        second = client.MqttSession("192.168.1.10", self.uuid, 123, token="access",
                                    auth_profile="static", client_id=paired_id)
        broker_ids = [call.kwargs["client_id"] for call in self.mqtt.call_args_list]
        self.assertNotEqual(broker_ids[0], broker_ids[1])
        for broker_id in broker_ids:
            self.assertLessEqual(len(broker_id), 23)
            self.assertNotIn("$", broker_id)
            self.assertNotEqual(broker_id, paired_id)
        self.assertEqual(first.client_id, paired_id)
        self.assertEqual(first.topics, second.topics)
        self.assertEqual(second.password, "access")

    def test_dynamic_broker_identity_matches_topics_and_disables_background_retries(self):
        for profile in protocol.AUTH_PROFILES:
            with self.subTest(profile=profile):
                session = client.MqttSession("192.168.1.10", self.uuid, 123,
                                             auth_profile=profile)
                options = self.mqtt.call_args.kwargs
                self.assertFalse(options["reconnect_on_failure"])
                if profile != "static":
                    self.assertEqual(options["client_id"], session.client_id)


if __name__ == "__main__":
    unittest.main()
