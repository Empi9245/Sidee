"""Preset catalog: apps ready to install with one click."""
from __future__ import annotations

import re

PRESETS: dict[str, dict] = {
    "nuvio": {
        "name": "Nuvio",
        "app_id": "nuviodebug",
        "url": "https://nuviotvsmart.vercel.app/",
        # VIDAA launcher icons are square; the horizontal wordmark is stretched.
        "image": "https://nuviotvsmart.vercel.app/assets/images/tizenIcon.png",
        "icon": "assets/nuvio-wordmark.png",
        "description": "Browse and stream your library",
    },
    "jellyfin": {
        "name": "Jellyfin",
        "app_id": "jellyfin",
        "url": "",  # built from the user's server address
        "needs_server": True,
        "server_placeholder": "192.168.1.50:8096",
        "image": "https://avatars.githubusercontent.com/u/35701260?s=512&v=4",
        "icon": "assets/jellyfin.png",
        "description": "Your media from your Jellyfin server",
    },
}


def get(key: str) -> dict | None:
    return PRESETS.get(key.lower())


def is_private_host(server: str) -> bool:
    """True for local/private network (LAN) hosts: HTTP is allowed only there."""
    host = re.split(r"[/:]", server.split("://")[-1])[0].strip().lower()
    if host in ("localhost",) or host.endswith(".local"):
        return True
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)\.(\d+)", host)
    if not m:
        return False
    o = [int(x) for x in m.groups()]
    return (o[0] == 10 or o[0] == 127
            or (o[0] == 172 and 16 <= o[1] <= 31)
            or (o[0] == 192 and o[1] == 168))


def build_server_url(server: str) -> str:
    """Server address -> web client URL, including scheme and path."""
    server = server.strip().rstrip("/")
    if "://" not in server:
        scheme = "http" if is_private_host(server) else "https"
        if ":" not in server.split("/")[-1]:
            server += ":8096"  # default Jellyfin port
        server = f"{scheme}://{server}"
    if not re.search(r"/web(/index\.html)?/?$", server):
        server = server.rstrip("/") + "/web/index.html"
    return server
