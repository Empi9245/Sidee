"""The phone link must reach the current dashboard and preserve its access key."""
import io
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core import webui


class TestPhoneAccess(unittest.TestCase):
    def get(self, path):
        handler = object.__new__(webui.Handler)
        handler.path = path
        handler.server = SimpleNamespace(server_address=("0.0.0.0", 43210))
        handler._json = Mock()
        handler.do_GET()
        return handler._json.call_args.args

    def test_authenticated_qr_uses_lan_address_actual_port_and_key(self):
        with patch.object(webui, "_local_ip", return_value="192.168.1.5"), \
                patch.object(webui, "ACCESS_KEY", "phone-test-key"):
            result = self.get("/api/phone?key=phone-test-key")[0]
        self.assertTrue(result["ok"])
        self.assertEqual(result["url"], "http://192.168.1.5:43210/?key=phone-test-key")
        self.assertTrue(result["qr"].startswith("data:image/svg+xml;base64,"))

    def test_missing_or_wrong_key_does_not_expose_phone_access(self):
        with patch.object(webui, "_phone_access") as prepare:
            for path in ("/api/phone", "/api/phone?key=wrong-key"):
                with self.subTest(path=path):
                    result, status = self.get(path)
                    self.assertEqual(status, 403)
                    self.assertNotIn("url", result)
            prepare.assert_not_called()

    def test_no_network_does_not_offer_a_loopback_qr_to_the_phone(self):
        for host in ("127.0.0.1", "0.0.0.0"):
            with self.subTest(host=host), \
                    patch.object(webui, "_local_ip", return_value=host), \
                    patch.object(webui, "qr_image") as generate:
                result = webui._phone_access(8787)
                self.assertFalse(result["ok"])
                self.assertNotIn("url", result)
                generate.assert_not_called()

    def test_phone_link_with_access_key_is_not_cached(self):
        handler = object.__new__(webui.Handler)
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        handler.wfile = io.BytesIO()
        handler._json({"url": "http://192.168.1.5:8787/?key=phone-test-key"})
        self.assertIn(unittest.mock.call("Cache-Control", "no-store"),
                      handler.send_header.call_args_list)


if __name__ == "__main__":
    unittest.main()
