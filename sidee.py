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
import gzip
import hashlib
import ipaddress
import http.client
import http.server
import json
import mimetypes
import os
import pathlib
import queue
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
import zlib

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

STORE_CATALOG_HOST = "category-ui.vidaahub.com"
STORE_TRACE_HOSTS = (
    STORE_CATALOG_HOST,
    "category-ui-eu.vidaahub.com",
    "detail-ui-eu.vidaahub.com",
    "appstore-vidaa.vidaahub.com",
    "tvmodules-vidaa.vidaahub.com",
)
STORE_TRACE_HOST_SET = set(STORE_TRACE_HOSTS)
STORE_TRACE_LOCK = threading.Lock()
STORE_TRACE_REPORT = None
STORE_TRACE_MAX_REQUESTS = 80
STORE_TRACE_MAX_ERRORS = 20
STORE_TRACE_MAX_EVENTS = 160
STORE_TRACE_MAX_JSON_BYTES = 2 * 1024 * 1024
STORE_TRACE_SENSITIVE_RE = re.compile(
    r"(?:authorization|cookie|token|secret|password|credential|signature|certificate|nonce|session|api[-_]?key|access[-_]?key)",
    re.IGNORECASE,
)
STORE_PROXY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}

STORE_DISCOVERY_LOCK = threading.Lock()
STORE_DISCOVERY_REPORT = None
STORE_DISCOVERY_MAX_HOSTS = 40
DNS_OBSERVATION_QUEUE = queue.Queue(maxsize=4096)
DNS_OBSERVATION_DROP_LOCK = threading.Lock()
DNS_OBSERVATION_DROPPED = 0
DNS_FORWARD_STATS_LOCK = threading.Lock()
DNS_FORWARD_STATS = {
    "queries": 0,
    "success": 0,
    "failures": 0,
    "lastLatencyMs": None,
    "maxLatencyMs": 0.0,
    "lastFailureHost": None,
}
DNS_REQUEST_SEMAPHORE = threading.BoundedSemaphore(32)
DNS_REQUEST_THREADS_LOCK = threading.Lock()
DNS_REQUEST_THREADS_ACTIVE = 0
DNS_REQUEST_THREADS_PEAK = 0
STORE_INSTALL_PROBE_MAX_EVENTS = 320
STORE_INSTALL_PROBE_MAX_HOSTS = 140
STORE_INSTALL_PROBE_TARGET = {
    "name": "Duplecast",
    "appId": "1876",
    "host": "vidaa.duplecast.com",
}
STORE_INSTALL_PROBE_CLIENT = None
STORE_INSTALL_AUTO_TRIGGER_HOSTS = {
    "category-ui-eu.vidaahub.com",
    "layout-ui-eu.vidaahub.com",
    "home-ui-eu.vidaahub.com",
    "detail-ui-eu.vidaahub.com",
    "recommend-ui-eu.vidaahub.com",
    "search-ui-eu.vidaahub.com",
    "appstore-vidaa.vidaahub.com",
    "tvmodules-vidaa.vidaahub.com",
}

NETWORK_CAPTURE_DIR = ROOT / "captures"
NETWORK_CAPTURE_LOCK = threading.Lock()
NETWORK_CAPTURE_STATE = {
    "status": "IDLE",
    "captureId": None,
    "armedAt": None,
    "startedAt": None,
    "stoppedAt": None,
    "triggerHost": None,
    "tvClientBound": False,
    "tvIp": None,
    "etlFile": None,
    "pcapngFile": None,
    "txtFile": None,
    "summary": None,
    "error": None,
    "pktmonOutput": None,
    "preflight": None,
}
NETWORK_CAPTURE_FILTER_NAME = "Sidee-TV"
NETWORK_CAPTURE_MAX_FILE_MB = 512

STORE_STATIC_MAP_LOCK = threading.Lock()
STORE_STATIC_MAP_LAST = None
STORE_STATIC_MAP_HOSTS = (
    "home-ui-eu.vidaahub.com",
    "layout-ui-eu.vidaahub.com",
    "detail-ui-eu.vidaahub.com",
    "category-ui-eu.vidaahub.com",
    "search-ui-eu.vidaahub.com",
    "recommend-ui-eu.vidaahub.com",
    "appstore-vidaa.vidaahub.com",
    "static-ui.vidaahub.com",
    "tvmodules-vidaa.vidaahub.com",
)
STORE_STATIC_MAP_HOST_SET = set(STORE_STATIC_MAP_HOSTS)
STORE_STATIC_MAP_MAX_BYTES = 1024 * 1024
STORE_STATIC_MAP_MAX_ASSETS = 28
STORE_STATIC_MAP_KEYWORDS = (
    "installApplication",
    "Hisense_installApp",
    "installApp",
    "download",
    "package",
    "pkgmgr",
    "configUrlDownload",
    "productCode",
    "appBundle",
    "appContentId",
    "signatureServer",
)
STORE_STATIC_API_RE = re.compile(
    r"(/api/[A-Za-z0-9._~!$&'()*+,;=:@%/?#\-]{3,220})",
    re.IGNORECASE,
)
STORE_STATIC_URL_RE = re.compile(
    r"(https?://[A-Za-z0-9._~:%\-]+(?:/[A-Za-z0-9._~!$&'()*+,;=:@%/?#\-]*)?)",
    re.IGNORECASE,
)
STORE_STATIC_SCRIPT_RE = re.compile(
    r"<(?:script|link)\b[^>]+?(?:src|href)\s*=\s*[\"']([^\"'#]+)[\"']",
    re.IGNORECASE,
)
STORE_STATIC_SENSITIVE_RE = re.compile(
    r"(authorization|cookie|token|secret|password|credential|api[-_]?key|access[-_]?key|client[-_]?secret)",
    re.IGNORECASE,
)


def _network_capture_public_state():
    with NETWORK_CAPTURE_LOCK:
        state = dict(NETWORK_CAPTURE_STATE)
    state.pop("tvIp", None)
    return json.loads(json.dumps(state))


def _network_capture_set(**values):
    with NETWORK_CAPTURE_LOCK:
        NETWORK_CAPTURE_STATE.update(values)
        return dict(NETWORK_CAPTURE_STATE)


def _network_capture_publish(reason=None):
    public = _network_capture_public_state()
    try:
        _network_capture_sync_report(public)
    except Exception as exc:
        print(f"[NETCAP] publish error: {exc}")
    if reason:
        print(f"[NETCAP] {reason} · {public.get('status')}")
    return public


def _network_capture_cmd(args, timeout=20):
    executable = shutil.which("pktmon")
    if not executable:
        raise RuntimeError("pktmon.exe is not available on this Windows PC")
    completed = subprocess.run(
        [executable] + list(args),
        capture_output=True,
        text=True,
        errors="replace",
        timeout=timeout,
        check=False,
    )
    output = ((completed.stdout or "") + "\n" + (completed.stderr or "")).strip()
    return completed.returncode, output


def _network_capture_status_probe():
    code, output = _network_capture_cmd(["status"], timeout=10)
    normalized = (output or "").replace("\\", "/").lower()
    capture_root = str(NETWORK_CAPTURE_DIR.resolve()).replace("\\", "/").lower().rstrip("/")
    etl_log_detected = ".etl" in normalized
    sidee_owned_etl = (
        etl_log_detected
        and "sidee-net-" in normalized
        and (
            "/captures/" in normalized
            or (capture_root and capture_root in normalized)
        )
    )
    return {
        "exitCode": code,
        "etlLogDetected": etl_log_detected,
        "sideeOwnedEtlDetected": sidee_owned_etl,
    }


def _network_capture_preflight():
    if os.name != "nt":
        raise RuntimeError("Full TV capture currently requires Windows pktmon")
    if not shutil.which("pktmon"):
        raise RuntimeError("pktmon.exe was not found")

    code, filters = _network_capture_cmd(["filter", "list"], timeout=10)
    if code != 0:
        raise RuntimeError("Could not inspect pktmon filters: " + filters[:400])

    status = _network_capture_status_probe()
    filter_lines = re.findall(r"(?m)^\s*\d+\s+.*$", filters or "")
    result = {
        "pktmon": True,
        "preexistingFilters": bool(filter_lines),
        "statusExitCode": status.get("exitCode"),
        "etlLogDetected": bool(status.get("etlLogDetected")),
        "sideeOwnedEtlDetected": bool(status.get("sideeOwnedEtlDetected")),
        "staleSideeCaptureStopped": False,
        "staleSideeCaptureStopExitCode": None,
        "staleSideeFilterCleared": False,
    }

    if filter_lines:
        own_filter_only = (
            len(filter_lines) == 1
            and NETWORK_CAPTURE_FILTER_NAME.lower() in filter_lines[0].lower()
        )
        if own_filter_only:
            # start-windows.bat force-stops stale sidee.py processes. pktmon can
            # survive that process, and status prose is localized by Windows.
            # If our sole filter remains, stop before removing it without
            # depending on English words such as "running" or "capturing".
            stop_code, _ = _network_capture_cmd(["stop"], timeout=20)
            result["staleSideeCaptureStopExitCode"] = stop_code
            result["staleSideeCaptureStopped"] = stop_code == 0

            remove_code, remove_output = _network_capture_cmd(["filter", "remove"], timeout=10)
            if remove_code != 0:
                raise RuntimeError(
                    "Found stale Sidee-TV pktmon filter but could not remove it: "
                    + remove_output[:400]
                )
            code, filters = _network_capture_cmd(["filter", "list"], timeout=10)
            filter_lines = re.findall(r"(?m)^\s*\d+\s+.*$", filters or "")
            if filter_lines:
                raise RuntimeError(
                    "Sidee cleared its stale filter but pktmon still reports active filters."
                )
            result["preexistingFilters"] = False
            result["staleSideeFilterCleared"] = True
            return result

        raise RuntimeError(
            "pktmon already has active filters not owned exclusively by Sidee. "
            "Sidee will not remove unrelated pktmon filters."
        )

    if status.get("sideeOwnedEtlDetected"):
        # Older Sidee builds could remove Sidee-TV without stopping a localized
        # pktmon session. Recover only an ETL whose status path is clearly ours.
        stop_code, _ = _network_capture_cmd(["stop"], timeout=20)
        result["staleSideeCaptureStopExitCode"] = stop_code
        result["staleSideeCaptureStopped"] = stop_code == 0
        return result

    if status.get("etlLogDetected"):
        raise RuntimeError(
            "pktmon appears to have an active ETL capture not owned by Sidee. "
            "Sidee will not stop or modify that capture."
        )

    return result


def _network_capture_id():
    return "sidee-net-" + time.strftime("%Y%m%d-%H%M%S", time.localtime())


def _network_capture_paths(capture_id):
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", str(capture_id))
    directory = (NETWORK_CAPTURE_DIR / safe).resolve()
    root = NETWORK_CAPTURE_DIR.resolve()
    if directory.parent != root:
        raise ValueError("Invalid capture directory")
    directory.mkdir(parents=True, exist_ok=True)
    return {
        "dir": directory,
        "etl": directory / (safe + ".etl"),
        "pcapng": directory / (safe + ".pcapng"),
        "txt": directory / (safe + ".txt"),
    }


def _network_capture_start_for_ip(tv_ip, trigger_host=None):
    try:
        parsed_ip = str(ipaddress.ip_address(str(tv_ip or "")))
        if ":" in parsed_ip:
            raise ValueError("IPv6 TV capture is not enabled in this probe")
    except ValueError as exc:
        _network_capture_set(status="ERROR", error="Invalid TV IPv4 address")
        raise RuntimeError("Invalid TV IPv4 address") from exc

    with NETWORK_CAPTURE_LOCK:
        if NETWORK_CAPTURE_STATE.get("status") not in ("ARMED", "STARTING"):
            public = dict(NETWORK_CAPTURE_STATE)
            public.pop("tvIp", None)
            return json.loads(json.dumps(public))
        capture_id = NETWORK_CAPTURE_STATE.get("captureId") or _network_capture_id()
        NETWORK_CAPTURE_STATE.update({
            "status": "STARTING",
            "captureId": capture_id,
            "triggerHost": _normalized_host(trigger_host or "") or None,
            "tvClientBound": True,
            "tvIp": parsed_ip,
            "error": None,
        })

    try:
        preflight = _network_capture_preflight()
        _network_capture_set(preflight=preflight)
        paths = _network_capture_paths(capture_id)
        code, output = _network_capture_cmd([
            "filter", "add", NETWORK_CAPTURE_FILTER_NAME, "-i", parsed_ip
        ], timeout=10)
        if code != 0:
            raise RuntimeError("pktmon filter add failed: " + output[:500])

        try:
            code, start_output = _network_capture_cmd([
                "start",
                "--capture",
                "--comp", "nics",
                "--type", "flow",
                "--pkt-size", "0",
                "--file-name", str(paths["etl"]),
                "--file-size", str(NETWORK_CAPTURE_MAX_FILE_MB),
                "--log-mode", "circular",
            ], timeout=15)
            if code != 0:
                raise RuntimeError("pktmon start failed: " + start_output[:700])
        except Exception:
            _network_capture_cmd(["filter", "remove"], timeout=10)
            raise

        _network_capture_set(
            status="CAPTURING",
            startedAt=_utc_timestamp(),
            etlFile=str(paths["etl"].relative_to(ROOT)),
            pcapngFile=str(paths["pcapng"].relative_to(ROOT)),
            txtFile=str(paths["txt"].relative_to(ROOT)),
            pktmonOutput=start_output[:1000],
        )
        _network_capture_publish("capture started")
        try:
            capture_cfg = load_config().get("store_download_capture", {})
            if capture_cfg.get("enabled") and capture_cfg.get("auto_stop_seconds"):
                _network_capture_schedule_auto_stop(capture_cfg.get("auto_stop_seconds"))
        except Exception as exc:
            print(f"[NETCAP] auto-stop scheduling error: {exc}")
        print(f"[NETCAP] CAPTURING {capture_id} for TV client")
    except Exception as exc:
        _network_capture_set(status="ERROR", error=str(exc)[:1000])
        _network_capture_publish("capture start failed")
        print(f"[NETCAP] start error: {exc}")
    return _network_capture_public_state()


def _network_capture_maybe_start(tv_ip, trigger_host):
    with NETWORK_CAPTURE_LOCK:
        status = NETWORK_CAPTURE_STATE.get("status")
        if status != "ARMED":
            return False
        NETWORK_CAPTURE_STATE["status"] = "STARTING"
    thread = threading.Thread(
        target=_network_capture_start_for_ip,
        args=(tv_ip, trigger_host),
        name="sidee-network-capture-start",
        daemon=True,
    )
    thread.start()
    return True


def _network_capture_auto_stop_after(seconds):
    try:
        seconds = max(15, min(int(seconds), 900))
    except Exception:
        seconds = 180
    deadline = time.time() + seconds
    while not stop_event.is_set() and time.time() < deadline:
        time.sleep(0.5)
    if stop_event.is_set():
        return
    with NETWORK_CAPTURE_LOCK:
        status = NETWORK_CAPTURE_STATE.get("status")
    if status not in ("CAPTURING", "STARTING"):
        return
    try:
        _network_capture_stop()
        print(f"[NETCAP] automatic Store capture stop after {seconds}s")
    except Exception as exc:
        print(f"[NETCAP] automatic stop error: {exc}")


def _network_capture_schedule_auto_stop(seconds):
    thread = threading.Thread(
        target=_network_capture_auto_stop_after,
        args=(seconds,),
        name="sidee-network-capture-auto-stop",
        daemon=True,
    )
    thread.start()
    return thread


def _network_capture_arm(manual_tv_ip=None):
    preflight = _network_capture_preflight()
    capture_id = _network_capture_id()
    state = _network_capture_set(
        status="ARMED",
        captureId=capture_id,
        armedAt=_utc_timestamp(),
        startedAt=None,
        stoppedAt=None,
        triggerHost=None,
        tvClientBound=False,
        tvIp=None,
        etlFile=None,
        pcapngFile=None,
        txtFile=None,
        summary=None,
        error=None,
        pktmonOutput=None,
        preflight=preflight,
    )
    _network_capture_publish("capture armed")
    client_ip = str(manual_tv_ip or STORE_INSTALL_PROBE_CLIENT or "").strip()
    if client_ip:
        _network_capture_set(status="STARTING")
        thread = threading.Thread(
            target=_network_capture_start_for_ip,
            args=(client_ip, "known-store-client"),
            name="sidee-network-capture-start",
            daemon=True,
        )
        thread.start()
    return _network_capture_public_state()


def _network_capture_parse_text(txt_path, tv_ip):
    summary = {
        "packetRecords": 0,
        "originalBytes": 0,
        "parsedIpPacketLines": 0,
        "tvMatchedPacketRecords": 0,
        "httpsPacketRecords": 0,
        "httpPacketRecords": 0,
        "dnsPacketRecords": 0,
        "tlsServerNames": [],
        "topPeers": [],
        "topologyClassification": "UNKNOWN",
    }
    if not txt_path.is_file():
        return summary

    peers = {}
    header_records = 0
    header_bytes = 0
    parsed_ip_lines = 0
    parsed_ip_bytes = 0
    pending_size = 0
    ip_pair = re.compile(
        r"(\d{1,3}(?:\.\d{1,3}){3})(?:[.:](\d+))?\s*>\s*"
        r"(\d{1,3}(?:\.\d{1,3}){3})(?:[.:](\d+))?"
    )
    for raw_line in txt_path.read_text(encoding="utf-8", errors="replace").splitlines():
        size_match = re.search(r"OriginalSize\s+(\d+)", raw_line, re.IGNORECASE)
        if size_match:
            pending_size = int(size_match.group(1))
            header_records += 1
            header_bytes += pending_size

        match = ip_pair.search(raw_line)
        if not match:
            continue

        parsed_ip_lines += 1
        length_matches = re.findall(r"\blength\s+(\d+)\b", raw_line, re.IGNORECASE)
        fallback_size = int(length_matches[-1]) if length_matches else 0
        parsed_ip_bytes += pending_size or fallback_size

        src, sport, dst, dport = match.groups()
        sport_i = int(sport) if sport else None
        dport_i = int(dport) if dport else None
        if src == tv_ip:
            peer, peer_port = dst, dport_i
        elif dst == tv_ip:
            peer, peer_port = src, sport_i
        else:
            pending_size = 0
            continue

        summary["tvMatchedPacketRecords"] += 1
        rec = peers.setdefault(peer, {"ip": peer, "packetRecords": 0, "bytes": 0, "ports": {}})
        rec["packetRecords"] += 1
        rec["bytes"] += pending_size or fallback_size
        if peer_port is not None:
            rec["ports"][str(peer_port)] = int(rec["ports"].get(str(peer_port), 0)) + 1
            if peer_port == 443:
                summary["httpsPacketRecords"] += 1
            elif peer_port == 80:
                summary["httpPacketRecords"] += 1
            elif peer_port == 53:
                summary["dnsPacketRecords"] += 1
        pending_size = 0

    summary["parsedIpPacketLines"] = parsed_ip_lines
    summary["packetRecords"] = header_records or parsed_ip_lines
    summary["originalBytes"] = header_bytes or parsed_ip_bytes

    ordered = sorted(peers.values(), key=lambda x: (x["bytes"], x["packetRecords"]), reverse=True)
    summary["topPeers"] = ordered[:30]
    if summary["httpsPacketRecords"] >= 5:
        summary["topologyClassification"] = "FULL_PATH_VISIBLE"
    elif summary["tvMatchedPacketRecords"] > 0:
        summary["topologyClassification"] = "DNS_OR_LOCAL_ONLY_LIKELY"
    elif summary["packetRecords"] > 0:
        summary["topologyClassification"] = "CAPTURED_BUT_TV_IP_NOT_VISIBLE"
    else:
        summary["topologyClassification"] = "NO_PACKET_RECORDS"
    return summary


def _network_capture_decode_ipv4_packet(packet, linktype):
    if not isinstance(packet, (bytes, bytearray)):
        return None
    data = bytes(packet)
    candidates = []

    if linktype == 1 and len(data) >= 14:
        offset = 14
        ether_type = int.from_bytes(data[12:14], "big")
        vlan_depth = 0
        while ether_type in (0x8100, 0x88A8, 0x9100) and vlan_depth < 2 and len(data) >= offset + 4:
            ether_type = int.from_bytes(data[offset + 2:offset + 4], "big")
            offset += 4
            vlan_depth += 1
        if ether_type == 0x0800:
            candidates.append(offset)
    elif linktype in (101, 228):
        candidates.append(0)
    elif linktype == 0:
        candidates.append(4)

    for offset in (0, 4, 14, 18, 22):
        if offset not in candidates:
            candidates.append(offset)

    for offset in candidates:
        if len(data) < offset + 20:
            continue
        first = data[offset]
        version = first >> 4
        ihl = (first & 0x0F) * 4
        if version != 4 or ihl < 20 or len(data) < offset + ihl:
            continue
        total_length = int.from_bytes(data[offset + 2:offset + 4], "big")
        if total_length and total_length < ihl:
            continue
        proto = data[offset + 9]
        src = socket.inet_ntoa(data[offset + 12:offset + 16])
        dst = socket.inet_ntoa(data[offset + 16:offset + 20])
        sport = dport = None
        l4 = offset + ihl
        tcp_payload = b""
        if proto in (6, 17) and len(data) >= l4 + 4:
            sport = int.from_bytes(data[l4:l4 + 2], "big")
            dport = int.from_bytes(data[l4 + 2:l4 + 4], "big")
        if proto == 6 and len(data) >= l4 + 20:
            tcp_header_len = (data[l4 + 12] >> 4) * 4
            if tcp_header_len >= 20 and len(data) >= l4 + tcp_header_len:
                tcp_payload = data[l4 + tcp_header_len:]
        return {
            "src": src,
            "dst": dst,
            "sport": sport,
            "dport": dport,
            "protocol": proto,
            "ipOffset": offset,
            "tcpPayload": tcp_payload,
        }
    return None


def _network_capture_tls_sni(payload):
    if not isinstance(payload, (bytes, bytearray)):
        return None
    data = bytes(payload)
    if len(data) < 9 or data[0] != 0x16:
        return None
    record_len = int.from_bytes(data[3:5], "big")
    if record_len < 4:
        return None
    if data[5] != 0x01:
        return None
    hello_len = int.from_bytes(data[6:9], "big")
    end = min(len(data), 9 + hello_len)
    pos = 9
    if pos + 34 > end:
        return None
    pos += 34
    if pos >= end:
        return None
    session_len = data[pos]
    pos += 1 + session_len
    if pos + 2 > end:
        return None
    cipher_len = int.from_bytes(data[pos:pos + 2], "big")
    pos += 2 + cipher_len
    if pos >= end:
        return None
    compression_len = data[pos]
    pos += 1 + compression_len
    if pos + 2 > end:
        return None
    extensions_len = int.from_bytes(data[pos:pos + 2], "big")
    pos += 2
    extensions_end = min(end, pos + extensions_len)
    while pos + 4 <= extensions_end:
        ext_type = int.from_bytes(data[pos:pos + 2], "big")
        ext_len = int.from_bytes(data[pos + 2:pos + 4], "big")
        pos += 4
        ext_end = pos + ext_len
        if ext_end > extensions_end:
            return None
        if ext_type == 0 and ext_len >= 5:
            if pos + 2 > ext_end:
                return None
            names_len = int.from_bytes(data[pos:pos + 2], "big")
            name_pos = pos + 2
            names_end = min(ext_end, name_pos + names_len)
            while name_pos + 3 <= names_end:
                name_type = data[name_pos]
                name_len = int.from_bytes(data[name_pos + 1:name_pos + 3], "big")
                name_pos += 3
                if name_pos + name_len > names_end:
                    break
                if name_type == 0:
                    try:
                        host = data[name_pos:name_pos + name_len].decode("ascii").strip().lower()
                    except UnicodeDecodeError:
                        return None
                    if host and len(host) <= 253 and re.fullmatch(r"[a-z0-9._*-]+", host):
                        return host
                name_pos += name_len
        pos = ext_end
    return None


def _network_capture_parse_pcapng(pcapng_path, tv_ip):
    summary = {
        "analysisSource": "PCAPNG",
        "packetRecords": 0,
        "originalBytes": 0,
        "pcapPacketBlocks": 0,
        "pcapIpv4Packets": 0,
        "tvMatchedPacketRecords": 0,
        "filterScopedPacketRecords": 0,
        "httpsPacketRecords": 0,
        "httpPacketRecords": 0,
        "dnsPacketRecords": 0,
        "tlsServerNames": [],
        "tlsHostFlows": [],
        "topPeers": [],
        "topologyClassification": "UNKNOWN",
    }
    if not pcapng_path.is_file():
        return summary

    raw = pcapng_path.read_bytes()
    pos = 0
    endian = "<"
    interfaces = []
    peers = {}
    sni_counts = {}
    packet_flows = []
    flow_to_sni = {}

    def tls_flow_identity(parsed):
        src = parsed["src"]
        dst = parsed["dst"]
        sport = parsed["sport"]
        dport = parsed["dport"]
        if dport == 443 and sport is not None:
            return (dst, int(sport), 443), dst
        if sport == 443 and dport is not None:
            return (src, int(dport), 443), src
        return None, None

    def record_filtered_flow(parsed, packet_bytes):
        src = parsed["src"]
        dst = parsed["dst"]
        sport = parsed["sport"]
        dport = parsed["dport"]
        summary["filterScopedPacketRecords"] += 1

        service_port = None
        peer = None
        if dport in (443, 80, 53):
            service_port = dport
            peer = dst
        elif sport in (443, 80, 53):
            service_port = sport
            peer = src
        elif dport is not None and sport is not None:
            if dport < 49152 <= sport:
                service_port = dport
                peer = dst
            elif sport < 49152 <= dport:
                service_port = sport
                peer = src

        if service_port == 443:
            summary["httpsPacketRecords"] += 1
        elif service_port == 80:
            summary["httpPacketRecords"] += 1
        elif service_port == 53:
            summary["dnsPacketRecords"] += 1

        if peer:
            rec = peers.setdefault(peer, {"ip": peer, "packetRecords": 0, "bytes": 0, "ports": {}})
            rec["packetRecords"] += 1
            rec["bytes"] += int(packet_bytes or 0)
            if service_port is not None:
                key = str(service_port)
                rec["ports"][key] = int(rec["ports"].get(key, 0)) + 1

    while pos + 12 <= len(raw):
        block_type_bytes = raw[pos:pos + 4]
        if block_type_bytes == b"\x0a\x0d\x0d\x0a":
            if pos + 12 > len(raw):
                break
            bom = raw[pos + 8:pos + 12]
            if bom == b"\x4d\x3c\x2b\x1a":
                endian = "<"
            elif bom == b"\x1a\x2b\x3c\x4d":
                endian = ">"
            else:
                break
            block_type = 0x0A0D0D0A
        else:
            block_type = struct.unpack_from(endian + "I", raw, pos)[0]

        block_len = struct.unpack_from(endian + "I", raw, pos + 4)[0]
        if block_len < 12 or pos + block_len > len(raw):
            break

        if block_type == 0x0A0D0D0A:
            interfaces = []
        elif block_type == 0x00000001 and block_len >= 20:
            linktype = struct.unpack_from(endian + "H", raw, pos + 8)[0]
            interfaces.append(linktype)
        elif block_type == 0x00000006 and block_len >= 32:
            interface_id = struct.unpack_from(endian + "I", raw, pos + 8)[0]
            captured_len = struct.unpack_from(endian + "I", raw, pos + 20)[0]
            packet_len = struct.unpack_from(endian + "I", raw, pos + 24)[0]
            data_start = pos + 28
            data_end = min(data_start + captured_len, pos + block_len - 4)
            packet = raw[data_start:data_end]
            linktype = interfaces[interface_id] if interface_id < len(interfaces) else None
            summary["pcapPacketBlocks"] += 1
            parsed = _network_capture_decode_ipv4_packet(packet, linktype)
            if parsed:
                summary["pcapIpv4Packets"] += 1
                summary["packetRecords"] += 1
                summary["originalBytes"] += int(packet_len or captured_len)
                sni = _network_capture_tls_sni(parsed.get("tcpPayload"))
                flow_key, flow_peer = tls_flow_identity(parsed)
                if sni:
                    sni_counts[sni] = int(sni_counts.get(sni, 0)) + 1
                    if flow_key:
                        flow_to_sni[flow_key] = sni
                if flow_key:
                    packet_flows.append((flow_key, flow_peer, int(packet_len or captured_len)))
                record_filtered_flow(parsed, packet_len or captured_len)
                if parsed["src"] == tv_ip or parsed["dst"] == tv_ip:
                    summary["tvMatchedPacketRecords"] += 1
        elif block_type == 0x00000003 and block_len >= 16:
            packet_len = struct.unpack_from(endian + "I", raw, pos + 8)[0]
            data_start = pos + 12
            data_end = min(data_start + packet_len, pos + block_len - 4)
            packet = raw[data_start:data_end]
            linktype = interfaces[0] if interfaces else None
            summary["pcapPacketBlocks"] += 1
            parsed = _network_capture_decode_ipv4_packet(packet, linktype)
            if parsed:
                summary["pcapIpv4Packets"] += 1
                summary["packetRecords"] += 1
                summary["originalBytes"] += int(packet_len)
                sni = _network_capture_tls_sni(parsed.get("tcpPayload"))
                flow_key, flow_peer = tls_flow_identity(parsed)
                if sni:
                    sni_counts[sni] = int(sni_counts.get(sni, 0)) + 1
                    if flow_key:
                        flow_to_sni[flow_key] = sni
                if flow_key:
                    packet_flows.append((flow_key, flow_peer, int(packet_len)))
                record_filtered_flow(parsed, packet_len)
                if parsed["src"] == tv_ip or parsed["dst"] == tv_ip:
                    summary["tvMatchedPacketRecords"] += 1

        pos += block_len

    host_flow_stats = {}
    for flow_key, flow_peer, packet_bytes in packet_flows:
        host = flow_to_sni.get(flow_key)
        if not host:
            continue
        rec = host_flow_stats.setdefault(
            host,
            {"host": host, "packetRecords": 0, "bytes": 0, "peerIps": {}},
        )
        rec["packetRecords"] += 1
        rec["bytes"] += int(packet_bytes or 0)
        if flow_peer:
            rec["peerIps"][flow_peer] = int(rec["peerIps"].get(flow_peer, 0)) + 1

    summary["tlsHostFlows"] = []
    for rec in sorted(
        host_flow_stats.values(),
        key=lambda item: (item["bytes"], item["packetRecords"]),
        reverse=True,
    )[:40]:
        summary["tlsHostFlows"].append({
            "host": rec["host"],
            "packetRecords": rec["packetRecords"],
            "bytes": rec["bytes"],
            "peerIps": [
                {"ip": ip, "packetRecords": count}
                for ip, count in sorted(
                    rec["peerIps"].items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ],
        })

    summary["tlsServerNames"] = [
        {"host": host, "count": count}
        for host, count in sorted(sni_counts.items(), key=lambda item: (-item[1], item[0]))[:40]
    ]
    ordered = sorted(peers.values(), key=lambda x: (x["bytes"], x["packetRecords"]), reverse=True)
    summary["topPeers"] = ordered[:30]
    if summary["httpsPacketRecords"] >= 5 and summary["tvMatchedPacketRecords"] > 0:
        summary["topologyClassification"] = "FULL_PATH_VISIBLE"
    elif summary["httpsPacketRecords"] >= 5:
        summary["topologyClassification"] = "FILTERED_FLOW_VISIBLE_AFTER_NAT"
    elif summary["tvMatchedPacketRecords"] > 0:
        summary["topologyClassification"] = "DNS_OR_LOCAL_ONLY_LIKELY"
    elif summary["packetRecords"] > 0:
        summary["topologyClassification"] = "CAPTURED_BUT_TV_IP_NOT_VISIBLE"
    elif summary["pcapPacketBlocks"] > 0:
        summary["topologyClassification"] = "PCAP_PACKETS_UNPARSED"
    else:
        summary["topologyClassification"] = "NO_PACKET_RECORDS"
    return summary


def _network_capture_latest_saved_report():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(REPORTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for report_path in files:
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        capture = report.get("fullNetworkCapture")
        if not isinstance(capture, dict):
            continue
        rel = capture.get("pcapngFile")
        if not rel:
            continue
        pcapng_path = ROOT / pathlib.Path(str(rel))
        if not pcapng_path.is_file():
            continue
        return report_path, report, pcapng_path
    raise RuntimeError("No saved Sidee PCAPNG capture was found")


def _network_capture_reanalyze_latest():
    global STORE_DISCOVERY_REPORT
    report_path, report, pcapng_path = _network_capture_latest_saved_report()
    capture = dict(report.get("fullNetworkCapture") or {})
    previous_summary = dict(capture.get("summary") or {})
    status_text = str(
        (previous_summary.get("pktmonStatusBeforeStop") or {}).get("output") or ""
    )
    match = re.search(r"Sidee-TV\s+(\d{1,3}(?:\.\d{1,3}){3})", status_text)
    if not match:
        raise RuntimeError("Could not recover the TV IPv4 from the saved capture report")
    tv_ip = str(ipaddress.ip_address(match.group(1)))

    summary = _network_capture_parse_pcapng(pcapng_path, tv_ip)
    for key in ("etlBytes", "pcapngBytes", "textBytes", "conversion", "pktmonStatusBeforeStop", "note"):
        if key in previous_summary:
            summary[key] = previous_summary[key]
    summary["reanalyzedAt"] = _utc_timestamp()
    capture["summary"] = summary
    capture["status"] = "STOPPED"
    capture["error"] = None

    report["fullNetworkCapture"] = capture
    report.setdefault("summary", {})["fullNetworkCapture"] = "STOPPED"
    report["updatedAt"] = _utc_timestamp()
    session_id = report.get("sessionId")
    if not session_id or not SESSION_ID_RE.match(str(session_id)):
        raise RuntimeError("Saved capture report has an invalid sessionId")

    write_session_report(session_id, report)
    queue_report_sync(session_id, report, "full-network-reanalysis")
    with STORE_DISCOVERY_LOCK:
        STORE_DISCOVERY_REPORT = json.loads(json.dumps(report))
    with NETWORK_CAPTURE_LOCK:
        NETWORK_CAPTURE_STATE.clear()
        NETWORK_CAPTURE_STATE.update(json.loads(json.dumps(capture)))
        NETWORK_CAPTURE_STATE["tvIp"] = tv_ip

    print(
        f"[NETCAP] REANALYZED {capture.get('captureId')} · "
        f"{summary.get('topologyClassification')} · "
        f"{summary.get('httpsPacketRecords')} HTTPS"
    )
    return _network_capture_public_state()


def _network_capture_sync_report(public_state):
    global STORE_DISCOVERY_REPORT
    try:
        with STORE_DISCOVERY_LOCK:
            if STORE_DISCOVERY_REPORT is None:
                STORE_DISCOVERY_REPORT = _new_store_domain_discovery_report()
                STORE_DISCOVERY_REPORT["accessMode"] = "FULL_TV_NETWORK_CAPTURE"
            report = STORE_DISCOVERY_REPORT
            report["updatedAt"] = _utc_timestamp()
            report["fullNetworkCapture"] = json.loads(json.dumps(public_state))
            report.setdefault("summary", {})["fullNetworkCapture"] = public_state.get("status")
            snapshot = json.loads(json.dumps(report))
        write_session_report(snapshot["sessionId"], snapshot)
        queue_report_sync(snapshot["sessionId"], snapshot, "full-network-capture")
    except Exception as exc:
        print(f"[NETCAP] report sync error: {exc}")


def _network_capture_stop():
    with NETWORK_CAPTURE_LOCK:
        state = dict(NETWORK_CAPTURE_STATE)
    if state.get("status") not in ("CAPTURING", "STARTING"):
        raise RuntimeError("No active Sidee full-network capture")

    status_code, status_before = _network_capture_cmd(["status"], timeout=10)
    code, stop_output = _network_capture_cmd(["stop"], timeout=20)
    tv_ip = state.get("tvIp")
    paths = _network_capture_paths(state.get("captureId"))
    conversion = {"stopExitCode": code, "pcapng": None, "text": None}

    if paths["etl"].is_file():
        pcap_code, pcap_output = _network_capture_cmd([
            "etl2pcap", str(paths["etl"]), "--out", str(paths["pcapng"])
        ], timeout=120)
        conversion["pcapng"] = {
            "exitCode": pcap_code,
            "output": pcap_output[:1000],
            "bytes": paths["pcapng"].stat().st_size if paths["pcapng"].is_file() else 0,
        }
        txt_code, txt_output = _network_capture_cmd([
            "etl2txt", str(paths["etl"]), "--out", str(paths["txt"]),
            "--timestamp-only"
        ], timeout=120)
        conversion["text"] = {
            "exitCode": txt_code,
            "output": txt_output[:1000],
            "bytes": paths["txt"].stat().st_size if paths["txt"].is_file() else 0,
        }

    _network_capture_cmd(["filter", "remove"], timeout=10)
    summary = None
    if tv_ip and paths["pcapng"].is_file():
        try:
            summary = _network_capture_parse_pcapng(paths["pcapng"], tv_ip)
        except Exception as exc:
            print(f"[NETCAP] PCAPNG parse error: {exc}")
    if not summary or summary.get("packetRecords", 0) == 0:
        text_summary = _network_capture_parse_text(paths["txt"], tv_ip) if tv_ip else None
        if text_summary and (
            not summary
            or text_summary.get("packetRecords", 0) > summary.get("packetRecords", 0)
        ):
            summary = text_summary
    summary = summary or {}
    summary["etlBytes"] = paths["etl"].stat().st_size if paths["etl"].is_file() else 0
    summary["pcapngBytes"] = paths["pcapng"].stat().st_size if paths["pcapng"].is_file() else 0
    summary["textBytes"] = paths["txt"].stat().st_size if paths["txt"].is_file() else 0
    summary["conversion"] = conversion
    summary["pktmonStatusBeforeStop"] = {
        "exitCode": status_code,
        "output": status_before[:1500],
    }
    summary["note"] = (
        "PCAPNG contains full captured packet bytes for the filtered TV IP. "
        "HTTPS payload/path remains encrypted unless the protocol itself exposes metadata such as SNI."
    )
    _network_capture_set(
        status="STOPPED",
        stoppedAt=_utc_timestamp(),
        summary=summary,
        error=None if code == 0 else ("pktmon stop returned " + str(code)),
        pktmonOutput=stop_output[:1000],
    )
    public = _network_capture_publish("capture stopped")
    print(f"[NETCAP] STOPPED {state.get('captureId')} · {summary.get('topologyClassification')}")
    return public


def _store_static_fetch(host, path):
    host = _normalized_host(host)
    if host not in STORE_STATIC_MAP_HOST_SET:
        raise ValueError("Store static host not allowed")
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("Store static path must be absolute")

    conn = http.client.HTTPSConnection(
        host, 443, timeout=8, context=ssl.create_default_context()
    )
    try:
        conn.request(
            "GET",
            path,
            headers={
                "User-Agent": "Sidee-Store-Static-Mapper/1.0",
                "Accept": "text/html,application/javascript,text/javascript,*/*;q=0.5",
                "Accept-Encoding": "identity",
                "Connection": "close",
            },
        )
        response = conn.getresponse()
        raw = response.read(STORE_STATIC_MAP_MAX_BYTES + 1)
        truncated = len(raw) > STORE_STATIC_MAP_MAX_BYTES
        if truncated:
            raw = raw[:STORE_STATIC_MAP_MAX_BYTES]
        ctype = response.getheader("Content-Type") or ""
        location = response.getheader("Location")
        text = None
        if (
            "text/" in ctype.lower()
            or "javascript" in ctype.lower()
            or "json" in ctype.lower()
            or path.lower().endswith((".js", ".mjs", ".html", ".htm", ".json"))
        ):
            text = raw.decode("utf-8", "replace")
        return {
            "host": host,
            "path": path,
            "status": int(response.status),
            "contentType": ctype[:160],
            "bytes": len(raw),
            "truncated": truncated,
            "location": location[:500] if isinstance(location, str) else None,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "text": text,
        }
    finally:
        conn.close()


def _store_static_extract(fetch):
    text = fetch.get("text")
    out = {
        "host": fetch.get("host"),
        "path": fetch.get("path"),
        "status": fetch.get("status"),
        "contentType": fetch.get("contentType"),
        "bytes": fetch.get("bytes"),
        "truncated": fetch.get("truncated"),
        "sha256": fetch.get("sha256"),
        "location": fetch.get("location"),
        "apiPaths": [],
        "urls": [],
        "keywordHits": [],
        "assetRefs": [],
    }
    if not isinstance(text, str) or not text:
        return out

    api_paths = []
    for match in STORE_STATIC_API_RE.finditer(text):
        value = match.group(1)[:240]
        if value not in api_paths and not STORE_STATIC_SENSITIVE_RE.search(value):
            api_paths.append(value)
        if len(api_paths) >= 80:
            break
    out["apiPaths"] = api_paths

    urls = []
    for match in STORE_STATIC_URL_RE.finditer(text):
        value = match.group(1)[:500]
        if STORE_STATIC_SENSITIVE_RE.search(value):
            continue
        if value not in urls:
            urls.append(value)
        if len(urls) >= 80:
            break
    out["urls"] = urls

    hits = []
    lower = text.lower()
    for keyword in STORE_STATIC_MAP_KEYWORDS:
        start = 0
        found = 0
        key_lower = keyword.lower()
        while found < 5:
            idx = lower.find(key_lower, start)
            if idx < 0:
                break
            excerpt = text[max(0, idx - 180):min(len(text), idx + 420)]
            excerpt = re.sub(r"\s+", " ", excerpt)
            if not STORE_STATIC_SENSITIVE_RE.search(excerpt):
                hits.append({"keyword": keyword, "excerpt": excerpt[:700]})
            start = idx + len(keyword)
            found += 1
            if len(hits) >= 60:
                break
        if len(hits) >= 60:
            break
    out["keywordHits"] = hits

    refs = []
    if "html" in str(fetch.get("contentType") or "").lower() or "<script" in lower:
        base = "https://" + str(fetch.get("host")) + str(fetch.get("path") or "/")
        for match in STORE_STATIC_SCRIPT_RE.finditer(text):
            ref = urllib.parse.urljoin(base, match.group(1))
            parsed = urllib.parse.urlsplit(ref)
            ref_host = _normalized_host(parsed.hostname or "")
            if ref_host not in STORE_STATIC_MAP_HOST_SET:
                continue
            if not parsed.path.lower().endswith((".js", ".mjs")):
                continue
            safe = "https://" + ref_host + (parsed.path or "/")
            if parsed.query:
                safe += "?" + parsed.query
            if safe not in refs:
                refs.append(safe)
            if len(refs) >= STORE_STATIC_MAP_MAX_ASSETS:
                break
    out["assetRefs"] = refs
    return out


def _sync_store_static_map_into_report(static_map):
    global STORE_DISCOVERY_REPORT
    with STORE_DISCOVERY_LOCK:
        if STORE_DISCOVERY_REPORT is None:
            STORE_DISCOVERY_REPORT = _new_store_domain_discovery_report()
            STORE_DISCOVERY_REPORT["accessMode"] = "VIDAA_STORE_STATIC_API_MAP"
        report = STORE_DISCOVERY_REPORT
        report["updatedAt"] = _utc_timestamp()
        report["storeStaticMap"] = json.loads(json.dumps(static_map))
        report.setdefault("summary", {})["storeStaticMap"] = static_map.get("status", "UNKNOWN")
        snapshot = json.loads(json.dumps(report))
    write_session_report(snapshot["sessionId"], snapshot)
    try:
        queue_report_sync(snapshot["sessionId"], snapshot, "store-static-api-map")
    except Exception as exc:
        print(f"[STORE-STATIC] sync error: {exc}")
    return snapshot


def _run_store_static_api_map():
    started = _utc_timestamp()
    queue = []
    seen = set()
    results = []
    errors = []
    for host in STORE_STATIC_MAP_HOSTS:
        queue.append((host, "/"))
        queue.append((host, "/index.html"))

    while queue and len(results) < STORE_STATIC_MAP_MAX_ASSETS:
        host, path = queue.pop(0)
        key = (host, path)
        if key in seen:
            continue
        seen.add(key)
        try:
            fetched = _store_static_fetch(host, path)
            item = _store_static_extract(fetched)
            results.append(item)

            location = fetched.get("location")
            if isinstance(location, str) and location:
                absolute = urllib.parse.urljoin("https://" + host + path, location)
                parsed = urllib.parse.urlsplit(absolute)
                redirect_host = _normalized_host(parsed.hostname or "")
                if redirect_host in STORE_STATIC_MAP_HOST_SET:
                    redirect_path = parsed.path or "/"
                    if parsed.query:
                        redirect_path += "?" + parsed.query
                    queue.append((redirect_host, redirect_path))

            for ref in item.get("assetRefs", []):
                parsed = urllib.parse.urlsplit(ref)
                asset_host = _normalized_host(parsed.hostname or "")
                asset_path = parsed.path or "/"
                if parsed.query:
                    asset_path += "?" + parsed.query
                if asset_host in STORE_STATIC_MAP_HOST_SET:
                    queue.append((asset_host, asset_path))
        except Exception as exc:
            errors.append({"host": host, "path": path, "error": str(exc)[:500]})
            if len(errors) >= 40:
                break

    api_paths = []
    keyword_summary = {}
    interesting_urls = []
    for item in results:
        for api_path in item.get("apiPaths", []):
            if api_path not in api_paths:
                api_paths.append(api_path)
        for hit in item.get("keywordHits", []):
            keyword = hit.get("keyword")
            keyword_summary[keyword] = keyword_summary.get(keyword, 0) + 1
        for url in item.get("urls", []):
            if any(k in url.lower() for k in (
                "install", "download", "package", "appstore", "configurl", "bundle"
            )):
                if url not in interesting_urls:
                    interesting_urls.append(url)

    report = {
        "startedAt": started,
        "finishedAt": _utc_timestamp(),
        "readOnly": True,
        "usesOfficialTls": True,
        "credentialsSent": False,
        "cookiesSent": False,
        "hostAllowlist": list(STORE_STATIC_MAP_HOSTS),
        "status": "COMPLETED" if results else "NO_RESULTS",
        "fetchCount": len(results),
        "errorCount": len(errors),
        "apiPaths": api_paths[:160],
        "interestingUrls": interesting_urls[:120],
        "keywordSummary": keyword_summary,
        "resources": results,
        "errors": errors,
    }
    global STORE_STATIC_MAP_LAST
    with STORE_STATIC_MAP_LOCK:
        STORE_STATIC_MAP_LAST = report
    _sync_store_static_map_into_report(report)
    return json.loads(json.dumps(report))


def _store_static_api_map_snapshot():
    with STORE_STATIC_MAP_LOCK:
        if STORE_STATIC_MAP_LAST is None:
            return {
                "status": "NOT_RUN",
                "readOnly": True,
                "usesOfficialTls": True,
                "hostAllowlist": list(STORE_STATIC_MAP_HOSTS),
            }
        return json.loads(json.dumps(STORE_STATIC_MAP_LAST))


def client_build_id():
    """Bind the UI, shared context probe and inline bootstrap to one build."""
    try:
        digest = hashlib.sha256(b"\0".join([
            (WEB_DIR / "app.js").read_bytes(),
            (WEB_DIR / "hspdk-context.js").read_bytes(),
            (WEB_DIR / "index.html").read_bytes(),
            pathlib.Path(__file__).read_bytes(),
        ])).hexdigest()[:12]
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


def _redact_store_message(value, limit=500):
    text = str(value or "")
    text = re.sub(
        r"(?i)((?:token|authorization|cookie|secret|password|credential|signature|session|nonce|api[-_]?key|access[-_]?key)\s*[=:]\s*)[^\s&,;]+",
        r"\1<redacted>",
        text,
    )
    text = re.sub(r"(?i)\bBearer\s+[^\s,;]+", "Bearer <redacted>", text)
    return text[:limit]


def _is_store_discovery_host(host):
    host = _normalized_host(host)
    if not host:
        return False
    if host == "vidaahub.com" or host.endswith(".vidaahub.com"):
        return True
    if host == "app-appstore.hismarttv.com":
        return True
    if re.fullmatch(r"(?:api-launcher|auth-launcher)-[^.]+\.hismarttv\.com", host):
        return True
    if re.fullmatch(r"unified-ter-[^.]+\.hismarttv\.com", host):
        return True
    return False


def _dns_qtype_name(qtype):
    return {1: "A", 28: "AAAA", 65: "HTTPS"}.get(int(qtype or 0), str(int(qtype or 0)))


def _new_store_domain_discovery_report():
    now = _utc_timestamp()
    session_id = _new_probe_session_id()
    return {
        "sessionId": session_id,
        "clientBuildId": client_build_id(),
        "serverBuildId": client_build_id(),
        "buildMatch": True,
        "startedAt": now,
        "updatedAt": now,
        "accessMode": "VIDAA_STORE_DOMAIN_DISCOVERY",
        "storeDomainDiscovery": {
            "passiveDnsOnly": True,
            "responsesModified": False,
            "queryValuesPersisted": False,
            "scope": [
                "*.vidaahub.com",
                "api-launcher-*.hismarttv.com",
                "auth-launcher-*.hismarttv.com",
                "app-appstore.hismarttv.com",
                "unified-ter-*.hismarttv.com",
            ],
            "status": "IDLE",
            "totalQueries": 0,
            "hostCount": 0,
            "hosts": [],
        },
        "summary": {"storeDomainDiscovery": "IDLE"},
    }


def _store_install_probe_auto_start(trigger_host, client_ip):
    global STORE_DISCOVERY_REPORT, STORE_INSTALL_PROBE_CLIENT
    trigger_host = _normalized_host(trigger_host)
    with STORE_DISCOVERY_LOCK:
        existing = (
            STORE_DISCOVERY_REPORT
            and STORE_DISCOVERY_REPORT.get("storeInstallProbe")
        )
        if isinstance(existing, dict):
            return False
        if STORE_DISCOVERY_REPORT is None:
            STORE_DISCOVERY_REPORT = _new_store_domain_discovery_report()
        report = STORE_DISCOVERY_REPORT
        now = _utc_timestamp()
        STORE_INSTALL_PROBE_CLIENT = str(client_ip or "")
        report["accessMode"] = "VIDAA_STORE_INSTALL_DNS_PROBE_AUTO"
        report["updatedAt"] = now
        report["storeInstallProbe"] = {
            "passiveDnsOnly": True,
            "tlsIntercepted": False,
            "captureMode": "AUTO_TV_DNS_TIMELINE",
            "target": dict(STORE_INSTALL_PROBE_TARGET),
            "status": "AUTO_CAPTURING",
            "startedAt": now,
            "triggerHost": trigger_host,
            "markers": [{"type": "AUTO_START", "timestamp": now, "host": trigger_host}],
            "dnsEvents": [],
            "allDnsHosts": [],
            "allDnsQueryCount": 0,
            "targetDomainHit": False,
            "targetDomainFirstSeenAt": None,
            "note": (
                "Automatic passive DNS timeline. Capture starts on the first VIDAA "
                "Store-family DNS query after Sidee restart and then records bounded "
                "DNS hostname activity from that same TV client. No HTTPS content is "
                "intercepted and the client IP is not persisted."
            ),
        }
        report.setdefault("summary", {})["storeInstallProbe"] = "AUTO_CAPTURING"
        snapshot = json.loads(json.dumps(report))
    try:
        write_session_report(snapshot["sessionId"], snapshot)
    except Exception as exc:
        print(f"[STORE-INSTALL] auto-start report error: {exc}")
    try:
        queue_report_sync(snapshot["sessionId"], snapshot, "store-install-auto-start")
    except Exception as exc:
        print(f"[STORE-INSTALL] auto-start sync error: {exc}")
    print(f"[STORE-INSTALL] AUTO_START · {trigger_host}")
    return True


def _record_store_install_dns_timeline(host, qtype, client_ip):
    global STORE_DISCOVERY_REPORT
    host = _normalized_host(host)
    if not host:
        return None
    with STORE_DISCOVERY_LOCK:
        report = STORE_DISCOVERY_REPORT
        probe = report.get("storeInstallProbe") if isinstance(report, dict) else None
        if not isinstance(probe, dict) or probe.get("status") not in (
            "AUTO_CAPTURING", "CAPTURING_NAVIGATION", "DETAIL_OPEN", "INSTALL_ARMED"
        ):
            return None
        if STORE_INSTALL_PROBE_CLIENT and str(client_ip or "") != STORE_INSTALL_PROBE_CLIENT:
            return None

        now = _utc_timestamp()
        qtype_name = _dns_qtype_name(qtype)
        phase = "AUTO_TIMELINE" if probe.get("status") == "AUTO_CAPTURING" else _store_install_probe_phase(probe)
        event = {
            "timestamp": now,
            "phase": phase,
            "host": host,
            "qtype": qtype_name,
            "vendorScoped": _is_store_discovery_host(host),
        }
        probe.setdefault("dnsEvents", []).append(event)
        if len(probe["dnsEvents"]) > STORE_INSTALL_PROBE_MAX_EVENTS:
            probe["dnsEvents"] = probe["dnsEvents"][-STORE_INSTALL_PROBE_MAX_EVENTS:]

        probe["allDnsQueryCount"] = int(probe.get("allDnsQueryCount", 0)) + 1
        hosts = probe.setdefault("allDnsHosts", [])
        item = next((entry for entry in hosts if entry.get("host") == host), None)
        new_host = item is None
        if item is None and len(hosts) < STORE_INSTALL_PROBE_MAX_HOSTS:
            item = {
                "host": host,
                "firstSeen": now,
                "lastSeen": now,
                "firstSeenIndex": probe["allDnsQueryCount"],
                "queryCount": 0,
                "qtypes": [],
                "vendorScoped": _is_store_discovery_host(host),
            }
            hosts.append(item)
        new_qtype = False
        if item is not None:
            item["lastSeen"] = now
            item["queryCount"] = int(item.get("queryCount", 0)) + 1
            if qtype_name not in item["qtypes"]:
                item["qtypes"].append(qtype_name)
                item["qtypes"].sort()
                new_qtype = True

        target_host = _normalized_host((probe.get("target") or {}).get("host", ""))
        if target_host and host == target_host:
            probe["targetDomainHit"] = True
            if not probe.get("targetDomainFirstSeenAt"):
                probe["targetDomainFirstSeenAt"] = now

        report["updatedAt"] = now
        report.setdefault("summary", {})["storeInstallProbe"] = probe.get("status", "AUTO_CAPTURING")
        snapshot = json.loads(json.dumps(report))
        should_sync = new_host or new_qtype or probe["allDnsQueryCount"] % 25 == 0

    try:
        write_session_report(snapshot["sessionId"], snapshot)
    except Exception as exc:
        print(f"[STORE-INSTALL] timeline report error: {exc}")
    if should_sync:
        try:
            queue_report_sync(snapshot["sessionId"], snapshot, "store-install-auto-dns")
        except Exception as exc:
            print(f"[STORE-INSTALL] timeline sync error: {exc}")
    return snapshot


def _store_install_probe_phase(probe):
    status = str((probe or {}).get("status") or "")
    return {
        "CAPTURING_NAVIGATION": "NAVIGATION",
        "DETAIL_OPEN": "DETAIL_IDLE",
        "INSTALL_ARMED": "INSTALL_WINDOW",
        "COMPLETED": "COMPLETE",
    }.get(status, "UNSCOPED")


def _store_discovery_host_names(discovery):
    return sorted({
        str(item.get("host") or "")
        for item in (discovery or {}).get("hosts", [])
        if item.get("host")
    })


def _store_install_probe_refresh(probe, discovery):
    if not isinstance(probe, dict):
        return
    events = probe.get("dnsEvents") or []
    phase_hosts = {}
    phase_counts = {}
    for item in events:
        phase = str(item.get("phase") or "UNSCOPED")
        host = str(item.get("host") or "")
        if not host:
            continue
        phase_hosts.setdefault(phase, set()).add(host)
        key = (phase, host)
        phase_counts[key] = int(phase_counts.get(key, 0)) + 1

    probe["phaseHosts"] = {
        phase: sorted(hosts)
        for phase, hosts in phase_hosts.items()
    }

    armed_hosts = set(probe.get("hostSnapshotAtInstallArm") or [])
    install_hosts = set(phase_hosts.get("INSTALL_WINDOW", set()))
    probe["contactedAfterInstallArm"] = sorted(install_hosts)
    probe["newHostsAfterInstallArm"] = sorted(install_hosts - armed_hosts)
    probe["queryDeltaAfterInstallArm"] = [
        {
            "host": host,
            "queries": phase_counts.get(("INSTALL_WINDOW", host), 0),
        }
        for host in sorted(install_hosts)
    ]
    probe["currentHosts"] = _store_discovery_host_names(discovery)


def _store_install_probe_mark(action, target=None):
    global STORE_DISCOVERY_REPORT, STORE_INSTALL_PROBE_CLIENT
    action = str(action or "").strip().upper()
    now = _utc_timestamp()
    with STORE_DISCOVERY_LOCK:
        if action == "START":
            STORE_DISCOVERY_REPORT = _new_store_domain_discovery_report()
            STORE_INSTALL_PROBE_CLIENT = None
            report = STORE_DISCOVERY_REPORT
            report["accessMode"] = "VIDAA_STORE_INSTALL_DNS_PROBE"
            report["storeInstallProbe"] = {
                "passiveDnsOnly": True,
                "tlsIntercepted": False,
                "target": dict(STORE_INSTALL_PROBE_TARGET),
                "status": "CAPTURING_NAVIGATION",
                "startedAt": now,
                "detailOpenedAt": None,
                "installArmedAt": None,
                "finishedAt": None,
                "markers": [{"type": "START", "timestamp": now}],
                "dnsEvents": [],
                "hostSnapshotAtDetail": [],
                "hostSnapshotAtInstallArm": [],
                "hostSnapshotAtFinish": [],
                "phaseHosts": {},
                "contactedAfterInstallArm": [],
                "newHostsAfterInstallArm": [],
                "queryDeltaAfterInstallArm": [],
                "currentHosts": [],
                "note": (
                    "Passive DNS differential only. Arm immediately before pressing "
                    "Install/Download on the TV. HTTPS content is not intercepted."
                ),
            }
            report.setdefault("summary", {})["storeInstallProbe"] = "CAPTURING_NAVIGATION"
        else:
            if STORE_DISCOVERY_REPORT is None or not isinstance(
                STORE_DISCOVERY_REPORT.get("storeInstallProbe"), dict
            ):
                raise ValueError("Start the Store install probe first")
            report = STORE_DISCOVERY_REPORT
            discovery = report["storeDomainDiscovery"]
            probe = report["storeInstallProbe"]
            hosts_now = _store_discovery_host_names(discovery)

            if action == "DETAIL_OPEN":
                if probe.get("status") != "CAPTURING_NAVIGATION":
                    raise ValueError("DETAIL_OPEN is only valid after START")
                probe["status"] = "DETAIL_OPEN"
                probe["detailOpenedAt"] = now
                probe["hostSnapshotAtDetail"] = hosts_now
            elif action == "ARM_INSTALL":
                if probe.get("status") not in ("CAPTURING_NAVIGATION", "DETAIL_OPEN"):
                    raise ValueError("ARM_INSTALL requires an active pre-install capture")
                probe["status"] = "INSTALL_ARMED"
                probe["installArmedAt"] = now
                probe["hostSnapshotAtInstallArm"] = hosts_now
            elif action == "FINISH":
                if probe.get("status") != "INSTALL_ARMED":
                    raise ValueError("FINISH requires ARM_INSTALL first")
                probe["status"] = "COMPLETED"
                probe["finishedAt"] = now
                probe["hostSnapshotAtFinish"] = hosts_now
            else:
                raise ValueError("Unknown Store install probe action")

            probe.setdefault("markers", []).append({
                "type": action,
                "timestamp": now,
            })
            _store_install_probe_refresh(probe, discovery)
            report["updatedAt"] = now
            report.setdefault("summary", {})["storeInstallProbe"] = probe["status"]

        discovery = report["storeDomainDiscovery"]
        probe = report["storeInstallProbe"]
        _store_install_probe_refresh(probe, discovery)
        snapshot = json.loads(json.dumps(report))

    try:
        write_session_report(snapshot["sessionId"], snapshot)
    except Exception as exc:
        print(f"[STORE-INSTALL] local report error: {exc}")
    try:
        queue_report_sync(
            snapshot["sessionId"],
            snapshot,
            "store-install-probe-" + action.lower(),
        )
    except Exception as exc:
        print(f"[STORE-INSTALL] sync error: {exc}")
    print(f"[STORE-INSTALL] {action} · {probe.get('status')}")
    return snapshot


def _store_install_probe_snapshot():
    with STORE_DISCOVERY_LOCK:
        if STORE_DISCOVERY_REPORT is None:
            return {"status": "IDLE", "target": dict(STORE_INSTALL_PROBE_TARGET)}
        probe = STORE_DISCOVERY_REPORT.get("storeInstallProbe")
        if not isinstance(probe, dict):
            return {"status": "IDLE", "target": dict(STORE_INSTALL_PROBE_TARGET)}
        snapshot = json.loads(json.dumps(probe))
        _store_install_probe_refresh(
            snapshot,
            STORE_DISCOVERY_REPORT.get("storeDomainDiscovery", {}),
        )
        return snapshot


def _record_store_domain_query(host, qtype):
    global STORE_DISCOVERY_REPORT
    host = _normalized_host(host)
    if not _is_store_discovery_host(host):
        return None

    qtype_name = _dns_qtype_name(qtype)
    with STORE_DISCOVERY_LOCK:
        if STORE_DISCOVERY_REPORT is None:
            STORE_DISCOVERY_REPORT = _new_store_domain_discovery_report()
        report = STORE_DISCOVERY_REPORT
        discovery = report["storeDomainDiscovery"]
        now = _utc_timestamp()
        report["updatedAt"] = now
        discovery["totalQueries"] = int(discovery.get("totalQueries", 0)) + 1

        item = next((entry for entry in discovery["hosts"] if entry.get("host") == host), None)
        new_host = item is None
        if item is None:
            if len(discovery["hosts"]) >= STORE_DISCOVERY_MAX_HOSTS:
                item = None
            else:
                item = {
                    "host": host,
                    "firstSeen": now,
                    "lastSeen": now,
                    "queryCount": 0,
                    "qtypes": [],
                }
                discovery["hosts"].append(item)
        new_qtype = False
        if item is not None:
            item["lastSeen"] = now
            item["queryCount"] = int(item.get("queryCount", 0)) + 1
            qtypes = item.setdefault("qtypes", [])
            if qtype_name not in qtypes:
                qtypes.append(qtype_name)
                qtypes.sort()
                new_qtype = True

        discovery["hostCount"] = len(discovery["hosts"])
        discovery["status"] = "QUERIES_CAPTURED" if discovery["hosts"] else "IDLE"
        report["summary"]["storeDomainDiscovery"] = discovery["status"]

        probe = report.get("storeInstallProbe")
        if (
            isinstance(probe, dict)
            and probe.get("status") != "COMPLETED"
            and probe.get("status") != "AUTO_CAPTURING"
        ):
            phase = _store_install_probe_phase(probe)
            probe.setdefault("dnsEvents", []).append({
                "timestamp": now,
                "phase": phase,
                "host": host,
                "qtype": qtype_name,
                "vendorScoped": True,
            })
            if len(probe["dnsEvents"]) > STORE_INSTALL_PROBE_MAX_EVENTS:
                probe["dnsEvents"] = probe["dnsEvents"][-STORE_INSTALL_PROBE_MAX_EVENTS:]
            _store_install_probe_refresh(probe, discovery)
            report["summary"]["storeInstallProbe"] = probe.get("status", "IDLE")

        snapshot = json.loads(json.dumps(report))
        should_sync = (
            new_host
            or new_qtype
            or discovery["totalQueries"] % 20 == 0
        )

    trace_snapshot = _store_trace_snapshot()
    if trace_snapshot.get("status") != "IDLE":
        snapshot["storeCatalogTrace"] = trace_snapshot
        snapshot.setdefault("summary", {})["storeCatalogTrace"] = trace_snapshot.get("status", "IDLE")

    try:
        write_session_report(snapshot["sessionId"], snapshot)
    except Exception as exc:
        print(f"[STORE-DNS] local report error: {exc}")
    if should_sync:
        try:
            queue_report_sync(snapshot["sessionId"], snapshot, "store-domain-discovery")
        except Exception as exc:
            print(f"[STORE-DNS] sync error: {exc}")

    if new_host:
        print(f"[STORE-DNS] discovered {host} ({qtype_name})")
    return snapshot


def _store_domain_discovery_snapshot():
    with STORE_DISCOVERY_LOCK:
        if STORE_DISCOVERY_REPORT is None:
            return {
                "status": "IDLE",
                "passiveDnsOnly": True,
                "responsesModified": False,
                "totalQueries": 0,
                "hostCount": 0,
                "hosts": [],
            }
        return json.loads(json.dumps(STORE_DISCOVERY_REPORT.get("storeDomainDiscovery", {})))


def _store_trace_status(trace):
    if trace.get("errors"):
        return "PROXY_ERROR"
    if int(trace.get("requestCount", 0)) > 0:
        return "REQUESTS_CAPTURED"
    if trace.get("httpProxyHit"):
        return "HTTP_PROXY_ACTIVE"
    if trace.get("tlsSniHit"):
        return "TLS_SNI_ONLY"
    if trace.get("dnsHit"):
        return "DNS_ONLY"
    return "IDLE"


def _new_store_host_stats(host):
    return {
        "host": _normalized_host(host),
        "dnsHit": False,
        "tlsSniHit": False,
        "httpProxyHit": False,
        "requestCount": 0,
        "errorCount": 0,
        "status": "IDLE",
    }


def _safe_catalog_scalar(value, limit=300):
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:limit]
    return None


def _catalog_url_summary(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = urllib.parse.urlsplit(value)
        if parsed.scheme and parsed.hostname:
            return {
                "scheme": parsed.scheme[:20],
                "host": str(parsed.hostname)[:255],
                "path": (parsed.path or "/")[:500],
            }
        return {"path": value.split("?", 1)[0].split("#", 1)[0][:500]}
    except Exception:
        return {"path": value.split("?", 1)[0].split("#", 1)[0][:500]}


def _decode_catalog_body_for_json(body, content_encoding):
    if not isinstance(body, (bytes, bytearray)):
        return None, "not-bytes"
    if len(body) > STORE_TRACE_MAX_JSON_BYTES:
        return None, "body-too-large"
    encoding = str(content_encoding or "").strip().lower()
    try:
        if encoding in ("", "identity"):
            return bytes(body), None
        if encoding in ("gzip", "x-gzip"):
            return gzip.decompress(body), None
        if encoding == "deflate":
            return zlib.decompress(body), None
        return None, "unsupported-content-encoding:" + encoding[:80]
    except Exception as exc:
        return None, "decode-error:" + type(exc).__name__


def _catalog_json_summary(body, content_type="", content_encoding=""):
    decoded, skipped = _decode_catalog_body_for_json(body, content_encoding)
    if decoded is None:
        return {"parseSkipped": skipped} if skipped else None
    content_type = str(content_type or "").lower()
    stripped = decoded.lstrip()
    if "json" not in content_type and not stripped.startswith((b"{", b"[")):
        return None
    try:
        value = json.loads(decoded.decode("utf-8"))
    except Exception as exc:
        return {"parseError": type(exc).__name__}

    summary = {
        "topLevelType": "object" if isinstance(value, dict) else "array" if isinstance(value, list) else type(value).__name__,
        "topLevelKeys": sorted(str(k)[:120] for k in value.keys())[:120] if isinstance(value, dict) else [],
        "catalogApps": [],
        "routeCategoryKeys": [],
        "redactedKeyNames": [],
    }
    redacted_keys = set()
    route_category_keys = set()
    seen_apps = set()
    nodes = 0

    def add_app(node):
        appinfo = node.get("appInfo") if isinstance(node.get("appInfo"), dict) else node
        unified_name = str(appinfo.get("unifiedAppName", ""))
        app_url = str(appinfo.get("url", ""))
        marker = (
            "app",
            unified_name or str(node.get("id", "")),
            app_url,
        )
        if marker in seen_apps:
            return
        record = {}
        for key in ("id", "appContentId", "productCode", "typeCode", "title", "name"):
            if key in node and not STORE_TRACE_SENSITIVE_RE.search(key):
                scalar = _safe_catalog_scalar(node.get(key))
                if scalar is not None:
                    record[key] = scalar
        for key in (
            "unifiedAppName", "openMode", "packaged", "hasDetailPage",
            "appHasDetailPage", "appBundle", "categoryName", "subCategory",
            "configUrlDownload", "StoreType",
        ):
            if key in appinfo and not STORE_TRACE_SENSITIVE_RE.search(key):
                scalar = _safe_catalog_scalar(appinfo.get(key))
                if scalar is not None:
                    record[key] = scalar
        url_summary = _catalog_url_summary(appinfo.get("url"))
        if url_summary:
            record["url"] = url_summary
        if "configUrl" in appinfo:
            record["configUrlPresent"] = bool(appinfo.get("configUrl"))
        if record:
            seen_apps.add(marker)
            summary["catalogApps"].append(record)

    def walk(node, depth=0):
        nonlocal nodes
        if nodes >= 4000 or depth > 8 or len(summary["catalogApps"]) >= 20:
            return
        nodes += 1
        if isinstance(node, dict):
            for key in node.keys():
                key_text = str(key)
                key_lower = key_text.lower()
                if STORE_TRACE_SENSITIVE_RE.search(key_text):
                    redacted_keys.add(key_text[:120])
                    continue
                if key_lower == "resultcode" and "resultCode" not in summary:
                    scalar = _safe_catalog_scalar(node.get(key))
                    if scalar is not None:
                        summary["resultCode"] = scalar
                if "route" in key_lower or "category" in key_lower:
                    route_category_keys.add(key_text[:120])
            if isinstance(node.get("appInfo"), dict) or "unifiedAppName" in node:
                add_app(node)
            for key, child in node.items():
                if STORE_TRACE_SENSITIVE_RE.search(str(key)):
                    continue
                if isinstance(child, (dict, list)):
                    walk(child, depth + 1)
        elif isinstance(node, list):
            for child in node[:300]:
                if len(summary["catalogApps"]) >= 20:
                    break
                walk(child, depth + 1)

    walk(value)
    summary["routeCategoryKeys"] = sorted(route_category_keys)[:80]
    summary["redactedKeyNames"] = sorted(redacted_keys)[:80]
    summary["catalogAppCountCaptured"] = len(summary["catalogApps"])
    return summary


def _new_store_trace_report():
    now = _utc_timestamp()
    session_id = _new_probe_session_id()
    return {
        "sessionId": session_id,
        "clientBuildId": client_build_id(),
        "serverBuildId": client_build_id(),
        "buildMatch": True,
        "startedAt": now,
        "updatedAt": now,
        "accessContext": {
            "href": "https://" + STORE_CATALOG_HOST + "/",
            "origin": "https://" + STORE_CATALOG_HOST,
            "protocol": "https:",
            "hostname": STORE_CATALOG_HOST,
            "host": STORE_CATALOG_HOST,
            "accessMode": "VIDAA_STORE_CATALOG_TRACE",
        },
        "accessMode": "VIDAA_STORE_CATALOG_TRACE",
        "storeCatalogTrace": {
            "host": STORE_CATALOG_HOST,
            "hosts": list(STORE_TRACE_HOSTS),
            "hostStats": {
                host: _new_store_host_stats(host)
                for host in STORE_TRACE_HOSTS
            },
            "passThroughOnly": True,
            "responsesModified": False,
            "requestBodiesPersisted": False,
            "requestHeadersPersisted": False,
            "dnsHit": False,
            "tlsSniHit": False,
            "httpProxyHit": False,
            "requestCount": 0,
            "status": "IDLE",
            "events": [],
            "requests": [],
            "errors": [],
            "redactionPolicy": {
                "queryValues": "NOT_STORED",
                "requestHeaders": "NOT_STORED",
                "requestBodies": "NOT_STORED",
                "sensitiveJsonValues": "NOT_STORED",
            },
        },
        "summary": {"storeCatalogTrace": "IDLE"},
    }


def _record_store_trace(event, detail=None):
    global STORE_TRACE_REPORT
    detail = detail if isinstance(detail, dict) else {}
    with STORE_TRACE_LOCK:
        if STORE_TRACE_REPORT is None:
            STORE_TRACE_REPORT = _new_store_trace_report()
        report = STORE_TRACE_REPORT
        trace = report["storeCatalogTrace"]
        now = _utc_timestamp()
        report["updatedAt"] = now

        event_type = {
            "DNS_A": "DNS",
            "DNS_AAAA": "DNS",
            "TLS_SNI": "TLS_SNI",
            "HTTP_BEGIN": "HTTP_REQUEST",
            "HTTP_RESPONSE": "HTTP_RESPONSE",
            "PROXY_ERROR": "PROXY_ERROR",
        }.get(event, str(event)[:80])
        event_host = _normalized_host(detail.get("host") or STORE_CATALOG_HOST)
        event_item = {
            "timestamp": now,
            "type": event_type,
            "host": event_host,
        }
        host_stats = trace.setdefault("hostStats", {}).setdefault(
            event_host, _new_store_host_stats(event_host)
        )
        if event_type in ("HTTP_REQUEST", "HTTP_RESPONSE", "PROXY_ERROR"):
            event_item["method"] = str(detail.get("method", ""))[:16]
            event_item["path"] = str(detail.get("path", ""))[:700]
        if event_type in ("HTTP_REQUEST", "HTTP_RESPONSE"):
            event_item["queryParameterNames"] = sorted(
                set(str(x)[:120] for x in detail.get("queryParameterNames", []))
            )[:80]
        if event_type == "HTTP_RESPONSE":
            event_item["upstreamStatus"] = detail.get("upstreamStatus")
            event_item["contentType"] = str(detail.get("contentType", ""))[:200]
            event_item["responseLength"] = detail.get("responseLength")
        elif event_type == "PROXY_ERROR":
            event_item["stage"] = str(detail.get("stage", "proxy"))[:80]
            event_item["errorType"] = str(detail.get("errorType", ""))[:120]
        trace["events"].append(event_item)
        if len(trace["events"]) > STORE_TRACE_MAX_EVENTS:
            trace["events"] = trace["events"][-STORE_TRACE_MAX_EVENTS:]

        if event in ("DNS_A", "DNS_AAAA"):
            trace["dnsHit"] = True
            host_stats["dnsHit"] = True
        elif event == "TLS_SNI":
            trace["tlsSniHit"] = True
            host_stats["tlsSniHit"] = True
        elif event == "HTTP_BEGIN":
            trace["httpProxyHit"] = True
            host_stats["httpProxyHit"] = True
        elif event == "HTTP_RESPONSE":
            trace["httpProxyHit"] = True
            trace["requestCount"] = int(trace.get("requestCount", 0)) + 1
            host_stats["httpProxyHit"] = True
            host_stats["requestCount"] = int(host_stats.get("requestCount", 0)) + 1
            item = {
                "timestamp": now,
                "host": event_host,
                "method": str(detail.get("method", ""))[:16],
                "path": str(detail.get("path", ""))[:700],
                "queryParameterNames": sorted(set(str(x)[:120] for x in detail.get("queryParameterNames", [])))[:80],
                "upstreamStatus": detail.get("upstreamStatus"),
                "contentType": str(detail.get("contentType", ""))[:200],
                "contentEncoding": str(detail.get("contentEncoding", ""))[:80],
                "responseLength": detail.get("responseLength"),
                "jsonSummary": detail.get("jsonSummary"),
            }
            trace["requests"].append(item)
            if len(trace["requests"]) > STORE_TRACE_MAX_REQUESTS:
                trace["requests"] = trace["requests"][-STORE_TRACE_MAX_REQUESTS:]
        elif event == "PROXY_ERROR":
            trace["httpProxyHit"] = True
            host_stats["httpProxyHit"] = True
            host_stats["errorCount"] = int(host_stats.get("errorCount", 0)) + 1
            item = {
                "timestamp": now,
                "host": event_host,
                "stage": str(detail.get("stage", "proxy"))[:80],
                "method": str(detail.get("method", ""))[:16],
                "path": str(detail.get("path", ""))[:700],
                "errorType": str(detail.get("errorType", ""))[:120],
                "message": _redact_store_message(detail.get("message", "")),
            }
            trace["errors"].append(item)
            if len(trace["errors"]) > STORE_TRACE_MAX_ERRORS:
                trace["errors"] = trace["errors"][-STORE_TRACE_MAX_ERRORS:]

        host_status_source = {
            "dnsHit": host_stats.get("dnsHit"),
            "tlsSniHit": host_stats.get("tlsSniHit"),
            "httpProxyHit": host_stats.get("httpProxyHit"),
            "requestCount": host_stats.get("requestCount", 0),
            "errors": [True] if int(host_stats.get("errorCount", 0)) > 0 else [],
        }
        host_stats["status"] = _store_trace_status(host_status_source)
        trace["status"] = _store_trace_status(trace)
        report["summary"]["storeCatalogTrace"] = trace["status"]
        report["summary"]["storeTraceHosts"] = {
            host: stats.get("status", "IDLE")
            for host, stats in trace.get("hostStats", {}).items()
        }
        snapshot = json.loads(json.dumps(report))

    discovery_snapshot = _store_domain_discovery_snapshot()
    if discovery_snapshot.get("status") != "IDLE":
        snapshot["storeDomainDiscovery"] = discovery_snapshot
        snapshot.setdefault("summary", {})["storeDomainDiscovery"] = discovery_snapshot.get("status", "IDLE")

    try:
        write_session_report(snapshot["sessionId"], snapshot)
    except Exception as exc:
        print(f"[STORE-TRACE] local report error: {exc}")
    try:
        queue_report_sync(snapshot["sessionId"], snapshot, "store-catalog-" + event.lower())
    except Exception as exc:
        print(f"[STORE-TRACE] sync error: {exc}")
    return snapshot


def _store_trace_snapshot():
    with STORE_TRACE_LOCK:
        if STORE_TRACE_REPORT is None:
            return {
                "host": STORE_CATALOG_HOST,
                "hosts": list(STORE_TRACE_HOSTS),
                "hostStats": {
                    host: _new_store_host_stats(host)
                    for host in STORE_TRACE_HOSTS
                },
                "status": "IDLE",
                "passThroughOnly": True,
                "responsesModified": False,
                "requestCount": 0,
            }
        return json.loads(json.dumps(STORE_TRACE_REPORT.get("storeCatalogTrace", {})))


def _store_query_parameter_names(path):
    try:
        parsed = urllib.parse.urlsplit(path)
        return sorted(set(k[:120] for k, _ in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)))[:80]
    except Exception:
        return []


def _proxy_request_headers(headers, upstream_host=STORE_CATALOG_HOST):
    upstream_host = _normalized_host(upstream_host)
    connection_tokens = set()
    try:
        connection_tokens = {
            item.strip().lower()
            for item in str(headers.get("Connection", "")).split(",")
            if item.strip()
        }
    except Exception:
        pass
    out = {}
    for key, value in headers.items():
        lower = str(key).lower()
        if lower == "host" or lower == "content-length" or lower in STORE_PROXY_HOP_HEADERS or lower in connection_tokens:
            continue
        out[str(key)] = str(value)
    out["Host"] = upstream_host
    return out


def _proxy_store_catalog_request(handler, upstream_host=None):
    upstream_host = _normalized_host(
        upstream_host or handler.headers.get("Host", "")
    )
    if upstream_host not in STORE_TRACE_HOST_SET:
        raise ValueError("Unsupported Store trace host")
    parsed = urllib.parse.urlsplit(handler.path)
    path_only = parsed.path or "/"
    query_names = _store_query_parameter_names(handler.path)
    method = str(handler.command or "GET").upper()
    _record_store_trace("HTTP_BEGIN", {
        "host": upstream_host,
        "method": method,
        "path": path_only,
        "queryParameterNames": query_names,
    })

    body = None
    try:
        length = int(handler.headers.get("Content-Length", "0") or "0")
    except Exception:
        length = 0
    if length > 0:
        body = handler.rfile.read(length)

    headers = _proxy_request_headers(handler.headers, upstream_host)
    conn = None
    try:
        conn = http.client.HTTPSConnection(
            upstream_host,
            443,
            timeout=20,
            context=ssl.create_default_context(),
        )
        conn.request(method, handler.path, body=body, headers=headers)
        upstream = conn.getresponse()
        response_body = upstream.read()
        response_headers = upstream.getheaders()
        content_type = upstream.getheader("Content-Type", "")
        content_encoding = upstream.getheader("Content-Encoding", "")
        json_summary = _catalog_json_summary(response_body, content_type, content_encoding)

        if hasattr(handler, "send_response_only"):
            handler.send_response_only(upstream.status, upstream.reason)
        else:
            handler.send_response(upstream.status, upstream.reason)
        response_connection_tokens = set()
        for key, value in response_headers:
            if str(key).lower() == "connection":
                response_connection_tokens.update(
                    item.strip().lower() for item in str(value).split(",") if item.strip()
                )
        for key, value in response_headers:
            lower = str(key).lower()
            if lower in STORE_PROXY_HOP_HEADERS or lower in response_connection_tokens or lower == "content-length":
                continue
            handler.send_header(key, value)
        handler.send_header("Content-Length", str(len(response_body)))
        handler.end_headers()
        if method != "HEAD":
            handler.wfile.write(response_body)

        _record_store_trace("HTTP_RESPONSE", {
            "host": upstream_host,
            "method": method,
            "path": path_only,
            "queryParameterNames": query_names,
            "upstreamStatus": upstream.status,
            "contentType": content_type,
            "contentEncoding": content_encoding,
            "responseLength": len(response_body),
            "jsonSummary": json_summary,
        })
        print(f"[STORE-PROXY] {upstream_host} {method} {path_only} -> {upstream.status} ({len(response_body)} bytes)")
    except Exception as exc:
        message = _redact_store_message(exc)
        _record_store_trace("PROXY_ERROR", {
            "host": upstream_host,
            "stage": "upstream",
            "method": method,
            "path": path_only,
            "errorType": type(exc).__name__,
            "message": message,
        })
        payload = b"Sidee Store pass-through proxy could not reach the upstream."
        handler.send_response(502)
        handler.send_header("Content-Type", "text/plain; charset=utf-8")
        handler.send_header("Content-Length", str(len(payload)))
        handler.send_header("Cache-Control", "no-store")
        handler.end_headers()
        if method != "HEAD":
            handler.wfile.write(payload)
        print(f"[STORE-PROXY] ERROR {upstream_host} {method} {path_only}: {type(exc).__name__}")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


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
    hspdk_source = (WEB_DIR / "hspdk-context.js").read_text(encoding="utf-8")
    build_json = json.dumps(client_build_id())
    cfg = load_config()
    handoff_url = "http://{}:{}/app-runtime-handoff".format(
        get_local_ip(),
        int(cfg.get("http_port", 8080)),
    )
    handoff_json = json.dumps(handoff_url)
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
p,pre,button{{font-size:2vw;line-height:1.4}}
button{{display:block;margin:2vh 0;padding:1.2vh 1.6vw;border:1px solid #666;border-radius:.8vw;background:#fff;color:#111}}
button:disabled{{opacity:.45}}
pre{{white-space:pre-wrap;background:#191919;padding:2vw;border-radius:1vw;max-width:90vw}}
.ok{{color:#9fe6ae}} .wait{{color:#f0d98a}}
</style>
</head>
<body>
<main>
<h1>Sidee · native app context</h1>
<p id="state" class="wait">Capturing read-only VIDAA identity…</p>
<p>HSPDK context inspection only. No file write or library load.</p>
<pre id="out">host: {host}\nexpected app: {app["name"]} ({app["id"]})</pre>
</main>
<script data-sidee>{hspdk_source}</script>
<script data-sidee>
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
  function descriptorInfo(root,name){{
    var cur=root;
    for(var depth=0;cur&&depth<6;depth++){{
      try{{
        var d=Object.getOwnPropertyDescriptor(cur,name);
        if(d)return {{
          found:true,ownerDepth:depth,enumerable:!!d.enumerable,configurable:!!d.configurable,
          writable:Object.prototype.hasOwnProperty.call(d,"writable")?!!d.writable:null,
          hasGetter:typeof d.get==="function",hasSetter:typeof d.set==="function"
        }};
        cur=Object.getPrototypeOf(cur);
      }}catch(e){{return {{found:false,error:String(e&&e.message||e)}};}}
    }}
    return {{found:false}};
  }}
  function sourceInfo(root,name){{
    var out={{path:name,available:false,descriptor:descriptorInfo(root,name),length:null,name:null,source:null,error:null}};
    try{{
      var fn=root&&root[name];
      if(typeof fn!=="function")return out;
      out.available=true;
      out.length=fn.length;
      out.name=fn.name||null;
      out.source=String(Function.prototype.toString.call(fn)).slice(0,6000);
    }}catch(e){{out.error=String(e&&e.message||e);}}
    return out;
  }}
  function accessorSourceInfo(root,name){{
    var out={{path:name,found:false,getterSource:null,setterSource:null,error:null}};
    var cur=root;
    for(var depth=0;cur&&depth<6;depth++){{
      try{{
        var d=Object.getOwnPropertyDescriptor(cur,name);
        if(d){{
          out.found=true;
          out.ownerDepth=depth;
          if(typeof d.get==="function")out.getterSource=String(Function.prototype.toString.call(d.get)).slice(0,6000);
          if(typeof d.set==="function")out.setterSource=String(Function.prototype.toString.call(d.set)).slice(0,6000);
          return out;
        }}
        cur=Object.getPrototypeOf(cur);
      }}catch(e){{out.error=String(e&&e.message||e);return out;}}
    }}
    return out;
  }}
  function objectShape(root){{
    var out={{available:!!root,properties:[],error:null}};
    if(!root)return out;
    try{{
      var names=Object.getOwnPropertyNames(root).slice(0,160);
      out.properties=names.filter(function(name){{
        return !/(token|secret|password|cookie|auth|key|sign|cert|nonce|session)/i.test(name);
      }}).slice(0,100);
    }}catch(e){{out.error=String(e&&e.message||e);}}
    return out;
  }}
  var svc=null,ctx=null;
  try{{svc=window.vowOS&&window.vowOS.service;}}catch(e){{}}
  try{{ctx=window.vowOSContext;}}catch(e){{}}
  var payload={{
    clientBuildId:{build_json},
    legacyHspdkContext:window.SideeHspdkContext(),
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
    }},
    bridgeSources:{{
      hiUtilsCreateRequest:sourceInfo(window,"HiUtils_createRequest"),
      supportAppConfig:sourceInfo(window,"Hisense_SupportAppConfig"),
      serviceSyncExecute:sourceInfo(svc,"syncExecute"),
      serviceGetIdentifier:sourceInfo(svc,"getIdentifier"),
      serviceExecuteHttpRequest:sourceInfo(svc,"executeHttpRequest"),
      serviceProcessResponse:sourceInfo(svc,"processResponse"),
      serviceExecute:sourceInfo(svc,"execute"),
      serviceRelaunch:sourceInfo(svc,"reLaunchService"),
      contextInit:sourceInfo(ctx,"init"),
      contextGetAppIdentifier:sourceInfo(ctx,"getAppIdentifier"),
      contextGetAppId:sourceInfo(ctx,"getAppId")
    }},
    bridgeObjects:{{
      service:objectShape(svc),
      context:objectShape(ctx),
      navigatorAppIdentifierDescriptor:descriptorInfo(navigator,"appIdentifier"),
      navigatorAppIdentifierAccessor:accessorSourceInfo(navigator,"appIdentifier")
    }}
  }};
  var out=document.getElementById("out"),state=document.getElementById("state");
  out.textContent=JSON.stringify(payload,null,2);

  function postJson(url,body){{
    return new Promise(function(resolve,reject){{
      try{{
        var xhr=new XMLHttpRequest();
        xhr.open("POST",url,true);
        xhr.setRequestHeader("Content-Type","application/json");
        xhr.onreadystatechange=function(){{
          if(xhr.readyState!==4)return;
          var parsed=null;try{{parsed=JSON.parse(xhr.responseText||"null");}}catch(e){{}}
          if(xhr.status>=200&&xhr.status<300)resolve(parsed||{{}});
          else reject(new Error((parsed&&parsed.error)||("HTTP "+xhr.status)));
        }};
        xhr.onerror=function(){{reject(new Error("network error"));}};
        xhr.send(JSON.stringify(body));
      }}catch(e){{reject(e);}}
    }});
  }}
  postJson("/api/app-context-bootstrap",payload).then(function(saved){{
    state.textContent="Saved app identity. Testing runtime handoff…";
    state.className="ok";
    var next={handoff_json}+"?sourceSession="+encodeURIComponent(saved&&saved.sessionId||"")+
      "&sourceHost="+encodeURIComponent(location.hostname)+
      "&sourceAppId="+encodeURIComponent(expected.id||"");
    setTimeout(function(){{ location.replace(next); }},700);
  }}).catch(function(e){{
    state.textContent="Captured locally in the page; server sync failed: "+String(e&&e.message||e);
  }});
}})();
</script>
</body>
</html>"""


def _app_runtime_handoff_html(query):
    source_session = str((query.get("sourceSession") or [""])[0])[:120]
    source_host = str((query.get("sourceHost") or [""])[0])[:255]
    source_app_id = str((query.get("sourceAppId") or [""])[0])[:80]
    build_json = json.dumps(client_build_id())
    source_session_json = json.dumps(source_session)
    source_host_json = json.dumps(source_host)
    source_app_id_json = json.dumps(source_app_id)
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,height=device-height,initial-scale=1">
<title>Sidee App Runtime Handoff</title>
<style>
html,body{{margin:0;background:#0d0d0d;color:#fff;font-family:Arial,sans-serif}}
main{{box-sizing:border-box;min-height:100vh;padding:7vh 6vw}}
h1{{font-size:4vw;margin:0 0 2vh}}
p,pre{{font-size:2vw;line-height:1.45}}
pre{{white-space:pre-wrap;background:#171717;padding:2vw;border-radius:1vw;max-width:90vw}}
.focus{{outline:6px solid #fff;outline-offset:8px}}
</style>
</head>
<body tabindex="-1">
<main>
<h1>Sidee · app runtime handoff</h1>
<p id="state">Checking whether VIDAA kept the installed-app runtime after navigation…</p>
<pre id="out">Starting…</pre>
</main>
<script>
(function(){{
  "use strict";
  var CLIENT_BUILD_ID={build_json};
  var sourceSession={source_session_json};
  var sourceHost={source_host_json};
  var sourceAppId={source_app_id_json};
  var events=[];

  function safe(v){{
    if(v===undefined)return "[undefined]";
    if(v===null||typeof v==="string"||typeof v==="number"||typeof v==="boolean")return v;
    try{{return JSON.parse(JSON.stringify(v));}}catch(e){{return Object.prototype.toString.call(v);}}
  }}
  function call(root,name){{
    try{{
      if(!root||typeof root[name]!=="function")return {{status:"UNAVAILABLE",value:null}};
      return {{status:"RETURNED",value:safe(root[name].call(root))}};
    }}catch(e){{return {{status:"ERROR",value:null,error:String(e&&e.message||e)}};}}
  }}
  function prop(root,name){{
    try{{return {{status:"RETURNED",value:safe(root&&root[name])}};}}
    catch(e){{return {{status:"ERROR",value:null,error:String(e&&e.message||e)}};}}
  }}
  function snapshot(){{
    var svc=null,ctx=null;
    try{{svc=window.vowOS&&window.vowOS.service;}}catch(e){{}}
    try{{ctx=window.vowOSContext;}}catch(e){{}}
    return {{
      timestamp:new Date().toISOString(),
      sourceSession:sourceSession,
      sourceHost:sourceHost,
      sourceAppId:sourceAppId,
      clientBuildId:CLIENT_BUILD_ID,
      href:location.href,
      origin:location.origin,
      hostname:location.hostname,
      userAgent:navigator.userAgent,
      identity:{{
        navigatorAppIdentifier:prop(navigator,"appIdentifier"),
        serviceIdentifier:call(svc,"getIdentifier"),
        appIdentifier:call(ctx,"getAppIdentifier"),
        appId:call(ctx,"getAppId"),
        supportAppConfig:call(window,"Hisense_SupportAppConfig")
      }},
      capabilities:{{
        hiUtils:typeof window.HiUtils_createRequest==="function",
        installLegacy:typeof window.Hisense_installApp==="function",
        installV2:typeof window.Hisense_installApp_V2==="function",
        omiPlatform:!!window.omi_platform,
        operaOmi:!!window.opera_omi,
        vowService:!!svc,
        vowContext:!!ctx
      }},
      remoteEvents:events.slice(-30)
    }};
  }}
  function post(payload){{
    try{{
      var xhr=new XMLHttpRequest();
      xhr.open("POST","/api/app-runtime-handoff",true);
      xhr.setRequestHeader("Content-Type","application/json");
      xhr.send(JSON.stringify(payload));
    }}catch(e){{}}
  }}
  function renderAndPost(){{
    var p=snapshot();
    document.getElementById("out").textContent=JSON.stringify(p,null,2);
    var appId=p.identity&&p.identity.appId&&p.identity.appId.value;
    var ident=p.identity&&p.identity.serviceIdentifier&&p.identity.serviceIdentifier.value;
    var preserved=String(appId||"")===String(sourceAppId||"") && !!String(ident||"").trim();
    document.getElementById("state").textContent=preserved
      ?"APP RUNTIME PRESERVED · press arrows / OK now"
      :"APP RUNTIME NOT PRESERVED · press arrows / OK for input check";
    post(p);
  }}

  ["keydown","keyup","keypress"].forEach(function(type){{
    window.addEventListener(type,function(e){{
      events.push({{
        timestamp:new Date().toISOString(),
        type:type,
        key:String(e&&e.key||""),
        code:String(e&&e.code||""),
        keyCode:Number(e&&e.keyCode||0),
        which:Number(e&&e.which||0)
      }});
      renderAndPost();
    }},true);
  }});

  try{{document.body.focus();}}catch(e){{}}
  renderAndPost();
  setTimeout(renderAndPost,1200);
  setTimeout(renderAndPost,3500);
}})();
</script>
</body>
</html>"""


def _save_app_runtime_handoff(data, client_ip):
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object")
    source_session = str(data.get("sourceSession") or "").strip()
    if not source_session or not SESSION_ID_RE.fullmatch(source_session):
        raise ValueError("Invalid sourceSession")
    path = session_report_path(source_session)
    if not path.is_file():
        raise ValueError("Source session report not found")
    with path.open("r", encoding="utf-8") as f:
        report = json.load(f)
    if not isinstance(report, dict) or report.get("sessionId") != source_session:
        raise ValueError("Invalid source session report")
    identity = data.get("identity") if isinstance(data.get("identity"), dict) else {}
    source_app_id = str(data.get("sourceAppId") or "")
    app_id = ""
    service_identifier = ""
    try:
        app_id = str((identity.get("appId") or {}).get("value") or "")
    except Exception:
        app_id = ""
    try:
        service_identifier = str((identity.get("serviceIdentifier") or {}).get("value") or "")
    except Exception:
        service_identifier = ""
    preserved = bool(source_app_id and app_id == source_app_id and service_identifier.strip())
    remote_events = data.get("remoteEvents") if isinstance(data.get("remoteEvents"), list) else []
    report["updatedAt"] = _utc_timestamp()
    report["appRuntimeHandoffProbe"] = {
        "timestamp": str(data.get("timestamp") or report["updatedAt"])[:80],
        "sourceSession": source_session,
        "sourceHost": str(data.get("sourceHost") or "")[:255],
        "sourceAppId": source_app_id[:80],
        "target": {
            "href": str(data.get("href") or "")[:1000],
            "origin": str(data.get("origin") or "")[:500],
            "hostname": str(data.get("hostname") or "")[:255],
        },
        "identity": identity,
        "capabilities": data.get("capabilities") if isinstance(data.get("capabilities"), dict) else {},
        "remoteEvents": remote_events[-30:],
        "runtimePreserved": preserved,
        "inputReachedPage": bool(remote_events),
        "serverObserved": {"clientIp": str(client_ip or "")[:80]},
        "classification": (
            "APP_RUNTIME_PRESERVED_AFTER_CROSS_ORIGIN_HANDOFF"
            if preserved else
            "APP_RUNTIME_LOST_AFTER_CROSS_ORIGIN_HANDOFF"
        ),
    }
    report.setdefault("summary", {})["appRuntimeHandoff"] = (
        "PRESERVED" if preserved else "LOST"
    )
    report["summary"]["handoffInput"] = (
        "EVENTS_CAPTURED" if remote_events else "NO_EVENTS"
    )
    write_session_report(source_session, report)
    queue_report_sync(source_session, report, "app-runtime-handoff")
    return report


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
        "clientBuildId": data.get("clientBuildId") or "MISSING",
        "serverBuildId": client_build_id(),
        "buildMatch": data.get("clientBuildId") == client_build_id(),
        "legacyHspdkContext": data.get("legacyHspdkContext") if isinstance(data.get("legacyHspdkContext"), dict) else None,
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
            "bridgeSources": data.get("bridgeSources") if isinstance(data.get("bridgeSources"), dict) else {},
            "bridgeObjects": data.get("bridgeObjects") if isinstance(data.get("bridgeObjects"), dict) else {},
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


def _save_app_context_noop_result(data, server_host, client_ip):
    host = _normalized_host(server_host)
    expected = APP_CONTEXT_HOSTS.get(host)
    if not expected:
        raise ValueError("Unknown app-context host")
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object")

    session_id = data.get("sessionId")
    if not isinstance(session_id, str) or not SESSION_ID_RE.fullmatch(session_id):
        raise ValueError("Invalid sessionId")

    report_path = session_report_path(session_id)
    if not report_path.is_file():
        raise ValueError("App-context session report not found")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read app-context session report: {exc}") from exc

    if report.get("sessionId") != session_id or report.get("accessMode") != expected["mode"]:
        raise ValueError("Session is not the expected installed-app context")

    backup_id = data.get("backupId")
    backup = read_appinfo_backup(session_id, backup_id)
    readback_raw = data.get("readbackRaw")
    readback_valid = False
    readback_count = None
    readback_sha256 = None
    readback_error = None
    identical = False

    if isinstance(readback_raw, str):
        try:
            parsed, encoded = _validate_appinfo_raw(readback_raw)
            readback_valid = True
            readback_count = len(parsed["AppInfo"])
            readback_sha256 = hashlib.sha256(encoded).hexdigest()
            identical = readback_raw == backup["raw"]
        except ValueError as exc:
            readback_error = str(exc)
    else:
        readback_error = "Missing readback raw Appinfo JSON"

    def compact_native_result(value):
        if not isinstance(value, dict):
            return {"ret": value if isinstance(value, bool) else None, "code": None, "msg": None}
        ret = value.get("ret")
        code = value.get("code")
        msg = value.get("msg")
        return {
            "ret": ret if isinstance(ret, bool) else None,
            "code": code if isinstance(code, (int, float, str)) else None,
            "msg": str(msg)[:1000] if msg is not None else None,
        }

    write_result = compact_native_result(data.get("writeResponse"))
    readback_result = compact_native_result(data.get("readbackResponse"))

    if not readback_valid:
        capability = "READBACK_FAILED"
    elif not identical:
        capability = "WRITE_CHANGED_CONTENT"
    elif write_result["ret"] is False:
        capability = "WRITE_DENIED"
    elif write_result["ret"] is True:
        capability = "WRITE_ALLOWED_AND_IDENTICAL"
    else:
        capability = "INCONCLUSIVE"

    now = _utc_timestamp()
    lab = {
        "timestamp": now,
        "accessMode": expected["mode"],
        "expectedContext": dict(expected),
        "serverObserved": {"host": host, "clientIp": str(client_ip or "")[:80]},
        "operation": "exact AppInfo no-op fileWrite from installed-app context",
        "path": "websdk/Appinfo.json",
        "mode": 6,
        "backup": {
            "backupId": backup["backupId"],
            "sha256": backup["sha256"],
            "bytes": backup["bytes"],
            "appInfoCount": backup["appInfoCount"],
        },
        "writeResponse": write_result,
        "readbackResponse": readback_result,
        "readback": {
            "valid": readback_valid,
            "sha256": readback_sha256,
            "appInfoCount": readback_count,
            "identicalToBackup": identical,
            "error": readback_error,
        },
        "writeCapability": capability,
        "safety": "The TV wrote only the exact raw Appinfo string that was first backed up immutably on the Sidee PC. No app entry was added or changed intentionally.",
    }
    report["updatedAt"] = now
    report["appContextNoopWriteLab"] = lab
    report.setdefault("summary", {})["appInfoWrite"] = capability
    report["summary"]["permissionGate"] = (
        "REJECTED"
        if write_result["ret"] is False and (
            str(write_result.get("code")) == "503"
            or "permission" in str(write_result.get("msg") or "").lower()
            or "appconfig" in str(write_result.get("msg") or "").lower()
        )
        else "PASSED" if capability == "WRITE_ALLOWED_AND_IDENTICAL" else "UNKNOWN"
    )
    write_session_report(session_id, report)
    queue_report_sync(session_id, report, "app-context-noop-write")
    return report, lab


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
    # Versioned filename intentionally prevents reuse of an older certificate
    # that did not include all currently traced Store hostnames.
    cert = CERT_DIR / "sidee-vidaa-multihost-store-v2.crt"
    key = CERT_DIR / "sidee-vidaa-multihost-store-v2.key"
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

    cert_hosts = [
        "vidaahub.com",
        "www.vidaahub.com",
        "vidaa.smartone-iptv.com",
        "vidaa.duplecast.com",
        *STORE_TRACE_HOSTS,
    ]
    san = ",".join("DNS:" + host for host in cert_hosts)
    cmd = [
        openssl, "req", "-x509", "-newkey", "rsa:2048",
        "-keyout", str(key), "-out", str(cert), "-days", "30", "-nodes",
        "-subj", "/CN=vidaahub.com",
        "-addext", "subjectAltName=" + san,
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        config = CERT_DIR / "sidee-openssl-store-v2.cnf"
        alt_names = "\n".join(
            f"DNS.{index} = {host}" for index, host in enumerate(cert_hosts, start=1)
        )
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
            + alt_names
            + "\n",
            encoding="utf-8",
        )
        fallback = [
            openssl, "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", str(key), "-out", str(cert), "-days", "30", "-nodes",
            "-config", str(config), "-extensions", "v3_req",
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


def _dns_forward_stats_snapshot():
    with DNS_FORWARD_STATS_LOCK:
        out = dict(DNS_FORWARD_STATS)
    with DNS_REQUEST_THREADS_LOCK:
        out["requestWorkersActive"] = DNS_REQUEST_THREADS_ACTIVE
        out["requestWorkersPeak"] = DNS_REQUEST_THREADS_PEAK
    with DNS_OBSERVATION_DROP_LOCK:
        out["observationQueueDropped"] = DNS_OBSERVATION_DROPPED
    out["observationQueueDepth"] = DNS_OBSERVATION_QUEUE.qsize()
    return out


def _dns_forward_stats_record(host, success, latency_ms):
    with DNS_FORWARD_STATS_LOCK:
        DNS_FORWARD_STATS["queries"] = int(DNS_FORWARD_STATS.get("queries", 0)) + 1
        if success:
            DNS_FORWARD_STATS["success"] = int(DNS_FORWARD_STATS.get("success", 0)) + 1
        else:
            DNS_FORWARD_STATS["failures"] = int(DNS_FORWARD_STATS.get("failures", 0)) + 1
            DNS_FORWARD_STATS["lastFailureHost"] = _normalized_host(host)
        DNS_FORWARD_STATS["lastLatencyMs"] = round(float(latency_ms), 2)
        DNS_FORWARD_STATS["maxLatencyMs"] = max(
            float(DNS_FORWARD_STATS.get("maxLatencyMs", 0.0)),
            float(latency_ms),
        )


def _queue_dns_observation(host, qtype, client_ip, spoofed):
    global DNS_OBSERVATION_DROPPED
    item = {
        "host": _normalized_host(host),
        "qtype": int(qtype or 0),
        "clientIp": str(client_ip or ""),
        "spoofed": bool(spoofed),
    }
    try:
        DNS_OBSERVATION_QUEUE.put_nowait(item)
        return True
    except queue.Full:
        with DNS_OBSERVATION_DROP_LOCK:
            DNS_OBSERVATION_DROPPED += 1
            dropped = DNS_OBSERVATION_DROPPED
        if dropped == 1 or dropped % 100 == 0:
            print(f"[DNS-OBS] queue full; dropped {dropped} observations")
        return False


def dns_observation_worker():
    while not stop_event.is_set():
        try:
            item = DNS_OBSERVATION_QUEUE.get(timeout=0.5)
        except queue.Empty:
            continue
        try:
            host = item.get("host") or ""
            qtype = int(item.get("qtype") or 0)
            client_ip = item.get("clientIp") or ""
            spoofed = bool(item.get("spoofed"))

            if host in STORE_INSTALL_AUTO_TRIGGER_HOSTS:
                try:
                    _network_capture_maybe_start(client_ip, host)
                except Exception as exc:
                    print(f"[DNS-OBS] full-network capture auto-start error: {exc}")
                try:
                    _store_install_probe_auto_start(host, client_ip)
                except Exception as exc:
                    print(f"[DNS-OBS] store-install auto-start error: {exc}")

            try:
                _record_store_install_dns_timeline(host, qtype, client_ip)
            except Exception as exc:
                print(f"[DNS-OBS] store-install timeline error: {exc}")

            if _is_store_discovery_host(host) and not spoofed:
                try:
                    _record_store_domain_query(host, qtype)
                except Exception as exc:
                    print(f"[DNS-OBS] store-domain discovery error: {exc}")

            if spoofed and host in APP_CONTEXT_HOSTS:
                try:
                    _sync_app_transport_observation(
                        "DNS_A" if qtype == 1 else "DNS_AAAA",
                        host,
                        "",
                    )
                except Exception as exc:
                    print(f"[DNS-OBS] app-context report error: {exc}")
            elif spoofed and host in STORE_TRACE_HOST_SET:
                try:
                    _record_store_trace(
                        "DNS_A" if qtype == 1 else "DNS_AAAA",
                        {"host": host},
                    )
                except Exception as exc:
                    print(f"[DNS-OBS] store-trace report error: {exc}")
        finally:
            DNS_OBSERVATION_QUEUE.task_done()


def _forward_dns_tcp(data, addr):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(2)
        sock.connect((addr, 53))
        sock.sendall(struct.pack("!H", len(data)) + data)
        header = b""
        while len(header) < 2:
            chunk = sock.recv(2 - len(header))
            if not chunk:
                return None
            header += chunk
        length = struct.unpack("!H", header)[0]
        body = bytearray()
        while len(body) < length:
            chunk = sock.recv(min(65535, length - len(body)))
            if not chunk:
                return None
            body.extend(chunk)
        return bytes(body)
    finally:
        sock.close()


def forward_dns(data, upstreams):
    for addr in upstreams:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.settimeout(1.5)
            sock.sendto(data, (addr, 53))
            response = sock.recvfrom(65535)[0]
            if len(response) >= 4 and (response[2] & 0x02):
                tcp_response = _forward_dns_tcp(data, addr)
                if tcp_response:
                    return tcp_response
            return response
        except Exception:
            pass
        finally:
            sock.close()
    return None


def _handle_dns_request(data, client, server_sock, domains, upstreams, local_ip):
    global DNS_REQUEST_THREADS_ACTIVE, DNS_REQUEST_THREADS_PEAK
    acquired = DNS_REQUEST_SEMAPHORE.acquire(timeout=0.25)
    if not acquired:
        print(f"[DNS] worker saturation; dropping query from {client[0]}")
        return
    try:
        with DNS_REQUEST_THREADS_LOCK:
            DNS_REQUEST_THREADS_ACTIVE += 1
            DNS_REQUEST_THREADS_PEAK = max(
                DNS_REQUEST_THREADS_PEAK,
                DNS_REQUEST_THREADS_ACTIVE,
            )

        host, qtype, _ = parse_dns_question(data)
        spoofed = host in domains
        response = None

        if spoofed and qtype == 1:
            response = dns_answer(data, local_ip)
        elif spoofed and qtype == 28:
            response = empty_dns_answer(data)
        else:
            started = time.perf_counter()
            response = forward_dns(data, upstreams)
            latency_ms = (time.perf_counter() - started) * 1000.0
            _dns_forward_stats_record(host, response is not None, latency_ms)

        if response:
            try:
                server_sock.sendto(response, client)
            except OSError:
                return
        else:
            print(f"[DNS] upstream failure for {client[0]} {host} type={_dns_qtype_name(qtype)}")

        if spoofed and qtype in (1, 28):
            print(f"[DNS] {client[0]} {host} -> {'local IPv4' if qtype == 1 else 'empty AAAA'}")

        _queue_dns_observation(host, qtype, client[0], spoofed)
    except Exception as exc:
        print(f"[DNS] request error: {type(exc).__name__}: {exc}")
    finally:
        with DNS_REQUEST_THREADS_LOCK:
            DNS_REQUEST_THREADS_ACTIVE = max(0, DNS_REQUEST_THREADS_ACTIVE - 1)
        DNS_REQUEST_SEMAPHORE.release()


def run_dns(config, local_ip):
    domains = {d.lower().rstrip(".") for d in config.get("spoof_domains", ["vidaahub.com"])}
    port = int(config.get("dns_port", 53))
    upstreams = config.get("upstream_dns", ["1.1.1.1", "8.8.8.8"])
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        server_sock.bind(("0.0.0.0", port))
    except OSError as exc:
        server_sock.close()
        print(f"[ERROR] DNS could not listen on UDP/{port}: {exc}")
        if os.name == "nt" and getattr(exc, "winerror", None) == 10048:
            print(f"[ERROR] UDP/{port} is already in use. Most often another Sidee instance is still running.")
            print(f'[ERROR] Check the owner with: netstat -ano -p udp | findstr ":{port}"')
            print('[ERROR] Then inspect it with: tasklist /FI "PID eq <PID>"')
            print('[ERROR] If it is an old Sidee/Python process, close that Sidee window or use: taskkill /PID <PID> /F')
        stop_event.set()
        return
    server_sock.settimeout(1)
    print(f"[DNS] UDP/{port} -> {', '.join(sorted(domains))} = {local_ip}")
    print("[DNS] Fast path enabled: reply first, diagnostics queued in background.")

    while not stop_event.is_set():
        try:
            data, client = server_sock.recvfrom(65535)
        except socket.timeout:
            continue
        except OSError:
            break

        thread = threading.Thread(
            target=_handle_dns_request,
            args=(data, client, server_sock, domains, upstreams, local_ip),
            name="sidee-dns-request",
            daemon=True,
        )
        thread.start()

    server_sock.close()


class SideeHandler(http.server.BaseHTTPRequestHandler):
    server_version = "Sidee/0.1"

    def log_message(self, fmt, *args):
        host = _normalized_host(self.headers.get("Host", "")) if hasattr(self, "headers") else ""
        if host in STORE_TRACE_HOST_SET:
            path = urllib.parse.urlsplit(getattr(self, "path", "")).path or "/"
            print(f"[WEB] {self.client_address[0]} STORE {host} {getattr(self, 'command', '')} {path}")
            return
        print(f"[WEB] {self.client_address[0]} {fmt % args}")

    def _maybe_proxy_store_catalog(self):
        host = _normalized_host(self.headers.get("Host", ""))
        if host not in STORE_TRACE_HOST_SET:
            return False
        _proxy_store_catalog_request(self, host)
        return True

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
        if self._maybe_proxy_store_catalog():
            return
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

        if path == "/app-runtime-handoff":
            query = urllib.parse.parse_qs(parsed.query)
            data = _app_runtime_handoff_html(query).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(data)
            return

        if path == "/api/dns-health":
            return self._send_json({
                "ok": True,
                "dnsHealth": _dns_forward_stats_snapshot(),
            })

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

        if path == "/api/store-catalog-trace":
            return self._send_json({"ok": True, "storeCatalogTrace": _store_trace_snapshot()})

        if path == "/api/store-install-probe":
            return self._send_json({
                "ok": True,
                "storeInstallProbe": _store_install_probe_snapshot(),
            })

        if path == "/api/full-network-capture":
            return self._send_json({
                "ok": True,
                "fullNetworkCapture": _network_capture_public_state(),
            })

        if path == "/api/store-static-map":
            return self._send_json({
                "ok": True,
                "storeStaticMap": _store_static_api_map_snapshot(),
            })

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
        if self._maybe_proxy_store_catalog():
            return
        path = urllib.parse.urlparse(self.path).path
        try:
            data = self._read_json()
        except Exception as exc:
            return self._send_json({"ok": False, "error": str(exc)}, 400)

        if path == "/api/full-network-capture":
            if not isinstance(data, dict):
                return self._send_json({"ok": False, "error": "Expected JSON object"}, 400)
            action = str(data.get("action") or "").strip().upper()
            try:
                if action == "ARM":
                    result = _network_capture_arm(data.get("tvIp"))
                elif action == "STOP":
                    result = _network_capture_stop()
                elif action == "REANALYZE_LATEST":
                    result = _network_capture_reanalyze_latest()
                else:
                    return self._send_json({
                        "ok": False,
                        "error": "Action must be ARM, STOP, or REANALYZE_LATEST",
                    }, 400)
            except Exception as exc:
                return self._send_json({
                    "ok": False,
                    "error": str(exc)[:1000],
                    "fullNetworkCapture": _network_capture_public_state(),
                }, 500)
            return self._send_json({
                "ok": True,
                "fullNetworkCapture": result,
            })

        if path == "/api/store-static-map":
            try:
                result = _run_store_static_api_map()
            except Exception as exc:
                return self._send_json({
                    "ok": False,
                    "error": ("Store static map failed: " + str(exc))[:1000],
                }, 500)
            return self._send_json({
                "ok": True,
                "storeStaticMap": result,
            })

        if path == "/api/store-install-probe":
            if not isinstance(data, dict):
                return self._send_json({"ok": False, "error": "Expected JSON object"}, 400)
            try:
                report = _store_install_probe_mark(
                    data.get("action"),
                    data.get("target") if isinstance(data.get("target"), dict) else None,
                )
            except ValueError as exc:
                return self._send_json({"ok": False, "error": str(exc)}, 400)
            probe = report.get("storeInstallProbe", {})
            return self._send_json({
                "ok": True,
                "sessionId": report.get("sessionId"),
                "storeInstallProbe": probe,
                "storeDomainDiscovery": report.get("storeDomainDiscovery", {}),
            })

        if path == "/api/app-runtime-handoff":
            try:
                report = _save_app_runtime_handoff(data, self.client_address[0])
            except ValueError as exc:
                return self._send_json({"ok": False, "error": str(exc)}, 400)
            except OSError as exc:
                return self._send_json({"ok": False, "error": f"Could not save app runtime handoff: {exc}"}, 500)
            probe = report.get("appRuntimeHandoffProbe", {})
            return self._send_json({
                "ok": True,
                "sessionId": report["sessionId"],
                "runtimePreserved": probe.get("runtimePreserved"),
                "inputReachedPage": probe.get("inputReachedPage"),
                "classification": probe.get("classification"),
            })

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
                "clientBuildId": report["clientBuildId"],
                "accessMode": report["accessMode"],
                "summary": report["summary"],
            })

        if path == "/api/app-context-noop-result":
            try:
                report, lab = _save_app_context_noop_result(
                    data,
                    self.headers.get("Host", ""),
                    self.client_address[0],
                )
            except ValueError as exc:
                return self._send_json({"ok": False, "error": str(exc)}, 400)
            except OSError as exc:
                return self._send_json({"ok": False, "error": f"Could not save app-context no-op result: {exc}"}, 500)
            return self._send_json({
                "ok": True,
                "sessionId": report["sessionId"],
                "writeCapability": lab["writeCapability"],
                "writeResponse": lab["writeResponse"],
                "readback": lab["readback"],
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

    def do_PUT(self):
        if self._maybe_proxy_store_catalog():
            return
        self.send_error(405)

    def do_PATCH(self):
        if self._maybe_proxy_store_catalog():
            return
        self.send_error(405)

    def do_DELETE(self):
        if self._maybe_proxy_store_catalog():
            return
        self.send_error(405)

    def do_HEAD(self):
        if self._maybe_proxy_store_catalog():
            return
        self.send_error(405)

    def do_OPTIONS(self):
        if self._maybe_proxy_store_catalog():
            return
        self.send_error(405)


class ThreadingHTTPServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def run_http(port, *, fatal=False, purpose="HTTP"):
    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), SideeHandler)
    except OSError as exc:
        print(f"[ERROR] {purpose} could not listen on TCP/{port}: {exc}")
        if int(port) == 80:
            print("[ERROR] The installed-app context test requires TCP/80 because the real Smartone/Duplecast StartCommand uses plain http:// with no custom port.")
            if os.name == "nt":
                print("[ERROR] Run start-windows.bat as Administrator. The current launcher adds the Sidee TCP/80 Windows Firewall rule automatically.")
        if fatal:
            stop_event.set()
        return

    server.timeout = 1
    print(f"[HTTP] http://0.0.0.0:{port} ({purpose})")
    try:
        while not stop_event.is_set():
            server.handle_request()
    finally:
        server.server_close()


def run_https(port, cert, key):
    try:
        server = ThreadingHTTPServer(("0.0.0.0", port), SideeHandler)
    except OSError as exc:
        print(f"[ERROR] HTTPS could not listen on TCP/{port}: {exc}")
        if os.name == "nt" and getattr(exc, "winerror", None) == 10048:
            print(f"[ERROR] TCP/{port} is already in use. A previous Sidee instance is probably still running.")
            print(f'[ERROR] Check the owner with: netstat -ano -p tcp | findstr ":{port}"')
            print('[ERROR] Then inspect it with: tasklist /FI "PID eq <PID>"')
        stop_event.set()
        return
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
        elif host in STORE_TRACE_HOST_SET:
            print(f"[TLS-SNI] {host} (store transport trace)")
            try:
                _record_store_trace("TLS_SNI", {"host": host})
            except Exception as exc:
                print(f"[TLS-SNI] store-trace report error: {exc}")

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
    print(f"Build ID: {client_build_id()}")
    try:
        head = _run_git(["rev-parse", "HEAD"], check=False).stdout.strip()
        if head:
            print(f"Git HEAD: {head}")
    except Exception:
        pass
    print(f"PC IP: {local_ip}")
    print(f"PC dashboard: http://{local_ip}:{cfg.get('http_port', 8080)}")
    print(f"Installed-app context probe HTTP: http://{local_ip}:{cfg.get('app_context_http_port', 80)}")
    print(f"Raw-IP A/B test: http://{local_ip}:{cfg.get('http_port', 8080)}")
    print("VIDAA Store transport trace hosts (pass-through only):")
    for store_host in STORE_TRACE_HOSTS:
        print(f"  https://{store_host}")
    if REPORT_SYNC_CONFIG.get("enabled"):
        print(
            "Report sync: Git remote "
            f"{REPORT_SYNC_CONFIG['remote']} -> branch {REPORT_SYNC_CONFIG['branch']}"
        )
    else:
        print("Report sync: disabled")
    print("TV flow:")
    print(f"  1. Set the TV DNS manually to {local_ip}")
    print("  2. Open the normal VIDAA App Store from the TV launcher")
    print("  3. Uninstall Duplecast first if it is already installed")
    print("  4. Install Duplecast normally from the Store while Sidee passively captures the TV flow")
    print("  5. No Sidee dashboard interaction is required")
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

    http_thread = threading.Thread(
        target=run_http,
        args=(int(cfg.get("http_port", 8080)),),
        kwargs={"purpose": "dashboard"},
        daemon=True,
    )
    http_thread.start()
    threads.append(http_thread)

    app_context_http_port = int(cfg.get("app_context_http_port", 80))
    if app_context_http_port != int(cfg.get("http_port", 8080)):
        app_context_http_thread = threading.Thread(
            target=run_http,
            args=(app_context_http_port,),
            kwargs={"fatal": True, "purpose": "installed-app context"},
            daemon=True,
        )
        app_context_http_thread.start()
        threads.append(app_context_http_thread)

    if not args.no_dns:
        dns_observation_thread = threading.Thread(
            target=dns_observation_worker,
            name="sidee-dns-observation",
            daemon=True,
        )
        dns_observation_thread.start()
        threads.append(dns_observation_thread)

        dns_thread = threading.Thread(target=run_dns, args=(cfg, local_ip), daemon=True)
        dns_thread.start()
        threads.append(dns_thread)

        capture_cfg = cfg.get("store_download_capture", {})
        if capture_cfg.get("enabled") and capture_cfg.get("auto_arm_on_start"):
            try:
                _network_capture_arm()
                print(
                    "[STORE-DOWNLOAD] full TV capture ARMED automatically · "
                    "open VIDAA Store and install the target app normally"
                )
            except Exception as exc:
                print(f"[STORE-DOWNLOAD] automatic capture arm failed: {exc}")

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
