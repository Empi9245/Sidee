"""The phone link must reach the current dashboard and preserve its access key."""
import io
import socket
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
        with patch.object(webui, "_local_ip", return_value="192.168.1.5") as local_ip, \
                patch.object(webui, "ACCESS_KEY", "phone-test-key"):
            result = self.get("/api/phone?key=phone-test-key")[0]
        local_ip.assert_called_once_with(None)
        self.assertTrue(result["ok"])
        self.assertEqual(result["url"], "http://192.168.1.5:43210/?key=phone-test-key")
        self.assertTrue(result["qr"].startswith("data:image/svg+xml;base64,"))

    def test_selected_tv_uses_its_lan_route_instead_of_the_vpn_default(self):
        connection = Mock()

        def local_address():
            target = connection.connect.call_args.args[0][0]
            # The Internet route would select the VPN. The TV has a LAN route.
            return ({"8.8.8.8": "10.88.0.2",
                     "172.16.8.42": "172.16.8.5"}[target], 54321)

        connection.getsockname.side_effect = local_address
        with patch.object(webui.socket, "socket", return_value=connection), \
                patch.object(webui, "ACCESS_KEY", "phone-test-key"):
            result = self.get("/api/phone?key=phone-test-key&tv_host=172.16.8.42")[0]
        self.assertTrue(result["ok"])
        self.assertEqual(result["url"], "http://172.16.8.5:43210/?key=phone-test-key")
        connection.connect.assert_called_once_with(("172.16.8.42", 36669))
        connection.send.assert_not_called()
        connection.sendto.assert_not_called()
        connection.close.assert_called_once()

    def test_before_discovery_phone_access_uses_broadcast_without_internet(self):
        connection = Mock()
        connection.getsockname.return_value = ("10.20.30.5", 54321)
        with patch.object(webui.socket, "socket", return_value=connection), \
                patch.object(webui, "ACCESS_KEY", "phone-test-key"):
            result = self.get("/api/phone?key=phone-test-key")[0]
        self.assertEqual(result["url"], "http://10.20.30.5:43210/?key=phone-test-key")
        connection.setsockopt.assert_called_once_with(
            socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        connection.connect.assert_called_once_with(("255.255.255.255", 1900))
        connection.send.assert_not_called()
        connection.sendto.assert_not_called()
        connection.close.assert_called_once()

    def test_invalid_tv_address_is_rejected_before_choosing_an_interface(self):
        with patch.object(webui, "_phone_access") as prepare:
            for host in ("", "your-tv", "%3A%3A1", "172.16.8.999"):
                with self.subTest(host=host):
                    result = self.get("/api/phone?key=" + webui.ACCESS_KEY
                                      + "&tv_host=" + host)[0]
                    self.assertFalse(result["ok"])
                    self.assertIn("invalid", result["error"])
                    self.assertNotIn("url", result)
            prepare.assert_not_called()

    def test_unavailable_lan_returns_an_error_and_never_generates_a_qr(self):
        for host in (None, "10.20.30.42"):
            connection = Mock()
            connection.connect.side_effect = OSError("No route to the LAN")
            with self.subTest(host=host), \
                    patch.object(webui.socket, "socket", return_value=connection), \
                    patch.object(webui, "qr_image") as generate:
                result = webui._phone_access(8787, host)
            self.assertFalse(result["ok"])
            self.assertIn("home network", result["error"])
            self.assertNotIn("url", result)
            generate.assert_not_called()
            connection.connect.assert_called_once()
            connection.close.assert_called_once()

    def test_missing_or_wrong_key_does_not_expose_phone_access(self):
        with patch.object(webui, "_phone_access") as prepare:
            for path in ("/api/phone", "/api/phone?key=wrong-key"):
                with self.subTest(path=path):
                    result, status = self.get(path)
                    self.assertEqual(status, 403)
                    self.assertNotIn("url", result)
            prepare.assert_not_called()

    def test_no_network_does_not_offer_a_loopback_qr_to_the_phone(self):
        for host in ("127.0.0.1", "0.0.0.0", "169.254.1.5", "239.255.255.250"):
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
