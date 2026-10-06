"""Keep one TV connection open between requesting and submitting a browser PIN."""
from __future__ import annotations

import re
import secrets
import threading
import time

from . import client

PIN_WAIT = 60.0  # the TV's PIN dialog lasts about one minute
START_WAIT = 35.0
TOKEN_WAIT = 20.0


class _Attempt:
    def __init__(self, host: str):
        self.host = host
        self.id = secrets.token_urlsafe(16)
        self.lock = threading.Lock()
        self.ready = threading.Event()
        self.submitted = threading.Event()
        self.done = threading.Event()
        self.state = "starting"
        self.pin = ""
        self.error = ""
        self.deadline = 0.0

    def result(self) -> dict:
        with self.lock:
            if self.state == "awaiting_pin":
                return {"ok": True, "pairing_id": self.id, "host": self.host,
                        "expires_in": max(0, self.deadline - time.monotonic())}
            if self.state == "complete":
                return {"ok": True, "host": self.host}
            return {"ok": False, "error": self.error or
                    "Pairing is still in progress. Please wait."}

    def cancel(self) -> None:
        with self.lock:
            if self.state not in ("starting", "awaiting_pin"):
                return
            self.state = "cancelled"
            self.error = "Code request cancelled. Request a new code."
            self.submitted.set()

    def _provide_pin(self) -> str:
        with self.lock:
            if self.state == "cancelled":
                raise client.PairingCancelled(self.error)
            self.state = "awaiting_pin"
            self.deadline = time.monotonic() + PIN_WAIT
            self.ready.set()
        if not self.submitted.wait(PIN_WAIT):
            raise TimeoutError("The code request expired. Request a new code.")
        with self.lock:
            if self.state == "cancelled":
                raise client.PairingCancelled(self.error)
            pin, self.pin = self.pin, ""
            return pin

    def run(self) -> None:
        try:
            client.pair(self.host, self._provide_pin, timeout=TOKEN_WAIT)
            with self.lock:
                self.state = "complete"
        except Exception as e:
            with self.lock:
                if self.state != "cancelled":
                    self.state = "failed"
                    self.error = str(e)
        finally:
            with self.lock:
                self.pin = ""
            self.ready.set()
            self.done.set()

    def submit(self, pin: str) -> None:
        with self.lock:
            if self.state in ("confirming", "complete"):
                return  # a repeated HTTP request must not publish the PIN twice
            if self.state != "awaiting_pin" or time.monotonic() >= self.deadline:
                raise ValueError(self.error or "The code request expired. Request a new code.")
            self.pin = pin
            self.state = "confirming"
            self.submitted.set()


class PairingFlow:
    def __init__(self):
        self.lock = threading.Lock()
        self.attempt: _Attempt | None = None

    def start(self, host: str) -> dict:
        with self.lock:
            if self.attempt:
                with self.attempt.lock:
                    busy = self.attempt.state in ("starting", "confirming")
                if busy:
                    raise ValueError("Pairing is already in progress. Please wait.")
                self.attempt.cancel()
            attempt = self.attempt = _Attempt(host)
            threading.Thread(target=attempt.run, daemon=True,
                             name="sidee-browser-pairing").start()
        if not attempt.ready.wait(START_WAIT):
            attempt.cancel()
            return {"ok": False, "error": "The TV did not respond. Request a new code."}
        return attempt.result()

    def confirm(self, pairing_id: str, pin: str) -> dict:
        if not re.fullmatch(r"[0-9]{4}", pin):
            raise ValueError("PIN must be 4 digits")
        with self.lock:
            attempt = self.attempt
            if not attempt or not secrets.compare_digest(attempt.id, pairing_id):
                raise ValueError("Code request not found. Request a new code.")
            attempt.submit(pin)
        attempt.done.wait(min(client.PIN_RESULT_WAIT, TOKEN_WAIT) + TOKEN_WAIT + 5)
        return attempt.result()

    def cancel(self, pairing_id: str) -> dict:
        with self.lock:
            if self.attempt and secrets.compare_digest(self.attempt.id, pairing_id):
                self.attempt.cancel()
        return {"ok": True}
