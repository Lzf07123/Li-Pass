#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# 优先使用本机 docker-compose.yaml；未复制示例文件时回退到仓库内的 example。
COMPOSE_FILE="docker-compose.yaml"
if [[ ! -f "$COMPOSE_FILE" ]]; then
  COMPOSE_FILE="docker-compose.example.yaml"
fi

if [[ $# -ne 1 ]]; then
  echo "用法: $0 <备份文件.sql.gz>"
  exit 1
fi

file="$1"
if [[ ! -f "$file" ]]; then
  echo "备份文件不存在: $file"
  exit 1
fi

echo "!! 恢复将覆盖当前数据库，此操作不可撤销"
read -r -p "确认继续？输入 yes: " answer
if [[ "$answer" != "yes" ]]; then
  echo "已取消"
  exit 1
fi

echo "==> 从 $file 恢复 PostgreSQL"
gunzip -c "$file" | docker compose -f "$COMPOSE_FILE" --profile bundle exec -T postgres \
  sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
echo "==> 恢复完成"
