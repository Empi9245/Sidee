#!/usr/bin/env python3
"""Sidee: add web apps as permanent tiles to the VIDAA launcher.

With no arguments, start the local web interface (click and you're done).
CLI commands: discover | pair <host> | refresh | install <preset> |
list | launch <preset>
"""
from __future__ import annotations

import argparse
import sys

from core import client, presets, webui


def cmd_cli(a) -> int:
    if a.cmd == "discover":
        for t in client.discover():
            print(f"  {t.host}  {t.friendly_name}  vidaa={t.is_vidaa}")
        return 0
    if a.cmd == "pair":
        s = client.pair(a.host, lambda: input("PIN shown on the TV: "))
        print(f"paired with {s.host}")
        return 0
    if a.cmd == "refresh":
        client.refresh(client.Session.load())
        print("tokens refreshed")
        return 0
    if a.cmd == "list":
        apps = client.list_tiles(client.Session.load())
        for x in apps:
            print(f"  {x.get('appId')}  {x.get('name')}  "
                  f"{str(x.get('url'))[:60]}")
        return 0
    if a.cmd == "install":
        p = presets.get(a.preset)
        if not p:
            print(f"unknown preset: {a.preset} "
                  f"(available: {', '.join(sorted(presets.PRESETS))})")
            return 2
        if p.get("needs_server"):
            if not getattr(a, "server", None):
                print(f"{p['name']} requires your server address: "
                      f"--server YOUR_SERVER_IP:8096")
                return 2
            p = dict(p)
            try:
                p["url"] = presets.build_server_url(a.server)
            except ValueError as error:
                print(str(error))
                return 2
        s = client.Session.load()
        apps = client.add_tile(s, p["app_id"], p["name"], p["url"], p["image"])
        ok = any(client.tile_matches_request(x, p["app_id"], p["url"]) for x in apps)
        print(f"{'REGISTERED' if ok else 'NOT confirmed by the TV'}: "
              f"{p['name']} ({p['app_id']}) -> {p['url']}")
        return 0 if ok else 1
    if a.cmd == "launch":
        p = presets.get(a.preset)
        if not p:
            print("unknown preset")
            return 2
        client.launch_tile(client.Session.load(), p["app_id"], p["name"],
                           p["url"])
        print("launched")
        return 0
    return 2


def main() -> int:
    p = argparse.ArgumentParser(prog="sidee", description=__doc__)
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("discover")
    pr = sub.add_parser("pair"); pr.add_argument("host")
    sub.add_parser("refresh")
    ins = sub.add_parser("install"); ins.add_argument("preset")
    ins.add_argument("--server", help="server address (for Jellyfin)")
    sub.add_parser("list")
    la = sub.add_parser("launch"); la.add_argument("preset")
    a = p.parse_args()

    if a.cmd is None:
        webui.serve()
        return 0
    return cmd_cli(a)


if __name__ == "__main__":
    sys.exit(main())
