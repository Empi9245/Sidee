import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core import native_api, native_session


class NativeSafetyTests(unittest.TestCase):
    def test_https_and_loopback_only(self):
        for url in ("http://192.168.1.5:8799", "http://example.com", "https://u:p@example.com", "https://example.com/path", "https://example.com?x=1", "ftp://example.com"):
            with self.subTest(url=url), self.assertRaises(native_api.ApiError):
                native_api._conn(url)
        for url in ("http://127.0.0.1:8799", "https://example.com"):
            native_api._conn(url).close()

    def test_utf8_limit_is_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "app.html"
            p.write_text("<html>" + "è" * 150_000, encoding="utf-8")
            with self.assertRaises(ValueError):
                native_session._resolve_target(str(p))

    def test_custom_file_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "test.html"
            html = "<!doctype html><html>Caffè</html>"
            p.write_text(html, encoding="utf-8")
            self.assertEqual(native_session._resolve_target(str(p)), {"custom_html": html, "name": "test"})

    def test_unknown_catalog_target_is_not_read_as_a_file(self):
        self.assertEqual(native_session._resolve_target("demo"), {"id": "demo"})

    def test_commands_reject_arbitrary_topics_and_unbounded_delay(self):
        valid = {"op": "publish", "topic_key": "ui", "topic_suffix": "actions/test", "payload": "{}"}
        native_session.validate_commands([valid], {"ui": "paired/"})
        invalid = [dict(valid, topic_key="attacker/topic"), dict(valid, topic_suffix="a/#"),
                   dict(valid, wait_ms=-1), dict(valid, wait_ms=float("nan")),
                   dict(valid, payload={}), {"op": "sleep", "ms": 999999}, {"op": "shell"}]
        for command in invalid:
            with self.subTest(command=command), self.assertRaises(ValueError):
                native_session.validate_commands([valid, command], {"ui": "paired/"})

    def test_missing_pairing_does_not_start_a_session(self):
        with patch.object(native_session.client.Session, "load_or_none", return_value=None), patch.object(native_api, "start_session") as start:
            self.assertFalse(native_session.install("demo", on_update=lambda _: None))
            start.assert_not_called()

    def test_invalid_batch_publishes_nothing(self):
        commands = [{"op": "publish", "topic_key": "ui", "topic_suffix": "actions/test", "payload": "{}"}, {"op": "shell"}]
        conn = Mock()
        def relay(callback, host):
            callback(conn, {"ui": "paired/"})
        with patch.object(native_session.client.Session, "load_or_none", return_value=Mock(device_uuid="paired", host="127.0.0.1")), patch.object(native_api, "start_session", return_value={"sid": "f" * 64, "commands": commands}), patch.object(native_session.client, "run_with_session", side_effect=relay):
            with self.assertRaises(ValueError):
                native_session.install("demo", on_update=lambda _: None)
        conn.publish.assert_not_called()

    def test_safe_error_message(self):
        conn = Mock()
        response = Mock(status=403)
        response.read.return_value = json.dumps({"error": "missing_key", "debug": "private-data"}).encode()
        conn.getresponse.return_value = response
        with patch.object(native_api, "_conn", return_value=conn):
            with self.assertRaises(native_api.ApiError) as error:
                native_api.start_session({"id": "custom"})
        self.assertNotIn("private-data", str(error.exception))
        self.assertIn("chiave", str(error.exception))
        conn.close.assert_called_once()

    def test_oversized_response_is_rejected(self):
        conn = Mock()
        conn.getresponse.return_value.read.return_value = b"x" * 2_000_001
        with patch.object(native_api, "_conn", return_value=conn), self.assertRaises(native_api.ApiError):
            native_api.catalog()

    def test_failure_description_hides_internal_reason(self):
        self.assertNotIn("backup_failed", native_api.describe({"state": "failed", "failure": "backup_failed"}))
        self.assertIn("license_invalid", native_api.describe({"state": "failed", "failure": "license_invalid"}))

    def test_invalid_url_does_not_echo_credentials(self):
        with self.assertRaises(native_api.ApiError) as error:
            native_api._conn("https://private-user:private-password@example.com")
        self.assertNotIn("private-password", str(error.exception))

    def test_successful_http_with_invalid_json_is_rejected(self):
        conn = Mock()
        conn.getresponse.return_value.status = 200
        conn.getresponse.return_value.read.return_value = b"<html>unexpected login</html>"
        with patch.object(native_api, "_conn", return_value=conn), self.assertRaises(native_api.ApiError):
            native_api.catalog()

    def test_unknown_error_payload_is_not_printed(self):
        for reason in ("private-secret-payload", {"token": "private-secret-payload"}):
            self.assertNotIn("private-secret-payload", native_api.describe({"state": "failed", "failure": reason}))

    def test_invalid_session_id_does_not_reach_server(self):
        with patch.object(native_api, "_request") as request, self.assertRaises(native_api.ApiError):
            native_api.poll_status("https://example.com", "../private", lambda _: None)
        request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
