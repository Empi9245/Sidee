"""Isolated VIDAA readiness receiver kept alongside the full v2 installer.

Collects browser descriptors and explicitly reported acceptance observations.
No native API execution, registry reads/writes, installation, DNS or TLS setup.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import http.client
import http.server
import ipaddress
import json
import os
import pathlib
import socket
import subprocess
import threading
import urllib.parse
import uuid

ROOT = pathlib.Path(__file__).resolve().parent
FILES = ("vidaa_readiness_v2.py", "web/vidaa-readiness-v2.js", "web/vidaa-readiness-v2.html")
MODE = "isolated-vidaa-readiness-v2"
KIND = "vidaa-readiness-v2"
OBSERVATIONS = ("launcher", "remote", "persisted", "pcOff", "playback")
CAPABILITIES = ("fetch", "Promise", "URL", "AbortController", "TextEncoder", "localStorage",
                "serviceWorker", "Hisense_GetModelName", "Hisense_GetFirmWareVersion", "Hisense_GetOSVersion")
DESCRIPTOR_STATES = {"function", "object", "absent", "accessor", "other", "unknown"}
MAX_BODY = 16 * 1024


def target_profile():
    try:
        value = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))["nuvio"]
        # Only names are exposed. No credentials, destination URL or configuration workers.
        return {"appId": str(value.get("app_id", ""))[:80],
                "appName": str(value.get("app_name", "Nuvio"))[:80]}
    except (OSError, ValueError, KeyError, TypeError):
        return {"appId": "", "appName": "Nuvio"}


def manifest():
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES}
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, timeout=3, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        head = None
    return {"collectionId": "vidaa-v2-" + uuid.uuid4().hex,
            "buildId": "vidaa-v2-" + hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()[:16],
            "fileSha256": hashes, "gitHead": head, "mode": MODE, "readOnly": True,
            "target": target_profile()}


def sanitize(data, provenance, expected_origin):
    if not isinstance(data, dict) or data.get("kind") != KIND or data.get("readOnly") is not True:
        raise ValueError("Wrong schema")
    if data.get("collectionId") != provenance["collectionId"] or data.get("clientBuildId") != provenance["buildId"]:
        raise ValueError("Collection/build mismatch")
    phase = data.get("phase")
    if phase not in {"probe", "observe", "verify"}:
        raise ValueError("Invalid phase")
    context = data.get("accessContext")
    if not isinstance(context, dict) or context.get("origin") != expected_origin:
        raise ValueError("Origin mismatch")
    timestamp = data.get("timestamp")
    if not isinstance(timestamp, str) or len(timestamp) > 40:
        raise ValueError("Invalid timestamp")
    parsed_time = datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if parsed_time.utcoffset() is None:
        raise ValueError("Timestamp must include timezone")
    payload = {"kind": KIND, "readOnly": True, "phase": phase, "timestamp": timestamp,
               "provenance": provenance, "clientBuildId": data["clientBuildId"], "buildMatch": True,
               "accessContext": {"origin": expected_origin, "secureContext": context.get("secureContext") is True},
               "nativeApisInvoked": False, "installationVerified": False}
    if phase == "probe":
        caps = data.get("capabilities")
        if not isinstance(caps, dict) or set(caps) != set(CAPABILITIES):
            raise ValueError("Invalid capability names")
        if any(not isinstance(value, str) or value not in DESCRIPTOR_STATES for value in caps.values()):
            raise ValueError("Invalid descriptor state")
        payload["capabilities"] = dict(caps)
        payload["outcome"] = "BROWSER_DESCRIPTORS_RECORDED"
        payload["evidenceSource"] = "current-page-property-descriptors"
    else:
        observations = data.get("observations")
        if not isinstance(observations, dict) or set(observations) != set(OBSERVATIONS):
            raise ValueError("Invalid observations")
        if any(not isinstance(value, str) or value not in {"yes", "no", "unknown"} for value in observations.values()):
            raise ValueError("Invalid observation value")
        reboot = data.get("rebootConfirmed")
        if type(reboot) is not bool or (phase == "verify" and reboot is not True):
            raise ValueError("A reboot declaration is required for the post-reboot phase")
        payload["observations"] = dict(observations)
        payload["rebootConfirmed"] = reboot
        payload["evidenceSource"] = "manual-user-observation"
        complete = all(value == "yes" for value in observations.values())
        payload["outcome"] = "ACCEPTANCE_REPORTED" if phase == "verify" and complete else "OBSERVATIONS_INCOMPLETE"
    return payload


class ReadinessHTTPServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = os.name != "nt"
    daemon_threads = True

    def server_bind(self):
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def make_handler(report_dir, provenance=None):
    provenance = provenance or manifest()
    lock = threading.Lock()
    latest = None
    html = (ROOT / "web/vidaa-readiness-v2.html").read_text(encoding="utf-8").replace(
        '/vidaa-readiness-v2.js"', '/vidaa-readiness-v2.js?v=' + provenance["buildId"] + '"').encode()
    script = (ROOT / "web/vidaa-readiness-v2.js").read_bytes()

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def origin(self):
            host = self.headers.get("Host", "")
            parsed = urllib.parse.urlsplit("http://" + host)
            allowed = {self.server.server_address[0]}
            if ipaddress.ip_address(self.server.server_address[0]).is_loopback:
                allowed.update({"localhost", "127.0.0.1"})
            if (parsed.hostname not in allowed or parsed.username or parsed.password or parsed.path or
                    parsed.query or parsed.fragment or (parsed.port or 80) != self.server.server_address[1]):
                raise ValueError("Invalid host")
            return "http://" + host

        def reply(self, code, data, content_type="application/json"):
            body = data if isinstance(data, bytes) else json.dumps(data).encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            try:
                self.origin()
            except (ValueError, TypeError):
                return self.reply(400, {"error": "Invalid host"})
            path = urllib.parse.urlsplit(self.path).path
            if path in ("/", "/vidaa-readiness-v2.html"):
                return self.reply(200, html, "text/html; charset=utf-8")
            if path == "/vidaa-readiness-v2.js":
                return self.reply(200, script, "application/javascript; charset=utf-8")
            if path == "/manifest":
                return self.reply(200, provenance)
            if path == "/status":
                with lock:
                    receipt = dict(latest) if latest else None
                return self.reply(200, {"mode": MODE, "provenance": provenance, "receipt": receipt})
            return self.reply(404, {"error": "Not found"})

        def do_POST(self):
            nonlocal latest
            if self.path != "/snapshot":
                return self.reply(404, {"error": "Not found"})
            try:
                origin = self.origin()
                if self.headers.get("Origin") != origin:
                    return self.reply(403, {"error": "Origin mismatch"})
                size = int(self.headers.get("Content-Length", "0"))
                if (not 0 < size <= MAX_BODY or self.headers.get("Transfer-Encoding") or
                        self.headers.get("Content-Type", "").split(";")[0] != "application/json"):
                    raise ValueError("Invalid body")
                raw = self.rfile.read(size)
                if len(raw) != size:
                    raise ValueError("Incomplete body")
                payload = sanitize(json.loads(raw), provenance, origin)
            except (ValueError, TypeError, KeyError, UnicodeError, OSError):
                return self.reply(400, {"error": "Invalid readiness report"})
            with lock:
                payload["receivedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                saved = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode()
                stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
                filename = "vidaa-v2-" + payload["phase"] + "-" + stamp + ".json"
                try:
                    report_dir.mkdir(parents=True, exist_ok=True)
                    (report_dir / filename).write_bytes(saved)
                    temporary = report_dir / "vidaa-v2-latest.tmp"
                    temporary.write_bytes(saved)
                    temporary.replace(report_dir / "vidaa-v2-latest.json")
                except OSError:
                    return self.reply(503, {"error": "Report storage unavailable"})
                latest = {"file": filename, "sha256": hashlib.sha256(saved).hexdigest(),
                          "phase": payload["phase"], "outcome": payload["outcome"],
                          "receivedAt": payload["receivedAt"], "installationVerified": False}
                receipt = dict(latest)
            self.reply(200, receipt)

    return Handler


def serve(host="127.0.0.1", port=8083, report_dir=None):
    if not 0 <= port <= 65535:
        raise ValueError("Invalid port")
    ipaddress.ip_address(host)
    provenance = manifest()
    try:
        server = ReadinessHTTPServer((host, port), make_handler(report_dir or ROOT / "reports", provenance))
    except OSError as error:
        if getattr(error, "winerror", None) != 10048 and error.errno not in (98, 48):
            raise
        connection = http.client.HTTPConnection(host, port, timeout=3)
        try:
            connection.request("GET", "/status")
            response = connection.getresponse()
            raw = response.read(64 * 1024 + 1)
            active = json.loads(raw)
            if (response.status != 200 or len(raw) > 64 * 1024 or active.get("mode") != MODE or
                    active.get("provenance", {}).get("fileSha256") != provenance["fileSha256"] or
                    active.get("provenance", {}).get("target") != provenance["target"]):
                raise ValueError("Different receiver")
        except (OSError, ValueError, AttributeError, http.client.HTTPException) as exc:
            raise RuntimeError(f"Porta {port} occupata da un altro servizio; nessun processo fermato.") from exc
        finally:
            connection.close()
        print("[VIDAA-V2] Ricevitore della stessa versione gia attivo; report conservati.", flush=True)
        return
    print(f"[VIDAA-V2] Verifica in sola lettura: http://{host}:{server.server_address[1]}/", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="Sidee VIDAA v2: diagnostica browser e osservazioni manuali")
    parser.add_argument("--host", default="127.0.0.1", help="IP locale del ricevitore")
    parser.add_argument("--port", type=int, default=8083)
    args = parser.parse_args()
    serve(args.host, args.port)


if __name__ == "__main__":
    main()
