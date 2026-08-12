# 审计日志扩展与分类筛选设计

- 日期：2026-08-13
- 状态：已实施完成（2026-08-13）
- 范围：后端审计事件补全 + 分类筛选 API + 前端审计面板筛选

## 1. 目标

1. 补齐目前缺失的关键审计事件（注册、邮箱验证、退出登录、资料修改、授权同意/拒绝、OIDC 授权码签发等）。
2. 为每条审计记录增加 `category` 分类，支持按分类、动作、操作者、时间范围筛选。
3. 前端审计面板提供分类下拉、动作关键字、加载更多，并展示分类徽章。

## 2. 分类体系

| `category` | 覆盖内容 |
| --- | --- |
| `auth` | 注册、邀请注册、邮箱验证/重发、登录成功、2FA 登录成功、找回密码、退出登录 |
| `user` | 个人资料修改、头像上传、修改密码、退出设备、注销账号、手机绑定 |
| `2fa` | 邮箱 2FA / TOTP 开启与关闭 |
| `consent` | 同意授权、拒绝授权、取消应用授权 |
| `oidc` | OIDC 授权码签发 |
| `admin_user` | 管理后台用户管理全部动作 |
| `admin_client` | 管理后台应用管理全部动作 |
| `admin_block` | 黑名单封禁/解封 |
| `admin_settings` | 站点设置变更 |
| `security` | 登录失败、2FA 失败、限流拒绝等风险事件 |

## 3. 事件补全清单

以下动作新增 `log_audit` 调用（已有调用仅补 `category`）：

| 分类 | action | 触发点 |
| --- | --- | --- |
| `auth` | `user_register` | 普通注册成功 |
| `auth` | `email_verify` | 邮箱验证成功 |
| `auth` | `email_verify_resend` | 验证码重发成功 |
| `auth` | `logout` | 退出登录 |
| `auth` | `password_reset_request` | 找回密码请求受理（仅目标邮箱存在时记录，避免枚举辅助） |
| `auth` | `user_register_by_invite` | 邀请注册（已有） |
| `auth` | `login` / `login_step1` / `2fa_login` | 登录链路（已有） |
| `user` | `profile_update` | 修改昵称/头像地址 |
| `user` | `avatar_upload` | 上传头像 |
| `user` | `session_revoke` | 退出其他设备 |
| `user` | `phone_bind_send` / `phone_bind` | 手机绑定验证码与绑定（功能未开放时仍保留埋点） |
| `user` | `password_change` / `user_delete_self` | 已有 |
| `consent` | `consent_approve` / `consent_deny` | 授权确认页同意/拒绝 |
| `consent` | `app_consent_revoke` | 已有 |
| `oidc` | `oauth_authorize` | OIDC 授权码签发成功（含 client_id、scopes） |
| `security` | `login_failed` / `2fa_login_failed` | 已有，归入 security |
| `security` | `rate_limit_rejected` | 注册/登录/验证码/找回密码/邀请触发限流时记录（detail 含 action 与 reason） |

已有管理后台动作（`admin_user` / `admin_client` / `admin_block` / `admin_settings`）全部补充 `category`，动作名不变。

## 4. 数据模型与迁移

- `AuditLog` 新增 `category: str | None`，列类型 `VARCHAR(30)`，建索引。
- 新增 Alembic 迁移：
  - `add_column("audit_logs", category)`；
  - 按现有 `action` 前缀/精确值回填历史记录分类，无法识别的填 `other`；
  - 创建 `ix_audit_logs_category` 索引。
- `log_audit` 签名增加 `category: str = "other"`；`audit.py` 维护 `AUDIT_CATEGORIES` 常量集合，传入未知分类时回退 `other`。
- 更新全部现有 `log_audit` 调用点（约 35 处）与新增调用点。

## 5. 筛选 API

`GET /api/v1/admin/audit-logs` 新增查询参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `category` | str | 精确匹配分类 |
| `action` | str | 精确匹配动作 |
| `actor_id` | str | 精确匹配操作者 |
| `start` | datetime | 起始时间（含） |
| `end` | datetime | 结束时间（含） |
| `limit` | int | 默认 100，最大 500 |
| `offset` | int | 默认 0 |

响应保持数组结构，记录新增 `category` 字段；返回条数 `< limit` 视为没有更多。前端“加载更多”用 `offset` 追加。

## 6. 前端

- `AuditLogOut` 增加 `category: string | null`；`adminAuditApi.list` 改为接收筛选参数对象。
- `AdminAuditPanel`：
  - 分类下拉：全部 + 10 个分类（中文标签）；
  - 动作筛选输入框（后端按完整 `action` 精确匹配，placeholder 提示“输入完整动作名”）；
  - “刷新”与“加载更多”按钮；
  - 表格新增“分类”列，用现有 badge 体系展示分类徽章；
  - 筛选变化后重置 offset 并重新加载。

## 7. 测试

- 后端：新增/更新审计事件写入测试（注册、邮箱验证、退出、资料修改、授权同意/拒绝、OIDC 授权码签发、限流拒绝），断言 `category` 正确落库；筛选接口测试覆盖 `category` / `action` / `actor_id` / 时间范围 / `offset`。
- 迁移：在本地按 `alembic upgrade head` 验证旧数据回填。
- 前端：审计面板分类筛选与加载更多的交互测试（mock fetch）。

## 8. 非目标

- 不做审计日志保留期/自动归档（当前 `audit_logs` 无清理策略，建议后续单独加）。
- 不记录每次 OIDC token 换取（高频噪音；如需可后续加开关）。
- 不改变审计日志权限模型（仍仅管理员可读）。
