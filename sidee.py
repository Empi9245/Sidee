#!/usr/bin/env python3
"""
Sidee - standalone VIDAA browser research / web-app installer host.

Runs:
- DNS responder on UDP/53 (vidaahub.com -> this PC)
- HTTPS UI on TCP/443
- HTTP dashboard/fallback on TCP/8080
- JSON report/config API

No third-party Python packages are required.
OpenSSL is used only to generate a temporary self-signed vidaahub.com certificate.
"""

from __future__ import annotations

import argparse
import http.server
import json
import mimetypes
import os
import pathlib
import re
import signal
import shutil
import socket
import ssl
import struct
import subprocess
import sys
import tempfile
import threading
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
REPORTS_DIR = ROOT / "reports"
CONFIG_PATH = ROOT / "config.json"
CERT_DIR = ROOT / ".sidee-certs"

stop_event = threading.Event()
REPORT_WRITE_LOCK = threading.Lock()
SESSION_ID_RE = re.compile(r"^sidee-\d{8}-\d{6}-[a-f0-9]{4}$")


def session_report_filename(session_id):
    if not isinstance(session_id, str) or not SESSION_ID_RE.fullmatch(session_id):
        raise ValueError("Invalid sessionId")
    return "sidee-session-" + session_id[len("sidee-"):] + ".json"


def session_report_path(session_id):
    filename = session_report_filename(session_id)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    reports_root = REPORTS_DIR.resolve()
    file_path = (REPORTS_DIR / filename).resolve()
    if file_path.parent != reports_root:
        raise ValueError("Invalid report path")
    return file_path


def write_session_report(session_id, report):
    if not isinstance(report, dict):
        raise ValueError("Expected report object")
    if report.get("sessionId") != session_id:
        raise ValueError("sessionId does not match report.sessionId")

    file_path = session_report_path(session_id)
    tmp_path = None
    with REPORT_WRITE_LOCK:
        try:
            fd, tmp_name = tempfile.mkstemp(
                prefix="." + file_path.name + ".",
                suffix=".tmp",
                dir=str(REPORTS_DIR),
            )
            tmp_path = pathlib.Path(tmp_name)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, file_path)
            tmp_path = None
        finally:
            if tmp_path is not None:
                try:
                    tmp_path.unlink()
                except FileNotFoundError:
                    pass
    return file_path




def load_config():
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_config(data):
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    tmp.replace(CONFIG_PATH)


def get_local_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("1.1.1.1", 80))
        return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        sock.close()


def generate_cert():
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    cert = CERT_DIR / "vidaahub.com.crt"
    key = CERT_DIR / "vidaahub.com.key"
    if cert.exists() and key.exists():
        return cert, key

    openssl = shutil.which("openssl")
    if not openssl and os.name == "nt":
        candidates = [
            r"C:\\Program Files\\Git\\usr\\bin\\openssl.exe",
            r"C:\\Program Files\\OpenSSL-Win64\\bin\\openssl.exe",
            r"C:\\Program Files (x86)\\OpenSSL-Win32\\bin\\openssl.exe",
        ]
        openssl = next((p for p in candidates if os.path.isfile(p)), None)
    if not openssl:
        raise RuntimeError(
            "OpenSSL was not found. Install Git for Windows or OpenSSL, then run Sidee again."
        )

    cmd = [
        openssl, "req", "-x509", "-newkey", "rsa:2048",
        "-keyout", str(key), "-out", str(cert), "-days", "30", "-nodes",
        "-subj", "/CN=vidaahub.com",
        "-addext", "subjectAltName=DNS:vidaahub.com,DNS:www.vidaahub.com",
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        fallback = [
            openssl, "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", str(key), "-out", str(cert), "-days", "30", "-nodes",
            "-subj", "/CN=vidaahub.com",
        ]
        subprocess.run(fallback, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return cert, key


def parse_dns_question(data):
    idx = 12
    labels = []
    while idx < len(data):
        length = data[idx]
        if length == 0:
            idx += 1
            break
        idx += 1
        labels.append(data[idx:idx + length].decode("ascii", errors="ignore"))
        idx += length
    qtype = struct.unpack("!H", data[idx:idx + 2])[0] if idx + 2 <= len(data) else 0
    return ".".join(labels).lower(), qtype, idx


def dns_answer(data, ip):
    _, _, end = parse_dns_question(data)
    question = data[12:end + 4]
    header = data[:2] + b"\x81\x80" + data[4:6] + b"\x00\x01\x00\x00\x00\x00"
    answer = (
        b"\xc0\x0c" + b"\x00\x01" + b"\x00\x01" +
        struct.pack("!I", 30) + b"\x00\x04" + socket.inet_aton(ip)
    )
    return header + question + answer


def empty_dns_answer(data):
    _, _, end = parse_dns_question(data)
    question = data[12:end + 4]
    return data[:2] + b"\x81\x80" + data[4:6] + b"\x00\x00\x00\x00\x00\x00" + question


def forward_dns(data, upstreams):
    for addr in upstreams:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.settimeout(2)
            s.sendto(data, (addr, 53))
            return s.recvfrom(4096)[0]
        except Exception:
            pass
        finally:
            s.close()
    return None


def run_dns(config, local_ip):
    domains = {d.lower().rstrip(".") for d in config.get("spoof_domains", ["vidaahub.com"])}
    port = int(config.get("dns_port", 53))
    upstreams = config.get("upstream_dns", ["1.1.1.1", "8.8.8.8"])
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("0.0.0.0", port))
    s.settimeout(1)
    print(f"[DNS] UDP/{port} -> {', '.join(sorted(domains))} = {local_ip}")
    while not stop_event.is_set():
        try:
            data, client = s.recvfrom(4096)
        except socket.timeout:
            continue
        except OSError:
            break
        try:
            host, qtype, _ = parse_dns_question(data)
            if host in domains and qtype == 1:
                response = dns_answer(data, local_ip)
                print(f"[DNS] {client[0]} {host} -> {local_ip}")
            elif host in domains and qtype == 28:
                response = empty_dns_answer(data)
            else:
                response = forward_dns(data, upstreams)
            if response:
                s.sendto(response, client)
        except Exception:
            continue
    s.close()


class SideeHandler(http.server.BaseHTTPRequestHandler):
    server_version = "Sidee/0.1"

    def log_message(self, fmt, *args):
        print(f"[WEB] {self.client_address[0]} {fmt % args}")

    def _send_json(self, data, status=200):
        payload = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            cfg = load_config()
            return self._send_json({
                "ok": True,
                "service": "Sidee",
                "host": self.headers.get("Host", ""),
                "client": self.client_address[0],
                "spoofDomains": cfg.get("spoof_domains", []),
            })

        if path == "/api/config":
            return self._send_json(load_config())

        if path == "/api/reports/latest":
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            files = sorted(REPORTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not files:
                return self._send_json({"ok": False, "message": "No reports yet"}, 404)
            with files[0].open("r", encoding="utf-8") as f:
                return self._send_json(json.load(f))

        if path == "/api/reports":
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            files = sorted(REPORTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            return self._send_json({
                "reports": [
                    {"name": p.name, "bytes": p.stat().st_size, "modified": p.stat().st_mtime}
                    for p in files[:50]
                ]
            })

        rel = path.lstrip("/") or "index.html"
        file_path = (WEB_DIR / rel).resolve()
        if WEB_DIR.resolve() not in file_path.parents and file_path != WEB_DIR.resolve():
            return self.send_error(403)
        if not file_path.is_file():
            file_path = WEB_DIR / "index.html"
        data = file_path.read_bytes()
        ctype = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            data = self._read_json()
        except Exception as exc:
            return self._send_json({"ok": False, "error": str(exc)}, 400)

        if path == "/api/reports/session":
            if not isinstance(data, dict):
                return self._send_json({"ok": False, "error": "Expected JSON object"}, 400)
            session_id = data.get("sessionId")
            report = data.get("report")
            try:
                file_path = write_session_report(session_id, report)
            except ValueError as exc:
                return self._send_json({"ok": False, "error": str(exc)}, 400)
            except OSError as exc:
                return self._send_json({"ok": False, "error": f"Could not write report: {exc}"}, 500)
            return self._send_json({
                "ok": True,
                "sessionId": session_id,
                "file": file_path.name,
            })

        if path == "/api/report":
            return self._send_json({
                "ok": False,
                "error": "Legacy report endpoint disabled; use /api/reports/session",
            }, 410)

        if path == "/api/config":
            current = load_config()
            nuvio = data.get("nuvio") if isinstance(data, dict) else None
            if not isinstance(nuvio, dict):
                return self._send_json({"ok": False, "error": "Expected nuvio object"}, 400)
            allowed = {"app_id", "app_name", "app_url", "icon_url", "store_type"}
            current.setdefault("nuvio", {})
            for key in allowed:
                if key in nuvio and isinstance(nuvio[key], str):
                    current["nuvio"][key] = nuvio[key].strip()
            save_config(current)
            return self._send_json({"ok": True, "nuvio": current["nuvio"]})

        return self._send_json({"ok": False, "error": "Not found"}, 404)


class ThreadingHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def run_http(port):
    server = ThreadingHTTPServer(("0.0.0.0", port), SideeHandler)
    server.timeout = 1
    print(f"[HTTP] http://0.0.0.0:{port}")
    while not stop_event.is_set():
        server.handle_request()
    server.server_close()


def run_https(port, cert, key):
    server = ThreadingHTTPServer(("0.0.0.0", port), SideeHandler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(cert), keyfile=str(key))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.timeout = 1
    print(f"[HTTPS] https://0.0.0.0:{port}")
    while not stop_event.is_set():
        server.handle_request()
    server.server_close()


def main():
    parser = argparse.ArgumentParser(description="Sidee VIDAA local toolkit")
    parser.add_argument("--no-dns", action="store_true", help="Do not start DNS server")
    parser.add_argument("--no-https", action="store_true", help="Do not start HTTPS server")
    args = parser.parse_args()

    cfg = load_config()
    local_ip = get_local_ip()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print("\nSidee - VIDAA local toolkit")
    print("=" * 52)
    print(f"PC IP: {local_ip}")
    print(f"PC dashboard: http://{local_ip}:{cfg.get('http_port', 8080)}")
    print("TV flow:")
    print(f"  1. Set the TV DNS manually to {local_ip}")
    print("  2. Open https://vidaahub.com in the TV browser")
    print("  3. Accept the local certificate warning if shown")
    print("  4. Run Read-only Scan before any installation test")
    print("=" * 52)

    threads = []

    http_thread = threading.Thread(target=run_http, args=(int(cfg.get("http_port", 8080)),), daemon=True)
    http_thread.start()
    threads.append(http_thread)

    if not args.no_dns:
        dns_thread = threading.Thread(target=run_dns, args=(cfg, local_ip), daemon=True)
        dns_thread.start()
        threads.append(dns_thread)

    if not args.no_https:
        cert, key = generate_cert()
        https_thread = threading.Thread(
            target=run_https,
            args=(int(cfg.get("https_port", 443)), cert, key),
            daemon=True,
        )
        https_thread.start()
        threads.append(https_thread)

    def shutdown(*_):
        stop_event.set()

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)

    try:
        while not stop_event.wait(0.5):
            pass
    finally:
        print("\nSidee stopped.")


if __name__ == "__main__":
    try:
        main()
    except PermissionError:
        print("\n[ERROR] Sidee needs Administrator/root rights for DNS port 53 and HTTPS port 443.")
        print("Use start-windows.bat on Windows or sudo ./start-mac-linux.sh on macOS/Linux.")
        sys.exit(1)
    except Exception as exc:
        print(f"\n[ERROR] {exc}")
        sys.exit(1)
