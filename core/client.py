"""Sidee client: TV discovery, pairing, sessions, and tile actions."""
from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import math
import os
import re
import socket
import ssl
import subprocess
import threading
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import wraps

import paho.mqtt.client as mqtt

from . import protocol

SSDP_MULTICAST = "239.255.255.250"
SSDP_BROADCAST = "255.255.255.255"
SSDP_PORT = 1900
MQTT_PORT = 36669
UPNP_PORTS = (18400, 38400)


# --- Client certificate (extracted from the official app, encoded blob) ---

def _cert_dir() -> str:
    home_dir = os.path.expanduser("~")
    base = os.path.join(home_dir, ".sidee")
    # Keep an existing TV pairing usable after the product rename.
    legacy = os.path.join(home_dir, ".vidaa-tile")
    if (not os.path.isfile(os.path.join(base, "session.json")) and
            os.path.isfile(os.path.join(legacy, "session.json"))):
        base = legacy
    os.makedirs(base, mode=0o700, exist_ok=True)
    return base


_CERT_BUNDLE = "certs.bin.k"


def _certificate_path() -> str:
    user_path = os.path.join(_cert_dir(), _CERT_BUNDLE)
    if os.path.isfile(user_path):
        return user_path
    project_dir = os.path.dirname(os.path.dirname(__file__))
    for folder in (".sidee", ".vidaa-tile"):
        project_path = os.path.join(project_dir, folder, _CERT_BUNDLE)
        if os.path.isfile(project_path):
            return project_path
    return os.path.join(os.path.dirname(__file__), "tv-client.bundle")


def _load_client_pem_key() -> tuple[bytes, bytes]:
    """Load the local client certificate bundle without exposing its contents."""
    path = _certificate_path()
    if not os.path.isfile(path):
        raise FileNotFoundError(
            "The TV connection certificate is missing. Prepare this installer "
            "before requesting a code.")
    with open(path, "rb") as f:
        blob = f.read()
    data = zlib_dec(blob)
    marker = b"-----END CERTIFICATE-----"
    i = data.find(marker) + len(marker)
    return data[:i] + b"\n", data[i:].strip() + b"\n"


def zlib_dec(blob: bytes) -> bytes:
    import base64 as _b64
    return _zlib_decompress(_xor(_b64.b85decode(blob), b"k3"))


def _xor(data: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def _zlib_decompress(data: bytes) -> bytes:
    import zlib
    return zlib.decompress(data)


def has_client_certificate() -> bool:
    return os.path.isfile(_certificate_path())


def install_client_certificate(blob_text: str) -> None:
    """Write the encoded bundle (base85+xor+zlib of PEM certificate+key)."""
    import base64 as _b64
    raw = blob_text.encode() if isinstance(blob_text, str) else blob_text
    enc = _b64.b85encode(_xor(_zlib_compress(raw), b"k3"))
    path = os.path.join(_cert_dir(), _CERT_BUNDLE)
    with open(path, "wb") as f:
        f.write(enc)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _zlib_compress(data: bytes) -> bytes:
    import zlib
    return zlib.compress(data, 9)


# --- Persistent session ---

class AuthError(Exception):
    """Token/session issue with a suggested action for the user."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind  # none | expired | rejected | needs_pairing | corrupt


class PairingCancelled(Exception):
    """A user cancelled a pending PIN request; the device identity stays valid."""


@dataclass
class Session:
    host: str = ""
    device_uuid: str = ""
    client_id: str = ""
    username: str = ""
    access_token: str = ""
    refresh_token: str = ""
    access_time: int = 0        # epoch reported by the TV (informational)
    access_days: int = 0
    refresh_time: int = 0
    refresh_days: int = 0
    expires_at: float = 0.0     # LOCAL access expiry epoch (avoids clock skew)
    pair_failures: int = 0

    @classmethod
    def path(cls) -> str:
        return os.path.join(_cert_dir(), "session.json")

    @classmethod
    def load(cls) -> "Session":
        with open(cls.path(), encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise AuthError("corrupt", "invalid session format")
        known = set(cls.__dataclass_fields__)
        s = cls(**{k: v for k, v in data.items() if k in known})
        for key in ("host", "device_uuid", "client_id", "username",
                    "access_token", "refresh_token"):
            if not isinstance(getattr(s, key), str):
                raise AuthError("corrupt", "invalid session fields")
        for key in ("access_time", "access_days", "refresh_time",
                    "refresh_days", "pair_failures", "expires_at"):
            value = getattr(s, key)
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value < 0):
                raise AuthError("corrupt", "invalid session expiry values")
        if not all((s.access_token, s.refresh_token, s.host, s.device_uuid)):
            raise AuthError("corrupt", "incomplete or corrupted session")
        if not s.expires_at and s.access_time and s.access_days:
            s.expires_at = s.access_time + s.access_days * 86400
        return s

    def set_tokens(self, tok: dict) -> None:
        """Update token fields and LOCAL expiry (avoids clock skew).
        The only function allowed to update expires_at."""
        access = tok.get("accesstoken")
        refresh_token = tok.get("refreshtoken", self.refresh_token)
        if not all(isinstance(t, str) and t for t in (access, refresh_token)):
            raise ValueError("incomplete token response")
        now = time.time()
        access_time = int(tok.get("accesstoken_time", now))
        access_days = int(tok.get("accesstoken_duration_day", self.access_days or 2))
        refresh_time = int(tok.get("refreshtoken_time",
                                  now if refresh_token != self.refresh_token
                                  else self.refresh_time or now))
        refresh_days = int(tok.get("refreshtoken_duration_day", self.refresh_days or 30))
        if min(access_time, refresh_time) < 0 or min(access_days, refresh_days) <= 0:
            raise ValueError("invalid token expiry values")
        expires_at = now + access_days * 86400
        self.access_token, self.refresh_token = access, refresh_token
        self.access_time, self.access_days = access_time, access_days
        self.refresh_time, self.refresh_days = refresh_time, refresh_days
        self.expires_at = expires_at

    def save(self) -> None:
        """Persist the state AS IS: expires_at is updated only by
        set_tokens (never when counting failures or touching the session)."""
        path = self.path()
        pending = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                             dir=os.path.dirname(path),
                                             delete=False) as f:
                pending = f.name
                json.dump(self.__dict__, f, indent=1)
            try:
                os.chmod(pending, 0o600)
            except OSError:
                pass
            os.replace(pending, path)
        finally:
            if pending and os.path.isfile(pending):
                os.remove(pending)

    def exists(self) -> bool:
        return os.path.isfile(self.path())

    def load_or_none(self) -> "Session | None":
        try:
            return self.load()
        except (OSError, ValueError, TypeError, AuthError, KeyError):
            return None


# --- TV discovery ---

@dataclass
class TvInfo:
    host: str
    friendly_name: str = ""
    model: str = ""
    is_vidaa: bool = False
    raw_description: str = field(default="", repr=False)


def _broadcasts_from_ipconfig(output: str) -> list[str]:
    """Read IPv4 address/mask pairs without depending on localized labels."""
    broadcasts = set()
    host = None
    for line in output.splitlines():
        match = re.search(r"(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?![\d.])", line)
        if "ipv4" in line.lower():
            host = match.group(1) if match else None
        elif host and match:
            try:
                network = ipaddress.IPv4Network(
                    f"{host}/{match.group(1)}", strict=False)
                if not network.is_loopback and network.prefixlen < 31:
                    broadcasts.add(str(network.broadcast_address))
            except ValueError:
                pass
            host = None
    return sorted(broadcasts)


def _local_broadcasts() -> list[str]:
    """Get directed broadcasts for Windows adapters, including their masks."""
    if os.name != "nt":
        return []
    try:
        result = subprocess.run(
            ["ipconfig"], capture_output=True, text=True, errors="replace",
            timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
        return _broadcasts_from_ipconfig(result.stdout)
    except (OSError, subprocess.TimeoutExpired):
        return []


def _msearch(sock: socket.socket, target: str) -> None:
    msg = "\r\n".join([
        "M-SEARCH * HTTP/1.1",
        f"HOST: {SSDP_MULTICAST}:{SSDP_PORT}",
        'MAN: "ssdp:discover"',
        "MX: 2",
        "ST: urn:schemas-upnp-org:device:MediaRenderer:1",
        "CONTENT-LENGTH: 0",
        "", "",
    ]).encode()
    try:
        sock.sendto(msg, (target, SSDP_PORT))
    except OSError:
        pass


def discover(timeout: float = 4.0) -> list[TvInfo]:
    """Find VIDAA TVs on the LAN: broadcast M-SEARCH (the channel used
    by the official app) and multicast, then validate the descriptor."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        sock.bind(("", 0))
    except OSError:
        pass
    sock.settimeout(0.5)
    # Global broadcast may use a virtual adapter; directed broadcasts use
    # each adapter's actual subnet, as measured with the official mobile app.
    targets = list(dict.fromkeys(_local_broadcasts()
                                + [SSDP_BROADCAST, SSDP_MULTICAST]))
    for target in targets:
        _msearch(sock, target)
    locations: dict[str, str] = {}
    end = time.time() + timeout
    while time.time() < end:
        try:
            data, addr = sock.recvfrom(4096)
        except socket.timeout:
            for target in targets:
                _msearch(sock, target)  # retransmit while waiting
            continue
        text = data.decode("utf-8", "replace")
        if not text.upper().startswith("HTTP/1.1 200"):
            continue
        m = re.search(r"Location:\s*(\S+)", text, re.I)
        if m:
            locations[addr[0]] = m.group(1)
    sock.close()

    found: dict[str, TvInfo] = {}
    for host, loc in locations.items():
        info = fetch_descriptor(host, loc)
        if info and info.is_vidaa:
            found[host] = info
    return sorted(found.values(), key=lambda t: t.host)


def fetch_descriptor(host: str, location: str | None = None) -> TvInfo | None:
    """Download the UPnP descriptor and identify a VIDAA TV."""
    for port in UPNP_PORTS:
        loc = location or f"http://{host}:{port}/MediaServer/rendererdevicedesc.xml"
        try:
            u = re.match(r"http://([^:/]+):(\d+)(/.*)", loc)
            if not u:
                return None
            conn = http.client.HTTPConnection(u.group(1), int(u.group(2)), timeout=3)
            conn.request("GET", u.group(3))
            r = conn.getresponse()
            xml = r.read().decode("utf-8", "replace")
            conn.close()
            if r.status != 200:
                continue
            name = re.search(r"<friendlyName>([^<]+)<", xml)
            model = re.search(r"<modelDescription>(.*?)</modelDescription>",
                              xml, re.S)
            desc = model.group(1) if model else ""
            is_vidaa = ("vidaa_support" in desc or "transport_protocol" in desc
                        or "hisense" in xml.lower())
            return TvInfo(host=host, friendly_name=(name.group(1) if name else host),
                          model=desc.strip()[:120], is_vidaa=is_vidaa,
                          raw_description=xml)
        except OSError:
            continue
    return None


def tv_timestamp(host: str) -> int:
    """TV clock from the UPnP descriptor's Date header."""
    for port in UPNP_PORTS:
        try:
            conn = http.client.HTTPConnection(host, port, timeout=3)
            conn.request("GET", "/MediaServer/rendererdevicedesc.xml")
            r = conn.getresponse()
            r.read()
            date = r.headers.get("Date", "")
            conn.close()
            if date:
                import email.utils
                dt = email.utils.parsedate_to_datetime(date)
                return int(dt.timestamp())
        except OSError:
            continue
    return int(time.time())


# --- MQTT session ---

class MqttSession:
    """TV broker connection: message collection and actions gated by step."""

    def __init__(self, host: str, device_uuid: str, tv_ts: int,
                 token: str | None = None):
        self.client_id, self.username, self.password = protocol.session_credentials(
            device_uuid, tv_ts, token)
        self.topics = protocol.tv_topics(self.client_id)
        self.host = host
        self.messages: list[tuple[str, str]] = []
        self.connected = threading.Event()
        self.connect_rc: int | None = None
        self.client = mqtt.Client(client_id=self.client_id,
                                  protocol=mqtt.MQTTv311)
        cert, key = _load_client_pem_key()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        # OpenSSL loads the certificate into memory before the temporary files
        # are removed. The decoded private key never remains on disk.
        with tempfile.TemporaryDirectory(prefix="sidee-tls-") as directory:
            cert_path = os.path.join(directory, "client.pem")
            key_path = os.path.join(directory, "client.key")
            for path, data in ((cert_path, cert), (key_path, key)):
                with open(path, "wb") as f:
                    f.write(data)
                os.chmod(path, 0o600)
            context.load_cert_chain(cert_path, key_path)
        self.client.tls_set_context(context)
        self.client.tls_insecure_set(True)
        self.client.username_pw_set(self.username, self.password)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, c, u, flags, rc, *a):
        self.connect_rc = getattr(rc, "value", rc)
        self.connected.set()  # rejection also ends the wait

    def _on_message(self, c, u, msg):
        self.messages.append((msg.topic,
                              msg.payload.decode("utf-8", "replace")))

    def start(self, wait: float = 10.0) -> int | None:
        self.client.connect(self.host, MQTT_PORT, 30)
        self.client.loop_start()
        self.connected.wait(timeout=wait)
        return self.connect_rc

    def stop(self):
        try:
            self.client.disconnect()
        except OSError:
            pass
        finally:
            self.client.loop_stop()

    def subscribe(self, topics: list[str]):
        self.client.subscribe([(t, 0) for t in topics])

    def publish(self, topic: str, payload: str = ""):
        self.client.publish(topic, payload)

    def wait_for(self, suffix: str, timeout: float, since: int = 0) -> str | None:
        end = time.time() + timeout
        while time.time() < end:
            for topic, payload in self.messages[since:]:
                if topic.endswith(suffix):
                    return payload
            time.sleep(0.3)
        return None


# --- Public operations ---

_OP_LOCK = threading.RLock()   # includes pairing and nested refreshes
PIN_RESULT_WAIT = 15.0
_PAIR_FAILURES_BEFORE_NEW_UUID = 2
_REFRESH_MARGIN = 12 * 3600   # refresh this far ahead of expiry


def _serialized_session(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        with _OP_LOCK:
            return fn(*args, **kwargs)
    return wrapped


def _stored_uuid() -> str | None:
    """UUID of the paired device: reuse avoids accumulating paired
    devices on the TV (which has a maximum limit)."""
    s = Session().load_or_none()
    return s.device_uuid if s and s.device_uuid else None


@_serialized_session
def pair(host: str, pin_provider, timeout: float = 60.0) -> Session:
    """Pairing: TV PIN -> tokens. Reuse the paired UUID;
    generate a new UUID only after multiple consecutive failures
    (invalid state on the TV)."""
    stored = _stored_uuid()
    reuse = (stored and stored != "NEW"
             and not _pair_failures_exceeded())
    device_uuid = stored if reuse else protocol.new_device_uuid()
    sess = MqttSession(host, device_uuid, tv_timestamp(host))
    try:
        rc = sess.start()
        if rc != 0:
            raise ConnectionError(f"connection refused by the TV (rc={rc})")
        since = len(sess.messages)
        sess.subscribe([
            sess.topics["mobile"] + "ui_service/data/authentication",
            sess.topics["mobile"] + "ui_service/data/authenticationcode",
            sess.topics["token_reply"],
        ])
        time.sleep(0.3)
        sess.publish(sess.topics["ui"] + "actions/vidaa_app_connect",
                     protocol.pair_connect_payload())
        if sess.wait_for("data/authentication", 15, since) is None:
            raise TimeoutError("the TV did not display the PIN")
        pin = pin_provider()
        if not pin:
            raise ValueError("PIN not entered")
        since_pin = len(sess.messages)
        sess.publish(sess.topics["ui"] + "actions/authenticationcode",
                     protocol.pair_pin_payload(pin))
        reply = sess.wait_for("ui_service/data/authenticationcode",
                              min(PIN_RESULT_WAIT, timeout), since_pin)
        if reply is None:
            raise TimeoutError("The TV did not confirm the PIN. Request a new code.")
        try:
            result = json.loads(reply)
        except (ValueError, TypeError) as e:
            raise ValueError("invalid PIN response from the TV") from e
        if not isinstance(result, dict) or "result" not in result:
            raise ValueError("invalid PIN response from the TV")
        if result["result"] != 1:
            raise ValueError("PIN expired or incorrect. Request a new code.")
        # As in Sidee, PIN acceptance authorizes an explicit token request;
        # the TV does not issue tokens just because it accepted the code.
        sess.publish(sess.topics["platform"] + "data/gettoken",
                     protocol.token_request_payload(""))
        sess.publish(sess.topics["ui"] + "actions/authenticationcodeclose", "")
        raw = sess.wait_for("platform_service/data/tokenissuance", timeout,
                            since_pin)
        if raw is None:
            raise TimeoutError("PIN accepted, but the TV did not send a token. "
                               "Request a new code.")
        tok = protocol.parse_token_message(raw)
        if not tok:
            raise ValueError("invalid token response")
    except Exception as e:
        if not isinstance(e, PairingCancelled):
            _register_pair_failure(reuse)
        raise
    finally:
        sess.stop()
    s = Session(host=host, device_uuid=device_uuid,
                client_id=sess.client_id, username=sess.username,
                pair_failures=0)
    s.set_tokens(tok)
    s.save()
    return s


def _pair_failures_exceeded() -> bool:
    s = Session().load_or_none()
    return bool(s and s.pair_failures >= _PAIR_FAILURES_BEFORE_NEW_UUID)


def _register_pair_failure(reused: bool) -> None:
    if not reused:
        return  # failures with a new UUID do not affect the old one
    s = Session().load_or_none()
    if s:
        s.pair_failures = s.pair_failures + 1
        s.save()


@_serialized_session
def refresh(session: Session) -> Session:
    """Refresh tokens using the refresh token. Error classification:
    AuthError('rejected') = TV no longer recognizes the device (pair again)."""
    stored = Session().load_or_none()
    if (stored and stored.host == session.host
            and stored.device_uuid == session.device_uuid):
        session.__dict__.update(stored.__dict__)
    sess = MqttSession(session.host, session.device_uuid,
                       tv_timestamp(session.host), token=session.refresh_token)
    try:
        rc = sess.start()
        if rc in (4, 5):
            raise AuthError("rejected",
                            "the TV no longer recognizes the refresh token")
        if rc != 0:
            raise ConnectionError(f"TV unreachable during token refresh (rc={rc})")
        sess.subscribe([sess.topics["token_reply"]])
        time.sleep(0.3)
        sess.publish(sess.topics["platform"] + "data/gettoken",
                     protocol.token_request_payload(session.refresh_token))
        raw = sess.wait_for("platform_service/data/tokenissuance", 20)
    finally:
        sess.stop()
    tok = protocol.parse_token_message(raw) if raw else None
    if not tok:
        raise AuthError("rejected", "no token received during refresh: pair again")
    try:
        session.set_tokens(tok)
    except (ValueError, TypeError, OverflowError) as e:
        raise AuthError("rejected", "invalid refresh response: pair again") from e
    session.save()
    return session


def _ensure_ready(session: Session) -> Session:
    """Refresh if the access token is about to expire (calculated using
    the local clock, unaffected by TV clock skew)."""
    if session.expires_at and time.time() < session.expires_at - _REFRESH_MARGIN:
        return session
    log("auth", "access token nearing expiry: refreshing automatically")
    return refresh(session)


def run_with_session(op, host: str | None = None):
    """Run op(sess, topics) with resilient session lifecycle handling:
    proactive refresh, one retry after refresh if the TV rejects tokens,
    and errors classified as AuthError. Serialize operations."""
    with _OP_LOCK:
        session = Session().load_or_none()
        if not session:
            raise AuthError("none", "no TV paired: pair your TV first")
        if host:
            session.host = host
        session = _ensure_ready(session)
        for attempt in range(2):
            sess = MqttSession(session.host, session.device_uuid,
                               tv_timestamp(session.host),
                               token=session.access_token)
            try:
                try:
                    rc = sess.start()
                except OSError:
                    if attempt:
                        raise
                    rc = None
                if rc == 0:
                    return op(sess, sess.topics), session
                if attempt:
                    raise AuthError("rejected",
                                    f"connection refused by the TV (rc={rc})")
            finally:
                sess.stop()
            # Close the rejected client before opening the refresh connection.
            log("auth", "connection failed: refreshing tokens and retrying")
            session = refresh(session)


def _mark_needs_pairing() -> None:
    s = Session().load_or_none()
    if s:
        s.pair_failures = s.pair_failures + 1
        s.save()


def add_tile(session: Session, app_id: str, name: str, url: str,
             image: str = "") -> list[dict]:
    """Register a web app as a launcher tile. Return the updated app list."""
    def op(sess, topics):
        sess.subscribe([topics["applist_reply"]])
        time.sleep(0.3)
        sess.publish(topics["ui"] + "actions/uievent",
                     protocol.install_payload(app_id, name, url, image))
        time.sleep(8)
        apps = []
        for attempt in range(2):
            # Installing a tile need not push an app list. Ask for a fresh
            # snapshot, ignoring any list sent before this request.
            since = len(sess.messages)
            sess.publish(topics["ui"] + "actions/applist", "0")
            raw = sess.wait_for("ui_service/data/applist", 8, since)
            apps = protocol.parse_applist_message(raw) if raw else []
            if apps and any(isinstance(a, dict) and
                            str(a.get("appId", "")).lower() == app_id.lower()
                            for a in apps):
                return apps
            if attempt == 0:
                time.sleep(2)  # allow the launcher to finish registering the tile
        return apps or []

    apps, _ = run_with_session(op, session.host)
    return apps or []


def list_tiles(session: Session) -> list[dict]:
    def op(sess, topics):
        sess.subscribe([topics["applist_reply"]])
        time.sleep(0.3)
        sess.publish(topics["ui"] + "actions/applist", "0")
        raw = sess.wait_for("data/applist", 10)
        return protocol.parse_applist_message(raw) if raw else []

    apps, _ = run_with_session(op, session.host)
    return apps or []


def launch_tile(session: Session, app_id: str, name: str, url: str) -> None:
    def op(sess, topics):
        sess.publish(topics["ui"] + "actions/launchapp",
                     protocol.launch_payload(app_id, name, url))
        time.sleep(4)

    run_with_session(op, session.host)


def sha256_short(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def log(tag: str, msg: str) -> None:
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {tag}: {msg}")
