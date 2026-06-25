#!/usr/bin/env bash
set -euo pipefail

URL="${1:-${DIPLOM_HEALTH_URL:-http://127.0.0.1/healthz/}}"

curl --silent --show-error --fail --max-time 8 "$URL" >/dev/null
echo "OK: $URL"
