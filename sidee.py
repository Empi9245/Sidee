#!/usr/bin/env python3
"""
Sidee - standalone VIDAA browser research / web-app installer host.

Runs:
- DNS responder on UDP/53 (configured VIDAA hosts -> this PC)
- HTTPS UI on TCP/443
- HTTP dashboard/fallback on TCP/8080
- installed-app context probe host on TCP/80
- raw-IP HTTP A/B test UI on the existing TCP/8080 dashboard
- JSON report/config API

No third-party Python packages are required.
OpenSSL is used only to generate a temporary self-signed vidaahub.com certificate.
"""

from __future__ import annotations

import argparse
import hashlib
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
import time
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"
REPORTS_DIR = ROOT / "reports"
CONFIG_PATH = ROOT / "config.json"
CERT_DIR = ROOT / ".sidee-certs"
APPINFO_BACKUP_DIR = ROOT / "backups" / "appinfo"
APPINFO_BACKUP_ID_RE = re.compile(r"^appinfo-backup-\d{8}-\d{6}-[a-f0-9]{8}$")
APPINFO_MAX_BACKUP_BYTES = 4 * 1024 * 1024

stop_event = threading.Event()
REPORT_WRITE_LOCK = threading.Lock()
SESSION_ID_RE = re.compile(r"^sidee-\d{8}-\d{6}-[a-f0-9]{4}$")
APP_CONTEXT_HOSTS = {
    "vidaa.smartone-iptv.com": {"id": "1470", "name": "Smartone IPTV", "mode": "SMARTONE_APP_CONTEXT"},
    "vidaa.duplecast.com": {"id": "1876", "name": "Duplecast", "mode": "DUPLECAST_APP_CONTEXT"},
}
APP_CONTEXT_HIT_LOCK = threading.Lock()
APP_CONTEXT_LAST_HIT = None
APP_CONTEXT_TRANSPORT_LOCK = threading.Lock()
APP_CONTEXT_TRANSPORT_LAST = {}


def client_build_id():
    """Content-derived ID for the exact web/app.js bytes served by this host."""
    try:
        digest = hashlib.sha256((WEB_DIR / "app.js").read_bytes()).hexdigest()[:12]
        return "app-" + digest
    except OSError:
        return "app-unavailable"


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


def _validate_appinfo_raw(raw):
    if not isinstance(raw, str):
        raise ValueError("Expected raw Appinfo JSON string")
    encoded = raw.encode("utf-8")
    if len(encoded) > APPINFO_MAX_BACKUP_BYTES:
        raise ValueError("Appinfo backup exceeds size limit")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid Appinfo JSON: {exc}") from exc
    if not isinstance(parsed, dict) or not isinstance(parsed.get("AppInfo"), list):
        raise ValueError("Appinfo JSON must contain an AppInfo array")
    return parsed, encoded


def _appinfo_backup_dir(session_id):
    session_report_filename(session_id)
    root = APPINFO_BACKUP_DIR.resolve()
    target = (APPINFO_BACKUP_DIR / session_id).resolve()
    if target.parent != root:
        raise ValueError("Invalid Appinfo backup directory")
    target.mkdir(parents=True, exist_ok=True)
    return target


def create_appinfo_backup(session_id, raw, client_hash=None, client_build=None):
    server_build = client_build_id()
    if client_build is not None and client_build != server_build:
        raise ValueError(f"Stale client build: {client_build!r} != {server_build!r}")
    parsed, encoded = _validate_appinfo_raw(raw)
    sha256 = hashlib.sha256(encoded).hexdigest()
    if client_hash is not None and client_hash != sha256:
        raise ValueError("Client/server Appinfo hash mismatch")

    backup_dir = _appinfo_backup_dir(session_id)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    nonce = hashlib.sha256(f"{session_id}:{time.time_ns()}".encode("utf-8")).hexdigest()[:8]
    backup_id = f"appinfo-backup-{stamp}-{nonce}"
    if not APPINFO_BACKUP_ID_RE.fullmatch(backup_id):
        raise ValueError("Invalid generated backup ID")

    path = (backup_dir / f"{backup_id}.json").resolve()
    if path.parent != backup_dir:
        raise ValueError("Invalid Appinfo backup path")

    with path.open("x", encoding="utf-8", newline="") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())

    return {
        "backupId": backup_id,
        "sessionId": session_id,
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha256,
        "bytes": len(encoded),
        "appInfoCount": len(parsed["AppInfo"]),
        "createdAt": _utc_timestamp(),
        "clientBuildId": client_build,
        "serverBuildId": server_build,
    }


def read_appinfo_backup(session_id, backup_id):
    if not isinstance(backup_id, str) or not APPINFO_BACKUP_ID_RE.fullmatch(backup_id):
        raise ValueError("Invalid Appinfo backup ID")

    backup_dir = _appinfo_backup_dir(session_id)
    path = (backup_dir / f"{backup_id}.json").resolve()
    if path.parent != backup_dir or not path.is_file():
        raise ValueError("Appinfo backup not found")

    raw = path.read_text(encoding="utf-8")
    parsed, encoded = _validate_appinfo_raw(raw)
    return {
        "backupId": backup_id,
        "sessionId": session_id,
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "bytes": len(encoded),
        "appInfoCount": len(parsed["AppInfo"]),
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(path.stat().st_mtime)),
        "raw": raw,
    }

REPORT_SYNC_LOCK = threading.Lock()
REPORT_SYNC_EVENT = threading.Event()
REPORT_SYNC_CONFIG = {}
REPORT_SYNC_PENDING = None
REPORT_SYNC_STATUS = {
    "enabled": False,
    "state": "DISABLED",
    "message": "GitHub report sync is disabled.",
    "sessionId": None,
    "remote": None,
    "branch": None,
    "commit": None,
    "lastAttemptAt": None,
    "lastSuccessAt": None,
}


def _utc_timestamp():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _new_probe_session_id():
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    nonce = hashlib.sha256(f"{time.time_ns()}:{os.getpid()}".encode("utf-8")).hexdigest()[:4]
    return f"sidee-{stamp}-{nonce}"


def _normalized_host(value):
    return str(value or "").split(":", 1)[0].strip().lower().rstrip(".")


def _sync_app_transport_observation(transport, host, path=""):
    host = _normalized_host(host)
    app = APP_CONTEXT_HOSTS.get(host)
    if not app:
        return None
    key = f"{transport}:{host}:{path}"
    now_epoch = time.time()
    with APP_CONTEXT_TRANSPORT_LOCK:
        previous = float(APP_CONTEXT_TRANSPORT_LAST.get(key, 0))
        if now_epoch - previous < 3.0:
            return None
        APP_CONTEXT_TRANSPORT_LAST[key] = now_epoch
    session_id = _new_probe_session_id()
    now = _utc_timestamp()
    report = {
        "sessionId": session_id,
        "clientBuildId": client_build_id(),
        "serverBuildId": client_build_id(),
        "buildMatch": True,
        "startedAt": now,
        "updatedAt": now,
        "accessContext": {
            "href": (("https://" if transport == "TLS_SNI" else "http://") + host + str(path or ""))[:1200],
            "origin": ("https://" if transport == "TLS_SNI" else "http://") + host,
            "protocol": "https:" if transport == "TLS_SNI" else "http:",
            "hostname": host,
            "host": host,
            "accessMode": app["mode"],
        },
        "accessMode": app["mode"],
        "contextIdentityFingerprint": {
            "timestamp": now,
            "automatic": True,
            "transportOnly": True,
            "expectedContext": dict(app),
            "transportObservation": {
                "transport": transport,
                "host": host,
                "path": str(path or "")[:500],
            },
            "classification": "APP_CONTEXT_" + transport + "_OBSERVED",
            "safety": "Server-side transport observation only; no native API call or write was made.",
        },
        "summary": {
            "runtimeIdentity": "UNKNOWN",
            "contextInit": "NOT_RUN",
            "contextFingerprint": "APP_CONTEXT_" + transport + "_OBSERVED",
            "permissionGate": "UNKNOWN",
            "appInfoWrite": "NOT_RUN",
        },
    }
    write_session_report(session_id, report)
    queue_report_sync(session_id, report, "app-context-" + transport.lower())
    return report


def _record_app_context_hit(host, path, client_ip, headers):
    global APP_CONTEXT_LAST_HIT
    app = APP_CONTEXT_HOSTS.get(host)
    if not app:
        return None
    hit = {
        "timestamp": _utc_timestamp(),
        "host": host,
        "path": str(path or "")[:500],
        "clientIp": str(client_ip or "")[:80],
        "userAgent": str(headers.get("User-Agent", ""))[:500],
        "referer": str(headers.get("Referer", ""))[:500],
        "expectedApp": dict(app),
    }
    with APP_CONTEXT_HIT_LOCK:
        APP_CONTEXT_LAST_HIT = hit
    print(f"[APP-CONTEXT] {client_ip} {host} {path}")
    _sync_app_transport_observation("HTTP", host, path)
    return hit


def _app_context_bootstrap_html(host):
    app = APP_CONTEXT_HOSTS[host]
    app_json = json.dumps(app, ensure_ascii=False)
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,height=device-height,initial-scale=1">
<title>Sidee App Context Probe</title>
<style>
html,body{{margin:0;background:#101010;color:#fff;font-family:Arial,sans-serif}}
main{{box-sizing:border-box;min-height:100vh;padding:6vh 6vw}}
h1{{font-size:4vw;margin:0 0 2vh}}
p,pre{{font-size:2vw;line-height:1.4}}
pre{{white-space:pre-wrap;background:#191919;padding:2vw;border-radius:1vw;max-width:90vw}}
.ok{{color:#9fe6ae}} .wait{{color:#f0d98a}}
</style>
</head>
<body>
<main>
<h1>Sidee · native app context</h1>
<p id="state" class="wait">Capturing read-only VIDAA identity…</p>
<pre id="out">host: {host}\nexpected app: {app["name"]} ({app["id"]})</pre>
</main>
<script>
(function(){{
  "use strict";
  var expected={app_json};
  function safeValue(v){{
    if(v===undefined)return "[undefined]";
    if(v===null||typeof v==="string"||typeof v==="number"||typeof v==="boolean")return v;
    return Object.prototype.toString.call(v);
  }}
  function prop(root,name){{
    try{{return {{status:"RETURNED",value:safeValue(root&&root[name])}};}}
    catch(e){{return {{status:"ERROR",value:null,error:String(e&&e.message||e)}};}}
  }}
  function call(root,name){{
    try{{
      if(!root||typeof root[name]!=="function")return {{status:"UNAVAILABLE",value:null}};
      return {{status:"RETURNED",value:safeValue(root[name].call(root))}};
    }}catch(e){{return {{status:"ERROR",value:null,error:String(e&&e.message||e)}};}}
  }}
  var svc=null,ctx=null;
  try{{svc=window.vowOS&&window.vowOS.service;}}catch(e){{}}
  try{{ctx=window.vowOSContext;}}catch(e){{}}
  var payload={{
    timestamp:new Date().toISOString(),
    href:location.href,
    origin:location.origin,
    protocol:location.protocol,
    hostname:location.hostname,
    expectedApp:expected,
    userAgent:navigator.userAgent,
    identity:{{
      navigatorAppIdentifier:prop(navigator,"appIdentifier"),
      serviceIdentifier:call(svc,"getIdentifier"),
      appIdentifier:call(ctx,"getAppIdentifier"),
      appId:call(ctx,"getAppId"),
      roleId:call(window,"Hisense_GetRoleID"),
      customerId:call(window,"Hisense_GetCustomerID"),
      supportAppConfig:call(window,"Hisense_SupportAppConfig")
    }},
    capabilities:{{
      hiUtils:typeof window.HiUtils_createRequest==="function",
      installLegacy:typeof window.Hisense_installApp==="function",
      installV2:typeof window.Hisense_installApp_V2==="function",
      fileRead:typeof window.Hisense_FileRead==="function",
      fileWrite:typeof window.Hisense_FileWrite==="function",
      vowService:!!svc,
      vowContext:!!ctx
    }}
  }};
  var out=document.getElementById("out"),state=document.getElementById("state");
  out.textContent=JSON.stringify(payload,null,2);
  try{{
    var xhr=new XMLHttpRequest();
    xhr.open("POST","/api/app-context-bootstrap",true);
    xhr.setRequestHeader("Content-Type","application/json");
    xhr.onreadystatechange=function(){{
      if(xhr.readyState!==4)return;
      if(xhr.status>=200&&xhr.status<300){{
        state.textContent="Captured and synced. You can leave this screen open.";
        state.className="ok";
      }}else{{
        state.textContent="Captured locally in the page; server sync failed ("+xhr.status+").";
      }}
    }};
    xhr.send(JSON.stringify(payload));
  }}catch(e){{
    state.textContent="Capture complete; upload failed: "+String(e&&e.message||e);
  }}
}})();
</script>
</body>
</html>"""


def _save_app_context_bootstrap(data, server_host, client_ip):
    host = _normalized_host(server_host)
    expected = APP_CONTEXT_HOSTS.get(host)
    if not expected:
        raise ValueError("Unknown app-context host")
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object")
    session_id = _new_probe_session_id()
    now = _utc_timestamp()
    identity = data.get("identity") if isinstance(data.get("identity"), dict) else {}
    report = {
        "sessionId": session_id,
        "clientBuildId": client_build_id(),
        "serverBuildId": client_build_id(),
        "buildMatch": True,
        "startedAt": now,
        "updatedAt": now,
        "accessContext": {
            "href": str(data.get("href") or "")[:1000],
            "origin": str(data.get("origin") or "")[:500],
            "protocol": str(data.get("protocol") or "")[:40],
            "hostname": str(data.get("hostname") or host)[:255],
            "host": host,
            "accessMode": expected["mode"],
        },
        "accessMode": expected["mode"],
        "serverAccess": {"host": server_host, "requestScheme": "http", "requestPort": 80},
        "device": {"userAgent": str(data.get("userAgent") or "")[:1000]},
        "baseline": {
            "label": "appContextBootstrap",
            "timestamp": str(data.get("timestamp") or now)[:80],
            "navigatorAppIdentifier": identity.get("navigatorAppIdentifier"),
            "serviceIdentifier": identity.get("serviceIdentifier"),
            "appIdentifier": identity.get("appIdentifier"),
            "appId": identity.get("appId"),
            "roleId": identity.get("roleId"),
            "customerId": identity.get("customerId"),
        },
        "contextIdentityFingerprint": {
            "timestamp": str(data.get("timestamp") or now)[:80],
            "automatic": True,
            "bootstrap": True,
            "pageContext": {
                "href": str(data.get("href") or "")[:1000],
                "origin": str(data.get("origin") or "")[:500],
                "protocol": str(data.get("protocol") or "")[:40],
                "hostname": str(data.get("hostname") or host)[:255],
                "accessMode": expected["mode"],
            },
            "expectedContext": dict(expected),
            "identity": identity,
            "capabilities": data.get("capabilities") if isinstance(data.get("capabilities"), dict) else {},
            "serverObserved": {"host": host, "clientIp": str(client_ip or "")[:80]},
            "classification": "APP_CONTEXT_BOOTSTRAP_CAPTURED",
            "safety": "Read-only bootstrap. No setters, install/uninstall, file writes or guessed native calls.",
        },
        "summary": {
            "runtimeIdentity": "PRESENT" if any(
                isinstance(identity.get(k), dict) and str(identity[k].get("value") or "").strip()
                for k in ("navigatorAppIdentifier", "serviceIdentifier", "appIdentifier", "appId")
            ) else "MISSING",
            "contextInit": "NOT_RUN",
            "contextFingerprint": "APP_CONTEXT_BOOTSTRAP_CAPTURED",
            "permissionGate": "UNKNOWN",
            "appInfoWrite": "NOT_RUN",
        },
    }
    write_session_report(session_id, report)
    queue_report_sync(session_id, report, "app-context-bootstrap")
    return report


def _report_sync_status():
    with REPORT_SYNC_LOCK:
        return dict(REPORT_SYNC_STATUS)


def _set_report_sync_status(**updates):
    with REPORT_SYNC_LOCK:
        REPORT_SYNC_STATUS.update(updates)
        return dict(REPORT_SYNC_STATUS)


def configure_report_sync(config):
    global REPORT_SYNC_CONFIG
    raw = config.get("github_report_sync", {}) if isinstance(config, dict) else {}
    REPORT_SYNC_CONFIG = {
        "enabled": bool(raw.get("enabled", False)),
        "remote": str(raw.get("remote", "origin")).strip() or "origin",
        "branch": str(raw.get("branch", "sidee-reports")).strip() or "sidee-reports",
        "base_branch": str(raw.get("base_branch", "main")).strip() or "main",
        "latest_path": str(raw.get("latest_path", "reports/latest.json")).strip() or "reports/latest.json",
        "history_dir": str(raw.get("history_dir", "reports/sessions")).strip() or "reports/sessions",
        "debounce_seconds": max(0.5, min(float(raw.get("debounce_seconds", 2.0)), 10.0)),
    }
    state = "IDLE" if REPORT_SYNC_CONFIG["enabled"] else "DISABLED"
    message = (
        "Waiting for a report to sync."
        if REPORT_SYNC_CONFIG["enabled"]
        else "GitHub report sync is disabled."
    )
    _set_report_sync_status(
        enabled=REPORT_SYNC_CONFIG["enabled"],
        state=state,
        message=message,
        remote=REPORT_SYNC_CONFIG["remote"],
        branch=REPORT_SYNC_CONFIG["branch"],
        commit=None,
    )


def _validate_git_name(value, label):
    if not re.fullmatch(r"[A-Za-z0-9._/-]{1,160}", value):
        raise ValueError(f"Invalid Git {label}")
    if (
        value.startswith(("/", ".", "-"))
        or value.endswith(("/", "."))
        or ".." in value
        or "@{" in value
        or "//" in value
    ):
        raise ValueError(f"Invalid Git {label}")
    return value


def _validate_remote_name(value):
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", value):
        raise ValueError("Invalid Git remote")
    return value


def _validate_repo_relative_path(value, label):
    pure = pathlib.PurePosixPath(value)
    if pure.is_absolute() or not pure.parts or any(part in ("", ".", "..") for part in pure.parts):
        raise ValueError(f"Invalid {label}")
    return pure


def _run_git(args, cwd=ROOT, timeout=45, check=True):
    git = shutil.which("git")
    if not git:
        raise RuntimeError("Git executable not found")
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    proc = subprocess.run(
        [git] + list(args),
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        env=env,
    )
    if check and proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "git command failed").strip()
        raise RuntimeError(detail[:800])
    return proc


def _write_sync_file(worktree, relative_path, content):
    pure = _validate_repo_relative_path(relative_path, "report sync path")
    destination = worktree.joinpath(*pure.parts)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    return pure.as_posix()


def _sync_report_job(job):
    cfg = job["config"]
    remote = _validate_remote_name(cfg["remote"])
    branch = _validate_git_name(cfg["branch"], "branch")
    base_branch = _validate_git_name(cfg["base_branch"], "base branch")

    top = pathlib.Path(_run_git(["rev-parse", "--show-toplevel"]).stdout.strip()).resolve()
    if top != ROOT.resolve():
        raise RuntimeError("Sidee must run from its Git repository checkout for automatic GitHub sync")

    fetch_target = _run_git(
        ["fetch", "--quiet", "--no-tags", remote, branch],
        check=False,
    )
    if fetch_target.returncode != 0:
        _run_git(["fetch", "--quiet", "--no-tags", remote, base_branch])
    base_ref = "FETCH_HEAD"

    session_name = session_report_filename(job["sessionId"])
    history_dir = _validate_repo_relative_path(cfg["history_dir"], "history directory")
    history_path = (history_dir / session_name).as_posix()
    latest_path = _validate_repo_relative_path(cfg["latest_path"], "latest report path").as_posix()

    with tempfile.TemporaryDirectory(prefix="sidee-report-sync-") as temp_root:
        worktree = pathlib.Path(temp_root) / "repo"
        added = False
        try:
            _run_git(
                ["worktree", "add", "--detach", "--quiet", str(worktree), base_ref],
                cwd=ROOT,
            )
            added = True
            _write_sync_file(worktree, latest_path, job["reportText"])
            _write_sync_file(worktree, history_path, job["reportText"])

            _run_git(["add", "-f", "--", latest_path, history_path], cwd=worktree)
            changed = _run_git(["diff", "--cached", "--quiet"], cwd=worktree, check=False)
            if changed.returncode not in (0, 1):
                raise RuntimeError("Could not inspect staged report changes")
            if changed.returncode == 1:
                reason = re.sub(r"[^A-Za-z0-9._-]+", "-", job.get("reason") or "autosave")[:40]
                _run_git(
                    [
                        "-c", "user.name=Sidee",
                        "-c", "user.email=sidee@local",
                        "commit", "--no-verify",
                        "-m", f"reports: sync {job['sessionId']} ({reason})",
                    ],
                    cwd=worktree,
                )

            commit_sha = _run_git(["rev-parse", "HEAD"], cwd=worktree).stdout.strip()
            push = _run_git(
                ["push", "--quiet", remote, f"HEAD:refs/heads/{branch}"],
                cwd=worktree,
                timeout=60,
                check=False,
            )
            if push.returncode != 0:
                detail = (push.stderr or push.stdout or "git push failed").strip()
                raise RuntimeError(detail[:800])
            return {"commit": commit_sha, "branch": branch}
        finally:
            if added:
                _run_git(
                    ["worktree", "remove", "--force", str(worktree)],
                    cwd=ROOT,
                    check=False,
                )
                _run_git(["worktree", "prune"], cwd=ROOT, check=False)


def queue_report_sync(session_id, report, reason=None):
    global REPORT_SYNC_PENDING
    cfg = dict(REPORT_SYNC_CONFIG)
    if not cfg.get("enabled"):
        return _report_sync_status()

    report_text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    job = {
        "sessionId": session_id,
        "reportText": report_text,
        "reason": str(reason or "autosave"),
        "config": cfg,
    }
    with REPORT_SYNC_LOCK:
        REPORT_SYNC_PENDING = job
        REPORT_SYNC_STATUS.update({
            "enabled": True,
            "state": "QUEUED",
            "message": "Report saved locally; GitHub sync queued.",
            "sessionId": session_id,
            "remote": cfg["remote"],
            "branch": cfg["branch"],
            "commit": None,
            "lastAttemptAt": None,
        })
        snapshot = dict(REPORT_SYNC_STATUS)
    REPORT_SYNC_EVENT.set()
    return snapshot


def report_sync_worker():
    global REPORT_SYNC_PENDING
    while not stop_event.is_set():
        if not REPORT_SYNC_EVENT.wait(0.5):
            continue
        REPORT_SYNC_EVENT.clear()

        debounce = float(REPORT_SYNC_CONFIG.get("debounce_seconds", 2.0))
        while not stop_event.is_set() and REPORT_SYNC_EVENT.wait(debounce):
            REPORT_SYNC_EVENT.clear()

        with REPORT_SYNC_LOCK:
            job = REPORT_SYNC_PENDING
            REPORT_SYNC_PENDING = None
        if not job:
            continue

        _set_report_sync_status(
            state="SYNCING",
            message="Syncing the latest report to GitHub.",
            sessionId=job["sessionId"],
            lastAttemptAt=_utc_timestamp(),
        )
        try:
            result = _sync_report_job(job)
            _set_report_sync_status(
                state="SYNCED",
                message="Report saved locally and synced to GitHub.",
                sessionId=job["sessionId"],
                branch=result["branch"],
                commit=result["commit"],
                lastSuccessAt=_utc_timestamp(),
            )
        except Exception as exc:
            _set_report_sync_status(
                state="ERROR",
                message=("Local report is safe; GitHub sync failed: " + str(exc))[:1000],
                sessionId=job["sessionId"],
                commit=None,
            )


REMOTE_DIAGNOSTIC_LOCK = threading.Lock()
REMOTE_DIAGNOSTIC_CONFIG = {}
REMOTE_DIAGNOSTIC_REQUEST = None
REMOTE_DIAGNOSTIC_LAST_ID = None
REMOTE_DIAGNOSTIC_STATUS = {
    "enabled": False,
    "state": "DISABLED",
    "message": "Remote diagnostic requests are disabled.",
    "requestId": None,
    "fetchedAt": None,
    "acknowledgedAt": None,
}


def configure_remote_diagnostics(config):
    global REMOTE_DIAGNOSTIC_CONFIG
    raw = config.get("remote_diagnostics", {}) if isinstance(config, dict) else {}
    REMOTE_DIAGNOSTIC_CONFIG = {
        "enabled": bool(raw.get("enabled", False)),
        "remote": str(raw.get("remote", "origin")).strip() or "origin",
        "branch": str(raw.get("branch", "sidee-control")).strip() or "sidee-control",
        "request_path": str(raw.get("request_path", "control/request.json")).strip() or "control/request.json",
        "poll_seconds": max(1.0, min(float(raw.get("poll_seconds", 2.0)), 30.0)),
    }
    with REMOTE_DIAGNOSTIC_LOCK:
        REMOTE_DIAGNOSTIC_STATUS.update({
            "enabled": REMOTE_DIAGNOSTIC_CONFIG["enabled"],
            "state": "IDLE" if REMOTE_DIAGNOSTIC_CONFIG["enabled"] else "DISABLED",
            "message": (
                "Waiting for a read-only diagnostic request."
                if REMOTE_DIAGNOSTIC_CONFIG["enabled"]
                else "Remote diagnostic requests are disabled."
            ),
            "requestId": None,
            "fetchedAt": None,
            "acknowledgedAt": None,
        })


def _remote_diagnostic_snapshot(include_request=False):
    with REMOTE_DIAGNOSTIC_LOCK:
        out = dict(REMOTE_DIAGNOSTIC_STATUS)
        out["request"] = dict(REMOTE_DIAGNOSTIC_REQUEST) if include_request and REMOTE_DIAGNOSTIC_REQUEST else None
        return out


def _remote_request_expired(expires_at):
    if not isinstance(expires_at, str) or not expires_at:
        return True
    try:
        from datetime import datetime, timezone
        normalized = expires_at[:-1] + "+00:00" if expires_at.endswith("Z") else expires_at
        expiry = datetime.fromisoformat(normalized)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return expiry.timestamp() <= time.time()
    except Exception:
        return True


def _fetch_remote_diagnostic_request():
    cfg = dict(REMOTE_DIAGNOSTIC_CONFIG)
    remote = _validate_remote_name(cfg["remote"])
    branch = _validate_git_name(cfg["branch"], "remote diagnostic branch")
    request_path = _validate_repo_relative_path(cfg["request_path"], "remote diagnostic request path").as_posix()

    fetch = _run_git(["fetch", "--quiet", "--no-tags", remote, branch], timeout=30, check=False)
    if fetch.returncode != 0:
        detail = (fetch.stderr or fetch.stdout or "git fetch failed").strip()
        raise RuntimeError(detail[:500])

    show = _run_git(["show", f"FETCH_HEAD:{request_path}"], timeout=15, check=False)
    if show.returncode != 0:
        detail = (show.stderr or show.stdout or "diagnostic request file unavailable").strip()
        raise RuntimeError(detail[:500])
    return json.loads(show.stdout)


def remote_diagnostic_worker():
    global REMOTE_DIAGNOSTIC_REQUEST, REMOTE_DIAGNOSTIC_LAST_ID
    while not stop_event.is_set():
        try:
            raw = _fetch_remote_diagnostic_request()
            workflow = None
            required_build = None
            if isinstance(raw, dict):
                safe_readonly = raw.get("runSafeDiagnostic") is True
                safe_readonly_v2 = raw.get("runSafeDiagnosticV2") is True
                direct_noop = raw.get("runDirectAppInfoWriteNoop") is True
                direct_noop_v2 = raw.get("runDirectAppInfoWriteNoopV2") is True
                identity_write_gate = raw.get("runIdentityWriteGateLabV1") is True
                selected = int(bool(safe_readonly)) + int(bool(safe_readonly_v2)) + int(bool(direct_noop)) + int(bool(direct_noop_v2)) + int(bool(identity_write_gate))
                if selected > 1:
                    raise ValueError("Diagnostic request selects multiple workflows")
                if safe_readonly_v2:
                    workflow = "safe-readonly"
                    required_build = raw.get("requiresBuildId")
                    if required_build != client_build_id():
                        raise ValueError("Read-only diagnostic request is waiting for its required Sidee build")
                elif safe_readonly:
                    workflow = "safe-readonly"
                elif direct_noop_v2:
                    workflow = "direct-appinfo-noop"
                    required_build = raw.get("requiresBuildId")
                    if required_build != client_build_id():
                        raise ValueError("Direct AppInfo no-op request is waiting for its required Sidee build")
                elif direct_noop:
                    workflow = "direct-appinfo-noop"
                elif identity_write_gate:
                    workflow = "identity-write-gate"
                    required_build = raw.get("requiresBuildId")
                    if required_build != client_build_id():
                        raise ValueError("Identifier write-gate request is waiting for its required Sidee build")

            if workflow is None:
                with REMOTE_DIAGNOSTIC_LOCK:
                    if REMOTE_DIAGNOSTIC_STATUS["state"] not in ("RUNNING", "COMPLETED"):
                        REMOTE_DIAGNOSTIC_STATUS.update({
                            "state": "IDLE",
                            "message": "Waiting for a supported diagnostic request.",
                            "fetchedAt": _utc_timestamp(),
                        })
            else:
                request_id = raw.get("requestId")
                if not isinstance(request_id, str) or not re.fullmatch(r"sidee-request-\d{8}-\d{6}-[a-f0-9]{4}", request_id):
                    raise ValueError("Invalid diagnostic requestId")
                if _remote_request_expired(raw.get("expiresAt")):
                    raise ValueError("Diagnostic request expired")
                request = {
                    "requestId": request_id,
                    "workflow": workflow,
                    "requiresBuildId": required_build,
                    "createdAt": raw.get("createdAt"),
                    "expiresAt": raw.get("expiresAt"),
                    "requestedBy": str(raw.get("requestedBy") or "unknown")[:80],
                    "note": str(raw.get("note") or "")[:300],
                }
                message = (
                    "Backup-protected AppInfo no-op write requested; waiting for an armed TV page."
                    if workflow == "direct-appinfo-noop"
                    else "Identifier write-gate lab requested; waiting for an armed TV page."
                    if workflow == "identity-write-gate"
                    else "Read-only diagnostic requested; waiting for an armed TV page."
                )
                with REMOTE_DIAGNOSTIC_LOCK:
                    if request_id != REMOTE_DIAGNOSTIC_LAST_ID:
                        REMOTE_DIAGNOSTIC_LAST_ID = request_id
                        REMOTE_DIAGNOSTIC_REQUEST = request
                        REMOTE_DIAGNOSTIC_STATUS.update({
                            "state": "PENDING",
                            "message": message,
                            "requestId": request_id,
                            "fetchedAt": _utc_timestamp(),
                            "acknowledgedAt": None,
                        })
        except ValueError as exc:
            with REMOTE_DIAGNOSTIC_LOCK:
                if REMOTE_DIAGNOSTIC_STATUS["state"] not in ("RUNNING", "COMPLETED"):
                    REMOTE_DIAGNOSTIC_STATUS.update({
                        "state": "IDLE",
                        "message": str(exc)[:500],
                        "fetchedAt": _utc_timestamp(),
                    })
        except Exception as exc:
            with REMOTE_DIAGNOSTIC_LOCK:
                if REMOTE_DIAGNOSTIC_STATUS["state"] not in ("RUNNING", "COMPLETED"):
                    REMOTE_DIAGNOSTIC_STATUS.update({
                        "state": "ERROR",
                        "message": ("Diagnostic request fetch failed: " + str(exc))[:500],
                        "fetchedAt": _utc_timestamp(),
                    })
        stop_event.wait(float(REMOTE_DIAGNOSTIC_CONFIG.get("poll_seconds", 2.0)))


def acknowledge_remote_diagnostic(data):
    global REMOTE_DIAGNOSTIC_REQUEST
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object")
    request_id = data.get("requestId")
    status = data.get("status")
    if status not in ("RUNNING", "COMPLETED", "FAILED"):
        raise ValueError("Invalid diagnostic status")
    with REMOTE_DIAGNOSTIC_LOCK:
        if not REMOTE_DIAGNOSTIC_REQUEST or request_id != REMOTE_DIAGNOSTIC_REQUEST.get("requestId"):
            raise ValueError("Unknown diagnostic requestId")
        REMOTE_DIAGNOSTIC_STATUS.update({
            "state": status,
            "message": str(data.get("message") or status)[:500],
            "acknowledgedAt": _utc_timestamp(),
        })
        if status in ("COMPLETED", "FAILED"):
            REMOTE_DIAGNOSTIC_REQUEST = None
        return dict(REMOTE_DIAGNOSTIC_STATUS)

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
    cert = CERT_DIR / "sidee-vidaa-multihost.crt"
    key = CERT_DIR / "sidee-vidaa-multihost.key"
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
        "-addext", "subjectAltName=DNS:vidaahub.com,DNS:www.vidaahub.com,DNS:vidaa.smartone-iptv.com,DNS:vidaa.duplecast.com",
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
        host = _normalized_host(self.headers.get("Host", ""))

        if host in APP_CONTEXT_HOSTS and not path.startswith("/api/"):
            _record_app_context_hit(host, path, self.client_address[0], self.headers)
            data = _app_context_bootstrap_html(host).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.send_header("X-Sidee-App-Context", APP_CONTEXT_HOSTS[host]["mode"])
            self.end_headers()
            self.wfile.write(data)
            return

        if path == "/api/status":
            cfg = load_config()
            request_scheme = "https" if isinstance(self.request, ssl.SSLSocket) else "http"
            return self._send_json({
                "ok": True,
                "service": "Sidee",
                "host": self.headers.get("Host", ""),
                "client": self.client_address[0],
                "requestScheme": request_scheme,
                "requestPort": self.server.server_address[1],
                "spoofDomains": cfg.get("spoof_domains", []),
                "clientBuildId": client_build_id(),
            })

        if path == "/api/config":
            return self._send_json(load_config())

        if path == "/api/reports/sync":
            return self._send_json(_report_sync_status())

        if path == "/api/app-context/last-hit":
            with APP_CONTEXT_HIT_LOCK:
                hit = dict(APP_CONTEXT_LAST_HIT) if APP_CONTEXT_LAST_HIT else None
            return self._send_json({"ok": True, "hit": hit})

        if path == "/api/remote-diagnostic/request":
            snapshot = _remote_diagnostic_snapshot(include_request=True)
            request = snapshot.get("request")
            if request and request.get("requiresBuildId"):
                params = urllib.parse.parse_qs(parsed.query)
                supplied_build = (params.get("clientBuildId") or [""])[0]
                if supplied_build != request.get("requiresBuildId") or supplied_build != client_build_id():
                    snapshot["state"] = "STALE_CLIENT"
                    snapshot["message"] = "Reload Sidee before the build-bound diagnostic."
                    snapshot["request"] = None
            return self._send_json(snapshot)

        if path == "/api/appinfo/backup":
            params = urllib.parse.parse_qs(parsed.query)
            session_id = (params.get("sessionId") or [None])[0]
            backup_id = (params.get("backupId") or [None])[0]
            try:
                backup = read_appinfo_backup(session_id, backup_id)
            except ValueError as exc:
                return self._send_json({"ok": False, "error": str(exc)}, 400)
            except OSError as exc:
                return self._send_json({"ok": False, "error": f"Could not read backup: {exc}"}, 500)
            return self._send_json({"ok": True, "backup": backup})

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
        build_id = client_build_id()
        if file_path.name == "index.html":
            text = file_path.read_text(encoding="utf-8")
            data = text.replace("__SIDEE_BUILD_ID__", build_id).encode("utf-8")
        else:
            data = file_path.read_bytes()
        ctype = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("X-Sidee-Build", build_id)
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            data = self._read_json()
        except Exception as exc:
            return self._send_json({"ok": False, "error": str(exc)}, 400)

        if path == "/api/app-context-bootstrap":
            try:
                report = _save_app_context_bootstrap(
                    data,
                    self.headers.get("Host", ""),
                    self.client_address[0],
                )
            except ValueError as exc:
                return self._send_json({"ok": False, "error": str(exc)}, 400)
            except OSError as exc:
                return self._send_json({"ok": False, "error": f"Could not save app-context report: {exc}"}, 500)
            return self._send_json({
                "ok": True,
                "sessionId": report["sessionId"],
                "accessMode": report["accessMode"],
                "summary": report["summary"],
            })

        if path == "/api/appinfo/backup":
            if not isinstance(data, dict):
                return self._send_json({"ok": False, "error": "Expected JSON object"}, 400)
            session_id = data.get("sessionId")
            raw = data.get("raw")
            client_hash = data.get("clientSha256")
            client_build = data.get("clientBuildId")
            if client_hash is not None:
                if not isinstance(client_hash, str) or not re.fullmatch(r"[a-f0-9]{64}", client_hash):
                    return self._send_json({"ok": False, "error": "Invalid clientSha256"}, 400)
            try:
                backup = create_appinfo_backup(session_id, raw, client_hash, client_build)
            except ValueError as exc:
                return self._send_json({"ok": False, "error": str(exc)}, 400)
            except FileExistsError:
                return self._send_json({"ok": False, "error": "Backup collision; retry"}, 409)
            except OSError as exc:
                return self._send_json({"ok": False, "error": f"Could not create backup: {exc}"}, 500)
            return self._send_json({"ok": True, "backup": backup})

        if path == "/api/reports/session":
            if not isinstance(data, dict):
                return self._send_json({"ok": False, "error": "Expected JSON object"}, 400)
            session_id = data.get("sessionId")
            report = data.get("report")
            if isinstance(report, dict):
                report = dict(report)
                server_build_id = client_build_id()
                raw_client_build_id = report.get("clientBuildId")
                client_id = raw_client_build_id if isinstance(raw_client_build_id, str) and raw_client_build_id else "MISSING"
                report["clientBuildId"] = client_id
                report["serverBuildId"] = server_build_id
                report["buildMatch"] = client_id == server_build_id
            else:
                server_build_id = client_build_id()
            try:
                file_path = write_session_report(session_id, report)
            except ValueError as exc:
                return self._send_json({"ok": False, "error": str(exc)}, 400)
            except OSError as exc:
                return self._send_json({"ok": False, "error": f"Could not write report: {exc}"}, 500)
            reason = data.get("reason")
            try:
                sync_state = queue_report_sync(session_id, report, reason)
            except Exception as exc:
                sync_state = _set_report_sync_status(
                    state="ERROR",
                    message=("Local report is safe; GitHub sync could not be queued: " + str(exc))[:1000],
                    sessionId=session_id,
                    commit=None,
                )
            return self._send_json({
                "ok": True,
                "sessionId": session_id,
                "file": file_path.name,
                "clientBuildId": report.get("clientBuildId") if isinstance(report, dict) else None,
                "serverBuildId": server_build_id,
                "buildMatch": report.get("buildMatch") if isinstance(report, dict) else False,
                "githubSync": sync_state,
            })

        if path == "/api/remote-diagnostic/ack":
            try:
                status = acknowledge_remote_diagnostic(data)
            except ValueError as exc:
                return self._send_json({"ok": False, "error": str(exc)}, 400)
            return self._send_json({"ok": True, "remoteDiagnostic": status})

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

    def _sni_observer(ssl_socket, server_name, ssl_context):
        host = _normalized_host(server_name)
        if host in APP_CONTEXT_HOSTS:
            print(f"[TLS-SNI] {host}")
            try:
                _sync_app_transport_observation("TLS_SNI", host, "")
            except Exception as exc:
                print(f"[TLS-SNI] report error: {exc}")

    context.set_servername_callback(_sni_observer)
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
    configure_report_sync(cfg)
    configure_remote_diagnostics(cfg)

    print("\nSidee - VIDAA local toolkit")
    print("=" * 52)
    print(f"PC IP: {local_ip}")
    print(f"PC dashboard: http://{local_ip}:{cfg.get('http_port', 8080)}")
    print(f"Installed-app context probe HTTP: http://{local_ip}:{cfg.get('app_context_http_port', 80)}")
    print(f"Raw-IP A/B test: http://{local_ip}:{cfg.get('http_port', 8080)}")
    if REPORT_SYNC_CONFIG.get("enabled"):
        print(
            "Report sync: Git remote "
            f"{REPORT_SYNC_CONFIG['remote']} -> branch {REPORT_SYNC_CONFIG['branch']}"
        )
    else:
        print("Report sync: disabled")
    print("TV flow:")
    print("  Installed-app context probe: with TV DNS pointed to this PC, launch Smartone IPTV or Duplecast from the VIDAA launcher.")
    print(f"  1. Set the TV DNS manually to {local_ip}")
    print("  2. Open https://vidaahub.com in the TV browser")
    print("  3. Accept the local certificate warning if shown")
    print("  4. Capture Baseline, initialize runtime context, then run the explicit permission test")
    print(f"  A/B raw-IP check: open http://{local_ip}:{cfg.get('http_port', 8080)} without changing DNS")
    print("=" * 52)

    threads = []

    if REPORT_SYNC_CONFIG.get("enabled"):
        sync_thread = threading.Thread(target=report_sync_worker, daemon=True)
        sync_thread.start()
        threads.append(sync_thread)

    if REMOTE_DIAGNOSTIC_CONFIG.get("enabled"):
        remote_diagnostic_thread = threading.Thread(target=remote_diagnostic_worker, daemon=True)
        remote_diagnostic_thread.start()
        threads.append(remote_diagnostic_thread)

    http_thread = threading.Thread(target=run_http, args=(int(cfg.get("http_port", 8080)),), daemon=True)
    http_thread.start()
    threads.append(http_thread)

    app_context_http_port = int(cfg.get("app_context_http_port", 80))
    if app_context_http_port != int(cfg.get("http_port", 8080)):
        app_context_http_thread = threading.Thread(
            target=run_http,
            args=(app_context_http_port,),
            daemon=True,
        )
        app_context_http_thread.start()
        threads.append(app_context_http_thread)

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
