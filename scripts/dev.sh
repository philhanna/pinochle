#!/usr/bin/env bash
# Run the server for development, on localhost only.
#
# Fixed admin token, so the console and scripts/seed.py need no copying and
# pasting between restarts. Never use this for anything reachable from
# outside the machine.
set -euo pipefail

cd "$(dirname "$0")/.."

export PINOCHLE_ADMIN_TOKEN="${PINOCHLE_ADMIN_TOKEN:-dev}"
export PINOCHLE_PUBLIC_BASE_URL="${PINOCHLE_PUBLIC_BASE_URL:-http://localhost:8000}"
export PINOCHLE_COMPUTER_DELAY_SECONDS="${PINOCHLE_COMPUTER_DELAY_SECONDS:-1.0}"
export PINOCHLE_TRICK_CLEAR_SECONDS="${PINOCHLE_TRICK_CLEAR_SECONDS:-1.5}"
export PINOCHLE_LOG_LEVEL="${PINOCHLE_LOG_LEVEL:-INFO}"

# The repo's virtualenv if there is one, so `make dev` works without the
# caller having activated it.
uvicorn="uvicorn"
if [[ -x .venv/bin/uvicorn ]]; then
  uvicorn=".venv/bin/uvicorn"
fi

echo "admin token:    ${PINOCHLE_ADMIN_TOKEN}"
# With the token in it, so the console needs nothing typed into it.
echo "console:        ${PINOCHLE_PUBLIC_BASE_URL}/admin?t=${PINOCHLE_ADMIN_TOKEN}"
echo "computer delay: ${PINOCHLE_COMPUTER_DELAY_SECONDS}s   trick clear: ${PINOCHLE_TRICK_CLEAR_SECONDS}s"
echo

# --workers 1 is not a default here either: a second worker would hold a
# second, empty in-memory game (see docker/Dockerfile).
exec "${uvicorn}" pinochle.web.main:app \
  --reload --reload-dir pinochle \
  --host 127.0.0.1 --port 8000 --workers 1
