"""Sidee native mode: HTTPS client for the Sidee install service.

The client is a thin, generic relay: it requests an install session,
executes the opaque per-session commands the server returns (publishing
JSON strings on the TV's MQTT topics), and polls the server for progress.
It contains no installation logic or credentials beyond your TV pairing.
"""
from __future__ import annotations

import json
import re
import ssl
import time
import http.client
import urllib.parse
from datetime import datetime, timezone

# Set once before release: your deployed Worker URL (https).
DEFAULT_API_BASE = "https://set-your-worker-url.example"

MAX_POLL_SECONDS = 15 * 60


class ApiError(Exception):
    pass


def _conn(base: str) -> http.client.HTTPSConnection:
    u = urllib.parse.urlsplit(base if "//" in base else "//" + base)
    local = u.scheme == "http" and u.hostname in ("127.0.0.1", "localhost", "::1")
    if u.scheme != "https" and not local:
        raise ApiError("the install service must be https")
    if not u.hostname or u.username or u.password or u.path not in ("", "/") or u.query or u.fragment:
        raise ApiError("invalid service URL")
    if local:
        return http.client.HTTPConnection(u.hostname, u.port or 80, timeout=20)
    return http.client.HTTPSConnection(
        u.hostname, u.port or 443, timeout=20,
        context=ssl.create_default_context(),
    )


def _request(base: str, method: str, path: str, body=None,
             extra_headers=None) -> dict:
    c = _conn(base or DEFAULT_API_BASE)
    try:
        headers = {"Content-Type": "application/json",
                   "Accept": "application/json"}
        if extra_headers:
            headers.update(extra_headers)
        payload = json.dumps(body, ensure_ascii=True) if body is not None else None
        c.request(method, path, body=payload, headers=headers)
        r = c.getresponse()
        raw_bytes = r.read(2_000_001)
        if len(raw_bytes) > 2_000_000:
            raise ApiError("service response too large")
        raw = raw_bytes.decode("utf-8", "replace")
        try:
            data = json.loads(raw)
        except ValueError:
            data = None
        if r.status != 200:
            code = data.get("error", "request_failed") if isinstance(data, dict) else "request_failed"
            if not isinstance(code, str):
                code = "request_failed"
            raise ApiError(_ERRORS.get(code, f"service request failed ({r.status})"))
        if not isinstance(data, dict):
            raise ApiError("invalid service response")
        return data
    finally:
        c.close()


def catalog(api_base: str | None = None) -> list[dict]:
    d = _request(api_base or DEFAULT_API_BASE, "GET", "/v1/catalog")
    return d.get("apps", [])


def start_session(app: dict, gate_key: str | None = None,
                  api_base: str | None = None,
                  device_uuid: str = "") -> dict:
    headers = {"X-Sidee-Key": gate_key} if gate_key else None
    d = _request(api_base or DEFAULT_API_BASE, "POST", "/v1/session/start",
                 {"app": app, "tv": {"device_uuid": device_uuid}},
                 headers)
    if not d.get("ok"):
        code = d.get("error")
        raise ApiError(_ERRORS.get(code, "unable to start install session") if isinstance(code, str) else "unable to start install session")
    if not isinstance(d.get("sid"), str) or not re.fullmatch(r"[0-9a-f]{64}", d["sid"]):
        raise ApiError("invalid install session")
    return d


def poll_status(api_base: str, sid: str, on_update,
                interval_s: float = 3.0,
                max_seconds: float = MAX_POLL_SECONDS) -> dict:
    """Poll progress; print changes; return the final status dict."""
    if not isinstance(sid, str) or not re.fullmatch(r"[0-9a-f]{64}", sid):
        raise ApiError("invalid install session")
    last: tuple | None = None
    t0 = time.monotonic()
    while time.monotonic() - t0 < max_seconds:
        d = _request(api_base, "GET", f"/v1/session/{sid}/status")
        key = (d.get("state"), d.get("stage"))
        if last != key:
            last = key
            on_update(datetime.now(timezone.utc).strftime("%H:%M:%S")
                      + "  " + describe(d))
            if d.get("state") in ("done", "failed", "missing"):
                return d
        time.sleep(max(0.1, min(interval_s, 30)))
    return {"state": "failed", "failure": "session timed out"}


_MESSAGES = {
    "created": "In attesa che il TV apra la pagina di sessione…",
    "launched": "Il TV ha aperto la pagina: verifica in corso…",
    "attested": "Installazione in corso. Fase {stage}…",
    "done": "Fatto! Stacca la spina del TV (non standby), riaccendi e apri "
            "la nuova tile dalla HOME.",
    "failed": "Installazione non riuscita ({failure}).",
}


def describe(d: dict) -> str:
    st = str(d.get("state", "?"))
    if st == "attested":
        return _MESSAGES["attested"].format(stage=d.get("stage", "?"))
    if st == "failed":
        failure = d.get("failure")
        safe = failure if isinstance(failure, str) and failure in _SAFE_FAILURES else "errore sconosciuto"
        return _MESSAGES["failed"].format(failure=safe)
    return _MESSAGES.get(st, "Stato di installazione non disponibile.")


_SAFE_FAILURES = {"expired", "license_invalid", "missing_device", "tv_unavailable", "installation_failed"}


_ERRORS = {
    "missing_key": "Serve una chiave di attivazione valida anche per la demo nativa.",
    "invalid_key": "Chiave non valida o revocata. Contatta l'assistenza con il riferimento d'acquisto.",
    "missing_device": "Identificativo di accoppiamento assente: accoppia nuovamente il TV.",
    "too_many_tvs": "Limite dei dispositivi raggiunto. Chiedi assistenza per il cambio TV.",
    "rate_limited": "Troppe richieste: riprova tra un'ora.",
}
