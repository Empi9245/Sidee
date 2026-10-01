import hashlib
import http.client
import json
import pathlib
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

from bridge_source_check import SourceHTTPServer, make_handler, serve


class BridgeSourceReceiverTest(unittest.TestCase):
    def test_access_distinguishes_connection_and_request_without_private_query(self):
        provenance = {'collectionId': 'test', 'buildId': 'fixture'}
        with tempfile.TemporaryDirectory(prefix='sidee-http-access-') as directory:
            reports = pathlib.Path(directory)
            access = reports / 'access.json'
            server = SourceHTTPServer(('127.0.0.1', 0), make_handler(reports, provenance), access)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                conn = http.client.HTTPConnection(*server.server_address, timeout=3)
                conn.request('GET', '/bridge-source-check.js?token=never-store', headers={'Host': 'vidaahub.com'})
                response = conn.getresponse()
                self.assertEqual(response.status, 200)
                response.read()
                conn.close()
                saved = json.loads(access.read_text())
                peer = saved['clients']['127.0.0.1']
                self.assertEqual(peer['connections'], 1)
                self.assertEqual(peer['requests'], 1)
                self.assertEqual(peer['lastPath'], '/bridge-source-check.js')
                self.assertEqual(peer['lastHost'], 'vidaahub.com')
                self.assertEqual(peer['paths'], {'/bridge-source-check.js': 1})
                self.assertNotIn('never-store', access.read_text())
                self.assertFalse((reports / 'bridge-source-latest.json').exists())
                # A TCP connection that sends no HTTP must remain distinguishable.
                accepted = threading.Event()
                record_access = server.record_access

                def observed_access(*args, **kwargs):
                    record_access(*args, **kwargs)
                    if len(args) == 1:
                        accepted.set()

                with patch.object(server, 'record_access', side_effect=observed_access):
                    with socket.create_connection(server.server_address, timeout=3) as connection:
                        self.assertTrue(accepted.wait(timeout=3))
                        connection.shutdown(socket.SHUT_WR)
                peer = server.access_snapshot()['127.0.0.1']
                self.assertEqual(peer['connections'], 2)
                self.assertEqual(peer['requests'], 1)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=3)

    def test_https_origin_and_receiver_context_are_enforced(self):
        provenance = {"collectionId": "test", "buildId": "fixture", "fileSha256": {"fixture": "same-source"}}
        with tempfile.TemporaryDirectory(prefix="sidee-source-https-test-") as directory:
            reports = pathlib.Path(directory)
            server = SourceHTTPServer(("127.0.0.1", 0), make_handler(reports, provenance))
            server.scheme = "https"
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            origin = "https://vidaahub.com"

            try:
                fixture = {"kind": "loaded-bridge-source-v1", "readOnly": True, "timestamp": "2026-09-30T12:00:00Z",
                           "collectionId": "test", "clientBuildId": "fixture", "userAgent": "off-TV fixture",
                           "accessContext": {"origin": origin, "hostname": "vidaahub.com", "protocol": "https:", "secureContext": True},
                           "discovery": {"timingStatus": "OBSERVED", "timingCount": 0},
                           "sources": []}
                conn = http.client.HTTPConnection(*server.server_address, timeout=3)
                conn.request("POST", "/snapshot", json.dumps(fixture), {
                    "Host": "vidaahub.com",
                    "Origin": origin,
                    "Content-Type": "application/json",
                })
                response = conn.getresponse()
                self.assertEqual(response.status, 200)
                response.read()
                conn.close()

                saved = json.loads((reports / "bridge-source-latest.json").read_text())
                self.assertEqual(saved["accessContext"]["origin"], "https://vidaahub.com")
                self.assertEqual(saved["receiverContext"]["transport"], "https")
                self.assertTrue(saved["accessContext"]["secureContext"])
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=3)

    def test_isolation_build_binding_hashes_and_single_receipt(self):
        provenance = {"collectionId": "test", "buildId": "fixture", "fileSha256": {"fixture": "same-source"}}
        with tempfile.TemporaryDirectory(prefix="sidee-source-test-") as directory:
            reports = pathlib.Path(directory)
            server = SourceHTTPServer(("127.0.0.1", 0), make_handler(reports, provenance))
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
                # A second launcher must reuse this live receiver, without
                # replacing its collected report, collection ID or receipt.
                with patch("bridge_source_check.manifest", return_value=provenance):
                    serve("127.0.0.1", server.server_address[1])
                self.assertEqual((reports / "bridge-source-latest.json").read_bytes(), raw)
                self.assertEqual(json.loads(request("GET", "/status")[1])["receipt"], json.loads(receipt))
                with patch("bridge_source_check.manifest", return_value=dict(provenance, fileSha256={"fixture": "different-source"})):
                    with self.assertRaises(RuntimeError):
                        serve("127.0.0.1", server.server_address[1])
                self.assertEqual(request("GET", "/status")[0], 200)
                self.assertEqual((reports / "bridge-source-latest.json").read_bytes(), raw)
                changed = dict(fixture, timestamp="2026-09-30T12:00:01Z")
                self.assertEqual(request("POST", "/snapshot", json.dumps(changed))[0], 409)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
