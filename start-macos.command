#!/bin/sh
# Double-click this file in Finder to start the Sidee browser dashboard on macOS.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec /bin/sh "$root/start-unix.sh" "$@"
