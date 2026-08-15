# OIDC 验证邮箱后自动回到授权流程设计

## 目标

修复「应用跳转 SSO 验证后无法跳回应用」：请求 `email` scope 且用户邮箱未验证时，门户把用户转到验证邮箱页后丢失原授权请求，验证完成后停留在验证页，无法自动回到应用。

## 现状与约束

- `GET /oauth2/authorize` 检测到「请求含 `email` scope 且邮箱未验证」时，302 到 `{frontend}/verify-email?email=...`，不携带任何回跳信息（[oidc.py](../../../backend/app/api/routes/oidc.py)）。
- 前端 `VerifyEmailPage` 验证成功后只弹「去登录」提示，不回到授权流程；对接文档此前把「验证后需重新发起授权」写成既定行为（[oidc-integration.md](../../oidc-integration.md)）。
- 已有登录链路对 `next` 的处理可作为参照：`/login?next=<编码后的授权请求>`，前端用 `isSafeNext` 只放行同源或 API 同源地址，防止开放重定向。
- 强制 2FA 不变式：验证邮箱后默认启用邮箱验证码，新登录必须 2FA；本次会话是邮箱未验证时建立的 1FA 会话，继续走授权流程时 `acr` 如实反映会话强度（1fa）。

## 方案与取舍

保留回跳而非「验证后要求重新发起授权」：

1. 后端在验证页跳转 URL 追加 `next`（`quote(原授权请求, safe='')`），与登录页 `next` 机制一致。
2. 前端 `VerifyEmailPage` 校验 `isSafeNext` 后在验证成功时 `window.location.href = next`，自动回到 `/oauth2/authorize`，随后按常规链路走同意页并跳回 `redirect_uri`。
3. 登录页「注册新账号」链接与注册页「注册成功跳登录」也透传 `next`，覆盖「从应用发起注册」的同类丢回跳问题。

取舍：

- 继续原会话（不强制重新 2FA 登录）：验证邮箱本身已证明邮箱控制权，且该会话在登录时邮箱尚未验证（按设计允许 1FA）。强制重新登录会打断刚完成的登录流程；`id_token` 的 `acr` 会如实标记 1fa，不虚报。
- 前端仍用 `isSafeNext` 校验 `next`，后端只构造自身 issuer 的授权地址，双保险防开放重定向。

## 接口变更

- `GET /oauth2/authorize`（未验证邮箱分支）302 Location 由 `/verify-email?email=...` 变为 `/verify-email?email=...&next=<urlencoded>`。
- 不改变任何请求参数、响应体或 OIDC 令牌契约；纯前端跳转链路变化。

## 安全影响

- 无新增认证绕过：验证邮箱后仅回到需要合法会话的授权端点；未登录访问 `next` 仍会先被带去登录页。
- `next` 仅放行同源/API 同源 http(s) 地址，维持既有开放重定向防护。
- 审计不变：`email_verify`、`consent_approve`、`oauth_authorize` 等既有审计点覆盖新链路。

## UI

- 复用现有 `VerifyEmailPage` 表单与 `isSafeNext` 校验，无视觉变化（遵循 [MASTER.md](../../../design-system/lipass/MASTER.md)）。

## 验收标准

- 未验证邮箱用户从应用发起含 `email` scope 的授权：登录 → 验证邮箱 → 自动回到同意页 → 同意 → 跳回 `redirect_uri`。
- 注册新账号路径：登录页 → 注册 → 登录（含 2FA）→ 验证邮箱 → 自动回到应用。
- 非法 `next`（跨域/协议相对）被忽略，回退到原「去登录」提示。
- 后端 `pytest` 与前端 `tsc/lint/test/build` 全绿；真实浏览器端到端复现通过。

## 风险

- 前端页面级跳转依赖浏览器执行 JS；纯 HTTP 客户端不受影响（该分支本就是人机交互流程）。
- 会话 `acr=1fa` 的令牌若被接入方要求 2FA 强度，接入方需自行校验 `acr`（现有契约已发布 `acr`，非本次引入）。
