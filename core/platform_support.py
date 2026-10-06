"""Small platform boundary for resources, private state, and LAN discovery."""
from __future__ import annotations

import errno
import ipaddress
import os
from pathlib import Path
import re
import socket
import subprocess
import sys


def resource_root(module_file: str | None = None) -> Path:
    """Return packaged data without relying on the launcher's working folder."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)).resolve()
    parent = Path(module_file or __file__).resolve().parent
    return parent.parent if parent.name == "core" else parent


def _state_override() -> Path | None:
    value = os.environ.get("SIDEE_STATE_DIR", "").strip()
    return Path(value).expanduser().resolve() if value else None


def profile_dir() -> Path:
    """Preserve existing pairings; explicit test state never reads the profile."""
    base = _state_override()
    if base is None:
        home = Path(os.path.expanduser("~"))
        base, legacy = home / ".sidee", home / ".vidaa-tile"
        if not (base / "session.json").is_file() and (legacy / "session.json").is_file():
            base = legacy
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    return base


def dashboard_state_path(project_root: str | Path) -> Path:
    """Keep writable runtime files outside a frozen macOS application bundle."""
    override = _state_override()
    if override is not None:
        return override / "runtime" / "dashboard.json"
    if sys.platform == "darwin" and getattr(sys, "frozen", False):
        return (Path(os.path.expanduser("~")) / "Library" / "Application Support"
                / "Sidee" / "runtime" / "dashboard.json")
    return Path(project_root) / ".runtime" / "dashboard.json"


def allow_reuse_address() -> bool:
    """Unix can reuse closed listeners; Windows must reserve its own port."""
    return os.name != "nt"


def configure_exclusive_tcp_socket(sock: socket.socket) -> None:
    if os.name == "nt":
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)


def address_in_use(error: OSError) -> bool:
    return (error.errno == errno.EADDRINUSE
            or getattr(error, "winerror", None) in (10013, 10048))


def _broadcast(host: str, mask: str) -> str | None:
    try:
        address = ipaddress.IPv4Address(host)
        network = ipaddress.IPv4Network(f"{address}/{mask}", strict=False)
        if network.is_loopback or network.prefixlen >= 31:
            return None
        return str(network.broadcast_address)
    except ValueError:
        return None


def broadcasts_from_ipconfig(output: str) -> list[str]:
    """Read IPv4 address/mask pairs without depending on localized labels."""
    broadcasts = set()
    host = None
    for line in output.splitlines():
        match = re.search(r"(?<![\d.])(\d{1,3}(?:\.\d{1,3}){3})(?![\d.])", line)
        if "ipv4" in line.lower():
            host = match.group(1) if match else None
        elif host and match:
            target = _broadcast(host, match.group(1))
            if target:
                broadcasts.add(target)
            host = None
    return sorted(broadcasts)


def broadcasts_from_ifconfig(output: str) -> list[str]:
    """Parse active macOS broadcast interfaces, including hexadecimal masks."""
    broadcasts = set()
    active = False
    pending = set()
    for line in output.splitlines():
        if line and not line[0].isspace():
            if active:
                broadcasts.update(pending)
            pending = set()
            flags = re.search(r"<([^>]+)>", line)
            names = set(flags.group(1).split(",")) if flags else set()
            active = {"UP", "BROADCAST"}.issubset(names) and not names.intersection(
                {"LOOPBACK", "POINTOPOINT"})
        elif re.search(r"\bstatus:\s+inactive\b", line):
            active = False
        if not active:
            continue
        match = re.search(r"\binet\s+(\d{1,3}(?:\.\d{1,3}){3})\s+netmask\s+(\S+)", line)
        if not match:
            continue
        try:
            address = ipaddress.IPv4Address(match.group(1))
        except ValueError:
            continue
        if (address.is_unspecified or address.is_multicast or address.is_link_local):
            continue
        mask = match.group(2)
        if mask.lower().startswith("0x"):
            try:
                mask = str(ipaddress.IPv4Address(int(mask, 16)))
            except (ValueError, ipaddress.AddressValueError):
                continue
        target = _broadcast(match.group(1), mask)
        if target:
            pending.add(target)
    if active:
        broadcasts.update(pending)
    return sorted(broadcasts)


def local_broadcasts() -> list[str]:
    """Use only native interface inspection, with global/multicast fallback."""
    kwargs = dict(capture_output=True, text=True, errors="replace", timeout=3)
    if sys.platform == "darwin":
        command, parser = ["/sbin/ifconfig"], broadcasts_from_ifconfig
    elif os.name == "nt":
        command, parser = ["ipconfig"], broadcasts_from_ipconfig
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        return []
    try:
        result = subprocess.run(command, **kwargs)
        return parser(result.stdout) if result.returncode == 0 else []
    except (OSError, subprocess.TimeoutExpired):
        return []
