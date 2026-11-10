#!/bin/sh
# First-run launcher for macOS and Linux. It keeps dependencies inside .runtime.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$root"

python_command=${PYTHON:-}
if [ -z "$python_command" ]; then
    for candidate in python3 python; do
        if command -v "$candidate" >/dev/null 2>&1; then
            python_command=$candidate
            break
        fi
    done
fi
if [ -z "$python_command" ]; then
    echo "Sidee needs Python 3.9 or newer. Install Python 3, then run this launcher again." >&2
    exit 1
fi

venv="$root/.runtime/venv"
if [ ! -x "$venv/bin/python" ]; then
    echo "First launch: preparing the local Python environment..."
    if ! "$python_command" -m venv "$venv"; then
        echo "Python venv is unavailable. On Debian/Ubuntu install python3-venv; on macOS install Python 3 from python.org or Homebrew." >&2
        exit 1
    fi
fi

if ! "$venv/bin/python" -c "import paho.mqtt.client" >/dev/null 2>&1; then
    echo "Preparing the TV connection library..."
    if ! "$venv/bin/python" -m pip install --disable-pip-version-check -r "$root/requirements.txt"; then
        echo "Could not install the TV connection library. Check your Internet connection and retry." >&2
        exit 1
    fi
fi

exec "$venv/bin/python" "$root/sidee.py" "$@"
