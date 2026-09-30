"""Isolated receiver for already-loaded browser source. No TV native commands."""
from __future__ import annotations

import datetime
import hashlib
import http.server
import json
import pathlib
import re
import subprocess
import threading
import urllib.parse
import uuid

ROOT = pathlib.Path(__file__).resolve().parent
PRIVATE_LITERAL = re.compile(
    r"(?:token|secret|password|cookie|authorization|signature|credential|api[_-]?key)"
    r"[\"']?\s*[:=]\s*[\"'`][^\"'`\r\n]+[\"'`]|Bearer\s+[A-Za-z0-9._~+/\-]{8,}", re.I
)
STATUSES = {"SIDEE_OWNED_SKIPPED", "PRIVATE_URL_SKIPPED", "OUT_OF_SCOPE", "DENIED",
            "UNAVAILABLE", "TRUNCATED", "COMPLETE", "EMPTY", "SENSITIVE_SOURCE_OMITTED", "NOT_COLLECTED_LIMIT"}
FILES = ("bridge_source_check.py", "web/bridge-source-check.js", "web/bridge-source-check.html", "sidee.py")


def manifest():
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES}
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, timeout=3, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", *FILES], cwd=ROOT,
                               capture_output=True, text=True, timeout=3, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        head, dirty = None, None
    return {"collectionId": "bridge-" + uuid.uuid4().hex,
            "buildId": "bridge-" + hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:16],
            "fileSha256": hashes, "gitHead": head, "collectorDirty": bool(dirty) if dirty is not None else None,
            "firmwareReference": {"value": "V0000.09.60A.Q0707", "provenance": "historical; not read by this collector"}}


def sanitize(data, provenance):
    if not isinstance(data, dict) or data.get("kind") != "loaded-bridge-source-v1" or data.get("readOnly") is not True:
        raise ValueError("Wrong schema")
    if data.get("collectionId") != provenance["collectionId"] or data.get("clientBuildId") != provenance["buildId"]:
        raise ValueError("Collection/build mismatch")
    context = data.get("accessContext")
    if not isinstance(context, dict) or context.get("protocol") not in ("http:", "https:"):
        raise ValueError("Invalid context")
    origin = urllib.parse.urlsplit(context.get("origin", ""))
    if origin.username or origin.password or origin.query or origin.fragment or origin.path not in ("", "/"):
        raise ValueError("Private/invalid origin")
    if not origin.hostname or origin.hostname != context.get("hostname") or origin.scheme + ":" != context["protocol"]:
        raise ValueError("Inconsistent context")
    entries = data.get("sources")
    discovery = data.get("discovery")
    if not isinstance(entries, list) or len(entries) > 64 or not isinstance(discovery, dict):
        raise ValueError("Invalid sources")
    sources, total = [], 0
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("status") not in STATUSES:
            raise ValueError("Invalid status")
        if entry.get("observedVia") not in ("document.scripts", "performance.resource"):
            raise ValueError("Unobserved source")
        url = entry.get("url")
        if url is not None:
            parsed = urllib.parse.urlsplit(url)
            if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("Invalid source URL")
        item = {key: entry.get(key) for key in ("url", "observedVia", "inline", "status", "observedQueryOmitted")}
        if entry.get("scheme") in {"http:", "https:", "file:", "data:", "blob:", "javascript:"}:
            item["scheme"] = entry["scheme"]
        for key in ("httpStatus", "receivedBytes"):
            if key in entry and type(entry[key]) is int and 0 <= entry[key] <= 1024 * 1024:
                item[key] = entry[key]
        if entry.get("reason") in {"BOUNDED_STREAM_UNAVAILABLE", "INVALID_OR_SPLIT_UTF8", "TIMEOUT", "NETWORK_CORS_OR_TLS", "INLINE_TOO_LARGE"}:
            item["reason"] = entry["reason"]
        source = entry.get("source")
        if source is not None:
            if not isinstance(source, str) or entry["status"] not in {"COMPLETE", "TRUNCATED", "EMPTY"}:
                raise ValueError("Invalid source body")
            if url and not (url.startswith(data["accessContext"]["origin"] + "/") or parsed.hostname == "tvmodules-vidaa.vidaahub.com"):
                raise ValueError("Source outside scope")
            raw = source.encode("utf-8")
            if len(raw) > 1024 * 1024:
                raise ValueError("Source too large")
            if PRIVATE_LITERAL.search(source):
                item["status"] = "SENSITIVE_SOURCE_OMITTED"
                item["complete"] = False
            else:
                total += len(raw)
                item.update(source=source, sha256=hashlib.sha256(raw).hexdigest(), storedUtf8Bytes=len(raw),
                            complete=entry["status"] in {"COMPLETE", "EMPTY"}, hashRepresentation="decoded-source-utf8")
        elif entry["status"] in {"COMPLETE", "EMPTY"}:
            raise ValueError("Complete source without body")
        sources.append(item)
    if total > 4 * 1024 * 1024:
        raise ValueError("Total source limit")
    ua = data.get("userAgent", "")
    if not isinstance(ua, str) or PRIVATE_LITERAL.search(ua):
        raise ValueError("Invalid user agent")
    timestamp = data.get("timestamp")
    if not isinstance(timestamp, str) or len(timestamp) > 40:
        raise ValueError("Invalid timestamp")
    datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    non_owned = [item for item in sources if item["status"] != "SIDEE_OWNED_SKIPPED"]
    return {"kind": "loaded-bridge-source-v1", "readOnly": True, "timestamp": timestamp,
            "provenance": provenance, "clientBuildId": data["clientBuildId"], "buildMatch": True,
            "accessContext": {key: context.get(key) for key in ("origin", "hostname", "protocol", "secureContext")},
            "preferredContextObserved": origin.hostname == "vidaahub.com", "userAgent": ua[:500],
            "clientDeviceHint": "TV_LIKE" if re.search(r"VIDAA|Hisense|SmartTV|Smart-TV", ua, re.I) else "UNCONFIRMED",
            "discovery": {key: discovery.get(key) for key in ("timingStatus", "timingCount", "eligibleCount", "enumerationTruncated")
                          if isinstance(discovery.get(key), (str, int, bool, type(None)))},
            "sources": sources, "storedSourceBytes": total,
            "outcome": "OBSERVED_SOURCES" if non_owned else "NO_NON_SIDEE_SCRIPT_OBSERVED",
            "limits": ["Client context and user agent are reported by the page, not TV attestation.",
                       "Only the current page; no other-process, native-code or full-firmware coverage.",
                       "No native operations or install/launcher/resource persistence test.",
                       "No DNS, TLS impersonation, SDK loading or Git report upload.",
                       "HTTP vidaahub differs from the historical HTTPS context; LAN is a separate observation."]}


def make_handler(report_dir, provenance=None):
    provenance = provenance or manifest()
    lock = threading.Lock()
    latest = None
    submitted = None
    html = (ROOT / "web/bridge-source-check.html").read_text(encoding="utf-8").replace(
        '/bridge-source-check.js"', '/bridge-source-check.js?v=' + provenance["buildId"] + '"').encode()
    script = (ROOT / "web/bridge-source-check.js").read_bytes()

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, code, data, content_type="application/json"):
            body = data if isinstance(data, bytes) else json.dumps(data).encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Sidee-Build", provenance["buildId"])
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urllib.parse.urlsplit(self.path).path
            if path in ("/", "/bridge-source-check.html"):
                return self.reply(200, html, "text/html; charset=utf-8")
            if path == "/bridge-source-check.js":
                return self.reply(200, script, "application/javascript")
            if path == "/manifest":
                return self.reply(200, provenance)
            if path == "/status":
                return self.reply(200, {"mode": "isolated-bridge-source-check", "provenance": provenance, "receipt": latest})
            self.reply(404, {"error": "Not found"})

        def do_POST(self):
            nonlocal latest, submitted
            if self.path != "/snapshot":
                return self.reply(404, {"error": "Not found"})
            origin = self.headers.get("Origin")
            expected_origin = "http://" + self.headers.get("Host", "")
            if origin != expected_origin:
                return self.reply(403, {"error": "Origin mismatch"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 16 * 1024 * 1024 or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    raise ValueError("Invalid body")
                raw = self.rfile.read(size)
                payload = sanitize(json.loads(raw), provenance)
                if payload["accessContext"]["origin"] != expected_origin:
                    raise ValueError("Reported origin mismatch")
            except (ValueError, TypeError, KeyError, UnicodeError):
                return self.reply(400, {"error": "Invalid source report"})
            input_hash = hashlib.sha256(raw).hexdigest()
            with lock:
                if submitted is not None:
                    if input_hash == submitted:
                        return self.reply(200, latest)
                    return self.reply(409, {"error": "Single collection already received"})
                payload["receivedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                payload["receiverContext"] = {"transport": "http", "hostHeader": self.headers.get("Host"), "originHeader": origin}
                saved = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode()
                report_dir.mkdir(parents=True, exist_ok=True)
                stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
                filename = "bridge-source-" + stamp + ".json"
                (report_dir / filename).write_bytes(saved)
                temporary = report_dir / "bridge-source-latest.tmp"
                temporary.write_bytes(saved)
                temporary.replace(report_dir / "bridge-source-latest.json")
                latest = {"file": filename, "sha256": hashlib.sha256(saved).hexdigest(), "bytes": len(saved),
                          "receivedAt": payload["receivedAt"], "origin": payload["accessContext"]["origin"],
                          "preferredContextObserved": payload["preferredContextObserved"], "outcome": payload["outcome"],
                          "clientDeviceHint": payload["clientDeviceHint"],
                          "sourceStates": [item["status"] for item in payload["sources"]]}
                submitted = input_hash
            print("[BRIDGE-SOURCE] Single collection received; " + latest["outcome"], flush=True)
            self.reply(200, latest)

    return Handler


def serve(host, port=8082):
    server = http.server.ThreadingHTTPServer((host, port), make_handler(ROOT / "reports"))
    print(f"[BRIDGE-SOURCE] Receiver http://{host}:{port}/bridge-source-check.html", flush=True)
    print("[BRIDGE-SOURCE] Explicit single collection only. No DNS/TLS/SDK/native/Git workers.", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
