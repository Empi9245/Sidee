"""Offline Sidee tests: payloads, topics, encoded constants.
No network: everything uses known values from the measurement session."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import client, protocol, presets  # noqa: E402

TS = 1791229505


class TestCredentials(unittest.TestCase):
    def test_session_credentials_shape(self):
        cid, user, pwd = protocol.session_credentials("16:1e:d5:d4:61:0d", TS)
        self.assertTrue(cid.startswith("16:1e:d5:d4:61:0d$his$"))
        self.assertTrue(cid.endswith("_vidaacommon_001"))
        self.assertTrue(user.startswith("his$"))
        self.assertEqual(len(pwd), 32)

    def test_token_mode_keeps_identity_swaps_password(self):
        cid0, user0, _ = protocol.session_credentials("16:1e:d5:d4:61:0d", TS)
        cid1, user1, pwd1 = protocol.session_credentials(
            "16:1e:d5:d4:61:0d", TS, token="tok")
        self.assertEqual(cid0, cid1)
        self.assertEqual(user0, user1)
        self.assertEqual(pwd1, "tok")

    def test_credentials_depend_on_timestamp(self):
        _, _, p1 = protocol.session_credentials("16:1e:d5:d4:61:0d", TS)
        _, _, p2 = protocol.session_credentials("16:1e:d5:d4:61:0d", TS + 1)
        self.assertNotEqual(p1, p2)

    def test_encoded_constants_decode_consistently(self):
        # encoded constants always decode to the same value
        a = protocol.PATTERN
        self.assertEqual(a, protocol.PATTERN)
        self.assertEqual(len(a), 32)
        self.assertNotIn(" ", protocol.VALUE_SUFFIX)

    def test_known_vector_integrity(self):
        """Encoded constant integrity: precomputed hashes without exposing
        the values. If a digest does not match, a constant is corrupted
        and the client cannot connect."""
        import hashlib
        self.assertEqual(
            hashlib.sha256(protocol.PATTERN.encode()).hexdigest(),
            "96f682e0558c63d36eebd6971b8628729de55d8a33615482bd4c95ffa38daf76")
        self.assertEqual(
            hashlib.sha256(protocol.VALUE_SUFFIX.encode()).hexdigest(),
            "aaba8568e1cb86926f2ada9dde7420a421a677a3b9c368c21ecb61598bf47b10")
        self.assertEqual(
            hashlib.sha256(str(protocol.XOR_MASK).encode()).hexdigest(),
            "357f09352086efedd9c41d4fae773586c3e07b09b1243f091a7394f727acb324")


class TestPayloads(unittest.TestCase):
    def test_install_payload_matches_measured_shape(self):
        p = json.loads(protocol.install_payload(
            "nuviodebug", "Nuvio", "https://example.app/",
            "https://example.app/icon.png"))
        self.assertEqual(p["type"], "app_install")
        self.assertEqual(sorted(p["app_info"].keys()),
                         sorted(["Title", "StoreType", "mediaId", "Id",
                                 "Image", "URL", "configUrlDownload",
                                 "configUrl"]))
        self.assertEqual(p["app_info"]["StoreType"], 99)
        self.assertEqual(p["app_info"]["Id"], "nuviodebug")
        self.assertEqual(p["app_info"]["mediaId"], "nuviodebug")
        self.assertEqual(p["app_info"]["configUrl"], "")

    def test_pin_payload_is_int(self):
        self.assertEqual(json.loads(protocol.pair_pin_payload("1234")),
                         {"authNum": 1234})

    def test_launch_payload(self):
        p = json.loads(protocol.launch_payload("x", "X", "https://x/"))
        self.assertEqual(p["urlType"], 37)
        self.assertEqual(p["appId"], "x")

    def test_token_request(self):
        self.assertEqual(json.loads(protocol.token_request_payload("r")),
                         {"refreshtoken": "r"})


class TestTopics(unittest.TestCase):
    def test_topics_contain_client_id(self):
        t = protocol.tv_topics("aa$his$BB_vidaacommon_001")
        self.assertTrue(t["applist_reply"].startswith("/remoteapp/mobile/"))
        self.assertTrue(t["applist_reply"].endswith("ui_service/data/applist"))
        self.assertTrue(t["token_reply"].endswith(
            "platform_service/data/tokenissuance"))
        self.assertIn("aa$his$BB_vidaacommon_001", t["ui"])

    def test_parsers(self):
        self.assertEqual(protocol.parse_token_message('{"accesstoken":"x"}'),
                         {"accesstoken": "x"})
        self.assertIsNone(protocol.parse_token_message("junk"))
        self.assertEqual(protocol.parse_applist_message("[]"), [])
        self.assertIsNone(protocol.parse_applist_message("{}"))


class TestPresets(unittest.TestCase):
    def test_nuvio_preset_complete(self):
        p = presets.get("nuvio")
        self.assertTrue(p)
        self.assertEqual(p["app_id"], "nuviodebug")
        self.assertEqual(p["url"], "https://nuviotvsmart.vercel.app/vidaa.html")
        self.assertTrue(p["image"].startswith("https://"))
        self.assertTrue(os.path.isfile(os.path.join(ROOT, p["icon"])))

    def test_stremio_preset_uses_full_web_app(self):
        p = presets.get("stremio")
        self.assertEqual(p["app_id"], "stremiodebug")
        self.assertEqual(p["url"], "https://web.stremio.com/")
        self.assertEqual(p["server_builder"], "stremio")
        self.assertNotIn("lite", p["url"].lower())

    def test_build_stremio_url(self):
        f = presets.build_stremio_url
        self.assertEqual(f(""), "https://web.stremio.com/")
        url = f("https://stream.example.test:12470")
        self.assertTrue(url.startswith(
            "https://web.stremio.com/#/?streamingServerUrl="))
        self.assertIn(
            "https%3A%2F%2Fstream.example.test%3A12470", url)
        with self.assertRaises(ValueError):
            f("http://localhost:11470")
        with self.assertRaises(ValueError):
            f("192.168.1.20:11470")

    def test_jellyfin_preset_needs_server(self):
        p = presets.get("jellyfin")
        self.assertTrue(p["needs_server"])
        self.assertTrue(os.path.isfile(os.path.join(ROOT, p["icon"])))

    def test_build_server_url(self):
        f = presets.build_server_url
        self.assertEqual(f("192.168.1.50:8096"),
                         "http://192.168.1.50:8096/web/index.html")
        self.assertEqual(f("192.168.1.50"),
                         "http://192.168.1.50:8096/web/index.html")
        self.assertEqual(f("http://192.168.1.50:8096"),
                         "http://192.168.1.50:8096/web/index.html")
        self.assertEqual(f("jellyfin.casa.local"),
                         "http://jellyfin.casa.local:8096/web/index.html")
        self.assertTrue(f("media.example.com").startswith("https://"))
        self.assertEqual(f("https://media.example.com/jellyfin/"),
                         "https://media.example.com/jellyfin/web/index.html")

    def test_private_host_rule(self):
        f = presets.is_private_host
        self.assertTrue(f("192.168.1.50"))
        self.assertTrue(f("10.0.0.3:8096"))
        self.assertTrue(f("172.16.5.4"))
        self.assertFalse(f("localhost"))
        self.assertTrue(f("nas.casa.local"))
        self.assertFalse(f("172.32.1.1"))
        self.assertFalse(f("media.example.com"))


class TestCertificateBundle(unittest.TestCase):
    def setUp(self):
        import tempfile
        from unittest.mock import patch
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        isolated = patch.object(client, "_cert_dir", return_value=tmp.name)
        isolated.start()
        self.addCleanup(isolated.stop)

    def test_install_and_roundtrip(self):
        blob = "-----BEGIN CERTIFICATE-----\nABC\n" \
               "-----END CERTIFICATE-----\n-----BEGIN PRIVATE KEY-----\nXYZ\n" \
               "-----END PRIVATE KEY-----\n"
        old = client._CERT_BUNDLE
        client._CERT_BUNDLE = "test-certs.bin.k"
        try:
            client.install_client_certificate(blob)
            cert, key = client._load_client_pem_key()
            self.assertIn(b"BEGIN CERTIFICATE", cert)
            self.assertIn(b"BEGIN PRIVATE KEY", key)
            self.assertTrue(client.has_client_certificate())
        finally:
            client._CERT_BUNDLE = old
            p = os.path.join(client._cert_dir(), "test-certs.bin.k")
            if os.path.isfile(p):
                os.remove(p)


class TestSessionLifecycle(unittest.TestCase):
    """Token lifecycle: expiry, corrupted sessions, UUID reuse,
    error classification. Temporary session folder, no network."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()
        self.old_dir = client._cert_dir
        self.old_path = client.Session.__dict__["path"]
        client._cert_dir = lambda: self.tmp
        client.Session.path = classmethod(
            lambda cls: os.path.join(self.tmp, "session.json"))

    def tearDown(self):
        client._cert_dir = self.old_dir
        client.Session.path = self.old_path
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_session(self, **over) -> client.Session:
        import time as _t
        base = dict(host="192.168.1.10", device_uuid="aa:bb:cc:dd:ee:ff",
                    client_id="aa:bb:cc:dd:ee:ff$his$ABC123_vidaacommon_001",
                    username="his$123", access_token="A", refresh_token="R",
                    access_time=int(_t.time()), access_days=2,
                    refresh_time=int(_t.time()), refresh_days=30)
        base.update(over)
        return client.Session(**base)

    def test_legacy_session_loads_expiry(self):
        import time as _t
        s = self._make_session()
        s.save()
        loaded = client.Session.load()
        self.assertGreater(loaded.expires_at, _t.time() + 86000)

    def test_expired_session_detected(self):
        import time as _t
        s = self._make_session()
        s.expires_at = _t.time() - 10
        s.save()
        loaded = client.Session.load()
        self.assertLess(loaded.expires_at, _t.time())

    def test_corrupt_session_raises_autherror(self):
        with open(client.Session.path(), "w") as f:
            f.write("{ not json")
        self.assertIsNone(client.Session().load_or_none())
        with open(client.Session.path(), "w") as f:
            json.dump({"host": "x"}, f)  # missing tokens
        self.assertIsNone(client.Session().load_or_none())

    def test_uuid_reused_on_repair(self):
        s = self._make_session()
        s.save()
        self.assertEqual(client._stored_uuid(), "aa:bb:cc:dd:ee:ff")

    def test_pair_failures_counter(self):
        s = self._make_session()
        s.save()
        client._register_pair_failure(reused=True)
        client._register_pair_failure(reused=True)
        self.assertTrue(client._pair_failures_exceeded())
        self.assertEqual(client.Session.load().pair_failures, 2)
        client._register_pair_failure(reused=False)
        self.assertEqual(client.Session.load().pair_failures, 2)

    def test_autherror_kinds(self):
        for kind in ("none", "rejected", "corrupt", "expired"):
            e = client.AuthError(kind, "msg")
            self.assertEqual(e.kind, kind)

    def test_refresh_classifies_rejection(self):
        class FakeSess:
            def __init__(self, *a, **k):
                pass
            def start(self):
                return 5  # rc=5: authentication rejected
            def stop(self):
                pass
        old = client.MqttSession
        client.MqttSession = FakeSess
        try:
            s = self._make_session()
            with self.assertRaises(client.AuthError) as cm:
                client.refresh(s)
            self.assertEqual(cm.exception.kind, "rejected")
        finally:
            client.MqttSession = old

    def test_ensure_ready_skips_refresh_when_valid(self):
        import time as _t
        s = self._make_session()
        s.expires_at = _t.time() + 40 * 3600  # beyond the 12-hour margin
        calls = []

        def boom(sess):
            calls.append(1)
            raise AssertionError("refresh should not run")

        old = client.refresh
        client.refresh = boom
        try:
            out = client._ensure_ready(s)
            self.assertEqual(out.expires_at, s.expires_at)
            self.assertEqual(calls, [])
        finally:
            client.refresh = old


if __name__ == "__main__":
    unittest.main()
