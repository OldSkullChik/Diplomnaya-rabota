#!/usr/bin/env bash
set -euo pipefail

HEALTH_URL="${DIPLOM_HEALTH_URL:-http://127.0.0.1/healthz/}"

log() {
    printf '[%s] %s\n' "$(date -Is)" "$*"
}

if curl --silent --show-error --fail --max-time 8 "$HEALTH_URL" >/dev/null; then
    log "healthy: $HEALTH_URL"
    exit 0
fi

log "healthcheck failed, trying controlled restart"

if ! systemctl is-active --quiet postgresql; then
    log "postgresql is not active, restarting"
    systemctl restart postgresql
fi

log "restarting diplom-gunicorn"
systemctl restart diplom-gunicorn

if nginx -t; then
    log "reloading nginx"
    systemctl reload nginx
else
    log "nginx config test failed"
    exit 1
fi

sleep 5

curl --silent --show-error --fail --max-time 8 "$HEALTH_URL" >/dev/null
log "recovery check passed"
