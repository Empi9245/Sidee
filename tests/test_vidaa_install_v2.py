import http.client
import json
import pathlib
import shutil
import ssl
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

import vidaa_install_v2 as v2


class InstallReceiverTests(unittest.TestCase):
    def setUp(self):
        self.target = {"appId": "nuviodebug", "appName": "Nuvio TV",
                       "appUrl": "http://192.168.1.5:4173/?wrapper=vidaa",
                       "iconUrl": "http://192.168.1.5:4173/assets/images/icon.png",
                       "storeType": "store",
                       "identityMd5": "f31ae32083f6dc690241c46ad36b9526"}
        self.provenance = {"collectionId": "fixture", "buildId": "fixture-build",
                           "fileSha256": {"fixture": "hash"}, "mode": v2.MODE,
                           "target": self.target}

    def report(self, phase, origin):
        outcomes = {"probe": "READ_OK_WRITE_PRIMITIVE_PRESENT",
                    "install": "ALL_WRITE_PATHS_FAILED", "verify": "ENTRY_PERSISTED"}
        report = {"kind": "vidaa-install-v2", "phase": phase,
                  "timestamp": "2026-10-01T12:00:00Z", "collectionId": "fixture",
                  "clientBuildId": "fixture-build", "outcome": outcomes[phase],
                  "userAgent": "VIDAA test", "accessContext": {
                      "origin": origin, "hostname": "127.0.0.1",
                      "protocol": "https:" if origin.startswith("https") else "http:",
                      "secureContext": origin.startswith("https")}}
        if phase == "probe":
            report["capabilities"] = {"Hisense_FileRead": True, "Hisense_FileWrite": True}
            report["registryBefore"] = {"content": '{"AppInfo":[]}', "bytes": 14, "entryCount": 0}
        if phase == "install":
            report["appEntry"] = {"Id": self.target["appId"], "AppName": self.target["appName"],
                                  "URL": self.target["appUrl"], "StartCommand": self.target["appUrl"],
                                  "Type": "Browser", "StoreType": self.target["storeType"],
                                  "InstallTime": "2026-10-01"}
        return report

    def test_target_comes_from_sidee_config(self):
        self.assertEqual(v2.target_profile(), self.target)
        manifest = v2.manifest()
        self.assertEqual(manifest["target"], self.target)
        self.assertEqual(manifest["mode"], v2.MODE)

    def test_schema_rejects_wrong_phase_origin_target_and_naive_time(self):
        origin = "http://127.0.0.1:8084"
        valid = self.report("install", origin)
        self.assertEqual(v2.sanitize(valid, self.provenance, origin)["outcome"], "ALL_WRITE_PATHS_FAILED")
        cases = []
        wrong_outcome = dict(valid, outcome="ENTRY_PERSISTED")
        cases.append(wrong_outcome)
        wrong_time = dict(valid, timestamp="2026-10-01T12:00:00")
        cases.append(wrong_time)
        wrong_target = json.loads(json.dumps(valid))
        wrong_target["appEntry"]["URL"] = "http://other.invalid/"
        cases.append(wrong_target)
        for report in cases:
            with self.subTest(report=report), self.assertRaises(ValueError):
                v2.sanitize(report, self.provenance, origin)
        with self.assertRaises(ValueError):
            v2.sanitize(valid, self.provenance, "http://other.invalid")

    def test_pkgmgr_channel_fields_are_preserved(self):
        origin = "http://127.0.0.1:8084"
        report = self.report("install", origin)
        report["outcome"] = "ONLY_PKG_REGISTER_CALLED_UNVERIFIED"
        report["identifierProvenance"] = {
            "getIdentifierSource": "function() { return window.vowOSContext.getAppIdentifier() }",
            "nativeContextResult": '""',
            "navigatorAppIdentifier": {"hasGetter": True, "hasSetter": False}}
        report["pkgmgrObservation"] = {"status": "CALLED", "pkgCount": 2,
                                       "pkgNames": ["tv.vidaa.app.tvbrowser", "tv.vidaa.app.phoenix"]}
        report["identifierLab"] = {"identifiersTried": ["", "tv.vidaa.app.tvbrowser"],
                                   "writeSucceeded": True, "registerSucceeded": False,
                                   "baseline503": "client request permission check error, please check appconfig"}
        cleaned = v2.sanitize(report, self.provenance, origin)
        self.assertEqual(cleaned["outcome"], "ONLY_PKG_REGISTER_CALLED_UNVERIFIED")
        self.assertEqual(cleaned["pkgmgrObservation"]["pkgNames"][0], "tv.vidaa.app.tvbrowser")
        self.assertIn("vowOSContext", cleaned["identifierProvenance"]["getIdentifierSource"])
        self.assertEqual(cleaned["identifierLab"]["identifiersTried"][1], "tv.vidaa.app.tvbrowser")
        self.assertIs(cleaned["identifierLab"]["writeSucceeded"], True)

    def test_http_serves_build_and_persists_all_three_phases(self):
        with tempfile.TemporaryDirectory(prefix="sidee-install-v2-") as directory:
            reports = pathlib.Path(directory)
            server = v2.InstallHTTPServer(("127.0.0.1", 0), v2.make_handler(reports, self.provenance))
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            origin = "http://127.0.0.1:" + str(server.server_address[1])

            def request(method, path, body=None, headers=None):
                connection = http.client.HTTPConnection(*server.server_address, timeout=3)
                connection.request(method, path, body, headers or {})
                response = connection.getresponse()
                result = response.status, response.read()
                connection.close()
                return result

            try:
                status, html = request("GET", "/")
                self.assertEqual(status, 200)
                self.assertIn(b"vidaa-install-v2.js?v=fixture-build", html)
                self.assertEqual(request("GET", "/status", headers={"Host": "other.invalid"})[0], 400)
                receipts = []
                for phase in ("probe", "install", "verify"):
                    report = self.report(phase, origin)
                    status, raw = request("POST", "/snapshot", json.dumps(report),
                                          {"Origin": origin, "Content-Type": "application/json"})
                    self.assertEqual(status, 200)
                    receipts.append(json.loads(raw))
                self.assertEqual(len(list(reports.glob("vidaa-install-v2-*-*.json"))), 3)
                latest = json.loads((reports / "vidaa-install-v2-latest.json").read_text())
                self.assertEqual(latest["phase"], "verify")
                status_payload = json.loads(request("GET", "/status")[1])
                self.assertEqual(status_payload["receipt"], receipts[-1])
                self.assertEqual(request("POST", "/snapshot", "{}",
                                         {"Origin": "http://other.invalid", "Content-Type": "application/json"})[0], 403)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=3)

    def test_shared_receipts_across_handlers(self):
        with tempfile.TemporaryDirectory(prefix="sidee-install-v2-") as directory:
            reports = pathlib.Path(directory)
            shared = {}
            servers = []
            for _ in range(2):
                server = v2.InstallHTTPServer(("127.0.0.1", 0),
                                              v2.make_handler(reports, self.provenance, shared))
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                servers.append((server, worker))
            origin_a = "http://127.0.0.1:" + str(servers[0][0].server_address[1])
            try:
                connection = http.client.HTTPConnection(*servers[0][0].server_address, timeout=3)
                connection.request("POST", "/snapshot", json.dumps(self.report("probe", origin_a)),
                                   {"Origin": origin_a, "Content-Type": "application/json"})
                self.assertEqual(connection.getresponse().status, 200)
                connection.close()
                connection = http.client.HTTPConnection(*servers[1][0].server_address, timeout=3)
                connection.request("GET", "/status")
                payload = json.loads(connection.getresponse().read())
                connection.close()
                self.assertEqual(payload["receipt"]["phase"], "probe",
                                 "le ricevute devono essere condivise tra HTTP e HTTPS")
            finally:
                for server, worker in servers:
                    server.shutdown()
                    server.server_close()

    def test_https_serves_page_and_shares_receipts(self):
        if shutil.which("openssl") is None:
            self.skipTest("openssl non disponibile")
        with tempfile.TemporaryDirectory(prefix="sidee-install-v2-") as directory:
            reports = pathlib.Path(directory)
            cert = pathlib.Path(directory) / "test.crt"
            key = pathlib.Path(directory) / "test.key"
            subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                            "-keyout", str(key), "-out", str(cert), "-days", "1",
                            "-subj", "/CN=127.0.0.1"], check=True, capture_output=True)
            shared = {}
            server = v2.InstallHTTPServer(("127.0.0.1", 0),
                                          v2.make_handler(reports, self.provenance, shared))
            v2.wrap_tls(server, cert, key)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            origin = "https://127.0.0.1:" + str(server.server_address[1])
            client = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            client.check_hostname = False
            client.verify_mode = ssl.CERT_NONE
            try:
                connection = http.client.HTTPSConnection(*server.server_address, context=client, timeout=3)
                connection.request("GET", "/")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                html = response.read()
                connection.close()
                self.assertIn(b"vidaa-install-v2.js?v=fixture-build", html)
                connection = http.client.HTTPSConnection(*server.server_address, context=client, timeout=3)
                connection.request("POST", "/snapshot", json.dumps(self.report("probe", origin)),
                                   {"Origin": origin, "Content-Type": "application/json"})
                self.assertEqual(connection.getresponse().status, 200)
                connection.close()
                self.assertEqual(shared["latest"]["phase"], "probe")
                self.assertEqual(shared["latest"]["origin"], origin)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=3)

    def test_expected_origin_default_port_follows_scheme(self):
        with tempfile.TemporaryDirectory(prefix="sidee-install-v2-") as directory:
            handler_class = v2.make_handler(pathlib.Path(directory), self.provenance)
            import email.message
            stub = type("StubServer", (), {})()
            for scheme, port, host_header, valid in (
                    ("https", 443, "vidaahub.com", True),
                    ("http", 80, "vidaahub.com", True),
                    ("https", 443, "vidaahub.com:443", True),
                    ("https", 443, "vidaahub.com:80", False),
                    ("http", 8080, "vidaahub.com", False),
                    ("https", 443, "other.invalid", False)):
                message = email.message.Message()
                message["Host"] = host_header
                handler = object.__new__(handler_class)
                handler.headers = message
                stub.scheme = scheme
                stub.server_address = ("192.168.1.5", port)
                handler.server = stub
                if valid:
                    self.assertEqual(handler.expected_origin(), scheme + "://" + host_header)
                else:
                    with self.assertRaises(ValueError):
                        handler.expected_origin()

    def test_sidee_routes_full_installer_as_an_isolated_mode(self):
        import sidee
        with patch("sys.argv", ["sidee.py", "--vidaa-install-v2"]), \
                patch("sidee.get_local_ip", return_value="127.0.0.1"), \
                patch("sidee.load_config", return_value={}), \
                patch("vidaa_install_v2.serve") as receiver, \
                patch("sidee.configure_report_sync", side_effect=AssertionError("normal worker called")):
            sidee.main()
            receiver.assert_called_once_with("127.0.0.1", 80)
        with patch("sys.argv", ["sidee.py", "--vidaa-install-v2", "--vidaa-check-v2"]), \
                patch("sidee.load_config", side_effect=AssertionError("configuration unexpectedly loaded")):
            with self.assertRaises(SystemExit) as failure:
                sidee.main()
            self.assertEqual(failure.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
