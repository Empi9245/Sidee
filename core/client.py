"""Sidee client: TV discovery, pairing, sessions, and tile actions."""
from __future__ import annotations

import hashlib
import http.client
import json
import math
import os
import re
import socket
import ssl
import threading
import tempfile
import time
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import wraps

import paho.mqtt.client as mqtt

from . import platform_support, protocol

SSDP_MULTICAST = "239.255.255.250"
SSDP_BROADCAST = "255.255.255.255"
SSDP_PORT = 1900
SSDP_MEDIA_RENDERER = "urn:schemas-upnp-org:device:MediaRenderer:1"
MQTT_PORT = 36669
UPNP_PORTS = (18400, 38400, 80)


# --- Client certificate (extracted from the official app, encoded blob) ---

def _cert_dir() -> str:
    return str(platform_support.profile_dir())


_CERT_BUNDLE = "certs.bin.k"


def _certificate_path() -> str:
    user_path = os.path.join(_cert_dir(), _CERT_BUNDLE)
    if os.path.isfile(user_path):
        return user_path
    project_dir = platform_support.resource_root(__file__)
    for folder in (".sidee", ".vidaa-tile"):
        project_path = os.path.join(project_dir, folder, _CERT_BUNDLE)
        if os.path.isfile(project_path):
            return project_path
    return str(project_dir / "core" / "tv-client.bundle")


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
    auth_profile: str = "modern"
    brand: str = "his"          # brand declared by the TV in its descriptor

    @property
    def tokenless(self) -> bool:
        return (self.auth_profile == "static" and not self.access_token
                and not self.refresh_token)

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
        if s.auth_profile not in protocol.AUTH_PROFILES:
            raise AuthError("corrupt", "unsupported TV authentication profile")
        if not all((s.host, s.device_uuid)):
            raise AuthError("corrupt", "incomplete or corrupted session")
        if s.tokenless:
            if not all((s.client_id, s.username)) or s.expires_at:
                raise AuthError("corrupt", "incomplete static pairing")
            return s
        if not all((s.access_token, s.refresh_token)):
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
    brand: str = "his"
    raw_description: str = field(default="", repr=False)


def _descriptor_brand(description: str) -> str:
    """Brand identifier the TV declares in modelDescription (brand=his on
    Hisense, brand=tos on Toshiba-licensed firmware). Falls back to 'his'."""
    for line in description.splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() == "brand":
            value = value.strip().lower()
            if re.fullmatch(r"[a-z0-9]{1,8}", value):
                return value
    return "his"


def _broadcasts_from_ipconfig(output: str) -> list[str]:
    return platform_support.broadcasts_from_ipconfig(output)


def _local_broadcasts(interfaces: list[tuple[str, str]] | None = None) -> list[str]:
    if interfaces is None:
        return platform_support.local_broadcasts()
    return sorted({target for _, target in interfaces})


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


def _notify_listener(interfaces: list[str]) -> socket.socket | None:
    """Listen for SSDP on each LAN interface; tolerate individual failures."""
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        sock.bind(("", SSDP_PORT))
        joined = False
        for host in dict.fromkeys(interfaces or ["0.0.0.0"]):
            try:
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                                socket.inet_aton(SSDP_MULTICAST) + socket.inet_aton(host))
                joined = True
            except OSError:
                continue
        if not joined:
            sock.close()
            return None
        sock.setblocking(False)
        return sock
    except OSError:
        if sock is not None:
            sock.close()
        return None


def _ssdp_location(data: bytes) -> str | None:
    """Location of an M-SEARCH reply or a MediaRenderer ssdp:alive NOTIFY."""
    text = data.decode("utf-8", "replace")
    head = text.upper()
    if head.startswith("NOTIFY"):
        # Only the device type the M-SEARCH asks for, so routers, printers
        # and other UPnP devices don't trigger extra descriptor fetches.
        nt = re.search(r"^NT:\s*(\S+)", text, re.I | re.M)
        nts = re.search(r"^NTS:\s*(\S+)", text, re.I | re.M)
        if (not nts or nts.group(1).lower() != "ssdp:alive"
                or not nt or nt.group(1) != SSDP_MEDIA_RENDERER):
            return None
    elif not head.startswith("HTTP/1.1 200"):
        return None
    m = re.search(r"Location:\s*(\S+)", text, re.I)
    return m.group(1) if m else None


def _drain_notify(sock: socket.socket, locations: dict[str, str]) -> None:
    while True:
        try:
            data, addr = sock.recvfrom(4096)
        except OSError:  # includes BlockingIOError: nothing queued
            return
        loc = _ssdp_location(data)
        if loc:
            locations[addr[0]] = loc


def discover(timeout: float = 4.0) -> list[TvInfo]:
    """Find VIDAA TVs on the LAN: broadcast M-SEARCH (the channel used
    by the official app) and multicast, then validate the descriptor.
    Some firmwares never answer M-SEARCH directly and only multicast
    NOTIFY announcements, so the SSDP group is watched as well."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    notify = None
    locations: dict[str, str] = {}
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            sock.bind(("", 0))
        except OSError:
            pass
        sock.settimeout(0.5)
        interfaces = platform_support.local_ipv4_interfaces()
        notify = _notify_listener([host for host, _ in interfaces])
        # Global broadcast may use a virtual adapter; directed broadcasts use
        # each adapter's actual subnet, as measured with the official mobile app.
        targets = list(dict.fromkeys(_local_broadcasts(interfaces)
                                    + [SSDP_BROADCAST, SSDP_MULTICAST]))
        for target in targets:
            _msearch(sock, target)
        end = time.time() + timeout
        while time.time() < end:
            if notify is not None:
                _drain_notify(notify, locations)
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                for target in targets:
                    _msearch(sock, target)  # retransmit while waiting
                continue
            loc = _ssdp_location(data)
            if loc:
                locations[addr[0]] = loc
        if notify is not None:
            _drain_notify(notify, locations)
    finally:
        sock.close()
        if notify is not None:
            notify.close()

    found: dict[str, TvInfo] = {}
    for host, loc in locations.items():
        info = fetch_descriptor(host, loc)
        if info and info.is_vidaa:
            found[host] = info
    return sorted(found.values(), key=lambda t: t.host)


def fetch_descriptor(host: str, location: str | None = None) -> TvInfo | None:
    """Download the UPnP descriptor and identify a VIDAA TV."""
    locations = [location] if location else [
        f"http://{host}:{port}/MediaServer/rendererdevicedesc.xml" for port in UPNP_PORTS]
    for loc in locations:
        conn = None
        try:
            u = urllib.parse.urlsplit(loc)
            if u.scheme != "http" or not u.hostname or u.username or u.password:
                return None
            conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=3)
            target = u.path or "/"
            if u.query:
                target += "?" + u.query
            conn.request("GET", target)
            r = conn.getresponse()
            xml = r.read().decode("utf-8", "replace")
            if r.status != 200:
                continue
            name = re.search(r"<friendlyName>([^<]+)<", xml)
            model = re.search(r"<modelDescription>(.*?)</modelDescription>",
                              xml, re.S)
            desc = model.group(1) if model else ""
            is_vidaa = ("vidaa_support" in desc or "transport_protocol" in desc
                        or "hisense" in xml.lower() or "vidaa" in xml.lower())
            return TvInfo(host=host, friendly_name=(name.group(1) if name else host),
                          model=desc.strip()[:120], is_vidaa=is_vidaa,
                          brand=_descriptor_brand(desc),
                          raw_description=xml)
        except (OSError, ValueError, http.client.HTTPException):
            continue
        finally:
            if conn is not None:
                conn.close()
    return None


def tv_timestamp(host: str) -> int:
    """TV clock from the UPnP descriptor's Date header."""
    for port in UPNP_PORTS:
        conn = None
        try:
            conn = http.client.HTTPConnection(host, port, timeout=3)
            conn.request("GET", "/MediaServer/rendererdevicedesc.xml")
            r = conn.getresponse()
            r.read()
            date = r.headers.get("Date", "")
            if date:
                import email.utils
                dt = email.utils.parsedate_to_datetime(date)
                return int(dt.timestamp())
        except (OSError, ValueError, http.client.HTTPException):
            continue
        finally:
            if conn is not None:
                conn.close()
    return int(time.time())


# --- MQTT session ---

class MqttSession:
    """TV broker connection: message collection and actions gated by step."""

    def __init__(self, host: str, device_uuid: str, tv_ts: int,
                 token: str | None = None, *, auth_profile: str = "modern",
                 brand: str = "his",
                 client_id: str | None = None, username: str | None = None):
        self.brand = brand or "his"
        self.client_id, self.username, self.password = protocol.session_credentials(
            device_uuid, tv_ts, token, auth_profile=auth_profile, brand=self.brand)
        # Token authentication belongs to the identity accepted during pairing.
        self.client_id = client_id or self.client_id
        self.username = username or self.username
        self.topics = protocol.tv_topics(self.client_id)
        # Static firmware separates the MQTT connection from the identity in
        # remoteapp topics. Use a short, unique broker ID; keep the paired topic
        # identity stable, including sessions created by 0.1.4.
        self.mqtt_client_id = ("sidee_" + protocol.new_device_uuid().replace(":", "")
                               if auth_profile == "static" else self.client_id)
        self.host = host
        self.messages: list[tuple[str, str]] = []
        self.connected = threading.Event()
        self.connect_rc: int | None = None
        self.client = mqtt.Client(client_id=self.mqtt_client_id,
                                  protocol=mqtt.MQTTv311,
                                  reconnect_on_failure=False)
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


def _compatibility_details(host: str) -> str:
    """Read public TV metadata for an auth refusal, without device identifiers."""
    info = fetch_descriptor(host)
    if not info:
        return "TV details unavailable"
    try:
        root = ET.fromstring(info.raw_description)
    except ET.ParseError:
        return "TV details unavailable"
    fields = {}
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1]
        if tag in ("manufacturer", "modelName") and node.text:
            fields[tag] = node.text
        elif tag == "modelDescription" and node.text:
            for line in node.text.splitlines():
                key, sep, value = line.partition("=")
                if sep and key.strip() in ("brand", "transport_protocol"):
                    fields[key.strip()] = value
    # Never include friendly names, IPs, MACs, serial numbers, UDNs or tokens.
    details = [f"{key}={' '.join(value.split())[:48]}"
               for key, value in fields.items()]
    return ", ".join(details) if details else "TV details unavailable"


def _pairing_connection(host: str, device_uuid: str, timestamp: int,
                        preferred: str = "static",
                        brand: str = "his") -> tuple[MqttSession, str]:
    """Try each documented profile once, only after an explicit auth refusal.

    Reference implementations: stevene1919/hisense_vidaa/crypto.py,
    Lucent-/vidaa-control/vidaa/credentials.py (brand passed per-TV) and
    warrenrees/pyvidaa (static identity). The brand is the one the TV itself
    declares in its descriptor; the value suffixes are firmware constants.
    Network and TLS failures cannot be fixed by changing credentials.
    """
    profiles = list(dict.fromkeys((preferred,) + protocol.AUTH_PROFILES))
    attempted = []
    for profile in profiles:
        sess = MqttSession(host, device_uuid, timestamp, auth_profile=profile,
                           brand=brand)
        accepted = False
        try:
            rc = sess.start()
            attempted.append(f"{profile}: rc={rc}")
            log("auth", f"pairing connection {profile}: rc={rc}")
            if rc == 0:
                accepted = True
                return sess, profile
            if rc not in (4, 5):
                raise ConnectionError(f"connection refused by the TV (rc={rc})")
        finally:
            if not accepted:
                sess.stop()
    details = _compatibility_details(host)
    log("auth", f"TV compatibility: {details}")
    raise ConnectionError(
        "connection refused by the TV (" + "; ".join(attempted) + "). "
        "The TV refused authentication before a PIN could be requested. "
        "If the official VIDAA app can control it, this firmware needs "
        "further compatibility checks. " + details)


def _saved_connection(session: Session, token: str | None) -> MqttSession:
    return MqttSession(session.host, session.device_uuid,
                       0 if session.tokenless else tv_timestamp(session.host), token=token,
                       auth_profile=session.auth_profile,
                       brand=getattr(session, "brand", "his") or "his",
                       client_id=session.client_id or None,
                       username=session.username or None)


@_serialized_session
def pair(host: str, pin_provider, timeout: float = 60.0) -> Session:
    """Pairing: TV PIN -> tokens or a verified static identity. Reuse the paired UUID;
    generate a new UUID only after multiple consecutive failures
    (invalid state on the TV)."""
    previous = Session().load_or_none()
    stored = previous.device_uuid if previous and previous.host == host else None
    reuse = (stored and stored != "NEW"
             and not _pair_failures_exceeded())
    device_uuid = stored if reuse else protocol.new_device_uuid()
    # The brand must match what the TV itself declares: the official app
    # takes it as an input to the same credential algorithm (brand=his on
    # Hisense, brand=tos on Toshiba-licensed firmware).
    info = fetch_descriptor(host)
    brand = (getattr(info, "brand", "his") or "his") if info else "his"
    if not reuse and brand != "his":
        log("auth", f"TV declares brand={brand}: using it in the credentials")
    sess = None
    tok = None
    try:
        # A rejected dynamic attempt can throttle static authentication on
        # Toshiba firmware. Fresh pairings try static first; a known working
        # profile still takes priority when pairing the same TV again.
        preferred = previous.auth_profile if reuse else "static"
        if not reuse and info is not None and info.raw_description:
            protocol_match = re.search(
                r"transport_protocol\s*[=:]\s*(\d+)",
                info.raw_description,
                re.IGNORECASE,
            )
            if protocol_match and int(protocol_match.group(1)) >= 3290:
                preferred = "modern"
                log(
                    "auth",
                    f"Detected transport_protocol={protocol_match.group(1)}; "
                    "trying modern authentication first",
                )
        sess, auth_profile = _pairing_connection(host, device_uuid,
                                                tv_timestamp(host), preferred,
                                                brand=brand)
        since = len(sess.messages)
        sess.subscribe([
            sess.topics["mobile"] + "ui_service/data/authentication",
            sess.topics["mobile"] + "ui_service/data/authenticationcode",
            sess.topics["token_reply"],
        ])
        time.sleep(0.3)
        notification = None
        if auth_profile == "static":
            # Pre-token firmware shows the PIN in response to a state query.
            # Newer static-auth TVs can still use vidaa_app_connect.
            sess.publish(sess.topics["ui"] + "actions/gettvstate", "")
            notification = sess.wait_for("data/authentication", 5, since)
        if notification is None:
            sess.publish(sess.topics["ui"] + "actions/vidaa_app_connect",
                         protocol.pair_connect_payload())
            notification = sess.wait_for("data/authentication",
                                         10 if auth_profile == "static" else 15, since)
        if notification is None:
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
        raw = sess.wait_for("platform_service/data/tokenissuance",
                            min(timeout, 5.0) if auth_profile == "static" else timeout,
                            since_pin)
        if raw is None:
            if auth_profile != "static":
                raise TimeoutError("PIN accepted, but the TV did not send a token. "
                                   "Request a new code.")
            # Static firmware authorizes the client identity after the PIN.
            # Confirm it answers a fresh, read-only request before saving it.
            sess.subscribe([sess.topics["applist_reply"]])
            time.sleep(0.3)
            since_apps = len(sess.messages)
            sess.publish(sess.topics["ui"] + "actions/applist", "0")
            apps = sess.wait_for("ui_service/data/applist", min(timeout, 8.0), since_apps)
            if apps is None or protocol.parse_applist_message(apps) is None:
                raise TimeoutError("PIN accepted, but the TV did not confirm access "
                                   "to its app list. Request a new code.")
        else:
            tok = protocol.parse_token_message(raw)
            if not tok:
                raise ValueError("invalid token response")
    except Exception as e:
        if not isinstance(e, PairingCancelled):
            _register_pair_failure(reuse)
        raise
    finally:
        if sess is not None:
            sess.stop()
    s = Session(host=host, device_uuid=device_uuid,
                client_id=sess.client_id, username=sess.username,
                pair_failures=0, auth_profile=auth_profile,
                brand=brand)
    if tok is not None:
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
    if session.tokenless:
        return session
    sess = _saved_connection(session, session.refresh_token)
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
    if session.tokenless:
        return session
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
            sess = _saved_connection(session, None if session.tokenless else session.access_token)
            try:
                try:
                    rc = sess.start()
                except OSError:
                    if attempt:
                        raise
                    rc = None
                if rc == 0:
                    return op(sess, sess.topics), session
                if session.tokenless:
                    if rc in (4, 5):
                        raise AuthError("needs_pairing", "the TV no longer recognizes "
                                        "this pairing: request a new code")
                    raise ConnectionError(f"TV unreachable (rc={rc})")
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


def tile_matches_request(tile: object, app_id: str, url: str) -> bool:
    """Confirm both the tile identity and the address reported by the TV."""
    if not isinstance(tile, dict) or str(tile.get("appId", "")).lower() != app_id.lower():
        return False
    addresses = [tile[key].strip() for key in ("url", "appUrl", "URL")
                 if isinstance(tile.get(key), str) and tile[key].strip()]
    return bool(addresses) and all(address == url for address in addresses)


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
            if apps and any(tile_matches_request(a, app_id, url) for a in apps):
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
