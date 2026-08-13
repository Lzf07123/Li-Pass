# 管理后台数据统计设计

- 日期：2026-08-14
- 状态：已批准，实施中
- 范围：管理后台新增「数据统计」标签页，实时聚合展示账号、登录与认证方式等运营指标

## 1. 目标

为管理员提供一屏可读的运营数据：账号总量与构成、最近 N 天的登录/活跃/新增注册趋势、当前在线会话的认证方式分布。数据从现有 `users`、`sessions`、`audit_logs` 表实时聚合，不新增持久化存储与数据库迁移。

## 2. 接口设计

| 方法 | 路径 | 语义 |
| --- | --- | --- |
| `GET` | `/api/v1/admin/stats?days=30` | 返回统计快照；`days` 取值 7–90，默认 30，越界返回 422 |

- 权限：路由级 `get_current_admin`，非管理员 403、未登录 401（有测试）。
- 只读操作不记审计，与现有 GET 类管理接口（会话列表、站点设置读取）口径一致。

响应结构：

```json
{
  "generated_at": "2026-08-14T07:00:00+00:00",
  "timezone": "Asia/Shanghai",
  "days": 30,
  "overview": {
    "total_users": 128,
    "active_users": 126,
    "disabled_users": 2,
    "admins": 3,
    "verified_users": 120,
    "online_sessions": 9,
    "total_logins": 1024
  },
  "daily": [
    {
      "date": "2026-07-16",
      "logins": 12,
      "login_users": 9,
      "registrations": 1
    }
  ],
  "auth_methods": [
    { "method": "password", "count": 7 },
    { "method": "email_otp", "count": 1 },
    { "method": "totp", "count": 1 },
    { "method": "recovery", "count": 0 }
  ]
}
```

`daily` 长度恒等于 `days`，缺失日期补零。

## 3. 数据口径

- 账号总数/启用/禁用/管理员/已验证邮箱：`users` 表现状快照（`status`、`role`、`email_verified_at`）。
- 在线会话：`sessions` 中 `revoked_at IS NULL` 且 `expires_at >= now`。
- 登录事件：`audit_logs` 中 `action IN ('login', '2fa_login')`（成功登录统一口径）；「登录人数」按 `actor_id` 去重，「登录次数」计事件总数。
- 新增注册：`users.created_at` 落入窗口的行数。
- 时间聚合：按 Asia/Shanghai 自然日（与容器 `TZ` 一致）；SQLite 用 `strftime('%Y-%m-%d', created_at, '+8 hours')`，PostgreSQL 用 `date(timezone('Asia/Shanghai', created_at))`，索引过滤窗口后再按日分组。
- 认证方式：在线会话的 `auth_method`，按 `password / email_otp / totp / recovery` 排序并补零；未知类型追加到末尾，前端显示原始值兜底。
- 审计保留期 180 天，`days` 上限 90 天不会触达清理边界。

## 4. 前端交互

- 「数据统计」标签位于「系统信息」之后，路由 `/admin/stats`，与其它标签一致的子路由机制。
- 概览卡 6 张：账号总数（附启用/禁用拆分）、管理员、已验证邮箱、在线会话、累计登录次数。
- 折线图 3 系列：登录次数、登录人数、新增注册；带图例、指针悬停提示，以及仅供屏幕阅读器读取的数据表（图表本体 `role="img"` + `aria-label`）。
- 时间段切换：近 7 天 / 30 天 / 90 天（默认 30），切换即重新请求；头部另有手动「刷新」按钮。
- 认证方式横向分布条：标签、数量、按最大项归一化的色条。
- 图表为自研 SVG 组件，零新增 npm 依赖；颜色复用 CSS 变量令牌（`--portal-primary/success/warning`），明暗主题自动适配；不播放动画、尊重 `prefers-reduced-motion`。

## 5. 测试

- 后端：未登录 401、非管理员 403、`days=6/91` 返回 422、概览各字段口径、按日聚合与 `actor_id` 去重、缺失日期补零、认证方式分布。
- 前端：面板概览与图表图例渲染、切换时间范围触发对应 `days` 请求、请求失败 Toast、折线图的 `role="img"` 与屏幕阅读器数据表。

## 6. 安全

- 只读接口且仅管理员可访问；响应仅含聚合数量，不含邮箱、昵称等用户明细。
- 查询使用 SQLAlchemy 参数化语句与索引（`audit_logs.created_at`、`action`），窗口过滤后再聚合。
- 前端 React 转义渲染，无注入风险。
