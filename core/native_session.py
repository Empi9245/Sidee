"""Sidee native mode: install flow driver.

Runs the opaque per-session commands received from the service over the
already-paired MQTT channel, then polls the service for progress.
The client never inspects command payloads: it is a generic relay.
"""
from __future__ import annotations

import os
import time
import re

from . import client, native_api

MAX_CUSTOM_HTML = 300_000  # matching the service-side cap


def _resolve_target(target: str) -> dict:
    """A target is a catalog id, or a path to a self-contained .html app."""
    p = os.path.abspath(target)
    if os.path.isfile(p):
        with open(p, "rb") as f:
            raw = f.read(MAX_CUSTOM_HTML + 1)
        if len(raw) > MAX_CUSTOM_HTML:
            raise ValueError(
                f"custom app too large (max {MAX_CUSTOM_HTML} bytes)")
        html = raw.decode("utf-8")
        name = os.path.splitext(os.path.basename(p))[0][:40]
        return {"custom_html": html, "name": name}
    return {"id": target}


def validate_commands(commands, topics):
    if not isinstance(commands, list) or not 1 <= len(commands) <= 8:
        raise ValueError("invalid service commands")
    for c in commands:
        if not isinstance(c, dict) or c.get("op") not in ("publish", "sleep"):
            raise ValueError("invalid service command")
        wait = c.get("ms", 1000) if c["op"] == "sleep" else c.get("wait_ms", 1500)
        if isinstance(wait, bool) or not isinstance(wait, (float, int)) or not 0 <= wait <= 10_000:
            raise ValueError("invalid command delay")
        if c["op"] == "publish":
            key, suffix = c.get("topic_key"), c.get("topic_suffix")
            if key not in topics or not topics[key] or not isinstance(suffix, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+(/[a-zA-Z0-9_-]+)*", suffix) or len(suffix) > 128:
                raise ValueError("invalid command topic")
            if not isinstance(c.get("payload"), str) or len(c["payload"].encode("utf-8")) > 1_000_000:
                raise ValueError("invalid command payload")


def install(target: str, api_base: str | None = None, gate_key: str | None = None,
            on_update=print) -> bool:
    """Install one app as a permanent native tile. Returns True on success."""
    base = api_base or native_api.DEFAULT_API_BASE
    sess = client.Session().load_or_none()
    if not sess:
        on_update("Nessun TV accoppiato: usa Find TV + Request code "
                  "(o 'python sidee.py pair IP').")
        return False

    app = _resolve_target(target)
    info = native_api.start_session(
        app, gate_key=gate_key, api_base=base,
        device_uuid=sess.device_uuid,
    )
    sid = info["sid"]
    commands = info.get("commands", [])
    on_update(f"Sessione avviata ({info.get('expires_in', 0) // 60} min): "
              "comunico col TV…")

    def op(conn, topics):
        """Blind executor: publish whatever the service asked, verbatim."""
        validate_commands(commands, topics)  # validate entire batch before any publication
        for c in commands:
            kind = c.get("op")
            if kind == "sleep":
                time.sleep(c.get("ms", 1000) / 1000)
            elif kind == "publish":
                suffix = c.get("topic_suffix", "")
                key = c.get("topic_key", "ui")
                base_topic = topics[key]
                if suffix:
                    base_topic += suffix
                conn.publish(base_topic, str(c["payload"]))
                time.sleep(c.get("wait_ms", 1500) / 1000)
            else:
                raise ValueError(f"unknown command kind: {kind!r}")

    client.run_with_session(op, sess.host)
    final = native_api.poll_status(base, sid, on_update)
    return final.get("state") == "done"
