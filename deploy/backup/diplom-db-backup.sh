#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${ENV_FILE:-/home/oldskull/apps/Diplomnaya-rabota/.env}"
BACKUP_DIR="${BACKUP_DIR:-/home/oldskull/backups/diplom}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

if [[ ! -r "$ENV_FILE" ]]; then
  echo "Cannot read env file: $ENV_FILE" >&2
  exit 1
fi

DATABASE_URL="$(sed -n 's/^DATABASE_URL=//p' "$ENV_FILE" | head -n 1)"

if [[ -z "$DATABASE_URL" ]]; then
  echo "DATABASE_URL is not set in $ENV_FILE" >&2
  exit 1
fi

umask 077
mkdir -p "$BACKUP_DIR"

timestamp="$(date +%F_%H-%M-%S)"
tmp_file="$BACKUP_DIR/.diplom_${timestamp}.sql.gz.tmp"
backup_file="$BACKUP_DIR/diplom_${timestamp}.sql.gz"

pg_dump --no-owner --no-privileges "$DATABASE_URL" | gzip -9 > "$tmp_file"
mv "$tmp_file" "$backup_file"

find "$BACKUP_DIR" -type f -name 'diplom_*.sql.gz' -mtime "+$RETENTION_DAYS" -delete

echo "Backup written: $backup_file"
