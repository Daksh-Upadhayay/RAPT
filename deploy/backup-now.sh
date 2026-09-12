#!/usr/bin/env bash
# Take a backup right now (the backup container also makes one every night at 03:00).
set -euo pipefail
cd "$(dirname "$0")/.."
file="deploy/backups/rapt-$(date +%Y-%m-%d-%H%M)-manual.dump"
docker compose -f deploy/docker-compose.yml --env-file deploy/.env exec -T backup \
  sh -c 'pg_dump --format=custom' > "$file"
echo "Backup written: $file ($(du -h "$file" | cut -f1))"
