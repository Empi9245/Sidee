import copy
import http.client
import json
import pathlib
import tempfile
import threading
import unittest
from unittest.mock import patch

import vidaa_readiness_v2 as v2


class ReadinessReceiverTests(unittest.TestCase):
    def setUp(self):
        self.provenance = {"collectionId": "fixture", "buildId": "fixture-build",
                           "fileSha256": {"fixture": "hash"}, "target": {"appName": "Nuvio", "appId": "test"}}
        self.origin = "http://127.0.0.1:8083"

    def report(self, phase="probe"):
        report = {"kind": v2.KIND, "readOnly": True, "phase": phase,
                  "timestamp": "2026-10-01T12:00:00Z", "collectionId": "fixture",
                  "clientBuildId": "fixture-build", "accessContext": {"origin": self.origin, "secureContext": True}}
        if phase == "probe":
            report["capabilities"] = {name: "absent" for name in v2.CAPABILITIES}
        else:
            report["observations"] = {name: "yes" for name in v2.OBSERVATIONS}
            report["rebootConfirmed"] = phase == "verify"
        return report

    def test_manual_acceptance_never_becomes_native_installation_proof(self):
        result = v2.sanitize(self.report("verify"), self.provenance, self.origin)
        self.assertEqual(result["outcome"], "ACCEPTANCE_REPORTED")
        self.assertEqual(result["evidenceSource"], "manual-user-observation")
        self.assertIs(result["installationVerified"], False)
        self.assertIs(result["nativeApisInvoked"], False)
        report = self.report("verify")
        report["observations"]["pcOff"] = "unknown"
        self.assertEqual(v2.sanitize(report, self.provenance, self.origin)["outcome"], "OBSERVATIONS_INCOMPLETE")
        self.assertEqual(v2.sanitize(self.report("observe"), self.provenance, self.origin)["outcome"], "OBSERVATIONS_INCOMPLETE")

    def test_schema_build_origin_and_reboot_are_required(self):
        for field, value in (("kind", "vidaa-install-v2"), ("phase", "install"),
                             ("collectionId", "old"), ("clientBuildId", "old"),
                             ("readOnly", False), ("timestamp", "2026-10-01T12:00:00")):
            report = self.report()
            report[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                v2.sanitize(report, self.provenance, self.origin)
        report = self.report("verify")
        report["rebootConfirmed"] = False
        with self.assertRaises(ValueError):
            v2.sanitize(report, self.provenance, self.origin)
        report = self.report()
        report["accessContext"]["origin"] = "http://other.invalid"
        with self.assertRaises(ValueError):
            v2.sanitize(report, self.provenance, self.origin)

    def test_fields_are_strict_and_private_extras_are_omitted(self):
        report = self.report()
        report["rawRegistry"] = "token=private"
        result = v2.sanitize(report, self.provenance, self.origin)
        self.assertNotIn("private", json.dumps(result))
        report["capabilities"]["arbitrary"] = "function"
        with self.assertRaises(ValueError):
            v2.sanitize(report, self.provenance, self.origin)
        report = self.report("observe")
        report["observations"]["launcher"] = True
        with self.assertRaises(ValueError):
            v2.sanitize(report, self.provenance, self.origin)

    def test_http_history_isolation_validation_and_reuse(self):
        with tempfile.TemporaryDirectory(prefix="sidee-v2-test-") as directory:
            reports = pathlib.Path(directory)
            server = v2.ReadinessHTTPServer(("127.0.0.1", 0), v2.make_handler(reports, self.provenance))
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            origin = "http://127.0.0.1:" + str(server.server_address[1])

            def request(method, target, body=None, headers=None):
                conn = http.client.HTTPConnection(*server.server_address, timeout=3)
                conn.request(method, target, body, headers or {})
                response = conn.getresponse()
                result = response.status, response.read()
                conn.close()
                return result

            try:
                status, html = request("GET", "/")
                self.assertEqual(status, 200)
                self.assertIn(b"vidaa-readiness-v2.js?v=fixture-build", html)
                self.assertEqual(request("GET", "/../config.json")[0], 404)
                self.assertEqual(request("GET", "/api/config")[0], 404)
                self.assertEqual(request("GET", "/status", headers={"Host": "vidaahub.com"})[0], 400)
                headers = {"Origin": origin, "Content-Type": "application/json"}
                receipts = []
                for phase in ("probe", "observe", "verify"):
                    report = self.report(phase)
                    report["accessContext"]["origin"] = origin
                    status, body = request("POST", "/snapshot", json.dumps(report), headers)
                    self.assertEqual(status, 200)
                    receipts.append(json.loads(body))
                self.assertEqual(len(list(reports.glob("vidaa-v2-*-*.json"))), 3)
                latest = json.loads((reports / "vidaa-v2-latest.json").read_text())
                self.assertEqual(latest["phase"], "verify")
                self.assertIs(latest["installationVerified"], False)
                self.assertEqual(request("POST", "/snapshot", "{}", {"Origin": "http://other.invalid"})[0], 403)
                self.assertEqual(request("POST", "/snapshot", "{}", headers)[0], 400)
                with patch("vidaa_readiness_v2.manifest", return_value=self.provenance):
                    v2.serve("127.0.0.1", server.server_address[1])
                changed = dict(self.provenance, fileSha256={"fixture": "different"})
                with patch("vidaa_readiness_v2.manifest", return_value=changed):
                    with self.assertRaisesRegex(RuntimeError, "nessun processo fermato"):
                        v2.serve("127.0.0.1", server.server_address[1])
                self.assertEqual(json.loads(request("GET", "/status")[1])["receipt"], receipts[-1])
                with patch.object(pathlib.Path, "write_bytes", side_effect=OSError("locked report")):
                    report = self.report()
                    report["accessContext"]["origin"] = origin
                    self.assertEqual(request("POST", "/snapshot", json.dumps(report), headers)[0], 503)
                self.assertEqual(json.loads(request("GET", "/status")[1])["receipt"], receipts[-1])
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=3)

    def test_main_routes_to_new_mode_without_normal_workers(self):
        import sidee
        with patch("sys.argv", ["sidee.py", "--vidaa-check-v2"]), \
                patch("sidee.get_local_ip", return_value="127.0.0.1"), \
                patch("sidee.load_config", return_value={}), \
                patch("vidaa_readiness_v2.serve") as receiver, \
                patch("sidee.configure_report_sync", side_effect=AssertionError("normal worker called")):
            sidee.main()
            receiver.assert_called_once_with("127.0.0.1", 8083)
        for other in ("--bridge-source-check", "--post-store-check", "--check-https"):
            with patch("sys.argv", ["sidee.py", "--vidaa-check-v2", other]), \
                    patch("sidee.load_config", side_effect=AssertionError("configuration unexpectedly loaded")):
                with self.assertRaises(SystemExit) as failure:
                    sidee.main()
                self.assertEqual(failure.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
