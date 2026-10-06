"""Exercise the real source or frozen dashboard without opening a GUI or a TV."""
from __future__ import annotations

import argparse
import http.client
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent


def request(port, path, method="GET", body=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request(method, path, body=body,
                           headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        return response.status, response.getheaders(), response.read()
    finally:
        connection.close()


def wait_state(process, path):
    end = time.monotonic() + 45
    while time.monotonic() < end:
        if process.poll() is not None:
            raise AssertionError(f"Sidee exited during startup ({process.returncode})")
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            status, _, _ = request(state["port"], "/api/status?key=" + quote(state["key"]))
            if status == 200:
                return state
        except (OSError, ValueError, KeyError, http.client.HTTPException):
            pass
        time.sleep(0.1)
    raise AssertionError("Sidee did not open its HTTP port within 45 seconds")


def smoke(command):
    with tempfile.TemporaryDirectory(prefix="sidee-smoke-") as temporary:
        folder = Path(temporary)
        env = dict(os.environ, SIDEE_CI="1", SIDEE_STATE_DIR=str(folder))
        # An arbitrary working directory proves paths do not depend on cwd.
        working = folder / "unrelated working directory"
        working.mkdir()
        if os.name != "nt":
            working.chmod(0o555)
        checked = subprocess.run(command + ["--self-test"], cwd=working, env=env,
                                 capture_output=True, text=True, timeout=45)
        if checked.returncode:
            raise AssertionError("Bundled self-test failed: " + checked.stderr)
        state_path = folder / "runtime" / "dashboard.json"
        with (folder / "process.log").open("w+", encoding="utf-8") as output:
            process = subprocess.Popen(command + ["--headless", "--port", "0"],
                                       cwd=working, env=env, stdout=output, stderr=output)
            state = None
            try:
                state = wait_state(process, state_path)
                port, key = state["port"], quote(state["key"], safe="")
                assert type(port) is int and 0 < port < 65536
                assert type(state["pid"]) is int and state["pid"] > 0
                # Windows venv's Python redirector owns a child interpreter;
                # macOS onedir and Unix source runs have no redirector.
                if os.name != "nt":
                    assert state["pid"] == process.pid
                status, _, body = request(port, "/api/status?key=" + key)
                assert status == 200 and json.loads(body)["state"] == "needs_pairing"
                assert request(port, "/api/status")[0] == 403
                assert request(port, "/api/status?key=incorrect")[0] == 403
                status, _, body = request(port, "/?key=" + key)
                assert status == 200 and b"Find TV" in body and b"Use your phone" in body
                for name in ("sidee-logo.png", "nuvio-wordmark.png", "jellyfin.png"):
                    status, _, body = request(port, "/assets/" + name)
                    assert status == 200 and body.startswith(b"\x89PNG\r\n\x1a\n")
                status, _, body = request(port, "/api/phone?key=" + key)
                assert status == 200 and "ok" in json.loads(body)
                status, _, body = request(port, "/api/pair/start?key=" + key,
                                          "POST", '{"host":"invalid"}')
                assert status == 200 and not json.loads(body)["ok"]
                assert request(port, "/api/shutdown?key=incorrect", "POST", "{}")[0] == 403
                # A second launch must reopen the same server, then exit cleanly.
                reopened = subprocess.run(command + ["--headless"], cwd=working,
                                          env=env, capture_output=True, timeout=15)
                assert reopened.returncode == 0
                assert json.loads(state_path.read_text())["pid"] == state["pid"]
                assert request(port, "/api/shutdown?key=" + key, "POST", "{}")[0] == 200
                assert process.wait(timeout=10) == 0
                assert not state_path.exists(), "Dashboard state was not cleaned up"
                with socket.socket() as probe:
                    probe.settimeout(1)
                    assert probe.connect_ex(("127.0.0.1", port)) != 0, "HTTP port stayed open"
            except BaseException:
                # Never print the authenticated URLs recorded by source startup.
                print("Startup diagnostics withheld because they can contain the access key.", file=sys.stderr)
                raise
            finally:
                if process.poll() is None and state:
                    try:
                        request(state["port"], "/api/shutdown?key=" +
                                quote(state["key"], safe=""), "POST", "{}")
                        process.wait(timeout=5)
                    except (OSError, http.client.HTTPException, subprocess.TimeoutExpired):
                        pass
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
        if os.name != "nt":
            # Verify SIGTERM drives the same cleanup path on real Unix runners.
            process = subprocess.Popen(command + ["--headless", "--port", "0"],
                                       cwd=working, env=env, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL)
            try:
                wait_state(process, state_path)
                process.send_signal(signal.SIGTERM)
                assert process.wait(timeout=10) == 0
                assert not state_path.exists(), "SIGTERM left dashboard state behind"
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
    print("Sidee smoke test passed: runtime, HTTP, assets, authentication, reopening and shutdown.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--source", action="store_true")
    mode.add_argument("--executable", type=Path)
    parser.add_argument("--python", default=sys.executable,
                        help="Python for source smoke (e.g. the Windows private runtime)")
    parser.add_argument("--source-root", type=Path, default=ROOT,
                        help="Extracted source distribution to test instead of the checkout")
    args = parser.parse_args()
    command = ([str(args.executable.resolve())] if args.executable else
               [str(Path(args.python).resolve()), str(args.source_root.resolve() / "sidee.py")])
    smoke(command)


if __name__ == "__main__":
    main()
