#!/usr/bin/env bash
#
# Li&Pass 生产级热更新（零停机更新）脚本。
#
# 前置条件：栈必须用热更新覆盖文件启动：
#   docker compose -f docker-compose.yaml -f docker-compose.hot.yaml --profile bundle up -d --build
#
# 用法：
#   scripts/hot_update.sh frontend                     # 自动构建 dist 并热换装 + nginx reload
#   scripts/hot_update.sh frontend --skip-build        # 复用已有 dist，跳过自动构建
#   scripts/hot_update.sh backend                      # 后端代码零停机回收（可选迁移）
#   scripts/hot_update.sh backend --skip-migrations
#   scripts/hot_update.sh gateway                      # 网关配置重新 envsubst + reload
#   scripts/hot_update.sh all                          # gateway → frontend → backend
#   scripts/hot_update.sh --rollback <时间戳目录名>     # 用 deploy-backups/<ts> 回滚
#   scripts/hot_update.sh status                       # 只读状态检查
#   任意子命令可加 --dry-run：只打印将执行的命令，不做任何写操作
#
# 注意：
#   - 依赖/Dockerfile/入口命令/环境变量/compose 拓扑变更不属于热更新范围，需 up -d --build；
#   - 数据库迁移不会被 --rollback 自动 downgrade，破坏性迁移请按 expand/contract 顺序执行。
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_ROOT="${HOT_UPDATE_BACKUP_DIR:-$ROOT_DIR/deploy-backups}"
LOCK_DIR="${TMPDIR:-/tmp}/lipass-hot-update.lock"

COMPOSE_FILES=(-f "$ROOT_DIR/docker-compose.yaml" -f "$ROOT_DIR/docker-compose.hot.yaml")

DRY_RUN=0
SKIP_MIGRATIONS=0
SKIP_BUILD=0
ROLLBACK_TS=""
SUBCOMMAND=""
FRONTEND_BUILD_IMAGE="${FRONTEND_BUILD_IMAGE:-node:22-alpine}"
FRONTEND_DEPS_VOLUME="${FRONTEND_DEPS_VOLUME:-lipass-frontend-deps}"

CLEANUP=()
cleanup() {
  local path
  for path in "${CLEANUP[@]:-}"; do
    [[ -n "$path" ]] && rm -rf "$path"
  done
}
trap cleanup EXIT

log()  { printf '%s\n' "$*"; }
info() { printf '[hot_update] %s\n' "$*"; }
warn() { printf '[hot_update] WARN: %s\n' "$*" >&2; }
die()  { printf '[hot_update] ERROR: %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'EOF'
用法:
  scripts/hot_update.sh frontend                     # 自动构建 dist 并热换装 + nginx reload
  scripts/hot_update.sh frontend --skip-build        # 复用已有 dist，跳过自动构建
  scripts/hot_update.sh backend                      # 后端代码零停机回收（可选迁移）
  scripts/hot_update.sh backend --skip-migrations
  scripts/hot_update.sh gateway                      # 网关配置重新 envsubst + reload
  scripts/hot_update.sh all                          # gateway → frontend → backend
  scripts/hot_update.sh --rollback <时间戳目录名>     # 用 deploy-backups/<ts> 回滚
  scripts/hot_update.sh status                       # 只读状态检查
  任意子命令可加 --dry-run：只打印将执行的命令，不做任何写操作
EOF
}

compose() { docker compose "${COMPOSE_FILES[@]}" "$@"; }

mutate() {
  if [[ $DRY_RUN -eq 1 ]]; then
    info "dry-run 将执行: $*"
    return 0
  fi
  "$@"
}

service_container() {
  local service="$1"
  local cid
  cid="$(compose ps -q "$service" 2>/dev/null || true)"
  [[ -n "$cid" ]] || die "服务 $service 未运行：请先以热更新形态启动（见脚本头部注释）"
  printf '%s' "$cid"
}

container_mounts() {
  local cid="$1"
  docker inspect -f '{{range .Mounts}}{{.Destination}} {{end}}' "$cid" 2>/dev/null || true
}

wait_healthy() {
  local service="$1"
  local timeout="${2:-120}"
  local cid elapsed status
  cid="$(service_container "$service")"
  elapsed=0
  while [[ $elapsed -lt $timeout ]]; do
    status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$cid" 2>/dev/null || true)"
    [[ "$status" == "healthy" ]] && { info "$service 已 healthy（${elapsed}s）"; return 0; }
    sleep 2
    elapsed=$((elapsed + 2))
  done
  die "$service 在 ${timeout}s 内未恢复 healthy（当前: ${status:-unknown}）"
}

wait_sighup_log() {
  local i
  for i in $(seq 1 15); do
    if compose logs --tail 100 backend 2>/dev/null | grep -q "Received SIGHUP"; then
      info "已确认 uvicorn 收到 SIGHUP 并逐个 worker 回收"
      return 0
    fi
    sleep 1
  done
  warn "未在最近日志中确认 SIGHUP，请人工核对（健康检查已通过）"
}

ensure_hot_mode() {
  local backend_cid frontend_cid
  backend_cid="$(service_container backend)"
  frontend_cid="$(service_container frontend)"
  if [[ "$(container_mounts "$backend_cid")" != *"/app/app "* ]]; then
    die "backend 未挂载 backend-code:/app/app：当前栈不是热更新形态，请用 docker-compose.hot.yaml 启动"
  fi
  if [[ "$(container_mounts "$frontend_cid")" != *"/usr/share/nginx/html "* ]]; then
    die "frontend 未挂载 frontend-web:/usr/share/nginx/html：当前栈不是热更新形态"
  fi
}

file_sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

manifest_dir() {
  local dir="$1"
  local manifest="$dir.sha256"
  : >"$manifest"
  while IFS= read -r -d '' file; do
    local rel="${file#"$dir"/}"
    printf '%s  %s\n' "$(file_sha256 "$file")" "$rel" >>"$manifest"
  done < <(find "$dir" -type f -print0)
  info "已生成 SHA256 清单: ${manifest}（$(wc -l <"$manifest" | tr -d ' ') 个文件）"
}

snapshot() {
  local service="$1" container_path="$2" label="$3"
  local cid
  cid="$(service_container "$service")"
  if [[ $DRY_RUN -eq 1 ]]; then
    info "dry-run 将快照: $service:$container_path -> $BACKUP_ROOT/$TS/$label"
    return 0
  fi
  mkdir -p "$BACKUP_ROOT/$TS"
  docker cp "$cid:$container_path" "$BACKUP_ROOT/$TS/$label"
  manifest_dir "$BACKUP_ROOT/$TS/$label"
}

ensure_backend_prereqs() {
  local cid="$1"
  local workers store
  workers="$(docker exec "$cid" printenv UVICORN_WORKERS 2>/dev/null || echo 1)"
  if ! [[ "$workers" =~ ^[0-9]+$ ]] || [[ $workers -lt 2 ]]; then
    die "backend UVICORN_WORKERS=$workers < 2：SIGHUP 无法零停机回收，请在 .env 设置 HOT_UVICORN_WORKERS≥2 后重启栈"
  fi
  for store in PENDING_REQUEST_STORE TWOFA_STORE RATE_LIMITER; do
    local value
    value="$(docker exec "$cid" printenv "$store" 2>/dev/null || echo "")"
    [[ "$value" == "redis" ]] || die "$store=${value}（需 redis）：worker 回收会丢失内存态（2FA 挑战/限流/待授权请求）"
  done
}

update_frontend() {
  local cid
  ensure_hot_mode
  cid="$(service_container frontend)"
  if [[ $SKIP_BUILD -eq 1 ]]; then
    [[ -f "$ROOT_DIR/frontend/dist/index.html" ]] ||
      die "缺少 frontend/dist：--skip-build 要求已有构建产物"
  else
    build_frontend
  fi
  info "前端热换装开始（${TS}）"
  snapshot frontend /usr/share/nginx/html frontend-html
  mutate docker cp "$ROOT_DIR/frontend/dist/." "$cid:/usr/share/nginx/html/"
  mutate compose exec -T frontend nginx -s reload
  wait_healthy frontend 60
  if compose exec -T frontend wget -q -O /dev/null http://127.0.0.1:5173/ 2>/dev/null; then
    info "frontend 容器内自检 200"
  else
    warn "frontend 容器内自检失败"
  fi
  info "前端热换装完成"
}

update_backend() {
  local cid
  ensure_hot_mode
  cid="$(service_container backend)"
  [[ -d "$ROOT_DIR/backend/app" ]] || die "缺少 backend/app 目录"
  ensure_backend_prereqs "$cid"
  info "后端零停机更新开始（${TS}）"
  snapshot backend /app/app backend-app
  if [[ $SKIP_MIGRATIONS -eq 1 ]]; then
    warn "已跳过数据库迁移（--skip-migrations）"
  else
    mutate compose exec -T backend alembic upgrade head
  fi
  mutate docker cp "$ROOT_DIR/backend/app/." "$cid:/app/app/"
  mutate compose exec -T --user root backend chown -R 10001:10001 /app/app
  mutate compose kill -s HUP backend
  wait_healthy backend 180
  wait_sighup_log
  info "后端零停机更新完成"
}

update_gateway() {
  local cid
  cid="$(service_container gateway)"
  info "网关配置热更新开始（${TS}）"
  mutate compose exec -T gateway /docker-entrypoint.d/20-envsubst-on-templates.sh
  mutate compose exec -T gateway nginx -s reload
  wait_healthy gateway 60
  info "网关配置热更新完成"
}

rollback() {
  local ts dir
  ts="$1"
  dir="$BACKUP_ROOT/$ts"
  [[ -d "$dir" ]] || die "找不到快照目录: $dir"
  ensure_hot_mode
  if [[ -d "$dir/frontend-html" ]]; then
    local cid
    cid="$(service_container frontend)"
    info "回滚前端产物到 $ts"
    mutate compose exec -T frontend sh -c 'find /usr/share/nginx/html -mindepth 1 -delete'
    mutate docker cp "$dir/frontend-html/." "$cid:/usr/share/nginx/html/"
    mutate compose exec -T frontend nginx -s reload
    wait_healthy frontend 60
  fi
  if [[ -d "$dir/backend-app" ]]; then
    local cid
    cid="$(service_container backend)"
    ensure_backend_prereqs "$cid"
    info "回滚后端代码到 ${ts}（数据库迁移不会自动 downgrade）"
    mutate compose exec -T --user root backend sh -c 'find /app/app -mindepth 1 -delete'
    mutate docker cp "$dir/backend-app/." "$cid:/app/app/"
    mutate compose exec -T --user root backend chown -R 10001:10001 /app/app
    mutate compose kill -s HUP backend
    wait_healthy backend 180
    wait_sighup_log
    warn "如本次回滚前执行过迁移，请人工评估是否需要 alembic downgrade -1"
  fi
  info "回滚完成"
}

status() {
  info "栈状态："
  compose ps 2>/dev/null || true
  local cid
  cid="$(service_container backend)"
  info "backend mounts: $(container_mounts "$cid")"
  info "backend UVICORN_WORKERS=$(docker exec "$cid" printenv UVICORN_WORKERS 2>/dev/null || echo 1)"
  info "backend stores: PENDING_REQUEST_STORE=$(docker exec "$cid" printenv PENDING_REQUEST_STORE 2>/dev/null || echo '') TWOFA_STORE=$(docker exec "$cid" printenv TWOFA_STORE 2>/dev/null || echo '') RATE_LIMITER=$(docker exec "$cid" printenv RATE_LIMITER 2>/dev/null || echo '')"
  info "备份目录: $BACKUP_ROOT"
  if [[ -d "$BACKUP_ROOT" ]]; then
    ls -1 "$BACKUP_ROOT" 2>/dev/null | tail -5 || true
  fi
}

acquire_lock() {
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    printf '%s\n' $$ >"$LOCK_DIR/pid"
    CLEANUP+=("$LOCK_DIR")
    return 0
  fi
  local pid
  pid="$(cat "$LOCK_DIR/pid" 2>/dev/null || echo "")"
  if [[ -n "$pid" ]] && ! kill -0 "$pid" 2>/dev/null; then
    warn "检测到残留锁（pid=$pid 已不存在），清理后重试"
    rm -rf "$LOCK_DIR"
    mkdir "$LOCK_DIR" && printf '%s\n' $$ >"$LOCK_DIR/pid"
    CLEANUP+=("$LOCK_DIR")
    return 0
  fi
  die "另一热更新正在进行（锁: $LOCK_DIR）"
}

vite_env_file() {
  local env_file line key value
  env_file="$(mktemp "${TMPDIR:-/tmp}/lipass-vite-env.XXXXXX")"
  CLEANUP+=("$env_file")
  if [[ -f "$ROOT_DIR/.env" ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
      line="${line#"${line%%[![:space:]]*}"}"
      [[ "$line" == VITE_*=* ]] || continue
      key="${line%%=*}"
      value="${line#*=}"
      if [[ "$value" == \"*\" ]]; then value="${value#\"}"; value="${value%\"}"; fi
      if [[ "$value" == \'*\' ]]; then value="${value#\'}"; value="${value%\'}"; fi
      printf '%s=%s\n' "$key" "$value" >>"$env_file"
    done <"$ROOT_DIR/.env"
  fi
  printf '%s' "$env_file"
}

build_frontend() {
  local env_file
  env_file="$(vite_env_file)"
  info "前端自动构建开始（镜像 ${FRONTEND_BUILD_IMAGE}，依赖缓存卷 ${FRONTEND_DEPS_VOLUME}）"
  mutate docker run --rm \
    -v "$ROOT_DIR/frontend:/app" \
    -v "$FRONTEND_DEPS_VOLUME:/app/node_modules" \
    --env-file "$env_file" \
    -w /app \
    "$FRONTEND_BUILD_IMAGE" sh -c '
      lock_hash="$(sha256sum package-lock.json | awk "{print \$1}")"
      if [ ! -x node_modules/.bin/vite ] ||
         [ "$(cat node_modules/.lipass-lock-hash 2>/dev/null || true)" != "$lock_hash" ]; then
        npm ci --no-audit --no-fund
        echo "$lock_hash" > node_modules/.lipass-lock-hash
      fi
      test -f src/lib/brand.ts || cp src/lib/brand.example.ts src/lib/brand.ts
      npm run build'
  [[ -f "$ROOT_DIR/frontend/dist/index.html" ]] || die "前端构建完成但缺少 dist/index.html"
  info "前端自动构建完成"
}

TS="$(date +%Y%m%d-%H%M%S)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --skip-migrations) SKIP_MIGRATIONS=1; shift ;;
    --skip-build) SKIP_BUILD=1; shift ;;
    --rollback)
      ROLLBACK_TS="${2:-}"
      [[ -n "$ROLLBACK_TS" ]] || die "--rollback 需要时间戳目录名参数"
      shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *)
      [[ -n "$SUBCOMMAND" ]] && die "未知参数: $1（用法见 --help）"
      SUBCOMMAND="$1"
      shift ;;
  esac
done

case "$SUBCOMMAND" in
  frontend|backend|gateway|status) ;;
  all) ;;
  "")
    if [[ -n "$ROLLBACK_TS" ]]; then
      SUBCOMMAND="__rollback__"
    else
      usage
      die "缺少子命令（frontend|backend|gateway|all|status|--rollback <ts>）"
    fi
    ;;
  *) die "未知子命令: ${SUBCOMMAND}（见 --help）" ;;
esac

if [[ $SUBCOMMAND != "status" && $DRY_RUN -eq 0 ]]; then
  acquire_lock
fi

if [[ $DRY_RUN -eq 0 &&
      ($SUBCOMMAND == "frontend" || $SUBCOMMAND == "backend" ||
       $SUBCOMMAND == "gateway" || $SUBCOMMAND == "all") ]]; then
  mkdir -p "$BACKUP_ROOT/$TS"
  exec > >(tee -a "$BACKUP_ROOT/$TS/hot_update.log") 2>&1
fi

case "$SUBCOMMAND" in
  frontend) update_frontend ;;
  backend) update_backend ;;
  gateway) update_gateway ;;
  all)
    update_gateway
    update_frontend
    update_backend
    ;;
  status) status ;;
  __rollback__) rollback "$ROLLBACK_TS" ;;
esac

info "完成"
