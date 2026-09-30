import hashlib
import http.client
import json
import pathlib
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

from bridge_source_check import make_handler


class BridgeSourceReceiverTest(unittest.TestCase):
    def test_isolation_build_binding_hashes_and_single_receipt(self):
        provenance = {"collectionId": "test", "buildId": "fixture"}
        with tempfile.TemporaryDirectory(prefix="sidee-source-test-") as directory:
            reports = pathlib.Path(directory)
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(reports, provenance))
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            origin = "http://127.0.0.1:" + str(server.server_address[1])

            def request(method, path, body=None, extra=None):
                conn = http.client.HTTPConnection(*server.server_address, timeout=3)
                headers = {"Origin": origin, "Content-Type": "application/json"}
                headers.update(extra or {})
                conn.request(method, path, body, headers)
                response = conn.getresponse()
                result = response.status, response.read()
                conn.close()
                return result

            fixture = {"kind": "loaded-bridge-source-v1", "readOnly": True, "timestamp": "2026-09-30T12:00:00Z",
                       "collectionId": "test", "clientBuildId": "fixture", "userAgent": "off-TV fixture",
                       "accessContext": {"origin": origin, "hostname": "127.0.0.1", "protocol": "http:", "secureContext": False},
                       "discovery": {"timingStatus": "OBSERVED", "timingCount": 1},
                       "sources": [{"url": origin + "/script.js", "observedVia": "performance.resource", "inline": False,
                                    "status": "COMPLETE", "source": "function f() { return 'è'; }", "account": "omit-this"},
                                   {"url": None, "scheme": "file:", "status": "OUT_OF_SCOPE", "inline": False,
                                    "observedVia": "performance.resource"}],
                       "account": "omit-this"}
            try:
                code, html = request("GET", "/")
                self.assertEqual(code, 200)
                self.assertIn(b"bridge-source-check.js?v=fixture", html)
                self.assertNotIn(b"/app.js", html)
                for path in ("/api/reports/session", "/api/appinfo/backup", "/api/full-network-capture", "/../config.json"):
                    self.assertEqual(request("POST", path, "{}")[0], 404)
                self.assertIsNone(json.loads(request("GET", "/status")[1])["receipt"])
                self.assertFalse(list(reports.iterdir()))
                stale = dict(fixture, clientBuildId="stale")
                self.assertEqual(request("POST", "/snapshot", json.dumps(stale))[0], 400)
                self.assertEqual(request("POST", "/snapshot", json.dumps(fixture), {"Origin": "https://foreign.invalid"})[0], 403)
                private = dict(fixture, sources=[dict(fixture["sources"][0], url=origin + "/a.js?token=private")])
                self.assertEqual(request("POST", "/snapshot", json.dumps(private))[0], 400)
                encoded = json.dumps(fixture)
                code, receipt = request("POST", "/snapshot", encoded)
                self.assertEqual(code, 200)
                raw = (reports / "bridge-source-latest.json").read_bytes()
                saved = json.loads(raw)
                self.assertEqual(json.loads(receipt)["sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(saved["sources"][0]["sha256"], hashlib.sha256(fixture["sources"][0]["source"].encode()).hexdigest())
                self.assertEqual(saved["clientDeviceHint"], "UNCONFIRMED")
                self.assertNotIn(b"omit-this", raw)
                self.assertEqual(request("POST", "/snapshot", encoded)[0], 200)
                self.assertEqual(len(list(reports.glob("*.json"))), 2)
                changed = dict(fixture, timestamp="2026-09-30T12:00:01Z")
                self.assertEqual(request("POST", "/snapshot", json.dumps(changed))[0], 409)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
