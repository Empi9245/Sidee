"""Sidee protocol core.

Protocol parameters are stored in encoded form and decoded on import:
the public module describes HOW to use the client, rather than protocol
details. The client only performs the documented TV actions
(adding/listing/launching tiles): no other access.
"""
from __future__ import annotations

import base64
import hashlib
import json
import uuid as _uuid

_K = b"v1tile"


def _deco(data_b64: str, key: bytes) -> bytes:
    raw = base64.b85decode(data_b64)
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(raw))


_C = [
    "MF}upSs^t7L@!uSM*&SJUsF$TOkXM{GYLXpEnP!%",
    "9uOTVA4XC~Q2;UlP*7e7",
    "AgN#;M`qty",
]

PATTERN = _deco(_C[0], _K).decode("ascii")
VALUE_SUFFIX = _deco(_C[1], _K).decode("ascii")
XOR_MASK = int.from_bytes(_deco(_C[2], _K), "big")
BRAND = "his"
OPERATION = "vidaacommon_001"


def _md5u(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest().upper()


def new_device_uuid() -> str:
    """Client device identifier (random, MAC address format)."""
    return ":".join(f"{b:02x}" for b in _uuid.uuid4().bytes[:6])


def session_credentials(device_uuid: str, tv_timestamp: int,
                        token: str | None = None) -> tuple[str, str, str]:
    """(client_id, username, password) for the session.

    Without a token: password derived from the TV clock (initial handshake).
    With a token (access or refresh): same identity, token as password.
    """
    clean = device_uuid.replace("-", ":").lower()
    race = _md5u(f"{PATTERN}${clean}")[:6]
    client_id = f"{clean}${BRAND}${race}_{OPERATION}"
    username = f"{BRAND}${tv_timestamp ^ XOR_MASK}"
    if token is not None:
        return client_id, username, token
    digit = sum(int(d) for d in str(tv_timestamp)) % 10
    value_md5 = _md5u(f"{BRAND}{digit}{VALUE_SUFFIX}")[:6]
    return client_id, username, _md5u(f"{tv_timestamp}${value_md5}")


def tv_topics(client_id: str) -> dict[str, str]:
    mob = f"/remoteapp/mobile/{client_id}/"
    return {
        "ui": f"/remoteapp/tv/ui_service/{client_id}/",
        "platform": f"/remoteapp/tv/platform_service/{client_id}/",
        "mobile": mob,
        "broadcast": "/remoteapp/mobile/broadcast/",
        "applist_reply": mob + "ui_service/data/applist",
        "token_reply": mob + "platform_service/data/tokenissuance",
    }


def pair_connect_payload() -> str:
    return json.dumps({"app_version": 2, "connect_result": 0,
                       "device_type": "Mobile App"})


def pair_pin_payload(pin: int | str) -> str:
    return json.dumps({"authNum": int(pin)})


def token_request_payload(refresh_token: str) -> str:
    return json.dumps({"refreshtoken": refresh_token or ""})


def install_payload(app_id: str, name: str, url: str, image: str = "") -> str:
    """Tile registration: web app installation action (format
    equivalent to the one sent by the official mobile app)."""
    return json.dumps({
        "type": "app_install",
        "app_info": {
            "Title": name,
            "StoreType": 99,
            "mediaId": app_id,
            "Id": app_id,
            "Image": image,
            "URL": url,
            "configUrlDownload": 0,
            "configUrl": "",
        },
    })


def launch_payload(app_id: str, name: str, url: str) -> str:
    return json.dumps({"appId": app_id, "name": name, "url": url,
                       "urlType": 37, "appName": name, "appUrl": url})


def parse_token_message(payload: str) -> dict | None:
    try:
        d = json.loads(payload)
    except Exception:
        return None
    return d if isinstance(d, dict) and "accesstoken" in d else None


def parse_applist_message(payload: str) -> list | None:
    try:
        d = json.loads(payload)
    except Exception:
        return None
    return d if isinstance(d, list) else None
