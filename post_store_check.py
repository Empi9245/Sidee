"""Isolated Sidee inventory receiver. No DNS, sync workers or TV write paths."""
from __future__ import annotations

import datetime
import http.server
import json
import pathlib
import threading

ROOT = pathlib.Path(__file__).resolve().parent
MAX_BODY = 512 * 1024


def make_handler(report_dir: pathlib.Path):
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
            path = self.path.split("?", 1)[0]
            if path in ("/", "/post-store-check.html", "/post-store-check.js"):
                filename = "post-store-check.js" if path.endswith(".js") else "post-store-check.html"
                content_type = "application/javascript" if filename.endswith(".js") else "text/html; charset=utf-8"
                return self.reply(200, (ROOT / "web" / filename).read_bytes(), content_type)
            if path == "/status":
                with lock:
                    target = report_dir / "post-store-latest.json"
                    latest = json.loads(target.read_text(encoding="utf-8")) if target.exists() else None
                return self.reply(200, json.dumps({"mode": "post-store-check", "latest": latest}).encode())
            self.reply(404, b'{"error":"Not found"}')

        def do_POST(self):
            if self.path != "/snapshot":
                return self.reply(404, b'{"error":"Not found"}')
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + self.headers.get("Host", ""):
                return self.reply(403, b'{"error":"Origin mismatch"}')
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > MAX_BODY:
                    raise ValueError("Invalid size")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict) or data.get("kind") != "post-store-inventory-v1" or data.get("readOnly") is not True:
                    raise ValueError("Invalid inventory")
                if not isinstance(data.get("apps"), dict) or not isinstance(data.get("packages"), dict):
                    raise ValueError("Missing inventory sections")
            except (ValueError, TypeError):
                return self.reply(400, b'{"error":"Invalid inventory"}')
            data["receivedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            data["receiverMode"] = "isolated-post-store-check"
            data["receiverContext"] = {
                "transport": "http",
                "hostHeader": self.headers.get("Host", ""),
                "originHeader": origin,
            }
            payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
            with lock:
                report_dir.mkdir(parents=True, exist_ok=True)
                stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
                (report_dir / f"post-store-{stamp}.json").write_text(payload, encoding="utf-8")
                temporary = report_dir / "post-store-latest.tmp"
                temporary.write_text(payload, encoding="utf-8")
                temporary.replace(report_dir / "post-store-latest.json")
            print("[POST-STORE] Inventory received; no TV mutation or installation verified.", flush=True)
            self.reply(200, b'{"ok":true}')

    return Handler


def serve(host: str, port: int):
    server = http.server.ThreadingHTTPServer((host, port), make_handler(ROOT / "reports"))
    print(f"[POST-STORE] http://{host}:{port}/post-store-check.html", flush=True)
    print("[POST-STORE] Inventory only. No DNS, Git workers, install/write/capture endpoints.", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
