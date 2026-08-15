#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p backups
stamp=$(date +%Y%m%d-%H%M%S)
out="backups/lipass-${stamp}.sql.gz"

echo "==> 备份 PostgreSQL 到 $out"
docker compose --profile bundle exec -T postgres \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' | gzip > "$out"
echo "==> 备份完成：$out"
