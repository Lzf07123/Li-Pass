# 可变邮箱与 openid 统一账号标识设计

- 日期：2026-08-16
- 状态：已实现

## 1. 目标

1. 明确以 OIDC `sub`（用户 UUID，注册后终身不变、不跨账号复用）作为**统一账号标识**，
   对接网站按 `(sub, sid)` 绑定本地账号，不得以邮箱作为主键。
2. 支持用户**更换登录邮箱**：新邮箱经验证码验证 + 当前密码复核后生效；
   邮箱变为可变属性，账号身份（`sub`、会话、授权、封禁 by user_id）不受影响。

## 2. 现状与约束

- `sub` 已是稳定 UUID（`app/security/jwt.py`），`id_token`/`userinfo` 均以 `sub` 为主键语义；
  `access_token.aud` 为 userinfo 端点，与邮箱无关。
- 邮箱当前不可变：无变更接口；`User.email` 唯一约束 + 登录凭据。
- 邮箱被当作“准标识”使用的两处：
  - 网站黑名单 `ClientUserBlock`：`find_block` 同时匹配 `user_id` 与 `email`；
  - 验证码 `Otp.target`（投递地址，本身合理）。
- OTP `purpose` 为 PostgreSQL 原生枚举 `otppurpose`，新增取值必须 `ALTER TYPE ADD VALUE`
  （枚举只增不删，downgrade 为 no-op）。
- 所有会话/授权码/可信设备/审计均绑定 `user_id`，不依赖邮箱。

## 3. 方案与取舍

### 3.1 邮箱变更流程（双步 + 密码复核）

```text
用户中心「更换邮箱」表单
  1) POST /api/v1/me/email/change/request {new_email, current_password}
     - 新邮箱与当前邮箱不同；全库唯一；
     - 密码必须显式提供（step-up 30 分钟窗口不豁免，防会话窃取后改绑邮箱再重置密码接管）；
     - 通过后向「新邮箱」发送 6 位验证码（10 分钟有效，重发作废旧码）；
     - 限流：按新邮箱每小时配额 + 60 秒重发冷却；失败记审计。
  2) POST /api/v1/me/email/change/confirm {new_email, code}
     - 校验 change_email OTP（每码 5 次尝试锁）；
     - 全库唯一性并发兜底（IntegrityError → 409）；
     - 更新 email、审计 email_change、向旧邮箱发“邮箱已变更”提醒（不含新地址）；
     - 保留当前会话、可信设备与全部授权（sub 不变）。
```

取舍：
- 不在 request 阶段改邮箱（必须先证明新邮箱所有权）。
- 向旧邮箱的提醒为 best-effort（邮件不可达不影响变更），防静默改绑。
- 登录凭据随新邮箱切换；2FA 邮箱验证码后续投递到新邮箱。

### 3.2 黑名单语义

邮箱可变更后，**按 email 封禁的用户记录在换邮箱后不再命中**；按 `user_id` 封禁始终命中。
不自动迁移历史 email 封禁（会向封禁方泄露新邮箱）。对接文档明确建议：已注册用户封禁
使用 `user_id`；email 封禁仅用于“预封禁未来注册的邮箱”。

## 4. 接口与数据模型

### 4.1 后端接口（均需登录）

| 方法 | 路径 | 请求体 | 成功 | 错误 |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/me/email/change/request` | `{new_email: EmailStr, current_password: str}` | `{message}` | 400 密码错/新邮箱同旧邮箱；409 邮箱已注册；429 限流 |
| POST | `/api/v1/me/email/change/confirm` | `{new_email: EmailStr, code: str}` | `{message}` | 400 验证码无效/过期/未发起过；409 邮箱已注册 |

### 4.2 数据模型

- `OtpPurpose` 新增 `change_email = "change_email"`；迁移
  `ALTER TYPE otppurpose ADD VALUE 'change_email'`（downgrade no-op）。
- 无新表；审计动作：`email_change_request` / `email_change_failed` / `email_change`。
- 邮件服务新增 `send_email_changed(to)`：通知旧邮箱账号邮箱已被更换。

## 5. 安全影响

- 变更需要「当前密码 + 新邮箱验证码」双因子，且密码不享受 step-up 窗口豁免。
- 新邮箱唯一约束 + 并发兜底；OTP 每码 5 次锁、按新邮箱发送限流。
- `sub` 与全部既有会话/授权绑定不变，接入方无需迁移；旧 `id_token`（最长 5 分钟）中的
  旧邮箱随令牌自然过期。
- 邮箱封禁失效属预期行为，文档同步约束接入方。

## 6. UI 设计

用户中心「基本资料」内新增「更换邮箱」区块（引用 design-system/lipass 令牌）：
当前邮箱展示；新邮箱输入 + 当前密码输入 + 「发送验证码」（60 秒冷却）+ 6 位验证码 +
「确认更换」；错误内联提示；`prefers-reduced-motion` 下无动画。

## 7. 验收标准

- [ ] 后端 pytest：新用例覆盖 request 密码错/限流、confirm 错码/重复邮箱/成功（含审计与旧邮箱通知）红→绿
- [ ] 全量后端 pytest、前端 tsc/lint/test/build 通过
- [ ] 真实栈实测：A→B 邮箱变更后，旧邮箱登录失败、新邮箱登录 + 2FA 成功、OIDC `sub` 不变
- [ ] 文档：oidc-integration 增补“sub 稳定、邮箱可变、封禁建议 user_id”；README/CHANGELOG 同步
