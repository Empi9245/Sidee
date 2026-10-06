"""Local Sidee web interface: three steps — find TV -> enter
the PIN displayed on the TV -> click the app to install.

Security: the dashboard is accessible only with the unique key printed
at startup (in the URL and QR code); installation URLs must use
https; the PIN and tokens are never logged."""
from __future__ import annotations

import http.server
import http.client
import errno
import ipaddress
import json
import os
import re
import secrets
import socket
import tempfile
import threading
import time
import urllib.parse
import webbrowser

from . import client, presets
from .pairing import PairingFlow
from .phone import qr_image

_PORT = 8787
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACCESS_KEY = secrets.token_urlsafe(16)
PAIRING = PairingFlow()
# Enter your Ko-fi/Sponsors link here: it appears in the dashboard footer
KOFI_URL = "https://ko-fi.com/sidee"

with open(os.path.join(ROOT, "core", "dashboard.html"), encoding="utf-8") as _page_file:
    _PAGE = _page_file.read()


def _status() -> dict:
    s = client.Session().load_or_none()
    if not s:
        return {"paired": False, "state": "needs_pairing",
                "message": "Pair your TV: the PIN on the screen is required"}
    if s.expires_at and time.time() >= s.expires_at:
        return {"paired": True, "state": "expired", "host": s.host,
                "expires_at": s.expires_at,
                "message": "Token expired: pair your TV again to continue"}
    return {"paired": True, "state": "ok", "host": s.host,
            "expires_at": s.expires_at}


def _phone_access(port: int, tv_host: str | None = None) -> dict:
    host = _local_ip(tv_host)
    address = ipaddress.IPv4Address(host)
    if (address.is_loopback or address.is_unspecified or address.is_multicast
            or address.is_link_local):
        return {"ok": False, "error": "Connect this computer to your home network, "
                "then refresh this page to get the phone QR code."}
    url = f"http://{host}:{port}/?key={ACCESS_KEY}"
    return {"ok": True, "url": url, "qr": qr_image(url)}


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _authorized(self) -> bool:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        return q.get("key", [""])[0] == ACCESS_KEY

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Sidee", "2")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parts = urllib.parse.urlparse(self.path)
        path = parts.path
        if not path.startswith("/assets/") and not self._authorized():
            # static assets are public; everything else requires the key
            self._json({"error": "unauthorized"}, 403)
            return
        if path == "/":
            body = _PAGE.replace("KOFI_URL_PLACEHOLDER", KOFI_URL).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path.startswith("/assets/"):
            # allowlist: only PNG files from the assets/ package
            name = os.path.basename(path)
            p = os.path.join(ROOT, "assets", name)
            if not name.endswith(".png") or not os.path.isfile(p):
                self._json({"error": "not found"}, 404)
                return
            body = open(p, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/status":
            self._json(_status())
        elif path == "/api/phone":
            query = urllib.parse.parse_qs(parts.query, keep_blank_values=True)
            tv_host = query.get("tv_host", [None])[0]
            if tv_host is not None:
                try:
                    ipaddress.IPv4Address(tv_host)
                except ValueError:
                    self._json({"ok": False, "error": "The TV IP address is invalid. "
                                "Find your TV again to update the phone QR code."})
                    return
            self._json(_phone_access(self.server.server_address[1], tv_host))
        elif path == "/api/discover":
            try:
                tvs = [t.__dict__ | {"raw_description": ""}
                       for t in client.discover()]
                self._json({"ok": True, "tvs": tvs})
            except Exception as e:
                self._json({"ok": False, "error": repr(e)})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        parts = urllib.parse.urlparse(self.path)
        if not self._authorized():
            self._json({"error": "unauthorized"}, 403)
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 4096:
                self._json({"ok": False, "error": "payload too large"})
                return
            data = json.loads(self.rfile.read(length) or b"{}")
            if parts.path == "/api/pair/start":
                host = str(data.get("host", ""))
                try:
                    ipaddress.IPv4Address(host)
                except ValueError:
                    self._json({"ok": False, "error": "invalid IP address"})
                    return
                self._json(PAIRING.start(host))
            elif parts.path == "/api/pair":
                self._json(PAIRING.confirm(str(data.get("pairing_id", "")),
                                           str(data.get("pin", ""))))
            elif parts.path == "/api/pair/cancel":
                self._json(PAIRING.cancel(str(data.get("pairing_id", ""))))
            elif parts.path == "/api/install":
                try:
                    result = self._install(data)
                except client.AuthError as e:
                    self._json({"ok": False, "error": str(e),
                                "needs_pairing": e.kind in
                                ("none", "rejected", "expired", "corrupt")})
                    return
                self._json(result)
            else:
                self._json({"error": "not found"}, 404)
        except client.AuthError as e:
            self._json({"ok": False, "error": str(e),
                        "needs_pairing": e.kind in
                        ("none", "rejected", "expired", "corrupt")})
        except Exception as e:
            self._json({"ok": False, "error": str(e)})

    def _install(self, data: dict) -> dict:
        key = data.get("app", "")
        p = presets.get(key)
        if not p:
            return {"ok": False, "error": "unknown preset"}
        server = str(data.get("server", "")).strip()
        if p.get("needs_server"):
            if not server:
                return {"ok": False, "error": "enter your " + p["name"]
                                              + " server address"}
            p = dict(p)
            p["url"] = presets.build_server_url(server)
        elif p.get("server_builder") == "stremio":
            p = dict(p)
            p["url"] = presets.build_stremio_url(server)
        _validate_preset(p)
        s = client.Session.load()
        apps = client.add_tile(s, p["app_id"], p["name"], p["url"],
                               p["image"])
        found = [a for a in apps
                 if isinstance(a, dict) and
                 str(a.get("appId", "")).lower() == p["app_id"]]
        confirmed = any(client.tile_matches_request(a, p["app_id"], p["url"])
                        for a in found)
        dups = len(found)
        return {"ok": confirmed,
                "status": "installed" if confirmed else "unconfirmed",
                "error": None,
                "message": None if confirmed else
                p["name"] + " installation was requested, but the TV has not "
                "confirmed its current address yet. Check Home on your TV "
                "before trying again.",
                "duplicates": max(0, dups - 1) if found else 0}


def _validate_preset(p: dict) -> None:
    """Tile URLs must use https; http is allowed ONLY for hosts on
    the user's private network (e.g. their own Jellyfin server)."""
    if not re.fullmatch(r"[a-z0-9_]{1,32}", p["app_id"]):
        raise ValueError("invalid app_id")
    url = p["url"]
    if url.startswith("https://") and len(url) <= 300:
        pass
    elif url.startswith("http://") and presets.is_private_host(url) \
            and len(url) <= 300:
        pass
    else:
        raise ValueError("URL must use https (or http on your LAN)")
    if not re.fullmatch(r"[\w \-']{1,40}", p["name"]):
        raise ValueError("invalid name")
    if p["image"] and not p["image"].startswith("https://"):
        raise ValueError("icon URL must use https")


def _dashboard_state_path() -> str:
    return os.path.join(ROOT, ".runtime", "dashboard.json")


def _reopen_dashboard(open_browser: bool) -> bool:
    """A second double-click opens this folder's existing dashboard."""
    connection = None
    try:
        with open(_dashboard_state_path(), encoding="utf-8") as f:
            state = json.load(f)
        port, key = state["port"], state["key"]
        if (type(port) is not int or not 0 < port < 65536 or
                not isinstance(key, str) or not key):
            return False
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
        connection.request("GET", "/api/status?key=" + urllib.parse.quote(key, safe=""))
        response = connection.getresponse()
        if response.status != 200 or response.getheader("X-Sidee") != "2":
            return False
        response.read()
        url = f"http://127.0.0.1:{port}/?key={urllib.parse.quote(key, safe='')}"
        if open_browser:
            webbrowser.open(url)
        print("Your dashboard is already running. Use its original window to close it.")
        return True
    except (OSError, ValueError, TypeError, KeyError, http.client.HTTPException):
        return False
    finally:
        if connection:
            connection.close()


def _remember_dashboard(port: int) -> None:
    path = _dashboard_state_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pending = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         dir=os.path.dirname(path), delete=False) as f:
            pending = f.name
            json.dump({"port": port, "key": ACCESS_KEY, "pid": os.getpid()}, f)
        os.chmod(pending, 0o600)
        os.replace(pending, path)
    finally:
        if pending and os.path.isfile(pending):
            os.remove(pending)


def _forget_dashboard() -> None:
    try:
        path = _dashboard_state_path()
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
        if state.get("pid") == os.getpid() and state.get("key") == ACCESS_KEY:
            os.remove(path)
    except (OSError, ValueError, AttributeError):
        pass


class DashboardServer(http.server.ThreadingHTTPServer):
    # Windows SO_REUSEADDR can silently share the port with another process.
    # Each dashboard must exclusively own its address and access key.
    allow_reuse_address = os.name != "nt"
    allow_reuse_port = False

    def server_bind(self):
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def _bind_dashboard_server():
    try:
        return DashboardServer(("0.0.0.0", _PORT), Handler)
    except OSError as e:
        if (e.errno != errno.EADDRINUSE and
                getattr(e, "winerror", None) not in (10013, 10048)):
            raise
        return DashboardServer(("0.0.0.0", 0), Handler)


def serve(open_browser: bool = True) -> None:
    if _reopen_dashboard(open_browser):
        return
    srv = _bind_dashboard_server()
    port = srv.server_address[1]
    _remember_dashboard(port)
    local = f"http://127.0.0.1:{port}/?key={ACCESS_KEY}"
    lan = f"http://{_local_ip()}:{port}/?key={ACCESS_KEY}"
    print(f"Sidee (this computer): {local}")
    print(f"Sidee (from your phone, same network): {lan}")
    print("Use your phone: scan the QR code shown in the dashboard.")
    print("The key in the URL is the only way to access the dashboard: "
          "do not share it outside your home. Ctrl+C to quit.")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(local)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
        _forget_dashboard()


def _local_ip(tv_host: str | None = None) -> str:
    """Choose a local interface without sending traffic or needing Internet.

    The TV route takes precedence over a VPN's default route. Before a TV
    has been selected, the local broadcast route selects a LAN interface.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        if tv_host:
            s.connect((tv_host, client.MQTT_PORT))
        else:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.connect((client.SSDP_BROADCAST, client.SSDP_PORT))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()
