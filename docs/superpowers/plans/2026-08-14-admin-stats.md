# 管理后台数据统计 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 管理后台新增「数据统计」标签页：实时聚合账号总量、登录/注册趋势与认证方式分布并可视化。

**Architecture:** 后端新增只读 `GET /api/v1/admin/stats?days=30`，由服务层从 `users`、`sessions`、`audit_logs` 表按 Asia/Shanghai 自然日聚合（SQLite/PostgreSQL 两种日表达式）；前端新增自研 SVG 折线图组件与统计面板，接入现有 `/admin/*` 子路由标签机制。

**Tech Stack:** FastAPI + SQLAlchemy 2.0（后端）；React 19 + TypeScript + Tailwind CSS 4（前端），不新增 npm 依赖。

## Global Constraints

- `days` 取值 7–90，默认 30，越界 422（`Query(30, ge=7, le=90)`）。
- 登录口径：`action IN ('login', '2fa_login')`；「登录人数」按 `actor_id` 去重。
- 在线会话口径：`revoked_at IS NULL AND expires_at >= now`。
- `daily` 数组长度恒等于 `days`，按日期升序、缺失日期补零。
- 时区 Asia/Shanghai（`timezone(timedelta(hours=8))`，无夏令时）。
- 颜色只用 CSS 变量令牌（`--portal-primary/success/warning`），适配明暗主题；不播放图表动画。
- 只读接口不记审计；路由级 `get_current_admin`。

---

## 文件结构

- Create: `backend/app/services/admin_stats.py` — 纯聚合逻辑，无 FastAPI 依赖，可独立测试
- Create: `backend/app/api/routes/admin_stats.py` — 路由 + `days` 参数校验
- Modify: `backend/app/main.py` — 注册 router
- Test: `backend/tests/test_admin_stats.py`
- Modify: `frontend/src/api/types.ts` — `AdminStats*` 类型
- Modify: `frontend/src/api/client.ts` — `adminStatsApi`
- Create: `frontend/src/components/charts/LineChart.tsx` — 多系列 SVG 折线图
- Create: `frontend/src/pages/AdminStatsPanel.tsx` — 统计面板
- Modify: `frontend/src/pages/AdminPage.tsx` — 新增 `stats` 标签
- Test: `frontend/src/__tests__/AdminStatsPanel.test.tsx`、`frontend/src/__tests__/LineChart.test.tsx`
- Modify: `CHANGELOG.md` — 行为变更条目

---

## Task 1: 后端统计服务

**Files:**
- Create: `backend/app/services/admin_stats.py`

**Interfaces:**
- Produces: `collect_admin_stats(db: Session, days: int) -> dict`，返回 `{generated_at, timezone, days, overview, daily, auth_methods}`；`overview` 键为 `total_users / active_users / disabled_users / admins / verified_users / online_sessions / total_logins`；`daily` 元素为 `{date, logins, login_users, registrations}`；`auth_methods` 元素为 `{method, count}`。

- [ ] **Step 1: 写失败测试（Task 3 的用例先行）**

`tests/test_admin_stats.py` 中先建立 `test_collect_admin_stats_daily_bucketing_and_distinct_users`：
造 2 名用户、3 条登录事件（同一用户同日 2 条 + 次日 1 条，用 `datetime.now(timezone.utc) - timedelta(...)` 精确落位），断言 `daily` 补零长度、各日 `logins / login_users / registrations` 值。

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_stats.py -q`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

日表达式（方言分支）：

```python
def _day_expr(db: Session):
    if db.get_bind().dialect.name == "sqlite":
        return func.strftime("%Y-%m-%d", AuditLog.created_at, "+8 hours")
    return func.date(func.timezone("Asia/Shanghai", AuditLog.created_at))
```

登录聚合与注册聚合各一条 SQL（窗口用 `created_at >= start_utc AND created_at < now_utc`，过滤后再 `group_by(day)`），登录同时做 `func.count()` 与 `func.count(func.distinct(AuditLog.actor_id))`；补零字典先生成 `days` 个日期键（`(now.astimezone(TZ) - timedelta(days=days - 1 - i)).date().isoformat()`）。

- [ ] **Step 4: 运行确认通过**（同一命令）
- [ ] **Step 5: 无需单独提交（随功能整体评审）**

## Task 2: 路由与注册

**Files:**
- Create: `backend/app/api/routes/admin_stats.py`
- Modify: `backend/app/main.py`（`include_router` 处追加一行，import 块同构追加）

**Interfaces:**
- Consumes: `collect_admin_stats`（Task 1）
- Produces: `GET /api/v1/admin/stats`，`days: int = Query(30, ge=7, le=90)`，`dependencies=[Depends(get_current_admin)]`

- [ ] **Step 1:** 建立 router（prefix `/api/v1/admin`，tags `["admin-stats"]`），端点直接 `return collect_admin_stats(db, days)`
- [ ] **Step 2:** 在 `main.py` import 并 `include_router`，置于 `admin_system_routes` 之后
- [ ] **Step 3:** `cd backend && .venv/bin/python -m pytest tests/test_admin_system.py -q`（确认既有路由未破坏）

## Task 3: 后端测试

**Files:**
- Create: `backend/tests/test_admin_stats.py`

**Interfaces:**
- Consumes: `GET /api/v1/admin/stats`

- [ ] 401：未登录请求返回 401
- [ ] 403：普通用户登录后请求返回 403
- [ ] 422：`days=6`、`days=91` 返回 422
- [ ] 概览：造 3 用户（2 active / 1 disabled、1 admin、2 verified）+ 1 个未过期在线会话 + 2 条登录事件，断言 `overview` 各键
- [ ] 聚合：断言补零长度、按日计数、`actor_id` 去重、注册数与认证方式分布（含未知 `auth_method` 兜底）

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_stats.py -q` → 全绿。

## Task 4: 前端类型与 API 客户端

**Files:**
- Modify: `frontend/src/api/types.ts`、`frontend/src/api/client.ts`

**Interfaces:**
- Produces: `AdminStatsOverview`、`AdminStatsDailyPoint`、`AdminStatsAuthMethod`、`AdminStats` 接口；`adminStatsApi.get(days = 30)` 返回 `Promise<AdminStats>`，URL 为 `/api/v1/admin/stats?days=${days}`。

- [ ] 类型字段名与后端响应逐字一致（见 Task 1 Produces）
- [ ] `adminStatsApi` 放在 `adminSettingsApi` 之后

## Task 5: 自研 SVG 折线图

**Files:**
- Create: `frontend/src/components/charts/LineChart.tsx`

**Interfaces:**
- Produces: `<LineChart labels={string[]} series={LineSeries[]} formatValue={(n)=>string} height={number} />`；`LineSeries = { name: string; values: number[]; dashed?: boolean; color?: string }`，默认色板 `["var(--portal-primary)", "var(--portal-success)", "var(--portal-warning)"]`。

- [ ] 用 `ResizeObserver` 测容器宽度，按真实像素渲染（文字不随 viewBox 缩放）；`min-w-0` 容器内 `w-full`
- [ ] Y 轴取全系列最大值向上取「漂亮数」，画 4 条网格线；X 轴每 `Math.ceil(n/8)` 个标签（`MM-DD`）
- [ ] `role="img"` + `aria-label` 概述系列；同时渲染 `sr-only` 数据表（每行日期 + 各系列值），保证屏幕阅读器可读
- [ ] 指针移动按最近 X 索引显示绝对定位 tooltip（日期 + 各系列值），`pointer-events` 与移动端触摸可退化为无 tooltip
- [ ] 全零数据时 max 取 1、折线落在基线，不出现除零

- [ ] **Test:** `frontend/src/__tests__/LineChart.test.tsx` — `role="img"`、`aria-label`、sr-only 表内容、图例文本、`formatValue` 生效

## Task 6: 统计面板与标签接入

**Files:**
- Create: `frontend/src/pages/AdminStatsPanel.tsx`
- Modify: `frontend/src/pages/AdminPage.tsx`

**Interfaces:**
- Consumes: `adminStatsApi.get(days)`；`LineChart`（Task 5）
- Produces: `AdminStatsPanel`（无 props）

- [ ] 概览卡 6 张：账号总数（附启用/禁用拆分）、管理员、已验证邮箱、在线会话、累计登录次数（用 `Intl.NumberFormat("zh-CN")`）
- [ ] 折线图 3 系列：登录次数（primary 实线）、登录人数（success 实线）、新增注册（warning 虚线）
- [ ] 时间范围三按钮（近 7/30/90 天，激活 `btn-primary`）+「刷新」按钮（`useAsyncAction`）；切换即 `adminStatsApi.get(days)` 重载
- [ ] 认证方式横向分布条（`password/email_otp/totp/recovery` 中文标签，未知原样显示），全零时显示「暂无在线会话」
- [ ] `AdminPage.tsx` 的 `TABS` 在 `system` 后插入 `{ key: "stats", label: "数据统计" }`，并渲染 `<AdminStatsPanel />`

- [ ] **Test:** `AdminStatsPanel.test.tsx` — 概览数值、图例文本、认证方式标签、点击「近 7 天」触发 `days=7` 请求、失败 Toast

## Task 7: 文档与全量验证

**Files:**
- Modify: `CHANGELOG.md`（「行为变更」新增一条）

- [ ] `cd backend && .venv/bin/python -m pytest -q` → 全绿
- [ ] `cd frontend && npx tsc -b && npm run lint && npm test && npm run build` → 全绿

## 自审

1. Spec 覆盖：概览口径、补零、方言日表达式、图表可访问性、时间范围、认证方式分布均有对应任务。
2. 占位符：无 TBD/TODO；关键 SQL、类型与组件接口已给出。
3. 类型一致性：`AdminStats*` 字段与后端 `collect_admin_stats` 返回键逐字一致；`LineSeries` 引用一致。
