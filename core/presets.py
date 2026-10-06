"""Preset catalog: apps ready to install with one click."""
from __future__ import annotations

import re
import ipaddress
from urllib.parse import quote, urlsplit, urlunsplit

PRESETS: dict[str, dict] = {
    "nuvio": {
        "name": "Nuvio",
        "app_id": "nuviodebug",
        "url": "https://nuviotvsmart.vercel.app/vidaa.html",
        # VIDAA launcher icons are square; the horizontal wordmark is stretched.
        "image": "https://nuviotvsmart.vercel.app/assets/images/tizenIcon.png",
        "icon": "assets/nuvio-wordmark.png",
        "description": "Browse and stream your library",
    },
    "stremio": {
        "name": "Stremio",
        "app_id": "stremiodebug",
        "url": "https://web.stremio.com/",
        "server_builder": "stremio",
        "server_optional": True,
        "server_placeholder": "Remote HTTPS URL (optional)",
        "image": "https://web.stremio.com/images/icon_196x196.png",
        "description": "Full Stremio Web, with your streaming server",
    },
    "jellyfin": {
        "name": "Jellyfin",
        "app_id": "jellyfin",
        "url": "",  # built from the user's server address
        "needs_server": True,
        "server_placeholder": "Your server's IP or URL",
        "image": "https://avatars.githubusercontent.com/u/35701260?s=512&v=4",
        "icon": "assets/jellyfin.png",
        "description": "Your media from your Jellyfin server",
    },
}


def get(key: str) -> dict | None:
    return PRESETS.get(key.lower())


def is_private_host(server: str) -> bool:
    """True for local/private network (LAN) hosts: HTTP is allowed only there."""
    host = (urlsplit(server if "://" in server else "//" + server).hostname or "").rstrip(".")
    if host.endswith(".local"):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(address in ipaddress.ip_network(network) for network in
               ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7"))


def build_server_url(server: str) -> str:
    """Server address -> web client URL, including scheme and path."""
    server = server.strip().rstrip("/")
    has_scheme = "://" in server
    parsed = urlsplit(server if has_scheme else "//" + server)
    host = (parsed.hostname or "").rstrip(".")
    if not host:
        raise ValueError("Enter your Jellyfin server's LAN IP or full URL.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if (host == "localhost" or host.endswith(".localhost") or
            (address and (address.is_loopback or address.is_unspecified))):
        raise ValueError("Use your Jellyfin server's LAN IP or URL; localhost "
                         "and loopback addresses refer to the TV itself.")
    port = parsed.port  # also rejects malformed or out-of-range ports
    scheme = parsed.scheme if has_scheme else ("http" if is_private_host(server) else "https")
    authority = parsed.netloc
    if not has_scheme and port is None:
        authority += ":8096"  # default Jellyfin port
    path = parsed.path.rstrip("/")
    if not re.search(r"/web(/index\.html)?$", path):
        path += "/web/index.html"
    return urlunsplit((scheme, authority, path, parsed.query, parsed.fragment))


def build_stremio_url(server: str = "") -> str:
    """Build full Stremio Web, optionally preselecting a streaming server.

    The streamingServerUrl parameter is handled by Stremio Web itself.
    Remote servers should normally use the HTTPS URL exposed by Stremio
    Service/Desktop. Loopback addresses would point back to the TV.
    """
    server = server.strip().rstrip("/")
    if not server:
        return "https://web.stremio.com/"
    parsed = urlsplit(server)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError(
            "Paste the full Stremio streaming server URL, including http:// or https://.")
    host = parsed.hostname.rstrip(".").lower()
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if (host == "localhost" or host.endswith(".localhost") or
            (address and (address.is_loopback or address.is_unspecified))):
        raise ValueError(
            "Use the Stremio server address reachable by your TV; localhost points to the TV itself.")
    normalized = urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path or "", parsed.query, parsed.fragment))
    return "https://web.stremio.com/#/?streamingServerUrl=" + quote(
        normalized, safe="")
