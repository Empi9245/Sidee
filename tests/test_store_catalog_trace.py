import importlib.util
import io
import json
import pathlib
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sidee", ROOT / "sidee.py")
sidee = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sidee)


class _Headers(dict):
    def items(self):
        return super().items()


class _UpstreamResponse:
    status = 200
    reason = "OK"

    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def getheaders(self):
        return [
            ("Content-Type", "application/json"),
            ("Cache-Control", "max-age=60"),
            ("Set-Cookie", "opaque=do-not-log"),
        ]

    def getheader(self, name, default=""):
        values = dict(self.getheaders())
        return values.get(name, default)


class _Connection:
    last = None

    def __init__(self, *args, **kwargs):
        self.init_args = (args, kwargs)
        self.request_args = None
        self.response = _UpstreamResponse(json.dumps({
            "data": [{
                "id": 2446,
                "signatureServer": "must-not-appear",
                "appInfo": {
                    "url": "https://example.test/app/index.html?token=must-not-appear",
                    "openMode": "99",
                    "unifiedAppName": "2446",
                    "packaged": 0,
                    "appBundle": "",
                },
            }]
        }).encode("utf-8"))
        _Connection.last = self

    def request(self, method, path, body=None, headers=None):
        self.request_args = (method, path, body, headers)

    def getresponse(self):
        return self.response

    def close(self):
        pass


class _Handler:
    command = "GET"
    path = "/api/v1.0.0/categoryApi/categoryFirstResult?country=ITA&token=secret"

    def __init__(self, host=None):
        self.headers = _Headers({
            "Host": host or sidee.STORE_CATALOG_HOST,
            "Authorization": "Bearer forwarded-but-never-logged",
            "Cookie": "sid=forwarded-but-never-logged",
            "Accept": "application/json",
        })
        self.rfile = io.BytesIO()
        self.wfile = io.BytesIO()
        self.sent_status = None
        self.sent_headers = []

    def send_response(self, status, reason=None):
        self.sent_status = status

    def send_response_only(self, status, reason=None):
        self.sent_status = status

    def send_header(self, key, value):
        self.sent_headers.append((key, value))

    def end_headers(self):
        pass


class StoreCatalogTraceTests(unittest.TestCase):
    def test_json_summary_redacts_sensitive_values(self):
        body = json.dumps({
            "resultCode": 0,
            "categoryRoute": "featured",
            "signatureServer": "secret-signature",
            "items": [{
                "id": "1470",
                "appInfo": {
                    "url": "https://example.test/app?token=hidden",
                    "openMode": "98",
                    "unifiedAppName": "1470",
                    "packaged": 0,
                },
            }],
        }).encode("utf-8")
        summary = sidee._catalog_json_summary(body, "application/json", "")
        encoded = json.dumps(summary)
        self.assertNotIn("secret-signature", encoded)
        self.assertNotIn("hidden", encoded)
        self.assertIn("signatureServer", summary["redactedKeyNames"])
        self.assertEqual(summary["resultCode"], 0)
        self.assertIn("categoryRoute", summary["routeCategoryKeys"])
        self.assertEqual(summary["catalogApps"][0]["unifiedAppName"], "1470")
        self.assertEqual(summary["catalogApps"][0]["url"]["host"], "example.test")

    def test_proxy_passes_body_unchanged_and_logs_names_only(self):
        handler = _Handler()
        events = []

        def record(event, detail=None):
            events.append((event, detail or {}))
            return {}

        with mock.patch.object(sidee.http.client, "HTTPSConnection", _Connection), \
             mock.patch.object(sidee, "_record_store_trace", record):
            sidee._proxy_store_catalog_request(handler)

        upstream_body = _Connection.last.response._body
        self.assertEqual(handler.wfile.getvalue(), upstream_body)
        method, path, body, headers = _Connection.last.request_args
        self.assertEqual(method, "GET")
        self.assertEqual(path, handler.path)
        self.assertEqual(headers["Authorization"], "Bearer forwarded-but-never-logged")
        self.assertEqual(headers["Cookie"], "sid=forwarded-but-never-logged")

        response_event = [detail for event, detail in events if event == "HTTP_RESPONSE"][0]
        serialized = json.dumps(response_event)
        self.assertEqual(response_event["queryParameterNames"], ["country", "token"])
        self.assertNotIn("forwarded-but-never-logged", serialized)
        self.assertNotIn("secret", serialized)
        self.assertNotIn("must-not-appear", serialized)
        self.assertEqual(response_event["jsonSummary"]["catalogApps"][0]["url"]["host"], "example.test")

    def test_proxy_routes_each_observed_store_host_to_matching_upstream(self):
        for host in (
            "category-ui-eu.vidaahub.com",
            "detail-ui-eu.vidaahub.com",
            "appstore-vidaa.vidaahub.com",
            "tvmodules-vidaa.vidaahub.com",
        ):
            handler = _Handler(host)
            events = []

            def record(event, detail=None):
                events.append((event, detail or {}))
                return {}

            with mock.patch.object(sidee.http.client, "HTTPSConnection", _Connection), \
                 mock.patch.object(sidee, "_record_store_trace", record):
                sidee._proxy_store_catalog_request(handler)

            self.assertEqual(_Connection.last.init_args[0][0], host)
            self.assertEqual(_Connection.last.request_args[3]["Host"], host)
            begin = [detail for event, detail in events if event == "HTTP_BEGIN"][0]
            response = [detail for event, detail in events if event == "HTTP_RESPONSE"][0]
            self.assertEqual(begin["host"], host)
            self.assertEqual(response["host"], host)

    def test_event_trace_records_bounded_transport_events_and_redacts_errors(self):
        previous = sidee.STORE_TRACE_REPORT
        sidee.STORE_TRACE_REPORT = None
        try:
            with mock.patch.object(sidee, "write_session_report"), \
                 mock.patch.object(sidee, "queue_report_sync"):
                sidee._record_store_trace("DNS_A", {"host": sidee.STORE_CATALOG_HOST})
                sidee._record_store_trace("TLS_SNI", {"host": sidee.STORE_CATALOG_HOST})
                sidee._record_store_trace("HTTP_BEGIN", {
                    "host": sidee.STORE_CATALOG_HOST,
                    "method": "GET",
                    "path": "/api/v1.0.0/categoryApi/categoryFirstResult",
                    "queryParameterNames": ["country", "token"],
                })
                sidee._record_store_trace("HTTP_RESPONSE", {
                    "host": sidee.STORE_CATALOG_HOST,
                    "method": "GET",
                    "path": "/api/v1.0.0/categoryApi/categoryFirstResult",
                    "queryParameterNames": ["country", "token"],
                    "upstreamStatus": 200,
                    "contentType": "application/json",
                    "responseLength": 123,
                    "jsonSummary": {"resultCode": 0},
                })
                snapshot = sidee._record_store_trace("PROXY_ERROR", {
                    "host": sidee.STORE_CATALOG_HOST,
                    "stage": "upstream",
                    "method": "GET",
                    "path": "/detail",
                    "errorType": "RuntimeError",
                    "message": "authorization=topsecret Bearer anothersecret token=thirdsecret",
                })

            trace = snapshot["storeCatalogTrace"]
            self.assertEqual(
                [event["type"] for event in trace["events"]],
                ["DNS", "TLS_SNI", "HTTP_REQUEST", "HTTP_RESPONSE", "PROXY_ERROR"],
            )
            self.assertLessEqual(len(trace["events"]), sidee.STORE_TRACE_MAX_EVENTS)
            self.assertEqual(trace["events"][2]["queryParameterNames"], ["country", "token"])
            self.assertEqual(trace["events"][3]["upstreamStatus"], 200)
            self.assertEqual(
                trace["hostStats"][sidee.STORE_CATALOG_HOST]["status"],
                "PROXY_ERROR",
            )
            self.assertEqual(
                trace["hostStats"][sidee.STORE_CATALOG_HOST]["requestCount"],
                1,
            )
            serialized = json.dumps(trace)
            self.assertNotIn("topsecret", serialized)
            self.assertNotIn("anothersecret", serialized)
            self.assertNotIn("thirdsecret", serialized)
            self.assertIn("<redacted>", trace["errors"][-1]["message"])
        finally:
            sidee.STORE_TRACE_REPORT = previous

    def test_store_domain_discovery_is_vendor_scoped_and_deduped(self):
        self.assertTrue(sidee._is_store_discovery_host("appstore-vidaa.vidaahub.com"))
        self.assertTrue(sidee._is_store_discovery_host("vidaa-base-auth-oc.vidaahub.com"))
        self.assertTrue(sidee._is_store_discovery_host("api-launcher-em.hismarttv.com"))
        self.assertTrue(sidee._is_store_discovery_host("auth-launcher-na.hismarttv.com"))
        self.assertTrue(sidee._is_store_discovery_host("app-appstore.hismarttv.com"))
        self.assertFalse(sidee._is_store_discovery_host("example.com"))
        self.assertFalse(sidee._is_store_discovery_host("api-gps-em.hismarttv.com"))

        previous = sidee.STORE_DISCOVERY_REPORT
        sidee.STORE_DISCOVERY_REPORT = None
        try:
            with mock.patch.object(sidee, "write_session_report"), \
                 mock.patch.object(sidee, "queue_report_sync") as sync:
                sidee._record_store_domain_query("home-ui-eu.vidaahub.com", 1)
                snapshot = sidee._record_store_domain_query("home-ui-eu.vidaahub.com", 28)
                sidee._record_store_domain_query("example.com", 1)

            discovery = snapshot["storeDomainDiscovery"]
            self.assertEqual(discovery["status"], "QUERIES_CAPTURED")
            self.assertEqual(discovery["hostCount"], 1)
            self.assertEqual(discovery["hosts"][0]["host"], "home-ui-eu.vidaahub.com")
            self.assertEqual(discovery["hosts"][0]["qtypes"], ["A", "AAAA"])
            self.assertEqual(discovery["hosts"][0]["queryCount"], 2)
            self.assertEqual(sync.call_count, 2)
        finally:
            sidee.STORE_DISCOVERY_REPORT = previous

    def test_store_hosts_can_be_recorded_by_passive_discovery(self):
        previous = sidee.STORE_DISCOVERY_REPORT
        sidee.STORE_DISCOVERY_REPORT = None
        try:
            with mock.patch.object(sidee, "write_session_report"), \
                 mock.patch.object(sidee, "queue_report_sync"):
                snapshot = sidee._record_store_domain_query(
                    "detail-ui-eu.vidaahub.com", 1
                )
            self.assertEqual(
                snapshot["storeDomainDiscovery"]["hosts"][0]["host"],
                "detail-ui-eu.vidaahub.com",
            )
        finally:
            sidee.STORE_DISCOVERY_REPORT = previous

    def test_store_trace_and_domain_discovery_cross_correlate(self):
        previous_trace = sidee.STORE_TRACE_REPORT
        previous_discovery = sidee.STORE_DISCOVERY_REPORT
        sidee.STORE_TRACE_REPORT = None
        sidee.STORE_DISCOVERY_REPORT = None
        try:
            with mock.patch.object(sidee, "write_session_report"), \
                 mock.patch.object(sidee, "queue_report_sync"):
                sidee._record_store_domain_query("home-ui-eu.vidaahub.com", 1)
                trace_snapshot = sidee._record_store_trace(
                    "DNS_A", {"host": sidee.STORE_CATALOG_HOST}
                )
                discovery_snapshot = sidee._record_store_domain_query(
                    "home-ui-eu.vidaahub.com", 28
                )

            self.assertEqual(
                trace_snapshot["storeDomainDiscovery"]["status"],
                "QUERIES_CAPTURED",
            )
            self.assertEqual(
                discovery_snapshot["storeCatalogTrace"]["status"],
                "DNS_ONLY",
            )
            self.assertEqual(
                discovery_snapshot["summary"]["storeCatalogTrace"],
                "DNS_ONLY",
            )
            self.assertEqual(
                trace_snapshot["summary"]["storeDomainDiscovery"],
                "QUERIES_CAPTURED",
            )
        finally:
            sidee.STORE_TRACE_REPORT = previous_trace
            sidee.STORE_DISCOVERY_REPORT = previous_discovery

    def test_network_capture_text_summary_detects_https_full_path(self):
        sample = """
12:00:00.000 PktGroupId 1, OriginalSize 120, LoggedSize 120
        192.168.137.22.51000 > 203.0.113.10.443: Flags [S], length 0
12:00:00.100 PktGroupId 2, OriginalSize 1500, LoggedSize 1500
        203.0.113.10.443 > 192.168.137.22.51000: Flags [.], length 1448
12:00:00.200 PktGroupId 3, OriginalSize 1400, LoggedSize 1400
        192.168.137.22.51000 > 203.0.113.10.443: Flags [.], length 1348
12:00:00.300 PktGroupId 4, OriginalSize 1400, LoggedSize 1400
        203.0.113.10.443 > 192.168.137.22.51000: Flags [.], length 1348
12:00:00.400 PktGroupId 5, OriginalSize 1400, LoggedSize 1400
        203.0.113.10.443 > 192.168.137.22.51000: Flags [.], length 1348
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "capture.txt"
            path.write_text(sample, encoding="utf-8")
            summary = sidee._network_capture_parse_text(path, "192.168.137.22")

        self.assertEqual(summary["packetRecords"], 5)
        self.assertEqual(summary["httpsPacketRecords"], 5)
        self.assertEqual(summary["topologyClassification"], "FULL_PATH_VISIBLE")
        self.assertEqual(summary["topPeers"][0]["ip"], "203.0.113.10")
        self.assertEqual(summary["topPeers"][0]["ports"]["443"], 5)

    def test_network_capture_preflight_stops_sidee_filter_without_english_status(self):
        calls = []

        def command(args, timeout=20):
            calls.append(tuple(args))
            if args == ["filter", "list"]:
                seen = sum(1 for item in calls if item == ("filter", "list"))
                return (0, "1 Sidee-TV IPv4") if seen == 1 else (0, "")
            if args == ["status"]:
                return 0, "Parametri logger:\nFile di log: C:\\Temp\\legacy.etl"
            if args == ["stop"]:
                return 0, "Arresto raccolta dati completato."
            if args == ["filter", "remove"]:
                return 0, ""
            raise AssertionError(args)

        with mock.patch.object(sidee.os, "name", "nt"), \
             mock.patch.object(sidee.shutil, "which", return_value="pktmon.exe"), \
             mock.patch.object(sidee, "_network_capture_cmd", side_effect=command):
            result = sidee._network_capture_preflight()

        self.assertTrue(result["staleSideeCaptureStopped"])
        self.assertTrue(result["staleSideeFilterCleared"])
        self.assertLess(calls.index(("stop",)), calls.index(("filter", "remove")))

    def test_network_capture_preflight_recovers_orphaned_sidee_etl_without_filter(self):
        calls = []

        def command(args, timeout=20):
            calls.append(tuple(args))
            if args == ["filter", "list"]:
                return 0, ""
            if args == ["status"]:
                return (
                    0,
                    "Parametri logger:\n"
                    "File di log: C:\\work\\Sidee\\captures\\"
                    "sidee-net-20260929-164556\\sidee-net-20260929-164556.etl",
                )
            if args == ["stop"]:
                return 0, "Arrestato."
            raise AssertionError(args)

        with mock.patch.object(sidee.os, "name", "nt"), \
             mock.patch.object(sidee.shutil, "which", return_value="pktmon.exe"), \
             mock.patch.object(sidee, "_network_capture_cmd", side_effect=command):
            result = sidee._network_capture_preflight()

        self.assertTrue(result["sideeOwnedEtlDetected"])
        self.assertTrue(result["staleSideeCaptureStopped"])
        self.assertIn(("stop",), calls)

    def test_network_capture_preflight_preserves_unrelated_active_etl(self):
        calls = []

        def command(args, timeout=20):
            calls.append(tuple(args))
            if args == ["filter", "list"]:
                return 0, ""
            if args == ["status"]:
                return 0, "Log file: C:\\captures\\other-tool.etl"
            raise AssertionError(args)

        with mock.patch.object(sidee.os, "name", "nt"), \
             mock.patch.object(sidee.shutil, "which", return_value="pktmon.exe"), \
             mock.patch.object(sidee, "_network_capture_cmd", side_effect=command):
            with self.assertRaisesRegex(RuntimeError, "not owned by Sidee"):
                sidee._network_capture_preflight()

        self.assertNotIn(("stop",), calls)
        self.assertNotIn(("filter", "remove"), calls)

    def test_network_capture_public_state_hides_tv_ip(self):
        previous = dict(sidee.NETWORK_CAPTURE_STATE)
        try:
            sidee.NETWORK_CAPTURE_STATE.update({
                "status": "CAPTURING",
                "tvIp": "192.168.137.22",
                "tvClientBound": True,
            })
            public = sidee._network_capture_public_state()
            self.assertNotIn("tvIp", public)
            self.assertTrue(public["tvClientBound"])
        finally:
            sidee.NETWORK_CAPTURE_STATE.clear()
            sidee.NETWORK_CAPTURE_STATE.update(previous)

    def test_store_static_extract_finds_api_paths_and_install_metadata(self):
        html = """
        <html>
          <head>
            <script src="https://static-ui.vidaahub.com/store/main.js"></script>
          </head>
          <body>
            <script>
              const endpoint = "/api/v1.0.0/appApi/installApplication";
              const meta = {
                configUrlDownload: "https://appstore-vidaa.vidaahub.com/download/app.json",
                productCode: "1876",
                appBundle: "duplecast"
              };
            </script>
          </body>
        </html>
        """
        result = sidee._store_static_extract({
            "host": "home-ui-eu.vidaahub.com",
            "path": "/",
            "status": 200,
            "contentType": "text/html",
            "bytes": len(html),
            "truncated": False,
            "sha256": "0" * 64,
            "location": None,
            "text": html,
        })
        self.assertIn(
            "/api/v1.0.0/appApi/installApplication",
            result["apiPaths"],
        )
        self.assertIn(
            "https://static-ui.vidaahub.com/store/main.js",
            result["assetRefs"],
        )
        keywords = {item["keyword"] for item in result["keywordHits"]}
        self.assertIn("installApplication", keywords)
        self.assertIn("configUrlDownload", keywords)
        self.assertIn("productCode", keywords)
        self.assertIn("appBundle", keywords)

    def test_store_install_probe_isolates_post_install_dns_activity(self):
        previous = sidee.STORE_DISCOVERY_REPORT
        sidee.STORE_DISCOVERY_REPORT = None
        try:
            with mock.patch.object(sidee, "write_session_report"), \
                 mock.patch.object(sidee, "queue_report_sync"):
                started = sidee._store_install_probe_mark("START")
                self.assertEqual(
                    started["storeInstallProbe"]["status"],
                    "CAPTURING_NAVIGATION",
                )

                sidee._record_store_domain_query("home-ui-eu.vidaahub.com", 1)
                sidee._record_store_domain_query("detail-ui-eu.vidaahub.com", 1)
                detail = sidee._store_install_probe_mark("DETAIL_OPEN")
                self.assertIn(
                    "detail-ui-eu.vidaahub.com",
                    detail["storeInstallProbe"]["hostSnapshotAtDetail"],
                )

                armed = sidee._store_install_probe_mark("ARM_INSTALL")
                self.assertEqual(
                    armed["storeInstallProbe"]["status"],
                    "INSTALL_ARMED",
                )
                self.assertIn(
                    "detail-ui-eu.vidaahub.com",
                    armed["storeInstallProbe"]["hostSnapshotAtInstallArm"],
                )

                sidee._record_store_domain_query("detail-ui-eu.vidaahub.com", 1)
                sidee._record_store_domain_query("appstore-vidaa.vidaahub.com", 1)
                finished = sidee._store_install_probe_mark("FINISH")

            probe = finished["storeInstallProbe"]
            self.assertEqual(probe["status"], "COMPLETED")
            self.assertEqual(
                probe["newHostsAfterInstallArm"],
                ["appstore-vidaa.vidaahub.com"],
            )
            self.assertEqual(
                probe["contactedAfterInstallArm"],
                [
                    "appstore-vidaa.vidaahub.com",
                    "detail-ui-eu.vidaahub.com",
                ],
            )
            deltas = {
                item["host"]: item["queries"]
                for item in probe["queryDeltaAfterInstallArm"]
            }
            self.assertEqual(deltas["appstore-vidaa.vidaahub.com"], 1)
            self.assertEqual(deltas["detail-ui-eu.vidaahub.com"], 1)
            install_events = [
                item for item in probe["dnsEvents"]
                if item["phase"] == "INSTALL_WINDOW"
            ]
            self.assertEqual(len(install_events), 2)
        finally:
            sidee.STORE_DISCOVERY_REPORT = previous

    def test_store_install_probe_requires_arm_before_finish(self):
        previous = sidee.STORE_DISCOVERY_REPORT
        sidee.STORE_DISCOVERY_REPORT = None
        try:
            with mock.patch.object(sidee, "write_session_report"), \
                 mock.patch.object(sidee, "queue_report_sync"):
                sidee._store_install_probe_mark("START")
                with self.assertRaises(ValueError):
                    sidee._store_install_probe_mark("FINISH")
        finally:
            sidee.STORE_DISCOVERY_REPORT = previous

    def test_config_does_not_spoof_store_hosts_by_default(self):
        cfg = sidee.load_config()
        for host in sidee.STORE_TRACE_HOSTS:
            self.assertNotIn(host, cfg["spoof_domains"])
        self.assertNotIn("vidaa.duplecast.com", cfg["spoof_domains"])

    def test_store_trace_hosts_are_present_in_default_snapshot(self):
        previous = sidee.STORE_TRACE_REPORT
        sidee.STORE_TRACE_REPORT = None
        try:
            snapshot = sidee._store_trace_snapshot()
            self.assertEqual(snapshot["hosts"], list(sidee.STORE_TRACE_HOSTS))
            self.assertEqual(
                set(snapshot["hostStats"].keys()),
                set(sidee.STORE_TRACE_HOSTS),
            )
            self.assertTrue(all(
                item["status"] == "IDLE"
                for item in snapshot["hostStats"].values()
            ))
        finally:
            sidee.STORE_TRACE_REPORT = previous


if __name__ == "__main__":
    unittest.main()
