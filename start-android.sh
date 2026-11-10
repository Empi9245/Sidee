#!/bin/sh
# Termux launcher for Android. Install Termux first:
#   pkg update && pkg install python
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$root"

python_command=${PYTHON:-}
if [ -z "$python_command" ]; then
    for candidate in python python3; do
        if command -v "$candidate" >/dev/null 2>&1; then
            python_command=$candidate
            break
        fi
    done
fi
if [ -z "$python_command" ]; then
    echo "Python is not installed. In Termux run: pkg update && pkg install python" >&2
    exit 1
fi

venv="$root/.runtime/termux-venv"
if [ ! -x "$venv/bin/python" ]; then
    echo "First launch: preparing the local Python environment..."
    if ! "$python_command" -m venv "$venv"; then
        echo "Could not create the Termux virtual environment. Run: pkg install python && python -m ensurepip" >&2
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
