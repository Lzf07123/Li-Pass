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
- 管理后台会话监控新增「批量下线」与「全部下线」：表格支持勾选多个会话批量强制下线；全部下线只作用于除当前会话之外的全部在线会话，当前会话始终受到保护；批量/全部下线按管理员限流（默认 30 次/分钟）。安全审查结论见 [会话监控批量下线设计 §6](docs/superpowers/specs/2026-08-14-session-batch-revoke-design.md)。
- 新增站内信与自定义邮件通知：管理后台「通知管理」可向全部/指定用户发送站内信与邮件（正文支持 `{nickname}`、`{email}` 占位符）；用户中心新增收件箱与头部未读铃铛，并可在资料中关闭邮件通知。设计见 [站内信与自定义邮件通知设计](docs/superpowers/specs/2026-08-14-notifications-design.md)。
- 邮件通知升级为品牌风 HTML 模板：验证码、重置密码、邀请、账号删除与自定义通知五类邮件统一使用品牌 Logo（CID 内嵌、不依赖外网）、安全蓝按钮/验证码底色块与 Z 形品牌暗线，支持深色模式自适应；同时保留纯文本降级（`multipart/alternative`）以保障送达率。
- 新增 BIMI 发件人头像：内置从品牌 Logo 提取的 SVG Tiny P/S 矢量文件（`/bimi/logo.svg`），配合 DMARC 强制策略与 `default._bimi` DNS 记录即可在邮箱客户端展示品牌头像；配置说明见 [部署指南 §BIMI](docs/deployment.md)。
- 前端品牌氛围「环境呼吸感」：新增纯 Canvas 循环飘动背景（Z 形 / 正方形 / 平行四边形），认证页含输入聚焦减速、用户中心含滚动风速联动、管理后台极致克制；移动端自动减量，全部尊重 `prefers-reduced-motion`。设计见 [循环飘动氛围层设计](docs/superpowers/specs/2026-08-14-ambient-background-design.md)。
