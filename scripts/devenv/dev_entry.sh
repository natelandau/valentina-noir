#!/usr/bin/env bash
# Start the API in a local dev stack container.
set -euo pipefail

if [[ "${VAPI_DEV_DEBUGPY:-0}" == "1" ]]; then
    # The reloader restarts the server in a child process, which would drop the debugger session
    exec python -m debugpy --listen 0.0.0.0:5678 -m vapi run
fi

exec app run -r --reload-paths=src/
