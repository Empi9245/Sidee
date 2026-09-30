"""Serve the existing Nuvio build with isolated, bounded TV acceptance telemetry."""
from __future__ import annotations

import argparse
import datetime
import hashlib
import http.server
import json
import mimetypes
import pathlib
import threading
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent
MAX_BODY = 32 * 1024
FIELDS = {"timestamp", "session", "userAgent", "secureContext", "displayMode", "platform",
          "serviceWorkerApi", "serviceWorkerControlled", "manifestPresent",
          "installSignal", "storageMarker", "navigation", "ui", "errorCounts"}


def build_receipt(dist):
    files = {}
    for name in ("index.html", "app.bundle.js", "manifest.json", "sw.js"):
        data = (dist / name).read_bytes()
        files[name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    return {"dist": str(dist), "files": files,
            "telemetrySha256": hashlib.sha256((ROOT / "web/nuvio-tv-check.js").read_bytes()).hexdigest()}


def sanitize(value, depth=0):
    if depth > 5:
        return None
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:120]
    if isinstance(value, list):
        return [sanitize(item, depth + 1) for item in value[:24]]
    if isinstance(value, dict):
        return {str(key)[:40]: sanitize(item, depth + 1) for key, item in list(value.items())[:24]}
    return None


def make_handler(dist, report_dir, receipt):
    lock = threading.Lock()

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, code, body, content_type="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
            if path == "/__sidee/status":
                with lock:
                    target = report_dir / "nuvio-tv-check-latest.json"
                    latest = json.loads(target.read_text(encoding="utf-8")) if target.exists() else None
                return self.reply(200, json.dumps({"mode": "nuvio-tv-check", "build": receipt, "latest": latest}).encode())
            if path == "/__sidee/observer.js":
                return self.reply(200, (ROOT / "web/nuvio-tv-check.js").read_bytes(), "application/javascript")
            if path.startswith("/__sidee/"):
                return self.reply(404, b'{}')
            candidate = (dist / (path.lstrip("/") or "index.html")).resolve()
            if not candidate.is_relative_to(dist) or not candidate.is_file():
                return self.reply(404, b'{}')
            body = candidate.read_bytes()
            if candidate == dist / "index.html":
                body = body.replace(b"<head>", b'<head><script src="/__sidee/observer.js"></script>', 1)
            content_type = mimetypes.guess_type(str(candidate))[0] or "application/octet-stream"
            self.reply(200, body, content_type)

        def do_POST(self):
            if self.path != "/__sidee/observation":
                return self.reply(404, b'{}')
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + self.headers.get("Host", ""):
                return self.reply(403, b'{}')
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY:
                    raise ValueError()
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict) or data.get("kind") != "nuvio-tv-observation-v1":
                    raise ValueError()
            except (ValueError, TypeError):
                return self.reply(400, b'{}')
            result = {"kind": "nuvio-tv-observation-v1",
                      "observation": sanitize({key: data[key] for key in FIELDS if key in data}),
                      "receivedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      "build": receipt,
                      "limits": ["UI/keys observed in this launch; no native installation inferred.",
                                 "Own localStorage marker is not app-resource persistence.",
                                 "Insecure origin makes negative PWA observations inconclusive.",
                                 "No AppConfig, inventory, SDK injection, DNS/TLS or TV-file operations.",
                                 "Real launcher/reboot/server-off/playback require separate observed trials."]}
            payload = json.dumps(result, ensure_ascii=False, indent=2)
            with lock:
                report_dir.mkdir(parents=True, exist_ok=True)
                temporary = report_dir / "nuvio-tv-check-latest.tmp"
                temporary.write_text(payload, encoding="utf-8")
                temporary.replace(report_dir / "nuvio-tv-check-latest.json")
            self.reply(200, b'{"ok":true}')

    return Handler


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=8181)
    parser.add_argument("--dist", type=pathlib.Path, required=True)
    args = parser.parse_args()
    dist = args.dist.resolve()
    receipt = build_receipt(dist)
    server = http.server.ThreadingHTTPServer((args.host, args.port), make_handler(dist, ROOT / "reports", receipt))
    print(f"[NUVIO-TV] http://{args.host}:{args.port}/?wrapper=vidaa", flush=True)
    print("[NUVIO-TV] Existing Nuvio build + observations. No install or VIDAA privileged calls.", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
