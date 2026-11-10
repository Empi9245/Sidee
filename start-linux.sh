#!/bin/sh
# Start the Sidee browser dashboard on Linux.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec /bin/sh "$root/start-unix.sh" "$@"
