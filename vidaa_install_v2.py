"""Ricevitore isolato per l'installazione VIDAA v2.

Serve la pagina web/vidaa-install-v2.html alla radice (per il canale
http://vidaahub.com/ gia' instradato dalla TV) e riceve i report delle tre fasi
probe/install/verify su POST /snapshot. Ogni report e' salvato in reports/ con
timestamp; reports/vidaa-install-v2-latest.json punta all'ultimo.

Differenza dal collector bridge-source: qui sono ammesse piu' sottomissioni
(le fasi sono tre e attraversano un riavvio), ma ogni report e' validato,
provenienza inclusa, e nessun dato esce dal PC.

La pagina esegue operazioni native sulla TV solo dopo la pressione esplicita del
pulsante di installazione. La voce da registrare arriva da config.json, così il
ricevitore e il resto di Sidee condividono sempre lo stesso target Nuvio.
"""
from __future__ import annotations

import argparse
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
import socket
import subprocess
import threading
import urllib.parse
import uuid

ROOT = pathlib.Path(__file__).resolve().parent
PRIVATE_LITERAL = re.compile(
    r"(?:token|secret|password|cookie|authorization|signature|credential|api[_-]?key)"
    r"[\"']?\s*[:=]\s*[\"'`][^\"'`\r\n]+[\"'`]|Bearer\s+[A-Za-z0-9._~+/\-]{8,}", re.I
)
PHASES = {"probe", "install", "verify"}
OUTCOMES = {
    "READ_OK_WRITE_PRIMITIVE_PRESENT", "READ_OK_NO_WRITE_PRIMITIVE",
    "READ_FAILED_WRITE_PRIMITIVE_PRESENT", "NO_READ_NO_WRITE_PRIMITIVE",
    "READ_UNAVAILABLE_NO_INSTALL", "REGISTRY_WRITE_VERIFIED_REBOOT_REQUIRED",
    "REGISTRY_CHANGED_SINCE_PROBE",
    "ENTRY_ALREADY_PRESENT_WRITE_NOT_VERIFIED",
    "WRITE_OK_BUT_ENTRY_NOT_IN_READBACK", "ONLY_LEGACY_CALLED_UNVERIFIED",
    "ONLY_PKG_REGISTER_CALLED_UNVERIFIED",
    "ALL_WRITE_PATHS_FAILED", "READ_UNAVAILABLE", "ENTRY_PERSISTED",
    "ENTRY_ABSENT_AFTER_REBOOT", "READ_FAILED",
}
FILES = ("vidaa_install_v2.py", "web/vidaa-install-v2.js", "web/vidaa-install-v2.html", "config.json")
MAX_ATTEMPTS = 60
MAX_DETAIL = 1200
MAX_REGISTRY = 512 * 1024
MAX_BODY = 2 * 1024 * 1024
MODE = "isolated-vidaa-install-v2"


def _web_url(value, *, optional=False):
    value = str(value or "").strip()
    if optional and not value:
        return ""
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or
            parsed.password or parsed.fragment or len(value) > 500):
        raise ValueError("Invalid Nuvio URL in config.json")
    return value


def target_profile():
    data = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))["nuvio"]
    app_id = str(data.get("app_id", "")).strip()
    app_name = str(data.get("app_name", "")).strip()
    store_type = str(data.get("store_type", "custom")).strip() or "custom"
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", app_id):
        raise ValueError("Invalid nuvio.app_id in config.json")
    if not app_name or len(app_name) > 80 or any(ord(char) < 32 for char in app_name):
        raise ValueError("Invalid nuvio.app_name in config.json")
    if len(store_type) > 40 or any(ord(char) < 32 for char in store_type):
        raise ValueError("Invalid nuvio.store_type in config.json")
    return {"appId": app_id, "appName": app_name,
            "appUrl": _web_url(data.get("app_url")),
            "iconUrl": _web_url(data.get("icon_url"), optional=True),
            "storeType": store_type}


def manifest():
    hashes = {}
    for name in FILES:
        path = ROOT / name
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, timeout=3, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", *FILES], cwd=ROOT,
                               capture_output=True, text=True, timeout=3, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        head, dirty = None, None
    target = target_profile()
    build_material = {"hashes": hashes, "target": target}
    return {"collectionId": "install-v2-" + uuid.uuid4().hex,
            "buildId": "install-v2-" + hashlib.sha256(json.dumps(build_material, sort_keys=True).encode()).hexdigest()[:16],
            "fileSha256": hashes, "gitHead": head, "collectorDirty": bool(dirty) if dirty is not None else None,
            "mode": MODE, "target": target,
            "firmwareReference": {"value": "V0000.09.60A.Q0707", "provenance": "historical; not read by this receiver"}}


def _clean_context(context):
    if not isinstance(context, dict) or context.get("protocol") not in ("http:", "https:"):
        raise ValueError("Invalid context")
    origin = urllib.parse.urlsplit(context.get("origin", ""))
    if origin.username or origin.password or origin.query or origin.fragment or origin.path not in ("", "/"):
        raise ValueError("Private/invalid origin")
    if not origin.hostname or origin.hostname != context.get("hostname") or origin.scheme + ":" != context["protocol"]:
        raise ValueError("Inconsistent context")
    return {key: context.get(key) for key in ("origin", "hostname", "protocol", "secureContext")}


def _clean_attempts(value):
    if not isinstance(value, list) or len(value) > MAX_ATTEMPTS:
        raise ValueError("Invalid attempts")
    cleaned = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Invalid attempt")
        entry = {}
        for key in ("primitive", "phase", "path", "note"):
            if isinstance(item.get(key), str):
                entry[key] = item[key][:200]
        for key in ("ok", "denied", "entryPresent", "contentChanged"):
            if isinstance(item.get(key), bool):
                entry[key] = item[key]
        for key in ("mode", "bytes", "entryCount"):
            if type(item.get(key)) is int and 0 <= item[key] <= 64 * 1024 * 1024:
                entry[key] = item[key]
        for key in ("detail", "raw", "returnValue", "callbackValue", "sha256"):
            if isinstance(item.get(key), str):
                entry[key] = item[key][:MAX_DETAIL]
        cleaned.append(entry)
    return cleaned


def _clean_registry(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("Invalid registry summary")
    out = {}
    if type(value.get("bytes")) is int and 0 <= value["bytes"] <= 64 * 1024 * 1024:
        out["bytes"] = value["bytes"]
    if type(value.get("entryCount")) is int and 0 <= value["entryCount"] <= 100000:
        out["entryCount"] = value["entryCount"]
    ids = value.get("ids")
    if isinstance(ids, list):
        out["ids"] = [
            {k: (str(entry.get(k))[:120] if entry.get(k) is not None else None) for k in ("Id", "AppName", "Type")}
            for entry in ids[:100] if isinstance(entry, dict)
        ]
    if isinstance(value.get("omitted"), str):
        out["omitted"] = value["omitted"][:60]
    content = value.get("content")
    if isinstance(content, str):
        raw = content.encode("utf-8")
        if len(raw) > MAX_REGISTRY:
            out["omitted"] = "TOO_LARGE"
        elif PRIVATE_LITERAL.search(content):
            out["omitted"] = "SENSITIVE_LITERAL"
        else:
            out["content"] = content
            out["sha256"] = hashlib.sha256(raw).hexdigest()
    return out


def _clean_observation(value):
    if not isinstance(value, dict):
        return None
    out = {}
    for key, item in list(value.items())[:20]:
        name = str(key)[:60]
        if isinstance(item, str):
            out[name] = item[:MAX_DETAIL]
        elif isinstance(item, (int, bool)) or item is None:
            out[name] = item
        elif isinstance(item, list):
            out[name] = [str(entry)[:120] for entry in item[:40]]
        elif isinstance(item, dict):
            out[name] = {str(k)[:60]: str(v)[:MAX_DETAIL] for k, v in list(item.items())[:10]}
    return out


def sanitize(data, provenance, expected_origin=None):
    if not isinstance(data, dict) or data.get("kind") != "vidaa-install-v2":
        raise ValueError("Wrong schema")
    if data.get("phase") not in PHASES:
        raise ValueError("Invalid phase")
    if data.get("collectionId") != provenance["collectionId"] or data.get("clientBuildId") != provenance["buildId"]:
        raise ValueError("Collection/build mismatch")
    context = _clean_context(data.get("accessContext"))
    timestamp = data.get("timestamp")
    if not isinstance(timestamp, str) or len(timestamp) > 40:
        raise ValueError("Invalid timestamp")
    parsed_time = datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if parsed_time.utcoffset() is None:
        raise ValueError("Timestamp must include timezone")
    ua = data.get("userAgent", "")
    if not isinstance(ua, str) or PRIVATE_LITERAL.search(ua):
        raise ValueError("Invalid user agent")
    outcome = data.get("outcome")
    if outcome not in OUTCOMES:
        raise ValueError("Invalid outcome")
    phase_outcomes = {
        "probe": {"READ_OK_WRITE_PRIMITIVE_PRESENT", "READ_OK_NO_WRITE_PRIMITIVE",
                  "READ_FAILED_WRITE_PRIMITIVE_PRESENT", "NO_READ_NO_WRITE_PRIMITIVE"},
        "install": {"READ_UNAVAILABLE_NO_INSTALL", "REGISTRY_CHANGED_SINCE_PROBE",
                    "REGISTRY_WRITE_VERIFIED_REBOOT_REQUIRED", "ENTRY_ALREADY_PRESENT_WRITE_NOT_VERIFIED",
                    "WRITE_OK_BUT_ENTRY_NOT_IN_READBACK", "ONLY_LEGACY_CALLED_UNVERIFIED",
                    "ONLY_PKG_REGISTER_CALLED_UNVERIFIED", "ALL_WRITE_PATHS_FAILED"},
        "verify": {"READ_UNAVAILABLE", "ENTRY_PERSISTED", "ENTRY_ABSENT_AFTER_REBOOT", "READ_FAILED"},
    }
    if outcome not in phase_outcomes[data["phase"]]:
        raise ValueError("Outcome does not match phase")
    if expected_origin is not None and context["origin"] != expected_origin:
        raise ValueError("Reported origin mismatch")

    payload = {
        "kind": "vidaa-install-v2", "phase": data["phase"], "timestamp": timestamp,
        "provenance": provenance, "clientBuildId": data["clientBuildId"], "buildMatch": True,
        "accessContext": context,
        "preferredContextObserved": context["hostname"] == "vidaahub.com",
        "userAgent": ua[:500],
        "clientDeviceHint": "TV_LIKE" if re.search(r"VIDAA|Hisense|SmartTV|Smart-TV", ua, re.I) else "UNCONFIRMED",
        "outcome": outcome,
    }
    caps = data.get("capabilities")
    if isinstance(caps, dict):
        payload["capabilities"] = {str(k)[:80]: bool(v) for k, v in list(caps.items())[:80]}
    enumeration = data.get("globalEnumeration")
    if isinstance(enumeration, dict):
        entry = {"status": str(enumeration.get("status"))[:40]}
        if type(enumeration.get("totalWindowProps")) is int:
            entry["totalWindowProps"] = enumeration["totalWindowProps"]
        matched = enumeration.get("matched")
        if isinstance(matched, list):
            entry["matched"] = [str(name)[:120] for name in matched[:200]]
        entry["truncated"] = bool(enumeration.get("truncated"))
        payload["globalEnumeration"] = entry
    for key in ("readAttempts", "attempts"):
        if key in data:
            payload[key] = _clean_attempts(data[key])
    for key in ("identifierProvenance", "pkgmgrObservation", "identifierLab"):
        observation = _clean_observation(data.get(key))
        if observation is not None:
            payload[key] = observation
    for key in ("writePrimitivesPresent",):
        if isinstance(data.get(key), list):
            payload[key] = [str(v)[:80] for v in data[key][:20]]
    for key in ("registryBefore", "registryAfter", "registryCurrent"):
        if key in data:
            payload[key] = _clean_registry(data[key])
    if isinstance(data.get("merge"), dict):
        payload["merge"] = {k: v for k, v in data["merge"].items()
                            if k in ("countBefore", "countAfter") and type(v) is int}
        if type(data["merge"].get("entryPresentBefore")) is bool:
            payload["merge"]["entryPresentBefore"] = data["merge"]["entryPresentBefore"]
    if isinstance(data.get("appEntry"), dict):
        entry = data["appEntry"]
        payload["appEntry"] = {k: str(entry.get(k, ""))[:300] for k in
                               ("Id", "AppName", "URL", "StartCommand", "Type", "StoreType", "InstallTime")}
        target = provenance["target"]
        expected_entry = {"Id": target["appId"], "AppName": target["appName"],
                          "URL": target["appUrl"], "StartCommand": target["appUrl"],
                          "Type": "Browser", "StoreType": target["storeType"]}
        if any(payload["appEntry"].get(key) != value for key, value in expected_entry.items()):
            raise ValueError("Unexpected app target")
    elif data["phase"] == "install":
        raise ValueError("Missing app target")
    if isinstance(data.get("nextStep"), str):
        payload["nextStep"] = data["nextStep"][:400]
    if isinstance(data.get("limits"), list):
        payload["limits"] = [str(item)[:300] for item in data["limits"][:12]]
    return payload


def make_handler(report_dir, provenance=None):
    provenance = provenance or manifest()
    lock = threading.Lock()
    latest = None
    html = (ROOT / "web/vidaa-install-v2.html").read_text(encoding="utf-8").replace(
        '/vidaa-install-v2.js"', '/vidaa-install-v2.js?v=' + provenance["buildId"] + '"').encode()
    script = (ROOT / "web/vidaa-install-v2.js").read_bytes()

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def expected_origin(self):
            host = self.headers.get("Host", "")
            parsed = urllib.parse.urlsplit(self.server.scheme + "://" + host)
            allowed = {self.server.server_address[0], "vidaahub.com", "www.vidaahub.com"}
            try:
                if ipaddress.ip_address(self.server.server_address[0]).is_loopback:
                    allowed.update({"localhost", "127.0.0.1"})
            except ValueError:
                pass
            if (parsed.hostname not in allowed or parsed.username or parsed.password or parsed.path or
                    parsed.query or parsed.fragment or (parsed.port or 80) != self.server.server_address[1]):
                raise ValueError("Invalid host")
            return self.server.scheme + "://" + host

        def reply(self, code, data, content_type="application/json"):
            body = data if isinstance(data, bytes) else json.dumps(data).encode()
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.send_header("X-Sidee-Build", provenance["buildId"])
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            try:
                self.expected_origin()
            except (ValueError, TypeError):
                return self.reply(400, {"error": "Invalid host"})
            path = urllib.parse.urlsplit(self.path).path
            self.server.record_access(self.client_address[0], self.headers.get("Host", ""), "GET", path)
            if path in ("/", "/vidaa-install-v2.html"):
                return self.reply(200, html, "text/html; charset=utf-8")
            if path == "/vidaa-install-v2.js":
                return self.reply(200, script, "application/javascript")
            if path == "/manifest":
                return self.reply(200, provenance)
            if path == "/status":
                return self.reply(200, {"mode": MODE, "provenance": provenance,
                                        "transport": self.server.scheme, "receipt": latest,
                                        "httpAccess": self.server.access_snapshot()})
            self.reply(404, {"error": "Not found"})

        def do_POST(self):
            nonlocal latest
            self.server.record_access(self.client_address[0], self.headers.get("Host", ""), "POST",
                                      urllib.parse.urlsplit(self.path).path)
            if urllib.parse.urlsplit(self.path).path != "/snapshot" or urllib.parse.urlsplit(self.path).query:
                return self.reply(404, {"error": "Not found"})
            origin = self.headers.get("Origin")
            try:
                expected_origin = self.expected_origin()
            except (ValueError, TypeError):
                return self.reply(400, {"error": "Invalid host"})
            if origin != expected_origin:
                return self.reply(403, {"error": "Origin mismatch"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if (not 0 < size <= MAX_BODY or self.headers.get("Transfer-Encoding") or
                        self.headers.get("Content-Type", "").split(";")[0] != "application/json"):
                    raise ValueError("Invalid body")
                raw = self.rfile.read(size)
                if len(raw) != size:
                    raise ValueError("Incomplete body")
                payload = sanitize(json.loads(raw), provenance, expected_origin)
            except (ValueError, TypeError, KeyError, UnicodeError, OSError):
                return self.reply(400, {"error": "Invalid install report"})
            with lock:
                payload["receivedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                payload["receiverContext"] = {"transport": self.server.scheme,
                                              "hostHeader": self.headers.get("Host"), "originHeader": origin}
                saved = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode()
                stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
                filename = "vidaa-install-v2-" + payload["phase"] + "-" + stamp + ".json"
                try:
                    report_dir.mkdir(parents=True, exist_ok=True)
                    (report_dir / filename).write_bytes(saved)
                    temporary = report_dir / "vidaa-install-v2-latest.tmp"
                    temporary.write_bytes(saved)
                    temporary.replace(report_dir / "vidaa-install-v2-latest.json")
                except OSError:
                    return self.reply(503, {"error": "Report storage unavailable"})
                latest = {"file": filename, "sha256": hashlib.sha256(saved).hexdigest(), "bytes": len(saved),
                          "receivedAt": payload["receivedAt"], "phase": payload["phase"],
                          "origin": payload["accessContext"]["origin"],
                          "preferredContextObserved": payload["preferredContextObserved"],
                          "outcome": payload["outcome"], "clientDeviceHint": payload["clientDeviceHint"]}
            print("[INSTALL-V2] Report " + payload["phase"] + ": " + latest["outcome"], flush=True)
            self.reply(200, latest)

    return Handler


class InstallHTTPServer(http.server.ThreadingHTTPServer):
    # Windows SO_REUSEADDR puo' far condividere una porta a due ricevitori.
    allow_reuse_address = os.name != "nt"
    daemon_threads = True

    def __init__(self, address, handler, access_path=None):
        self.access_path = access_path
        self.scheme = "http"
        self.access_lock = threading.Lock()
        self.access_clients = {}
        super().__init__(address, handler)

    def record_access(self, client, host="", method=None, path=None):
        try:
            address = ipaddress.ip_address(client)
        except ValueError:
            return
        if not address.is_private:
            return
        allowed_paths = {"/", "/vidaa-install-v2.html", "/vidaa-install-v2.js", "/manifest", "/status", "/snapshot"}
        allowed_hosts = {"vidaahub.com", "vidaahub.com:80", self.server_address[0],
                         self.server_address[0] + ":" + str(self.server_address[1])}
        with self.access_lock:
            if client not in self.access_clients and len(self.access_clients) >= 32:
                return
            item = self.access_clients.setdefault(client, {"connections": 0, "requests": 0, "paths": {}})
            if method is None:
                item["connections"] += 1
            else:
                item["requests"] += 1
                item["lastMethod"] = method
                item["lastPath"] = path if path in allowed_paths else "[OTHER]"
                item["lastHost"] = host if host in allowed_hosts else "[OTHER]"
                item["paths"][item["lastPath"]] = item["paths"].get(item["lastPath"], 0) + 1
            item["lastAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            if self.access_path is not None:
                saved = {"mode": "isolated-install-v2-http-access", "transport": self.scheme, "pid": os.getpid(),
                         "bind": list(self.server_address), "clients": self.access_clients,
                         "scope": "Passive own receiver access; no body, query, cookies, TLS capture or TV API."}
                try:
                    self.access_path.parent.mkdir(parents=True, exist_ok=True)
                    temporary = self.access_path.with_suffix(".tmp")
                    temporary.write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
                    temporary.replace(self.access_path)
                except OSError:
                    pass

    def access_snapshot(self):
        with self.access_lock:
            return {client: dict(item, paths=dict(item["paths"])) for client, item in self.access_clients.items()}

    def get_request(self):
        connection, address = super().get_request()
        self.record_access(address[0])
        return connection, address

    def server_bind(self):
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def _status_connection(host, port):
    return http.client.HTTPConnection(host, port, timeout=3)


def serve(host, port=80, report_dir=None):
    if not 0 <= port <= 65535:
        raise ValueError("Invalid port")
    ipaddress.ip_address(host)
    provenance = manifest()
    try:
        reports = report_dir or ROOT / "reports"
        server = InstallHTTPServer((host, port), make_handler(reports, provenance),
                                   reports / "install-v2-http-status.json")
    except OSError as exc:
        if exc.errno != errno.EADDRINUSE and getattr(exc, "winerror", None) != 10048:
            raise
        connection = _status_connection(host, port)
        try:
            connection.request("GET", "/status")
            response = connection.getresponse()
            raw = response.read(64 * 1024 + 1)
            if response.status != 200 or len(raw) > 64 * 1024:
                raise ValueError("Unknown receiver")
            active = json.loads(raw)
            if (active.get("mode") != MODE or
                    active.get("provenance", {}).get("fileSha256") != provenance["fileSha256"] or
                    active.get("provenance", {}).get("target") != provenance["target"]):
                raise ValueError("Different service or build on this port")
        except (OSError, ValueError, AttributeError, http.client.HTTPException) as error:
            raise RuntimeError(f"Porta {port} occupata da un altro servizio. Nessun processo fermato.") from error
        finally:
            connection.close()
        print("[INSTALL-V2] Ricevitore gia attivo con la stessa build: report preservati.", flush=True)
        return
    entry = "http://vidaahub.com/" if port == 80 else f"http://vidaahub.com:{port}/"
    print(f"[INSTALL-V2] Ricevitore attivo. Sulla TV apri: {entry}", flush=True)
    print("[INSTALL-V2] Tre fasi esplicite: Analizza -> Installa -> riavvio TV -> Verifica.", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="Ricevitore isolato vidaa-install-v2")
    parser.add_argument("--host", default="192.168.1.5", help="IP LAN del PC (default 192.168.1.5)")
    parser.add_argument("--port", type=int, default=80, help="Porta HTTP (default 80, radice vidaahub)")
    args = parser.parse_args()
    serve(args.host, args.port)


if __name__ == "__main__":
    main()
