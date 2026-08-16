#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# 优先使用本机 docker-compose.yaml；未复制示例文件时回退到仓库内的 example。
COMPOSE_FILE="docker-compose.yaml"
if [[ ! -f "$COMPOSE_FILE" ]]; then
  COMPOSE_FILE="docker-compose.example.yaml"
fi

mkdir -p backups
stamp=$(date +%Y%m%d-%H%M%S)
out="backups/lipass-${stamp}.sql.gz"

echo "==> 备份 PostgreSQL 到 $out"
docker compose -f "$COMPOSE_FILE" --profile bundle exec -T postgres \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' | gzip > "$out"
echo "==> 备份完成：$out"
