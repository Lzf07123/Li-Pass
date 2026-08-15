# 可信设备设计：7 天免登录二次验证（仅登录环节）

日期：2026-08-16
状态：已实施

## 1. 目标

用户在登录完成二次验证（2FA）时，可选择「信任此设备」；此后 **7 天内**在该设备上用正确密码登录可跳过登录 2FA。豁免**仅限登录环节**：修改密码、注销账号、管理端操作、2FA 开关等敏感操作仍走原有 step-up/复核，不受可信设备影响。

## 2. 现状与约束

- 强制 2FA 已落地：已验证邮箱账号登录必须完成 2FA（邮箱验证码/TOTP/恢复码），见 `docs/superpowers/specs/2026-08-16-mandatory-2fa-design.md`。
- 登录挑战在 `POST /api/v1/auth/login` 创建（`create_challenge`），`POST /api/v1/auth/2fa/verify` 成功后 `_create_session_and_cookie` 建立会话。
- 敏感操作已有独立 step-up 体系（`app/services/stepup.py`），成功即重置限流、与登录 2FA 解耦——本特性不得触碰该体系。
- 会话（`sessions`）与设备信任是两层概念：会话有「记住我」30 天选项；可信设备是跨会话的登录 2FA 豁免。
- 安全产品约束：豁免 2FA 必须以显式用户授权为前提、可撤销、可审计，并限制在最短必要范围。

## 3. 方案

### 3.1 语义边界

- **授予**：仅在 `2fa/verify` 成功且请求带 `trust_device=true` 时授予；前端以「信任此设备：7 天内登录免二次验证」复选框（默认不勾选）呈现。
- **豁免**：仅 `login` 中「该账号需要 2FA」的分支检查可信设备；校验通过直接建会话，返回正常用户对象，不进入挑战。**密码仍必须正确**（豁免只替代 2FA，不替代密码）。
- **不复用**：可信设备不参与任何 step-up/敏感操作复核；`authorize_stepup`/`authorize_critical_operation` 不改动。
- **有效期**：固定 7 天（自授予起），重新勾选信任后重新计时；不做滑动续期。
- **撤销**：修改密码、退出所有设备、账号删除/停用、用户中心手动撤销单台设备。

### 3.2 凭证与存储

- Cookie：`lipass_trusted_device`，值为 256 位随机 token；`HttpOnly`、生产 `Secure`、`SameSite=Lax`、`Path=/`、`Max-Age=7 天`。
- 表 `trusted_devices`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID PK | 设备记录标识 |
| `user_id` | FK users.id CASCADE | 所属用户（索引） |
| `token_hash` | String(64) 唯一索引 | token 的 SHA-256 |
| `device_name` | String(120) | 友好设备名（复用 device_info） |
| `user_agent` | String(300) | 原始 UA |
| `ip` | String(45) | 授予时 IP |
| `created_at` | DateTime(tz) | 授予时间 |
| `expires_at` | DateTime(tz) | 7 天后 |
| `last_used_at` | DateTime(tz) 可空 | 最近一次豁免登录 |
| `revoked_at` | DateTime(tz) 可空 | 撤销时间 |

- 服务 `app/services/trusted_devices.py`：`grant(db,user,request)`、`find_valid(db,user_id,token)`（校验未撤销未过期并刷新 `last_used_at`）、`revoke_one/revoke_all`。

### 3.3 API 变更

| 接口 | 变更 |
| --- | --- |
| `POST /api/v1/auth/2fa/verify` | payload 新增可选 `trust_device: bool=false`；成功后授予并种 Cookie |
| `POST /api/v1/auth/login` | 需要 2FA 前先校验可信 Cookie；命中则跳过挑战直接建会话 |
| `GET /api/v1/me/trusted-devices` | 新增：列出本用户未撤销设备（含 `current` 标记） |
| `DELETE /api/v1/me/trusted-devices/{id}` | 新增：撤销单台；若为当前 Cookie 对应设备则同时清 Cookie |
| `POST /api/v1/sessions/revoke-all` | 一并撤销全部可信设备 |
| `POST /api/v1/me/password` | 修改密码后撤销全部可信设备 |

### 3.4 审计

- `trusted_device_granted`（category=security，detail: device_id、ttl_days）
- `2fa_trusted_skip`（category=security，detail: device_id）
- `trusted_device_revoked`（category=security，detail: device_id、reason）

### 3.5 前端

- LoginPage 2FA 步骤新增复选框（默认不勾选），`2fa/verify` 携带 `trust_device`。
- 用户中心「登录设备」新增「可信设备」卡片：设备名/UA/IP/授权时间/有效期/当前设备标记，逐台撤销；「退出所有设备」提示语注明会同时清除可信设备。
- API client 新增 `trustedDevicesApi`；`TwoFaVerifyRequest` 类型扩展。

## 4. 安全影响与取舍

- **风险**：窃取 `lipass_trusted_device` Cookie 可在 7 天内绕过登录 2FA（仍需密码）。缓解：HttpOnly+Secure+SameSite 防脚本读取与跨站携带；token 随机且仅存哈希；固定 7 天上限；服务端可撤销；每次豁免登录记审计并刷新 last_used_at 便于异常排查。
- **不变式**：强制 2FA 的账号安全基线不变——豁免仅覆盖用户显式授权的设备，密码验证不可绕过，敏感操作复核完全独立。
- **取舍**：不引入设备指纹绑定（指纹可漂移且收益有限）；不做滑动续期（安全优先、语义简单）；不提供管理端批量撤销（保持范围最小，用户侧已可逐台/全量撤销）。

## 5. 配置与文档

- 新增 `TRUSTED_DEVICE_TTL_DAYS=7`（默认 7），`.env.example`、`backend/.env.example`、`docs/deployment.md` 环境变量表同步。
- CHANGELOG「功能」与「行为变更」（登录 2FA 出现「信任此设备」选项，默认不勾选）。

## 6. 验收标准

- 勾选信任完成 2FA 后，7 天内同一浏览器密码登录跳过 2FA；不勾选则每次仍要求 2FA。
- 密码错误时即使带可信 Cookie 也拒绝登录。
- 敏感操作（改密码/注销/管理端）不因可信设备豁免复核。
- 修改密码、退出所有设备、手动撤销后，可信豁免立即失效。
- 后端全量、前端 tsc/lint/test/build 全绿；迁移 upgrade/downgrade 往返通过。
