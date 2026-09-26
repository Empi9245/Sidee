import importlib.util
import io
import json
import pathlib
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

    def __init__(self):
        self.headers = _Headers({
            "Host": sidee.STORE_CATALOG_HOST,
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
        self.assertFalse(sidee._is_store_discovery_host("example.com"))
        self.assertFalse(sidee._is_store_discovery_host("api-gps-em.hismarttv.com"))

        previous = sidee.STORE_DISCOVERY_REPORT
        sidee.STORE_DISCOVERY_REPORT = None
        try:
            with mock.patch.object(sidee, "write_session_report"), \
                 mock.patch.object(sidee, "queue_report_sync") as sync:
                sidee._record_store_domain_query("appstore-vidaa.vidaahub.com", 1)
                snapshot = sidee._record_store_domain_query("appstore-vidaa.vidaahub.com", 28)
                sidee._record_store_domain_query("example.com", 1)

            discovery = snapshot["storeDomainDiscovery"]
            self.assertEqual(discovery["status"], "QUERIES_CAPTURED")
            self.assertEqual(discovery["hostCount"], 1)
            self.assertEqual(discovery["hosts"][0]["host"], "appstore-vidaa.vidaahub.com")
            self.assertEqual(discovery["hosts"][0]["qtypes"], ["A", "AAAA"])
            self.assertEqual(discovery["hosts"][0]["queryCount"], 2)
            self.assertEqual(sync.call_count, 2)
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
                sidee._record_store_domain_query("appstore-vidaa.vidaahub.com", 1)
                trace_snapshot = sidee._record_store_trace(
                    "DNS_A", {"host": sidee.STORE_CATALOG_HOST}
                )
                discovery_snapshot = sidee._record_store_domain_query(
                    "appstore-vidaa.vidaahub.com", 28
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

    def test_config_spoofs_store_host(self):
        cfg = sidee.load_config()
        self.assertIn(sidee.STORE_CATALOG_HOST, cfg["spoof_domains"])


if __name__ == "__main__":
    unittest.main()
