#!/usr/bin/env bash
# Deploy (or update) RAPT: pull the code, build, migrate, restart. Run from the repo root.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f deploy/.env ] || { echo "deploy/.env is missing: copy deploy/.env.example and fill it in"; exit 1; }
mkdir -p deploy/backups

git pull --ff-only
compose="docker compose -f deploy/docker-compose.yml --env-file deploy/.env"
$compose build
$compose up -d   # migrate runs first, then the API starts
$compose ps
docker image prune -f >/dev/null
echo "Deployed. Health: curl -s https://\$(grep ^RAPT_DOMAIN deploy/.env | cut -d= -f2)/api/health"
