import http.client
import json
import pathlib
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

from post_store_check import make_handler


class IsolatedReceiverTest(unittest.TestCase):
    def test_http_isolation_and_fixed_report_destination(self):
        with tempfile.TemporaryDirectory(prefix="sidee-receiver-test-") as directory:
            reports = pathlib.Path(directory)
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(reports))
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()

            def request(method, path, body=None, headers=None):
                connection = http.client.HTTPConnection(*server.server_address, timeout=3)
                connection.request(method, path, body, headers or {})
                response = connection.getresponse()
                result = response.status, response.read()
                connection.close()
                return result

            try:
                code, body = request("GET", "/post-store-check.html")
                self.assertEqual(code, 200)
                self.assertIn(b"/post-store-check.js", body)
                self.assertNotIn(b"/app.js", body)
                self.assertEqual(request("POST", "/api/full-network-capture", "{}")[0], 404)
                self.assertEqual(request("GET", "/api/config")[0], 404)
                self.assertEqual(request("GET", "/../config.json")[0], 404)
                self.assertEqual(request("POST", "/snapshot", "{}")[0], 400)
                self.assertFalse(list(reports.iterdir()))

                fixture = json.dumps({"kind": "post-store-inventory-v1", "readOnly": True,
                    "apps": {"status": "UNAVAILABLE"}, "packages": {"status": "UNAVAILABLE"}})
                self.assertEqual(request("POST", "/snapshot", fixture,
                    {"Origin": "https://external.invalid"})[0], 403)
                self.assertFalse(list(reports.iterdir()))
                self.assertEqual(request("POST", "/snapshot", fixture)[0], 200)
                saved = json.loads((reports / "post-store-latest.json").read_text(encoding="utf-8"))
                self.assertEqual(saved["receiverMode"], "isolated-post-store-check")
                self.assertIn("receivedAt", saved)
                self.assertEqual(saved["receiverContext"]["transport"], "http")
                self.assertEqual(saved["receiverContext"]["hostHeader"], f"127.0.0.1:{server.server_address[1]}")
                self.assertEqual(request("GET", "/status")[0], 200)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
