import http.client
import json
import pathlib
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
                       "storeType": "store"}
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
                      "origin": origin, "hostname": "127.0.0.1", "protocol": "http:",
                      "secureContext": False}}
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
