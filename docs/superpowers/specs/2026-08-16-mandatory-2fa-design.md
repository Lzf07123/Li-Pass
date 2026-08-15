# 强制二次验证（2FA）与默认邮箱验证码设计

> 日期：2026-08-16 ｜ 状态：设计稿 ｜ 范围：后端 + 前端 + 数据迁移

## 1. 目标

1. **强制开启 2FA**：账号必须至少启用一种二次验证方案（邮箱验证码或 TOTP 认证器）。
2. **默认第一方案**：注册时验证邮箱后，系统直接启用邮箱验证码 2FA，无需用户手动开启。
3. **不可清空**：关闭 2FA 时若只剩最后一种方案，拒绝关闭；管理员重置 2FA 时恢复默认邮箱方案而非清零。
4. 已存在账号平滑迁移到强制 2FA（数据迁移 + 登录兜底双保险）。

## 2. 现状与约束

现状（相关代码）：

- 注册 → `POST /auth/email/verify` 只写 `email_verified_at`，不启用 2FA；
- 邀请注册（`/auth/invite/register`）与管理员代建（`/admin/users`）直接写入已验证邮箱，同样不启用 2FA；
- 登录：有任一 2FA 方案才进入挑战，否则密码后直接发会话（1FA）；
- `POST /me/2fa/email/disable` 与 `/me/2fa/totp/disable` 允许把两种方案全部关掉；
- 管理端 `POST /admin/users/{id}/reset-2fa` 把 TOTP 与邮箱 2FA 全部清空；
- 邮箱验证码登录闭环（`/2fa/send`、`/2fa/verify`、恢复码）已完整实现，无需新端点。

约束：安全产品，不得降低认证强度；数据库变更必须写 Alembic 迁移并在真实 PostgreSQL 验证往返；前端生产 CSP `style-src 'self'`。

## 3. 方案与取舍

### 3.1 自动启用邮箱 2FA（第一方案）

在四个位置把「已验证邮箱」与「邮箱 2FA 开启」绑定：

| 路径 | 改动 |
| --- | --- |
| `POST /auth/email/verify` 成功 | `email_otp_enabled = True`，审计 detail 记录 `2fa_email_auto_enabled` |
| 邀请注册 | 创建用户时 `email_otp_enabled = True` |
| 管理员代建 | 创建用户时 `email_otp_enabled = True` |
| 登录兜底 | 已验证邮箱且无 TOTP 且邮箱 2FA 关闭 → 自动开启并记审计，再进入 2FA 挑战 |

登录兜底是防御纵深：即使历史数据/代码路径留下「已验证但无 2FA」的用户，首次登录也会被强制纳入 2FA。

未验证邮箱的用户仍可 1FA 登录（无法接收验证码）；一旦验证邮箱即强制 2FA。

### 3.2 至少保留一种方案（不可清空）

- 关闭邮箱 2FA：`totp_secret_encrypted is None` → `400「至少保留一种二次验证方式，请先开启 TOTP 认证器」`；
- 关闭 TOTP：`email_otp_enabled is False` → 同上（文案通用）；
- 先完成 step-up 复核（现有窗口逻辑不变），再做不变式校验。

### 3.3 管理员重置 2FA 恢复默认方案

`reset-2fa` 语义从「清空全部」改为「恢复默认」：

- 清 TOTP 与全部恢复码；
- `email_otp_enabled = True`（默认第一方案，绑定已验证邮箱）；
- 依旧吊销该用户全部会话。

理由：重置的目的是移除攻击者配置的 2FA，而不是让账号退回 1FA；邮箱验证码是绑定已验证邮箱的基线方案。

### 3.4 历史数据迁移

新 Alembic 迁移（数据迁移）：

```sql
UPDATE users SET email_otp_enabled = true
WHERE email_verified_at IS NOT NULL
  AND email_otp_enabled = false
  AND totp_secret_encrypted IS NULL;
```

- downgrade 为 no-op：无法恢复「用户此前是否手动关闭过邮箱 2FA」的历史意图，回滚方向不做有损猜测，文档注明。
- 迁移之后用户登录立即进入邮箱 2FA 流程。

### 3.5 取舍记录

- **不做「强制 2FA 开关」站点设置**：需求是产品级强制行为；回滚路径 = 回退代码 + 后续迁移显式关回。若未来需要灰度，再按 `PUBLIC_REGISTRATION_ENABLED` 模式加 site_setting。
- **邮箱验证码作为默认方案**而非 TOTP：邮箱在注册阶段已验证，零额外配置即可获得第二因素；TOTP 作为可选的更强方案，符合「任选一项」。
- **管理员代建也默认启用**：代建账号视为已验证邮箱，必须同样满足「至少一种 2FA」，否则强制 2FA 被管理员通道绕过。

## 4. 数据模型 / 接口变更

- 无 schema 结构变更（`email_otp_enabled` 列已存在）；仅数据迁移。
- 接口语义变更（无新增端点）：
  - `POST /me/2fa/email/disable`、`POST /me/2fa/totp/disable`：最后一种方案 → 400；
  - `POST /admin/users/{id}/reset-2fa`：重置后邮箱 2FA 开启、TOTP/恢复码清空。

## 5. 安全影响

- **增强**：所有已验证邮箱用户登录强制二次验证；管理端不再能无意中把用户清成 1FA。
- **权衡**：邮箱验证码强度低于 TOTP，且依赖邮箱本身安全；已明确为默认基线，TOTP 作为升级项。
- **不变式**：登录失败/2FA 验证限流、恢复码、审计（`2fa_email_auto_enabled`、既有 `email_verify`/`login_step1`）保持或增强。

## 6. UI 设计

遵循 [MASTER.md](../../../design-system/lipass/MASTER.md) / [BRAND.md](../../../design-system/lipass/BRAND.md)，安全提示「清晰可行动、不唬人」：

1. 用户中心「安全设置」：
   - 邮箱二次验证开启时文案「已开启（默认方案）」；当 TOTP 未开启时「关闭」按钮禁用，旁注「至少保留一种二次验证方式，请先开启 TOTP 认证器」；
   - TOTP 开启时「关闭」按钮在邮箱 2FA 关闭时禁用，同理提示。
2. 验证邮箱页：验证成功后提示追加「已默认开启邮箱二次验证，登录时需要输入邮箱验证码」。
3. 登录页/2FA 挑战页无需改动（已有闭环）。

## 7. 验收标准

- 注册并验证邮箱后 `email_otp_enabled=True`；随后登录返回 `requires_2fa`，完成邮箱验证码后建立会话；
- 邀请注册、管理员代建的账号同样默认启用邮箱 2FA；
- 历史用户：数据迁移后在真实 PostgreSQL 上 `email_otp_enabled=True`；即使迁移未覆盖，登录兜底也会自动开启并进入 2FA；
- 关闭最后一种 2FA 返回 400；TOTP+邮箱共存时各自可正常关闭；
- 管理端 reset-2fa 后邮箱 2FA 开启、TOTP 与恢复码清空、会话全部吊销；
- 未验证邮箱用户仍可 1FA 登录；
- 迁移在真实 PostgreSQL 上 upgrade/downgrade/upgrade 往返成功；
- 后端全量、前端 `tsc/lint/test/build` 全绿。

## 8. 风险与回滚

- 上线后所有已验证用户登录多一步邮箱验证码；若邮箱不可达会被锁在门外，需保留管理端 reset-2fa（恢复默认邮箱方案并不能绕过邮箱不可达，管理员需先确认邮箱可用，或通过 TOTP 恢复码）。
- 回滚：回退代码 + 新迁移把 `email_otp_enabled` 按需关回（downgrade 为 no-op，见 3.4）。
