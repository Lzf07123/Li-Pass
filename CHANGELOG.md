# 更新日志

## 未发布（开发中）

### 破坏性变更

- OIDC `access_token` 的 `aud` 从 `client_id` 改为 `{issuer}/oauth2/userinfo`，并已在 userinfo 端点强制校验。`id_token` 的 `aud` 仍为 `client_id`，不受影响。此前若对接方校验过 `access_token` 的 `aud == client_id`，发布后需同步更新为 userinfo 端点地址。详见 [对接指南 §2.5](docs/oidc-integration.md)。

### 行为变更

- `/oauth2/authorize` 请求含 `email` scope 时，服务端强制校验邮箱已验证；未验证用户被 302 到验证邮箱页，验证后需重新发起授权（原授权上下文不保留，见 [统一登录门户设计 §4.4](docs/superpowers/specs/2026-08-12-unified-login-portal-design.md)）。
- `userinfo` 与 `id_token` 在 `profile` scope 下新增 `picture` claim（头像绝对 URL）。
- 审计日志与已吊销/已过期会话增加保留期自动清理（`AUDIT_RETENTION_DAYS` 默认 180 天、`SESSION_RETENTION_DAYS` 默认 30 天）。
- 新增可选的 JWT 签名密钥轮换（目录模式多 kid），未配置 `JWT_KEYS_DIR` 时行为不变。
- SMTP 邮件发送增加超时、瞬时失败重试与批量邀请单连接发送。
- 前端体验与可访问性：管理后台五个标签改为可直接访问的子路由（`/admin/*`）；全部密码框支持显示/隐藏切换；「当前密码」类校验失败改为字段旁内联提示；深色模式危险按钮文字对比度修正至 WCAG AA。
