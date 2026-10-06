"""Small macOS application launcher for Sidee's existing browser dashboard."""
from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import traceback


def _log_error() -> Path:
    override = os.environ.get("SIDEE_STATE_DIR")
    folder = (Path(override) / "logs" if override else
              Path.home() / "Library" / "Logs" / "Sidee")
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = folder / "sidee.log"
    with path.open("a", encoding="utf-8") as output:
        os.chmod(path, 0o600)
        traceback.print_exc(file=output)
    return path


def _fallback_error(message: str) -> None:
    # A native alert remains available if the bundled GUI cannot initialize.
    # Pass text as an argument, never interpolate it into AppleScript code.
    script = ('on run argv\n'
              'display alert "Sidee could not start" message (item 1 of argv) '
              'as critical buttons {"OK"} default button "OK"\nend run')
    try:
        subprocess.run(["/usr/bin/osascript", "-e", script, message],
                       capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired):
        pass


def run_gui() -> int:
    window = dashboard = None
    previous_signals = {}
    try:
        import tkinter as tk
        from tkinter import messagebox, ttk
        from core import webui

        if webui._reopen_dashboard(True):
            return 0
        window = tk.Tk()
        window.title("Sidee")
        window.resizable(False, False)
        frame = ttk.Frame(window, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Sidee", font=("Helvetica", 22, "bold")).pack()
        ttk.Label(frame, text="Use Sidee in your browser.\nKeep this window open "
                  "while pairing your TV.", justify="center").pack(pady=14)
        dashboard = webui.Dashboard()
        dashboard.start()

        def open_dashboard(*_):
            try:
                if not dashboard.open():
                    messagebox.showinfo("Open Sidee", "Open this complete address "
                        "in your browser:\n\n" + dashboard.url, parent=window)
            except Exception:
                messagebox.showinfo("Open Sidee", "Open this complete address "
                    "in your browser:\n\n" + dashboard.url, parent=window)

        def quit_sidee(*_):
            dashboard.stop_event.set()
            window.quit()

        def check_server():
            if dashboard.error:
                raise_error(dashboard.error)
                return
            if dashboard.stop_event.is_set():
                window.quit()
                return
            window.after(200, check_server)

        def raise_error(error):
            try:
                raise error
            except Exception:
                path = _log_error()
            messagebox.showerror("Sidee stopped", "The dashboard stopped. Quit "
                "and reopen Sidee. Details were saved to:\n" + str(path), parent=window)
            quit_sidee()

        ttk.Button(frame, text="Open dashboard", command=open_dashboard).pack(fill="x")
        ttk.Button(frame, text="Quit Sidee", command=quit_sidee).pack(fill="x", pady=(8, 0))
        window.protocol("WM_DELETE_WINDOW", quit_sidee)
        window.createcommand("::tk::mac::Quit", quit_sidee)
        window.createcommand("::tk::mac::ReopenApplication", open_dashboard)
        window.bind("<Command-q>", quit_sidee)
        for number in (signal.SIGINT, signal.SIGTERM):
            previous_signals[number] = signal.signal(
                number, lambda *_: dashboard.stop_event.set())
        window.after(200, check_server)
        window.after(100, open_dashboard)
        window.mainloop()
        return 1 if dashboard.error else 0
    except Exception:
        try:
            path = _log_error()
            message = ("Quit and reopen Sidee. Make sure the complete app was "
                       "copied to Applications. Details were saved to:\n" + str(path))
        except OSError:
            message = "Sidee could not start. Copy the complete app to Applications and try again."
        if window:
            from tkinter import messagebox
            messagebox.showerror("Sidee could not start", message, parent=window)
        else:
            _fallback_error(message)
        return 1
    finally:
        for number, handler in previous_signals.items():
            signal.signal(number, handler)
        if dashboard:
            dashboard.close()
        if window:
            window.destroy()


def main() -> int:
    if len(sys.argv) > 1 or os.environ.get("SIDEE_CI") == "1":
        import sidee
        return sidee.main()
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
