# 敏感操作 step-up 认证窗口设计（30 分钟免复核）

> 日期：2026-08-16 ｜ 状态：设计稿 ｜ 范围：后端 + 前端

## 1. 目标

对敏感操作加强身份认证，并引入「step-up 认证窗口」：

1. 用户在某个会话上成功通过一次密码复核（step-up）后，该会话在接下来 **30 分钟**内执行其他敏感操作时**免再次输入密码**；
2. 窗口过期、会话被吊销/登出/过期后，恢复「每次敏感操作必须重新复核」的现有强度；
3. 把当前散落在各路由里的密码校验统一为**一个带限流、审计、统一错误语义**的 step-up 服务，补齐现有 step-up 校验无独立限流的缺口。

关键安全边界：**登录成功不授予窗口**。窗口只能由「在已登录会话上重新证明密码」获得，避免把「会话被盗后 30 分钟内可静默执行敏感操作」的窗口提前到登录时刻。

## 2. 现状与约束

### 2.1 现状

现有「二次认证」（step-up）是散落的 `verify_password(current_password)` 校验，覆盖端点：

| 域 | 端点 | 现状 |
| --- | --- | --- |
| 用户中心 | `POST /api/v1/me/password` | 必须 `current_password` |
| 用户中心 | `POST /api/v1/me/delete` | 必须 `current_password` |
| 2FA | `/me/2fa/email/enable`、`/email/disable` | 必须 `current_password` |
| 2FA | `/me/2fa/totp/enable`、`/totp/disable` | 必须 `current_password` |
| 管理端 | `PATCH /admin/users/batch`（改角色）、`PATCH /admin/users/{id}`（改角色） | 角色变更时要求 `current_password` |
| 管理端 | `/admin/users/{id}/reset-password`、`/reset-2fa` | 必须 `current_password` |
| 管理端 | `/admin/users/batch/delete`、`/admin/users/{id}/delete` | 必须 `current_password` |
| 管理端 | `DELETE /admin/clients/{id}`、`POST /admin/clients/{id}/reset-secret` | 必须 `current_password` |

问题：

- 每次敏感操作都要重复输入密码，体验差；也没有统一的复核入口。
- 校验逻辑重复 10+ 处，错误码不统一（缺密码时 422 或 400、错密码 400）。
- step-up 密码校验**没有独立限流**：持有会话的攻击者可对账户密码做分布式爆破（登录限流只覆盖 `/login`）。
- 缺少「复核成功/失败/被拒」的专门审计动作，难以区分正常操作与疑似会话窃取。

### 2.2 约束

- 会话是服务端落库的不透明令牌（`sessions.token_hash`），字段变更需要 Alembic 迁移。
- 测试夹具用 SQLite 内存库，时区/DDL 语义与 PostgreSQL 有差异；新时间戳列必须 `DateTime(timezone=True)`，并做真实 PostgreSQL 往返验证。
- 安全产品：任何改动不得降低认证强度；窗口是「便利」而不是「放松」，必须保持限流与审计覆盖。
- 前端 CSP 生产环境 `style-src 'self'`，动效尊重 `prefers-reduced-motion`。

## 3. 方案与取舍

### 3.1 窗口存储：`sessions.stepup_at`（按会话）

在 `sessions` 表新增可空时间戳 `stepup_at`（UTC，`DateTime(timezone=True)`）。

- **按会话**而非按用户：设备 A 复核成功后，设备 B 的会话不豁免。会话吊销/过期/删除（含账号删除级联、管理员强制下线）时窗口随会话消失，无需额外清理。
- **固定窗口**而非滑动窗口：自复核时刻起 30 分钟，不做「每次操作顺延」。固定窗口更可预测、不会因持续活跃变成无限期豁免。
- **只存时间戳**：不存密码或哈希，数据最小化。

备选：Redis 键（缓存可能被清空、多 worker 下另一套过期语义）、独立 StepUp 表（增加级联清理复杂度）。会话列最贴合现有生命周期。

### 3.2 授权判定：统一服务 `app/services/stepup.py`

```text
authorize_stepup(request, db, user, session, password)
  ├─ password 非空：
  │    ├─ 限流（stepup:{email}:{ip} 与 stepup_email:{email}）超限 → 429（记审计一次）
  │    ├─ verify_password 失败 → 审计 stepup_failed → 400「当前密码错误」
  │    └─ 成功 → 清零限流、写 stepup_at=now、审计 stepup_verify_success
  └─ password 为空：
       ├─ now - stepup_at ≤ 30min → 放行
       └─ 否则 → 审计 stepup_required → 403「需要重新验证密码」
```

所有敏感端点都改为「`current_password` 可选 + 调用该服务」：

- 传密码：校验成功即**同时开窗**（用户刚证明过自己），旧客户端行为不变；
- 不传密码：窗口内放行，窗口外 403「需要重新验证密码」；
- 错密码仍 400「当前密码错误」，与前端现有内联错误处理兼容。

### 3.3 显式复核入口

新增两个端点（登录态可用，未登录 401）：

- `GET /api/v1/me/step-up`：返回 `{active, window_minutes, expires_in_seconds}`，供前端判断是否需要弹密码框；
- `POST /api/v1/me/step-up`：`{password}`，成功即开窗并返回同结构状态。

显式入口支持「先复核、再连做多个敏感操作」的流程；隐式开窗（敏感操作自带密码）则保证旧客户端与新客户端混跑时不丢体验。

### 3.4 取舍记录

- **登录不授窗**（3.1 之外最重要的取舍）：看似少了便利，但 step-up 的全部价值在于「会话与密码分离」；登录即授窗等于把复核提前，反而降低强度。放弃。
- **统一覆盖改密/注销等高危操作**：与「可免敏感操作再次二次认证」的需求一致；风险由「按会话 + 30 分钟 + 登录不授窗 + 限流审计」对冲。若部署方想更保守，可把 `STEPUP_WINDOW_MINUTES` 调小，或设 `0` 完全关闭窗口（回到每操作必验）。
- **限流按 email+IP 与全局 email 双层**：镜像登录的防爆破设计，防持有会话的分布式爆破；独立 `stepup` scope，不占用/不被登录限流配额干扰。
- **403 而非 400/422 表达「需要复核」**：语义更准确（资源可达但当前认证级别不足）；旧前端从不省略密码，不受影响。

## 4. 接口与数据模型变更

### 4.1 数据模型

`Session` 新增：

```python
stepup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

Alembic 迁移（revision 链自 `7f2a9d3c8e1b`）：`add_column`（upgrade）/ `drop_column`（downgrade）。

### 4.2 配置（`Settings` + `.env.example`）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `STEPUP_WINDOW_MINUTES` | `30` | 窗口时长；`0` = 关闭窗口（每操作必验） |
| `STEPUP_RATE_LIMIT` / `STEPUP_RATE_WINDOW_SECONDS` | `5` / `900` | 按 email+IP 的复核失败限流 |
| `STEPUP_EMAIL_RATE_LIMIT` / `STEPUP_EMAIL_RATE_WINDOW_SECONDS` | `10` / `900` | 全局按 email 复核失败限流 |

校验器：窗口 ≥0；各 limit 与 window ≥1。

### 4.3 Schema

以下 `current_password` 由必填改为可选（缺省 `None`，非空时 min_length=1）：

- `schemas/auth.py`：`PasswordChange`、`PasswordConfirm`、`TwoFaTotpEnable`；
- `routes/admin_users.py`：`AdminResetPassword`、`AdminDeleteUser`、`AdminBatchDeleteUser`（`AdminUserUpdate`/`AdminBatchUserUpdate` 本就可选）；
- 新增 `StepUpVerifyRequest{password}`。

### 4.4 错误语义（行为变更）

| 情形 | 旧 | 新 |
| --- | --- | --- |
| 缺密码且无窗口 | 422 或 400 | **403「需要重新验证密码」** |
| 密码错误 | 400「当前密码错误」 | 400「当前密码错误」（不变） |
| 窗口内缺密码 | 不可能 | 放行 |

## 5. 安全影响

**增强项**

- 复核动作统一限流 + 审计（`stepup_verify_success` / `stepup_failed` / `stepup_required`，category=`security`），疑似会话窃取的免密尝试可被追踪。
- 错误语义统一，前端能区分「密码错」与「需要复核」。

**风险与缓解**

- 会话窃取者若拿到「窗口内的会话」，可在窗口剩余时间内执行敏感操作。缓解：窗口仅 30 分钟、按会话隔离、登录不授窗、会话吊销（改密/强制下线/注销）立即失效。
- 复核爆破被限流挡住；`STEPUP_EMAIL_RATE_LIMIT` 存在与登录一致的「短时账号锁定」权衡，需在部署文档说明。

**不变式**

- 改密仍吊销其它会话；管理员重置密码/2FA 仍吊销目标用户全部会话（窗口随之失效）。
- 会话撤销、`revoke-all`、账号删除级联行为不变。

## 6. UI 设计

遵循 [MASTER.md](../../../design-system/lipass/MASTER.md) 与 [BRAND.md](../../../design-system/lipass/BRAND.md)：文案「信任但不唬人」，状态提示用 `.notice-*`/徽章语言，密码框复用 `PasswordInput`，危险操作沿用现有 `ConfirmDialog`/`Modal`。

1. 共享 Hook `useStepUp`：内存缓存状态 30 秒，提供 `refresh()` 与 `verify(password)`。
2. 各敏感弹窗/表单打开时 `refresh()`：
   - 窗口内：显示提示条「30 分钟内已通过身份复核，无需再次输入密码」，密码框变可选（不传 `current_password`）；
   - 窗口外：密码框必填，提交携带密码（后端隐式开窗）。
3. 提交收到 403「需要重新验证密码」：就地转为必填并提示「复核已过期，请重新输入当前密码」，用户重输后重试。
4. 涉及页面：用户中心（改密/2FA 开关/注销）、管理端用户（重置密码/重置 2FA/删除/批量删除）、管理端应用（删除/重置密钥）。

## 7. 验收标准

后端：

- 未复核时敏感操作缺密码返回 403 且文案为「需要重新验证密码」；密码错仍 400；
- `POST /api/v1/me/step-up` 成功开窗，`GET /api/v1/me/step-up` 返回 active 与剩余秒数；
- 开窗后各敏感端点免密码成功；把 `stepup_at` 前移 >30 分钟后免密码被拒；
- 会话隔离：第二个会话不共享第一个会话的窗口；登录新会话不自动开窗；
- 窗口随会话吊销失效；改密后其它会话吊销、当前会话窗口刷新；
- 连续错密码触发 429 与 `stepup_failed` 审计；`stepup_verify_success`/`stepup_required` 审计落库；
- Alembic upgrade/downgrade 在真实 PostgreSQL 往返成功。

前端：

- `npx tsc -b && npm run lint && npm test && npm run build` 全绿；新增 hook/页面交互测试覆盖「窗口内免密、窗口外必填、403 转必填」。

## 8. 风险与回滚

- 迁移为可空加列，无数据回填；downgrade 直接删列。线上先升级、后发布前端，旧前端始终带密码，行为兼容。
- 若窗口造成安全事故，运维可设 `STEPUP_WINDOW_MINUTES=0` 立即回到每操作必验，无需发版。
