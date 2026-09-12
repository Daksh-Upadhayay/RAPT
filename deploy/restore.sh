#!/usr/bin/env bash
# Restore a backup over the current database. DESTRUCTIVE: current data is replaced.
#   deploy/restore.sh deploy/backups/rapt-2026-09-12-0300.dump
set -euo pipefail
cd "$(dirname "$0")/.."
file="${1:?usage: deploy/restore.sh <backup file>}"
[ -f "$file" ] || { echo "No such file: $file"; exit 1; }
read -r -p "This REPLACES all current data with $file. Type 'restore' to continue: " answer
[ "$answer" = "restore" ] || { echo "Cancelled."; exit 1; }

compose="docker compose -f deploy/docker-compose.yml --env-file deploy/.env"
$compose stop api
$compose exec -T backup pg_restore --clean --if-exists --no-owner --dbname=rapt < "$file"
$compose up -d migrate api   # re-grants the API role and restarts
echo "Restored $file"
