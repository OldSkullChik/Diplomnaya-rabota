#!/usr/bin/env bash
set -euo pipefail

TARGET_URL="${1:-${DIPLOM_LOAD_URL:-http://127.0.0.1:8000/healthz/}}"
OUT_DIR="${2:-${DIPLOM_LOAD_OUT_DIR:-$HOME/load-tests/diplom}}"
STAGES="${DIPLOM_LOAD_STAGES:-30:1 120:4 300:10 600:20}"
HEALTH_URL="${DIPLOM_HEALTH_URL:-http://127.0.0.1:8000/healthz/}"
FORWARDED_PROTO="${DIPLOM_FORWARDED_PROTO:-https}"
STAMP="$(date +%Y-%m-%d_%H-%M-%S)"
RUN_DIR="$OUT_DIR/$STAMP"

if ! command -v ab >/dev/null 2>&1; then
    echo "apachebench is required. Install it with: sudo apt install -y apache2-utils" >&2
    exit 1
fi

mkdir -p "$RUN_DIR"

{
    echo "target_url=$TARGET_URL"
    echo "health_url=$HEALTH_URL"
    echo "forwarded_proto=$FORWARDED_PROTO"
    echo "stages=$STAGES"
    echo "started_at=$(date -Is)"
    echo
    echo "== system before =="
    uptime || true
    free -h || true
    systemctl is-active diplom-gunicorn 2>/dev/null || true
    systemctl is-active nginx 2>/dev/null || true
    echo
} | tee "$RUN_DIR/summary.txt"

stage_number=0
for stage in $STAGES; do
    requests="${stage%%:*}"
    concurrency="${stage##*:}"
    stage_number=$((stage_number + 1))
    log_file="$RUN_DIR/stage_${stage_number}_n${requests}_c${concurrency}.txt"

    {
        echo
        echo "== stage $stage_number: requests=$requests concurrency=$concurrency =="
        echo "started_at=$(date -Is)"
    } | tee -a "$RUN_DIR/summary.txt"

    ab -H "X-Forwarded-Proto: $FORWARDED_PROTO" -n "$requests" -c "$concurrency" -k "$TARGET_URL" | tee "$log_file"

    {
        grep -E "Complete requests|Failed requests|Non-2xx responses|Requests per second|Time per request|Transfer rate" "$log_file" || true
        echo "health_after_stage=$(curl --silent --show-error --max-time 8 --header "X-Forwarded-Proto: $FORWARDED_PROTO" "$HEALTH_URL" || true)"
        echo "finished_at=$(date -Is)"
    } | tee -a "$RUN_DIR/summary.txt"

    sleep 5
done

{
    echo
    echo "== system after =="
    uptime || true
    free -h || true
    echo "finished_at=$(date -Is)"
    echo "logs=$RUN_DIR"
} | tee -a "$RUN_DIR/summary.txt"
