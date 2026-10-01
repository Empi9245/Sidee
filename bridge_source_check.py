"""Isolated receiver for already-loaded browser source. No TV native commands."""
from __future__ import annotations

import datetime
import errno
import hashlib
import http.client
import http.server
import ipaddress
import json
import os
import pathlib
import re
import shutil
import socket
import ssl
import subprocess
import threading
import urllib.parse
import uuid

ROOT = pathlib.Path(__file__).resolve().parent
CERT_DIR = ROOT / ".sidee-certs"
PRIVATE_LITERAL = re.compile(
    r"(?:token|secret|password|cookie|authorization|signature|credential|api[_-]?key)"
    r"[\"']?\s*[:=]\s*[\"'`][^\"'`\r\n]+[\"'`]|Bearer\s+[A-Za-z0-9._~+/\-]{8,}", re.I
)
STATUSES = {"SIDEE_OWNED_SKIPPED", "PRIVATE_URL_SKIPPED", "OUT_OF_SCOPE", "DENIED",
            "UNAVAILABLE", "TRUNCATED", "COMPLETE", "EMPTY", "SENSITIVE_SOURCE_OMITTED", "NOT_COLLECTED_LIMIT"}
FILES = ("bridge_source_check.py", "web/bridge-source-check.js", "web/bridge-source-check.html", "sidee.py")


def _find_openssl():
    openssl = shutil.which("openssl")
    if openssl or os.name != "nt":
        return openssl
    candidates = [
        r"C:\\Program Files\\Git\\usr\\bin\\openssl.exe",
        r"C:\\Program Files\\OpenSSL-Win64\\bin\\openssl.exe",
        r"C:\\Program Files (x86)\\OpenSSL-Win32\\bin\\openssl.exe",
    ]
    return next((path for path in candidates if os.path.isfile(path)), None)


def generate_cert():
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    cert = CERT_DIR / "bridge-source-vidaahub-v1.crt"
    key = CERT_DIR / "bridge-source-vidaahub-v1.key"
    if cert.exists() and key.exists():
        return cert, key

    openssl = _find_openssl()
    if not openssl:
        reuse_cert = CERT_DIR / "sidee-vidaa-multihost-store-v2.crt"
        reuse_key = CERT_DIR / "sidee-vidaa-multihost-store-v2.key"
        if reuse_cert.exists() and reuse_key.exists():
            return reuse_cert, reuse_key
        raise RuntimeError("OpenSSL non trovato e nessun certificato HTTPS Sidee riutilizzabile presente.")

    hosts = ["vidaahub.com", "www.vidaahub.com"]
    san = ",".join("DNS:" + host for host in hosts)
    cmd = [
        openssl, "req", "-x509", "-newkey", "rsa:2048",
        "-keyout", str(key), "-out", str(cert), "-days", "30", "-nodes",
        "-subj", "/CN=vidaahub.com",
        "-addext", "subjectAltName=" + san,
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        config = CERT_DIR / "bridge-source-openssl.cnf"
        config.write_text(
            "[req]\n"
            "distinguished_name = dn\n"
            "prompt = no\n"
            "x509_extensions = v3_req\n"
            "[dn]\n"
            "CN = vidaahub.com\n"
            "[v3_req]\n"
            "subjectAltName = @alt_names\n"
            "[alt_names]\n"
            "DNS.1 = vidaahub.com\n"
            "DNS.2 = www.vidaahub.com\n",
            encoding="utf-8",
        )
        fallback = [
            openssl, "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", str(key), "-out", str(cert), "-days", "30", "-nodes",
            "-config", str(config), "-extensions", "v3_req",
        ]
        subprocess.run(fallback, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return cert, key


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
                       "No SDK loading or Git report upload.",
                       "Local DNS/TLS/browser context is an observation path, not proof of TV service trust."]}


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
            self.server.record_access(self.client_address[0], self.headers.get('Host', ''), 'GET', path)
            if path in ("/", "/bridge-source-check.html"):
                return self.reply(200, html, "text/html; charset=utf-8")
            if path == "/bridge-source-check.js":
                return self.reply(200, script, "application/javascript")
            if path == "/manifest":
                return self.reply(200, provenance)
            if path == "/status":
                return self.reply(200, {"mode": "isolated-bridge-source-check", "provenance": provenance,
                                        "transport": self.server.scheme, "receipt": latest,
                                        "httpAccess": self.server.access_snapshot()})
            self.reply(404, {"error": "Not found"})

        def do_POST(self):
            nonlocal latest, submitted
            self.server.record_access(self.client_address[0], self.headers.get('Host', ''), 'POST',
                                      urllib.parse.urlsplit(self.path).path)
            if self.path != "/snapshot":
                return self.reply(404, {"error": "Not found"})
            origin = self.headers.get("Origin")
            expected_origin = self.server.scheme + "://" + self.headers.get("Host", "")
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
                payload["receiverContext"] = {"transport": self.server.scheme, "hostHeader": self.headers.get("Host"), "originHeader": origin}
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


class SourceHTTPServer(http.server.ThreadingHTTPServer):
    # Windows SO_REUSEADDR can let two receivers share a port unpredictably.
    allow_reuse_address = os.name != "nt"

    def __init__(self, address, handler, access_path=None):
        self.access_path = access_path
        self.scheme = "http"
        self.access_lock = threading.Lock()
        self.access_clients = {}
        super().__init__(address, handler)

    def record_access(self, client, host='', method=None, path=None):
        try:
            address = ipaddress.ip_address(client)
        except ValueError:
            return
        if not address.is_private:
            return
        allowed_paths = {'/', '/bridge-source-check.html', '/bridge-source-check.js', '/manifest', '/status', '/snapshot'}
        allowed_hosts = {'vidaahub.com', 'vidaahub.com:80', 'vidaahub.com:443', self.server_address[0],
                         self.server_address[0] + ':' + str(self.server_address[1])}
        with self.access_lock:
            if client not in self.access_clients and len(self.access_clients) >= 32:
                return
            item = self.access_clients.setdefault(client, {'connections': 0, 'requests': 0, 'paths': {}})
            if method is None:
                item['connections'] += 1
            else:
                item['requests'] += 1
                item['lastMethod'] = method
                item['lastPath'] = path if path in allowed_paths else '[OTHER]'
                item['lastHost'] = host if host in allowed_hosts else '[OTHER]'
                item['paths'][item['lastPath']] = item['paths'].get(item['lastPath'], 0) + 1
            item['lastAt'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            if self.access_path is not None:
                saved = {'mode': 'isolated-collector-http-access', 'transport': self.scheme, 'pid': os.getpid(),
                         'bind': list(self.server_address), 'clients': self.access_clients,
                         'scope': 'Passive own receiver access; no body, query, cookies, TLS capture or TV API.'}
                try:
                    self.access_path.parent.mkdir(parents=True, exist_ok=True)
                    temporary = self.access_path.with_suffix('.tmp')
                    temporary.write_text(json.dumps(saved, indent=2) + '\n', encoding='utf-8')
                    temporary.replace(self.access_path)
                except OSError:
                    # Diagnostics must not prevent delivery of the collector.
                    pass

    def access_snapshot(self):
        with self.access_lock:
            return {client: dict(item, paths=dict(item['paths'])) for client, item in self.access_clients.items()}

    def get_request(self):
        connection, address = super().get_request()
        self.record_access(address[0])
        return connection, address

    def server_bind(self):
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def enable_https(server, cert, key):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(cert), keyfile=str(key))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.scheme = "https"
    return server


def _status_connection(host, port, use_https):
    if use_https:
        return http.client.HTTPSConnection(host, port, timeout=3, context=ssl._create_unverified_context())
    return http.client.HTTPConnection(host, port, timeout=3)


def serve(host, port=8082, *, use_https=False, cert=None, key=None):
    provenance = manifest()
    if use_https:
        cert, key = (cert, key) if cert and key else generate_cert()
    try:
        server = SourceHTTPServer((host, port), make_handler(ROOT / "reports", provenance),
                                  ROOT / 'reports/bridge-domain-http-status.json')
        if use_https:
            enable_https(server, cert, key)
    except OSError as exc:
        if exc.errno != errno.EADDRINUSE and getattr(exc, "winerror", None) != 10048:
            raise
        connection = _status_connection(host, port, use_https)
        try:
            connection.request("GET", "/status")
            response = connection.getresponse()
            raw = response.read(64 * 1024 + 1)
            if response.status != 200 or len(raw) > 64 * 1024:
                raise ValueError("Unknown receiver")
            active = json.loads(raw)
            if (active.get("mode") != "isolated-bridge-source-check" or
                    active.get("provenance", {}).get("fileSha256") != provenance["fileSha256"]):
                raise ValueError("Different service or collector build")
        except (OSError, ValueError, AttributeError, http.client.HTTPException) as error:
            raise RuntimeError(f"Porta {port} occupata da un altro servizio o collector diverso. Nessun processo fermato.") from error
        finally:
            connection.close()
        print("[BRIDGE-SOURCE] Collector gia attivo: raccolta e ricevuta correnti preservate.", flush=True)
        return
    scheme = "https" if use_https else "http"
    if use_https and port == 443:
        entry = "https://vidaahub.com/"
    elif not use_https and port == 80:
        entry = "http://vidaahub.com/"
    else:
        entry = f"{scheme}://{host}:{port}/bridge-source-check.html"
    print(f"[BRIDGE-SOURCE] Receiver {entry}", flush=True)
    if use_https:
        print(f"[BRIDGE-SOURCE] HTTPS certificate: {cert}", flush=True)
    print("[BRIDGE-SOURCE] Explicit single collection only. No SDK/native/Git workers.", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
