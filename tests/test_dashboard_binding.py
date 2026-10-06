"""Separate downloaded copies must not share a Windows dashboard socket."""
import errno
import http.client
import http.server
import json
import threading
import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock, call, patch

from core import webui


def keyed_handler(key):
    class KeyedHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            supplied = parse_qs(urlparse(self.path).query).get("key", [""])[0]
            authorized = supplied == key
            body = json.dumps({"authorized": authorized}).encode("utf-8")
            self.send_response(200 if authorized else 403)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return KeyedHandler


class TestDashboardBinding(unittest.TestCase):
    def _serve(self, server):
        thread = threading.Thread(target=server.serve_forever,
                                  kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()

        def stop():
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.addCleanup(stop)

    def _request(self, port, key):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            connection.request("GET", "/?key=" + key)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_downloaded_copies_bind_separate_ports_and_accept_only_their_keys(self):
        first_handler = keyed_handler("first-copy")
        second_handler = keyed_handler("second-copy")
        with patch.object(webui, "_PORT", 0), \
                patch.object(webui, "Handler", first_handler):
            first = webui._bind_dashboard_server()
        self._serve(first)
        first_port = first.server_address[1]
        with patch.object(webui, "_PORT", first_port), \
                patch.object(webui, "Handler", second_handler):
            second = webui._bind_dashboard_server()
        self._serve(second)
        second_port = second.server_address[1]

        self.assertNotEqual(first_port, second_port)
        for port, own_key, other_key in ((first_port, "first-copy", "second-copy"),
                                          (second_port, "second-copy", "first-copy")):
            with self.subTest(port=port):
                self.assertEqual(self._request(port, own_key),
                                 (200, {"authorized": True}))
                self.assertEqual(self._request(port, other_key),
                                 (403, {"authorized": False}))

    def test_new_download_does_not_share_the_running_legacy_server_port(self):
        self.assertTrue(http.server.ThreadingHTTPServer.allow_reuse_address)
        # This fixture tests socket ownership, not the runner's reverse DNS.
        with patch("socket.getfqdn", return_value="localhost"):
            legacy = http.server.ThreadingHTTPServer(("0.0.0.0", 0),
                                                    keyed_handler("legacy-copy"))
        self._serve(legacy)
        legacy_port = legacy.server_address[1]
        with patch.object(webui, "_PORT", legacy_port), \
                patch.object(webui, "Handler", keyed_handler("new-copy")):
            current = webui._bind_dashboard_server()
        self._serve(current)
        current_port = current.server_address[1]

        self.assertNotEqual(legacy_port, current_port)
        for port, own_key, other_key in ((legacy_port, "legacy-copy", "new-copy"),
                                          (current_port, "new-copy", "legacy-copy")):
            with self.subTest(port=port):
                self.assertEqual(self._request(port, own_key),
                                 (200, {"authorized": True}))
                self.assertEqual(self._request(port, other_key),
                                 (403, {"authorized": False}))

    def test_windows_exclusive_socket_access_error_uses_a_free_port(self):
        occupied = OSError(errno.EACCES, "The socket is already in use")
        occupied.winerror = 10013
        fallback = Mock()
        with patch.object(webui, "DashboardServer", side_effect=[occupied, fallback]) as create:
            self.assertIs(webui._bind_dashboard_server(), fallback)
        self.assertEqual(create.call_args_list,
                         [call(("0.0.0.0", webui._PORT), webui.Handler),
                          call(("0.0.0.0", 0), webui.Handler)])

    def test_unrelated_socket_failure_is_not_hidden_by_a_new_port(self):
        failure = OSError(errno.EIO, "Socket setup failed")
        with patch.object(webui, "DashboardServer", side_effect=failure) as create:
            with self.assertRaises(OSError) as raised:
                webui._bind_dashboard_server()
        self.assertIs(raised.exception, failure)
        create.assert_called_once_with(("0.0.0.0", webui._PORT), webui.Handler)


if __name__ == "__main__":
    unittest.main()
